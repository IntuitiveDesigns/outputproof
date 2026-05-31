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
Semantic assertions for OutputProof.

These assertions use LLM-based scoring to verify semantic properties of agent output,
such as intent matching and quality checks.
"""

from typing import Any, Optional

from outputproof.models import AssertionResult, AssertionType, VerificationRequest

from outputproof.assertions.base import Assertion


class SemanticMatchAssertion(Assertion):
    """Assertion that checks if output semantically matches an intended goal."""

    def __init__(
        self,
        intent: str,
        threshold: float = 0.7,
        judge_config: Optional[Any] = None,
    ) -> None:
        """Initialize SemanticMatchAssertion.

        Args:
            intent: The intended goal or description of what the output should achieve.
            threshold: Minimum similarity score required to pass (0.0-1.0).
            judge_config: Configuration for the LLM judge. If None, uses a simple heuristic.
        """
        self.intent = intent
        self.threshold = threshold
        self.judge_config = judge_config
        super().__init__(
            name=f"semantic_match({intent[:40]}...)",
            assertion_type=AssertionType.SEMANTIC,
            description=f"Check that output matches intent: '{intent}'",
        )

    async def evaluate(self, request: VerificationRequest) -> AssertionResult:
        """Evaluate semantic match."""
        # If judge_config is provided, use LLM-based scoring
        if self.judge_config and hasattr(self.judge_config, "score_semantic"):
            try:
                score = await self.judge_config.score_semantic(
                    prompt=request.prompt,
                    output=request.output,
                    intent=self.intent,
                )
                passed = score >= self.threshold
                message = (
                    f"Semantic similarity score: {score:.2f} "
                    f"(threshold: {self.threshold})"
                )
                return self._create_result(
                    passed=passed,
                    message=message,
                    confidence=score,
                    metadata={"score": score, "threshold": self.threshold},
                )
            except Exception as e:
                return self._create_result(
                    passed=False,
                    message=f"Judge scoring failed: {str(e)}",
                    confidence=0.0,
                )

        # Fallback: simple keyword-based heuristic
        score = self._heuristic_score(request)
        passed = score >= self.threshold
        message = (
            f"Heuristic similarity score: {score:.2f} "
            f"(threshold: {self.threshold})"
        )
        return self._create_result(
            passed=passed,
            message=message,
            confidence=score,
            metadata={"score": score, "threshold": self.threshold},
        )

    def _heuristic_score(self, request: VerificationRequest) -> float:
        """Simple heuristic score based on keyword overlap."""
        intent_words = set(self.intent.lower().split())
        output_words = set(request.output.lower().split())

        if not intent_words:
            return 0.0

        overlap = len(intent_words & output_words)
        return min(overlap / len(intent_words), 1.0)


class IntentMatchesAssertion(Assertion):
    """Assertion that checks if output matches one of several possible intents."""

    def __init__(
        self,
        intents: list[str],
        threshold: float = 0.6,
        require_all: bool = False,
    ) -> None:
        """Initialize IntentMatchesAssertion.

        Args:
            intents: List of possible intents the output should match.
            threshold: Minimum similarity score required for each intent.
            require_all: If True, all intents must be matched.
        """
        self.intents = intents
        self.threshold = threshold
        self.require_all = require_all
        super().__init__(
            name=f"intent_matches({len(intents)} intents)",
            assertion_type=AssertionType.SEMANTIC,
            description=f"Check that output matches intents: {intents}",
        )

    async def evaluate(self, request: VerificationRequest) -> AssertionResult:
        """Evaluate intent matching."""
        scores = []
        for intent in self.intents:
            assertion = SemanticMatchAssertion(intent=intent, threshold=self.threshold)
            result = await assertion.evaluate(request)
            scores.append(result.confidence)

        if self.require_all:
            passed = all(s >= self.threshold for s in scores)
        else:
            passed = any(s >= self.threshold for s in scores)

        avg_score = sum(scores) / len(scores) if scores else 0.0
        message = (
            f"Intent matching: avg score {avg_score:.2f}, "
            f"{'all' if self.require_all else 'any'} matched"
        )

        return self._create_result(
            passed=passed,
            message=message,
            confidence=avg_score,
            metadata={"scores": scores, "intents": self.intents},
        )


class QualityCheckAssertion(Assertion):
    """Assertion that performs a general quality check on the output."""

    def __init__(
        self,
        criteria: Optional[list[str]] = None,
        threshold: float = 0.7,
        rubric: Optional[str] = None,
    ) -> None:
        """Initialize QualityCheckAssertion.

        Args:
            criteria: List of quality criteria to check.
            threshold: Minimum quality score required to pass.
            rubric: Optional detailed rubric for scoring.
        """
        self.criteria = criteria or [
            "Code is well-structured and readable",
            "Follows best practices",
            "No obvious bugs or errors",
        ]
        self.threshold = threshold
        self.rubric = rubric
        super().__init__(
            name="quality_check",
            assertion_type=AssertionType.SEMANTIC,
            description="Check overall quality of output",
        )

    async def evaluate(self, request: VerificationRequest) -> AssertionResult:
        """Evaluate quality."""
        # Simple heuristic-based quality check
        score = self._heuristic_quality_score(request)
        passed = score >= self.threshold

        message = (
            f"Quality score: {score:.2f} (threshold: {self.threshold})"
            if passed
            else f"Quality score {score:.2f} below threshold {self.threshold}"
        )

        return self._create_result(
            passed=passed,
            message=message,
            confidence=score,
            metadata={
                "score": score,
                "criteria": self.criteria,
                "threshold": self.threshold,
            },
        )

    def _heuristic_quality_score(self, request: VerificationRequest) -> float:
        """Simple heuristic quality score."""
        output = request.output
        score = 0.5  # Base score

        # Check for code structure indicators
        if "def " in output or "class " in output:
            score += 0.1

        # Check for docstrings
        if '"""' in output or "'''" in output:
            score += 0.1

        # Check for comments
        if "#" in output:
            score += 0.05

        # Check for imports (indicates complete code)
        if "import " in output:
            score += 0.05

        # Penalize very short outputs
        if len(output) < 50:
            score -= 0.2
        elif len(output) < 100:
            score -= 0.1

        # Penalize error messages in output
        error_indicators = ["error:", "Error:", "ERROR:", "Traceback"]
        if any(indicator in output for indicator in error_indicators):
            score -= 0.2

        return max(0.0, min(1.0, score))


