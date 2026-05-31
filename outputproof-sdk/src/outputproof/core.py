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
Core verification logic for OutputProof.

This module provides the main `verify` decorator and `VerificationError` exception
that form the heart of the OutputProof verification system.
"""

import asyncio
import functools
import inspect
import logging
import uuid
from pathlib import Path
from typing import Any, Callable, Optional, Union

from outputproof.models import (
    AssertionMode,
    AssertionResult,
    AssertionType,
    RetryConfig,
    VerificationRequest,
    VerificationResult,
    VerificationVerdict,
)
from outputproof.assertions.base import Assertion

logger = logging.getLogger(__name__)


class VerificationError(Exception):
    """Exception raised when verification fails.

    This exception contains the full VerificationResult, including which
    assertions failed, the judge's confidence score, and a corrective prompt.

    Attributes:
        result: The verification result that triggered this exception.
    """

    def __init__(self, result: VerificationResult) -> None:
        """Initialize VerificationError with the result.

        Args:
            result: The verification result that triggered this exception.
        """
        self.result = result
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format a human-readable error message."""
        failed = self.result.failed_assertions
        messages = [f"  - {a.name}: {a.message}" for a in failed]
        message = (
            f"Verification failed with verdict={self.result.verdict.value}, "
            f"confidence={self.result.confidence_score:.2f}\n"
            f"Failed assertions:\n" + "\n".join(messages)
        )
        if self.result.corrective_prompt:
            message += "\nCorrective prompt is available on result.corrective_prompt."
        return message


