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
Data models for OutputProof verification system.

This module defines the core data structures used throughout the OutputProof
verification pipeline, including requests, results, agent profiles, and policies.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import hashlib
import uuid


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class VerificationVerdict(str, Enum):
    """Possible outcomes of a verification check."""

    PASS = "PASS"
    FAIL = "FAIL"
    PARTIAL = "PARTIAL"


class AssertionType(str, Enum):
    """Types of assertions supported by the verification engine."""

    STRUCTURAL = "structural"
    BEHAVIORAL = "behavioral"
    SEMANTIC = "semantic"
    CONTRACT = "contract"


class AssertionMode(str, Enum):
    """How assertion results are composed into an overall verdict."""

    ALL = "all"
    ANY = "any"
    THRESHOLD = "threshold"
    WEIGHTED = "weighted"


class EnforcementMode(str, Enum):
    """How strictly a policy should be enforced."""

    BLOCK = "block"
    WARN = "warn"
    LOG = "log"


@dataclass
class AssertionResult:
    """Result of a single assertion check.

    Attributes:
        assertion_id: Unique identifier for this assertion.
        assertion_type: The type of assertion that was checked.
        name: Human-readable name for the assertion.
        passed: Whether the assertion passed.
        message: Detailed message about the assertion result.
        confidence: Confidence score for this assertion (0.0-1.0).
        metadata: Additional metadata about the assertion execution.
    """

    assertion_id: str
    assertion_type: AssertionType
    name: str
    passed: bool
    message: str
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationRequest:
    """A request to verify agent output.

    Attributes:
        agent_id: Identifier for the agent that produced the output.
        session_id: Session identifier for grouping related verifications.
        prompt: The original prompt given to the agent.
        output: The output produced by the agent.
        prompt_hash: Hash of the prompt for deduplication.
        output_hash: Hash of the output for deduplication.
        timestamp: When this verification was requested.
        assertions: List of assertions to check.
        context: Additional context for verification.
    """

    agent_id: str
    prompt: str
    output: str
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    prompt_hash: str = field(default="", init=False)
    output_hash: str = field(default="", init=False)
    timestamp: datetime = field(default_factory=utc_now)
    assertions: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Compute hashes after initialization."""
        if not self.prompt_hash:
            self.prompt_hash = hashlib.sha256(self.prompt.encode()).hexdigest()[:16]
        if not self.output_hash:
            self.output_hash = hashlib.sha256(self.output.encode()).hexdigest()[:16]


@dataclass
class VerificationResult:
    """Result of a verification check.

    Attributes:
        request_id: Reference to the original verification request.
        agent_id: Identifier for the agent that produced the output.
        verdict: Overall pass/fail/partial verdict.
        confidence_score: Overall confidence in the verdict (0.0-1.0).
        assertion_results: Results for each individual assertion.
        judge_explanation: Explanation from the LLM judge, if used.
        corrective_prompt: Prompt that can be sent to the agent for retry.
        retry_count: Number of retries attempted.
        retry_history: Summary of prior failed attempts, if retries were used.
        timestamp: When this result was generated.
        error: Any error message if verification failed unexpectedly.
        metadata: Additional structured metadata about the verification.
    """

    request_id: str
    verdict: VerificationVerdict
    confidence_score: float
    assertion_results: list[AssertionResult]
    agent_id: Optional[str] = None
    judge_explanation: Optional[str] = None
    corrective_prompt: Optional[str] = None
    retry_count: int = 0
    retry_history: list[dict[str, Any]] = field(default_factory=list)
    timestamp: datetime = field(default_factory=utc_now)
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Check if verification passed."""
        return self.verdict == VerificationVerdict.PASS

    @property
    def failed_assertions(self) -> list[AssertionResult]:
        """Get list of failed assertions."""
        return [a for a in self.assertion_results if not a.passed]

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "request_id": self.request_id,
            "agent_id": self.agent_id,
            "verdict": self.verdict.value,
            "confidence_score": self.confidence_score,
            "assertion_results": [
                {
                    "assertion_id": a.assertion_id,
                    "assertion_type": a.assertion_type.value,
                    "name": a.name,
                    "passed": a.passed,
                    "message": a.message,
                    "confidence": a.confidence,
                    "metadata": a.metadata,
                }
                for a in self.assertion_results
            ],
            "judge_explanation": self.judge_explanation,
            "corrective_prompt": self.corrective_prompt,
            "retry_count": self.retry_count,
            "retry_history": self.retry_history,
            "timestamp": self.timestamp.isoformat(),
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class AgentProfile:
    """Profile tracking an agent's reliability over time.

    Attributes:
        agent_id: Unique identifier for the agent.
        integration_type: Type of integration (e.g., "claude_code", "langchain").
        pass_rate_7d: Pass rate over the last 7 days.
        pass_rate_30d: Pass rate over the last 30 days.
        common_failure_categories: Most common failure categories.
        total_verifications: Total number of verifications performed.
        created_at: When this profile was created.
        updated_at: When this profile was last updated.
    """

    agent_id: str
    integration_type: str
    pass_rate_7d: float = 0.0
    pass_rate_30d: float = 0.0
    common_failure_categories: list[str] = field(default_factory=list)
    total_verifications: int = 0
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass
class Policy:
    """A verification policy for governance.

    Attributes:
        policy_id: Unique identifier for this policy.
        name: Human-readable name for the policy.
        scope: Scope of the policy (global, agent-specific, task-specific).
        rules: List of policy rules.
        enforcement: How strictly to enforce this policy.
        threshold: Minimum confidence score required.
        enabled: Whether this policy is currently active.
        created_at: When this policy was created.
    """

    policy_id: str
    name: str
    scope: str = "global"
    rules: list[dict[str, Any]] = field(default_factory=list)
    enforcement: EnforcementMode = EnforcementMode.WARN
    threshold: float = 0.7
    enabled: bool = True
    created_at: datetime = field(default_factory=utc_now)


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        enabled: Whether retry is enabled.
        max_retries: Maximum number of retry attempts.
        backoff_factor: Multiplier for delay between retries.
        initial_delay: Initial delay before first retry in seconds.
        max_delay: Maximum delay between retries in seconds.
    """

    enabled: bool = False
    max_retries: int = 2
    backoff_factor: float = 2.0
    initial_delay: float = 1.0
    max_delay: float = 30.0


@dataclass
class JudgeConfig:
    """Configuration for the LLM-as-Judge scorer.

    Attributes:
        model: Model identifier for the judge LLM.
        api_key: API key for the judge LLM service.
        api_base: Base URL for the judge LLM API.
        temperature: Temperature for judge LLM responses.
        max_tokens: Maximum tokens in judge response.
        timeout: Timeout for judge API calls in seconds.
        use_local: Whether to use a local model (e.g., Ollama).
        local_model_url: URL for local model endpoint.
    """

    model: str = "claude-haiku-4-5"
    api_key: Optional[str] = None
    api_base: str = "https://api.anthropic.com/v1"
    temperature: float = 0.1
    max_tokens: int = 1024
    timeout: int = 30
    use_local: bool = False
    local_model_url: str = "http://localhost:11434"