# Factory functions for easy import


def semantic_match(
    intent: str,
    threshold: float = 0.7,
    judge_config: Optional[Any] = None,
) -> SemanticMatchAssertion:
    """Create a SemanticMatchAssertion.

    Args:
        intent: The intended goal or description of what the output should achieve.
        threshold: Minimum similarity score required to pass.
        judge_config: Configuration for the LLM judge.

    Returns:
        SemanticMatchAssertion instance.
    """
    return SemanticMatchAssertion(intent, threshold, judge_config)


def intent_matches(
    intents: list[str],
    threshold: float = 0.6,
    require_all: bool = False,
) -> IntentMatchesAssertion:
    """Create an IntentMatchesAssertion.

    Args:
        intents: List of possible intents the output should match.
        threshold: Minimum similarity score required for each intent.
        require_all: If True, all intents must be matched.

    Returns:
        IntentMatchesAssertion instance.
    """
    return IntentMatchesAssertion(intents, threshold, require_all)


def quality_check(
    criteria: Optional[list[str]] = None,
    threshold: float = 0.7,
    rubric: Optional[str] = None,
) -> QualityCheckAssertion:
    """Create a QualityCheckAssertion.

    Args:
        criteria: List of quality criteria to check.
        threshold: Minimum quality score required to pass.
        rubric: Optional detailed rubric for scoring.

    Returns:
        QualityCheckAssertion instance.
    """
    return QualityCheckAssertion(criteria, threshold, rubric)