class Verifier:
    """Core verification engine.

    The Verifier orchestrates the execution of assertions against agent output,
    optionally using an LLM-as-Judge for semantic verification, and handles
    retry logic when verification fails.

    Attributes:
        assertions: List of assertions to execute.
        judge: Optional LLM judge for semantic scoring.
        retry_config: Configuration for retry behavior.
    """

    def __init__(
        self,
        assertions: Optional[list[Union[Assertion, dict[str, Any]]]] = None,
        judge_config: Optional[Any] = None,
        retry_config: Optional[RetryConfig] = None,
        assertion_mode: Union[AssertionMode, str] = AssertionMode.ALL,
        assertion_threshold: float = 1.0,
        assertion_weights: Optional[dict[str, float]] = None,
        audit_log_path: Optional[Union[str, Path]] = None,
    ) -> None:
        """Initialize a Verifier.

        Args:
            assertions: List of assertions to execute. Can be Assertion objects
                or dictionaries that will be converted to assertions.
            judge_config: Optional configuration for LLM-as-Judge.
            retry_config: Configuration for retry behavior.
            assertion_mode: How assertion results compose into the verdict.
            assertion_threshold: Minimum pass ratio or weighted score required
                for threshold-based assertion modes.
            assertion_weights: Optional weights keyed by assertion name or type.
            audit_log_path: Optional JSONL path for local audit logging.
        """
        self.assertions = self._normalize_assertions(assertions or [])
        self.judge_config = judge_config
        self.retry_config = retry_config or RetryConfig(enabled=False)
        self.assertion_mode = AssertionMode(assertion_mode)
        self.assertion_threshold = max(0.0, min(assertion_threshold, 1.0))
        self.assertion_weights = assertion_weights or {}
        self.audit_log_path = audit_log_path
        self._judge = None

    async def verify(
        self,
        prompt: str,
        output: str,
        agent_id: str = "default",
        context: Optional[dict[str, Any]] = None,
    ) -> VerificationResult:
        """Run verification on agent output.

        Args:
            prompt: The original prompt given to the agent.
            output: The output produced by the agent.
            agent_id: Identifier for the agent.
            context: Additional context for verification.

        Returns:
            VerificationResult with the outcome of all assertions.
        """
        request = VerificationRequest(
            agent_id=agent_id,
            prompt=prompt,
            output=output,
            context=context or {},
        )

        result = await self._execute_verification(request)
        result.retry_count = int((context or {}).get("retry_count", 0))
        if not result.passed:
            result.corrective_prompt = self.generate_corrective_prompt(request, result)
        if self.audit_log_path:
            from outputproof.storage import append_verification

            append_verification(result, self.audit_log_path)
        return result

    def _normalize_assertions(
        self,
        assertions: list[Union[Assertion, dict[str, Any]]],
    ) -> list[Assertion]:
        """Convert supported assertion declarations into Assertion objects."""
        normalized = []
        for assertion in assertions:
            if isinstance(assertion, Assertion):
                normalized.append(assertion)
            elif isinstance(assertion, dict):
                from outputproof.assertions import assertion_from_config

                normalized.append(assertion_from_config(assertion))
            else:
                raise TypeError(f"Unsupported assertion declaration: {assertion!r}")
        return normalized

    async def _execute_verification(
        self, request: VerificationRequest
    ) -> VerificationResult:
        """Execute all assertions and optional judge scoring.

        Args:
            request: The verification request.

        Returns:
            VerificationResult with all assertion outcomes.
        """
        assertion_results: list[AssertionResult] = []

        # Execute each assertion
        for assertion in self.assertions:
            try:
                if isinstance(assertion, Assertion):
                    result = await assertion.evaluate(request)
                else:
                    # Skip unknown assertion types
                    continue
                assertion_results.append(result)
            except Exception as e:
                logger.error(f"Assertion {assertion.name} failed with error: {e}")
                assertion_results.append(
                    AssertionResult(
                        assertion_id=str(uuid.uuid4()),
                        assertion_type=AssertionType.STRUCTURAL,
                        name=assertion.name if isinstance(assertion, Assertion) else "unknown",
                        passed=False,
                        message=f"Assertion execution error: {str(e)}",
                        confidence=0.0,
                    )
                )

        verdict, confidence = self._score_assertions(assertion_results)

        # Apply judge scoring if configured
        judge_explanation = None
        if self.judge_config:
            try:
                if self._judge is None:
                    from outputproof.judge import LLMJudge

                    self._judge = LLMJudge(self.judge_config)
                judge_result = await self._judge.score(request, assertion_results)
                judge_score = float(judge_result.get("score", confidence))
                judge_verdict = judge_result.get("verdict")
                confidence = min(confidence, judge_score)
                judge_explanation = judge_result.get("explanation")
                if not assertion_results and judge_verdict:
                    verdict = VerificationVerdict(judge_verdict)
                elif verdict == VerificationVerdict.PASS and judge_verdict == "FAIL":
                    verdict = VerificationVerdict.FAIL
                elif verdict == VerificationVerdict.PASS and judge_verdict == "PARTIAL":
                    verdict = VerificationVerdict.PARTIAL
            except Exception as e:
                logger.warning(f"Judge scoring failed: {e}")

        return VerificationResult(
            request_id=f"{request.session_id}-{uuid.uuid4().hex[:8]}",
            verdict=verdict,
            confidence_score=confidence,
            assertion_results=assertion_results,
            agent_id=request.agent_id,
            judge_explanation=judge_explanation,
            metadata={
                "assertion_mode": self.assertion_mode.value,
                "assertion_threshold": self.assertion_threshold,
            },
        )

    def _score_assertions(
        self,
        assertion_results: list[AssertionResult],
    ) -> tuple[VerificationVerdict, float]:
        """Calculate the overall verdict from assertion results."""
        total_count = len(assertion_results)
        if total_count == 0:
            return VerificationVerdict.PASS, 1.0

        passed_count = sum(1 for result in assertion_results if result.passed)
        pass_rate = passed_count / total_count

        if self.assertion_mode == AssertionMode.ALL:
            if passed_count == total_count:
                return VerificationVerdict.PASS, 1.0
            if passed_count == 0:
                return VerificationVerdict.FAIL, 0.0
            return VerificationVerdict.PARTIAL, pass_rate

        if self.assertion_mode == AssertionMode.ANY:
            verdict = VerificationVerdict.PASS if passed_count > 0 else VerificationVerdict.FAIL
            return verdict, pass_rate

        if self.assertion_mode == AssertionMode.THRESHOLD:
            verdict = (
                VerificationVerdict.PASS
                if pass_rate >= self.assertion_threshold
                else VerificationVerdict.PARTIAL
                if passed_count > 0
                else VerificationVerdict.FAIL
            )
            return verdict, pass_rate

        weighted_score = self._weighted_assertion_score(assertion_results)
        verdict = (
            VerificationVerdict.PASS
            if weighted_score >= self.assertion_threshold
            else VerificationVerdict.PARTIAL
            if passed_count > 0
            else VerificationVerdict.FAIL
        )
        return verdict, weighted_score

    def _weighted_assertion_score(
        self,
        assertion_results: list[AssertionResult],
    ) -> float:
        """Calculate a weighted assertion pass ratio."""
        weighted_total = 0.0
        weighted_passed = 0.0
        for result in assertion_results:
            weight = self.assertion_weights.get(
                result.name,
                self.assertion_weights.get(result.assertion_type.value, 1.0),
            )
            weight = max(float(weight), 0.0)
            weighted_total += weight
            if result.passed:
                weighted_passed += weight
        if weighted_total == 0:
            return 0.0
        return weighted_passed / weighted_total

    def generate_corrective_prompt(
        self,
        request: VerificationRequest,
        result: VerificationResult,
    ) -> str:
        """Generate a retry prompt from failed assertions and judge feedback."""
        failed_assertions = "\n".join(
            f"- {assertion.name}: {assertion.message}"
            for assertion in result.failed_assertions
        )
        judge_feedback = result.judge_explanation or "No additional judge feedback."

        return f"""Please revise your previous output to pass verification.

## Original Request
{request.prompt}

## Previous Output
{request.output}

## Verification Results
Verdict: {result.verdict.value}
Confidence: {result.confidence_score:.2f}

## Failed Assertions
{failed_assertions or "None specified."}

## Judge Feedback
{judge_feedback}

Return a complete corrected output that satisfies the original request."""

    def set_judge(self, judge: Any) -> None:
        """Set the LLM judge for semantic scoring.

        Args:
            judge: An LLMJudge instance for semantic verification.
        """
        self._judge = judge


