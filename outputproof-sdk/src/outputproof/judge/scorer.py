# Copyright 2026 StreamKernel LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
LLM-as-Judge scorer implementation.

This module provides the LLMJudge class that uses a secondary LLM to evaluate
agent output semantically. It supports multiple backends including Anthropic
Claude, OpenAI, and local models via Ollama.
"""

import json
import logging
from collections.abc import Mapping
from typing import Any, Optional, Union

from outputproof.judge.prompts import (
    DEFAULT_JUDGE_PROMPT,
    RUBRIC_PROMPT,
    format_corrective_hints,
    format_rubric,
    render_prompt,
)
from outputproof.models import AssertionResult, VerificationRequest

logger = logging.getLogger(__name__)


class LLMJudge:
    """LLM-as-Judge scorer for semantic verification.

    This class uses a secondary LLM to evaluate agent output and provide
    a confidence score and explanation for the verification decision.

    Supported backends:
    - Anthropic Claude (default)
    - OpenAI GPT
    - Local models via Ollama

    Attributes:
        config: Configuration for the judge LLM.
    """

    def __init__(self, config: Any) -> None:
        """Initialize the LLMJudge.

        Args:
            config: JudgeConfig or similar configuration object.
        """
        self.config = config
        self._client = None
        self._initialized = False

    def _get_client(self) -> Any:
        """Get or create the LLM client."""
        if self._client is not None:
            return self._client

        if self.config.use_local:
            # Use Ollama or local model
            self._client = self._create_ollama_client()
        elif "anthropic" in self.config.api_base.lower():
            self._client = self._create_anthropic_client()
        elif "openai" in self.config.api_base.lower():
            self._client = self._create_openai_client()
        else:
            # Default to OpenAI-compatible client
            self._client = self._create_openai_compatible_client()

        self._initialized = True
        return self._client

    def _create_anthropic_client(self) -> Any:
        """Create an Anthropic Claude client."""
        try:
            from anthropic import AsyncAnthropic
            return AsyncAnthropic(api_key=self.config.api_key)
        except ImportError:
            raise ImportError(
                "anthropic package is required for Anthropic backend. "
                "Install with: pip install outputproof[judge]"
            )

    def _create_openai_client(self) -> Any:
        """Create an OpenAI client."""
        try:
            from openai import AsyncOpenAI
            return AsyncOpenAI(api_key=self.config.api_key)
        except ImportError:
            raise ImportError(
                "openai package is required for OpenAI backend. "
                "Install with: pip install outputproof[judge]"
            )

    def _create_ollama_client(self) -> Any:
        """Create an Ollama client (OpenAI-compatible)."""
        try:
            from openai import AsyncOpenAI
            return AsyncOpenAI(
                api_key="ollama",  # Ollama doesn't require a key
                base_url=f"{self.config.local_model_url}/v1",
            )
        except ImportError:
            raise ImportError(
                "openai package is required for Ollama backend. "
                "Install with: pip install outputproof[judge]"
            )

    def _create_openai_compatible_client(self) -> Any:
        """Create a generic OpenAI-compatible client."""
        try:
            from openai import AsyncOpenAI
            return AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=self.config.api_base,
            )
        except ImportError:
            raise ImportError(
                "openai package is required for OpenAI-compatible backend. "
                "Install with: pip install outputproof[judge]"
            )

    async def score(
        self,
        request: VerificationRequest,
        assertion_results: list[AssertionResult],
        rubric: Optional[Union[str, Mapping[str, Any]]] = None,
    ) -> dict[str, Any]:
        """Score agent output using the LLM judge.

        Args:
            request: The verification request.
            assertion_results: Results from assertion checks.
            rubric: Optional custom rubric for scoring. A mapping is rendered
                as JSON and should use stable criterion names as keys.

        Returns:
            Dictionary with 'score', 'verdict', and 'explanation' keys.
        """
        client = self._get_client()

        # Format assertion results for the prompt
        assertion_summary = self._format_assertion_results(assertion_results)

        if rubric:
            prompt = render_prompt(
                RUBRIC_PROMPT,
                prompt=request.prompt[:2000],  # Truncate long prompts
                output=request.output[:4000],  # Truncate long outputs
                rubric=format_rubric(rubric),
            )
        else:
            prompt = render_prompt(
                DEFAULT_JUDGE_PROMPT,
                prompt=request.prompt[:2000],  # Truncate long prompts
                output=request.output[:4000],  # Truncate long outputs
                assertion_results=assertion_summary,
            )

        # Call the LLM
        response = await self._call_llm(client, prompt)

        # Parse the response
        result = self._parse_response(response)

        return result

    async def score_semantic(
        self,
        prompt: str,
        output: str,
        intent: str,
    ) -> float:
        """Score semantic similarity between output and intent.

        Args:
            prompt: The original prompt given to the agent.
            output: The agent's output.
            intent: The intended goal.

        Returns:
            Similarity score between 0.0 and 1.0.
        """
        client = self._get_client()

        judge_prompt = f"""Evaluate how well the following output achieves the intended goal.

