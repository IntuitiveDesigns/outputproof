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
LangChain integration for OutputProof.

This module provides a callback handler for LangChain that verifies
agent output before it's returned to the caller.
"""

import logging
from typing import Any, Dict, List, Optional, Sequence, Union
import uuid

from outputproof.models import (
    VerificationRequest,
    VerificationResult,
    RetryConfig,
)
from outputproof.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)

try:
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.outputs import Generation, LLMResult
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False
    BaseCallbackHandler = object  # type: ignore


class LangChainCallback(BaseCallbackHandler if HAS_LANGCHAIN else BaseIntegration):  # type: ignore
    """LangChain callback handler for verification.

    This callback intercepts LLM output and verifies it against configured
    assertions before returning it to the chain.

    Attributes:
        assertions: List of assertions to check against output.
        agent_id: Identifier for the agent.
        retry_on_fail: Whether to retry on verification failure.
        raise_on_fail: Whether to raise an exception on failure.
    """

    def __init__(
        self,
        assertions: Optional[list] = None,
        agent_id: str = "langchain",
        retry_on_fail: bool = False,
        raise_on_fail: bool = True,
        judge_config: Optional[Any] = None,
    ) -> None:
        """Initialize the LangChain callback.

        Args:
            assertions: List of assertions to check.
            agent_id: Identifier for this agent.
            retry_on_fail: Whether to retry on failure.
            raise_on_fail: Whether to raise an exception on failure.
            judge_config: Optional LLM judge configuration.
        """
        if not HAS_LANGCHAIN:
            raise ImportError(
                "langchain-core is required for LangChain integration. "
                "Install with: pip install outputproof[langchain]"
            )

        super().__init__(name="langchain", enabled=True)

        self.assertions = assertions or []
        self.agent_id = agent_id
        self.retry_on_fail = retry_on_fail
        self.raise_on_fail = raise_on_fail
        self.judge_config = judge_config

        # Track current prompt for verification
        self._current_prompt: Optional[str] = None
        self._session_id: str = str(uuid.uuid4())

        # LangChain callback configuration
        self.run_inline = True

    @property
    def always_verbose(self) -> bool:
        """Whether to print verbose output."""
        return True

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs: Any,
    ) -> None:
        """Called when LLM starts running.

        Args:
            serialized: Serialized LLM info.
            prompts: List of prompts sent to the LLM.
            **kwargs: Additional keyword arguments.
        """
        if prompts:
            self._current_prompt = prompts[0]
        logger.debug(f"LLM started with prompt: {self._current_prompt[:100]}...")

    def on_llm_end(
        self,
        response: LLMResult,
        **kwargs: Any,
    ) -> None:
        """Called when LLM ends running.

        This is where verification happens.

        Args:
            response: The LLM response.
            **kwargs: Additional keyword arguments.
        """
        if not response.generations:
            return

        # Get the output text
        output = ""
        for generation_list in response.generations:
            for generation in generation_list:
                if isinstance(generation, Generation):
                    output = generation.text
                    break
            if output:
                break

        if not output or not self._current_prompt:
            return

        # Run verification asynchronously
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(
            self.intercept(
                prompt=self._current_prompt,
                output=output,
            )
        )

        if not result.passed and self.raise_on_fail:
            from outputproof.core import VerificationError
            raise VerificationError(result)

        logger.info(f"Verification {'passed' if result.passed else 'failed'} "
                   f"for agent={self.agent_id}")

    async def intercept(
        self,
        prompt: str,
        output: str,
        context: Optional[dict[str, Any]] = None,
    ) -> VerificationResult:
        """Intercept and verify agent output.

        Args:
            prompt: The original prompt.
            output: The agent's output.
            context: Additional context.

        Returns:
            VerificationResult.
        """
        from outputproof.core import Verifier
        from outputproof.judge import LLMJudge

        # Create verifier
        verifier = Verifier(
            assertions=self.assertions,
            judge_config=self.judge_config,
            retry_config=RetryConfig(enabled=self.retry_on_fail),
        )

        # Set judge if configured
        if self.judge_config:
            judge = LLMJudge(self.judge_config)
            verifier.set_judge(judge)

        # Run verification
        result = await verifier.verify(
            prompt=prompt,
            output=output,
            agent_id=self.agent_id,
            context=context,
        )

        return result

    async def on_verify_pass(
        self,
        request: VerificationRequest,
        result: VerificationResult,
    ) -> None:
        """Handle successful verification."""
        logger.info(f"Verification passed for {self.agent_id}")

    async def on_verify_fail(
        self,
        request: VerificationRequest,
        result: VerificationResult,
    ) -> None:
        """Handle failed verification."""
        logger.warning(f"Verification failed for {self.agent_id}: "
                      f"{result.failed_assertions}")

    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Called when chain starts running."""
        if "prompt" in inputs:
            self._current_prompt = str(inputs["prompt"])

    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Called when chain ends running."""
        self._current_prompt = None

    def on_llm_error(
        self,
        error: BaseException,
        **kwargs: Any,
    ) -> None:
        """Called when LLM encounters an error."""
        logger.error(f"LLM error: {error}")