def verify(
    assertions: Optional[list[Union[Assertion, dict[str, Any]]]] = None,
    agent_id: str = "default",
    retry_on_fail: bool = False,
    max_retries: int = 2,
    use_judge: bool = False,
    judge_config: Optional[Any] = None,
    assertion_mode: Union[AssertionMode, str] = AssertionMode.ALL,
    assertion_threshold: float = 1.0,
    assertion_weights: Optional[dict[str, float]] = None,
    audit_log_path: Optional[Union[str, Path]] = None,
) -> Callable:
    """Decorator to add verification to an agent function.

    This decorator wraps an async function that produces agent output and
    automatically verifies the output against the specified assertions.

    Args:
        assertions: List of assertions to check against the output.
        agent_id: Identifier for the agent (used in logging and analytics).
        retry_on_fail: Whether to automatically retry on verification failure.
        max_retries: Maximum number of retry attempts.
        use_judge: Whether to use LLM-as-Judge for semantic scoring.
        judge_config: Configuration for the LLM judge.
        assertion_mode: How assertion results compose into the verdict.
        assertion_threshold: Minimum pass ratio or weighted score required for
            threshold modes.
        assertion_weights: Optional weights keyed by assertion name or type.
        audit_log_path: Optional JSONL path for local audit logging.

    Returns:
        A decorator that wraps the target function.

    Example:
        >>> @verify(
        ...     assertions=[
        ...         a.file_exists("src/auth.py"),
        ...         a.function_present("authenticate_user"),
        ...     ],
        ...     retry_on_fail=True,
        ...     max_retries=2,
        ... )
        ... async def generate_code(prompt: str):
        ...     return await agent.execute(prompt)
    """
    retry_config = RetryConfig(
        enabled=retry_on_fail,
        max_retries=max_retries,
    )

    def decorator(func: Callable) -> Callable:
        verifier = Verifier(
            assertions=assertions,
            retry_config=retry_config,
            judge_config=judge_config if use_judge else None,
            assertion_mode=assertion_mode,
            assertion_threshold=assertion_threshold,
            assertion_weights=assertion_weights,
            audit_log_path=audit_log_path,
        )

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            original_prompt = kwargs.get("prompt", args[0] if args else "")
            attempt_prompt = str(original_prompt)
            retry_history: list[dict[str, Any]] = []
            last_result: Optional[VerificationResult] = None

            for attempt in range(max_retries + 1):
                output = await _call_agent_with_prompt(
                    func=func,
                    args=args,
                    kwargs=kwargs,
                    prompt=attempt_prompt,
                    replace_prompt=attempt > 0,
                )

                verification_result = await verifier.verify(
                    prompt=str(original_prompt),
                    output=str(output),
                    agent_id=agent_id,
                    context={"retry_count": attempt},
                )
                verification_result.retry_count = attempt
                verification_result.retry_history = list(retry_history)
                last_result = verification_result

                if verification_result.passed:
                    return output

                retry_history.append(
                    {
                        "attempt": attempt,
                        "verdict": verification_result.verdict.value,
                        "confidence_score": verification_result.confidence_score,
                        "failed_assertions": [
                            assertion.name
                            for assertion in verification_result.failed_assertions
                        ],
                        "corrective_prompt": verification_result.corrective_prompt,
                    }
                )

                if not retry_on_fail or attempt >= max_retries:
                    break

                delay = min(
                    retry_config.initial_delay
                    * (retry_config.backoff_factor ** attempt),
                    retry_config.max_delay,
                )
                logger.warning(
                    f"Verification failed on attempt {attempt + 1}; "
                    f"retrying in {delay:.1f}s for agent={agent_id}"
                )
                await asyncio.sleep(delay)
                attempt_prompt = (
                    verification_result.corrective_prompt
                    or f"{original_prompt}\n\nPlease correct the verification failures."
                )

            if last_result is not None:
                last_result.retry_history = retry_history
                raise VerificationError(last_result)

            raise VerificationError(
                VerificationResult(
                    request_id=str(uuid.uuid4()),
                    verdict=VerificationVerdict.FAIL,
                    confidence_score=0.0,
                    assertion_results=[],
                    error="Agent did not produce output.",
                )
            )

        return wrapper

    return decorator


async def _call_agent_with_prompt(
    func: Callable,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    prompt: str,
    replace_prompt: bool,
) -> Any:
    """Call an agent function, replacing the prompt argument on retries."""
    if not replace_prompt:
        return await func(*args, **kwargs)

    new_kwargs = dict(kwargs)
    new_args = list(args)

    if "prompt" in new_kwargs:
        new_kwargs["prompt"] = prompt
    elif new_args:
        new_args[0] = prompt
    elif "prompt" in inspect.signature(func).parameters:
        new_kwargs["prompt"] = prompt
    else:
        raise TypeError(
            "retry_on_fail requires the wrapped function to accept a prompt "
            "argument so the corrective prompt can be supplied."
        )

    return await func(*new_args, **new_kwargs)