Intent: {intent[:500]}
Prompt: {prompt[:1000]}
Output: {output[:2000]}

Rate the semantic similarity on a scale of 0.0 to 1.0, where:
- 1.0 means the output perfectly achieves the intent
- 0.5 means the output partially achieves the intent
- 0.0 means the output does not achieve the intent at all

Respond with only a number between 0.0 and 1.0."""

        response = await self._call_llm(client, judge_prompt)

        # Extract the score from the response
        try:
            # Try to find a number in the response
            import re
            numbers = re.findall(r"(\d+\.?\d*)", response)
            if numbers:
                return min(max(float(numbers[0]), 0.0), 1.0)
        except (ValueError, IndexError):
            pass

        # Default score if parsing fails
        return 0.5

    async def _call_llm(self, client: Any, prompt: str) -> str:
        """Call the LLM with the given prompt.

        Args:
            client: The LLM client.
            prompt: The prompt to send.

        Returns:
            The LLM's response text.
        """
        try:
            if hasattr(client, "chat") and hasattr(client.chat, "completions"):
                # OpenAI-style client
                response = await client.chat.completions.create(
                    model=self.config.model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are an AI code reviewer. Return only the "
                                "requested response format."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )
                return response.choices[0].message.content
            elif hasattr(client, "messages") and hasattr(client.messages, "create"):
                # Anthropic-style client
                response = await client.messages.create(
                    model=self.config.model,
                    max_tokens=self.config.max_tokens,
                    messages=[
                        {"role": "user", "content": prompt},
                    ],
                )
                return response.content[0].text
            else:
                raise ValueError(f"Unsupported client type: {type(client)}")
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return (
                '{"score": 0.5, "verdict": "PARTIAL", '
                '"explanation": "LLM call failed"}'
            )

    def _format_assertion_results(
        self, assertion_results: list[AssertionResult]
    ) -> str:
        """Format assertion results for the prompt.

        Args:
            assertion_results: List of assertion results.

        Returns:
            Formatted string summary.
        """
        lines = []
        for result in assertion_results:
            status = "PASS" if result.passed else "FAIL"
            lines.append(f"- {result.name}: {status} - {result.message}")
        return "\n".join(lines) if lines else "No assertions evaluated"

    def _parse_response(self, response: str) -> dict[str, Any]:
        """Parse the LLM response.

        Args:
            response: Raw response text from the LLM.

        Returns:
            Parsed result dictionary.
        """
        try:
            # Try to extract JSON from the response
            # Handle cases where the response has markdown code blocks
            if "```json" in response:
                start = response.index("```json") + 7
                end = response.index("```", start)
                response = response[start:end].strip()
            elif "```" in response:
                start = response.index("```") + 3
                end = response.index("```", start)
                response = response[start:end].strip()

            result = json.loads(response)
            score = result.get("score", result.get("overall_score", 0.5))

            parsed = {
                "score": float(score),
                "verdict": result.get("verdict", "PARTIAL"),
                "explanation": result.get("explanation", ""),
                "failed_aspects": result.get("failed_aspects", []),
                "corrective_hint": result.get("corrective_hint", ""),
            }

            if "criteria_scores" in result:
                parsed["criteria_scores"] = result["criteria_scores"]

            return parsed
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            return {
                "score": 0.5,
                "verdict": "PARTIAL",
                "explanation": f"Failed to parse response: {str(e)}",
                "failed_aspects": [],
                "corrective_hint": "",
            }

    def generate_corrective_prompt(
        self,
        request: VerificationRequest,
        result: dict[str, Any],
    ) -> str:
        """Generate a corrective prompt for agent retry.

        Args:
            request: The original verification request.
            result: The judge's scoring result.

        Returns:
            A corrective prompt to guide the agent's retry.
        """
        from outputproof.judge.prompts import CORRECTIVE_PROMPT_TEMPLATE

        failed_aspects = "\n".join(f"- {a}" for a in result.get("failed_aspects", []))
        corrective_hint = result.get("corrective_hint", "")

        return render_prompt(
            CORRECTIVE_PROMPT_TEMPLATE,
            original_prompt=request.prompt[:1000],
            previous_output=request.output[:2000],
            verification_results=f"Score: {result.get('score', 0):.2f}, "
            f"Verdict: {result.get('verdict', 'UNKNOWN')}",
            failed_assertions=failed_aspects or "None specified",
            judge_explanation=result.get("explanation", "")[:500],
            corrective_hints=format_corrective_hints(corrective_hint),
        )
