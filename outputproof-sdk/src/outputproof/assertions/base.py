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
Base assertion class for OutputProof.

This module defines the abstract base class that all assertion types inherit from.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
import uuid

from outputproof.models import AssertionResult, AssertionType, VerificationRequest


class Assertion(ABC):
    """Abstract base class for all assertions.

    An assertion is a check against agent output that returns a pass/fail result
    with an optional confidence score and explanatory message.

    Subclasses must implement the `evaluate` method to perform the actual check.

    Attributes:
        name: Human-readable name for this assertion.
        assertion_type: The type category of this assertion.
        description: Detailed description of what this assertion checks.
    """

    def __init__(
        self,
        name: str,
        assertion_type: AssertionType,
        description: Optional[str] = None,
    ) -> None:
        """Initialize an Assertion.

        Args:
            name: Human-readable name for this assertion.
            assertion_type: The type category of this assertion.
            description: Detailed description of what this assertion checks.
        """
        self.name = name
        self.assertion_type = assertion_type
        self.description = description or name

    @abstractmethod
    async def evaluate(self, request: VerificationRequest) -> AssertionResult:
        """Evaluate this assertion against the verification request.

        Args:
            request: The verification request containing prompt and output.

        Returns:
            AssertionResult with the outcome of this assertion.
        """
        pass

    def _create_result(
        self,
        passed: bool,
        message: str,
        confidence: float = 1.0,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AssertionResult:
        """Helper to create an AssertionResult.

        Args:
            passed: Whether the assertion passed.
            message: Detailed message about the result.
            confidence: Confidence score (0.0-1.0).
            metadata: Additional metadata.

        Returns:
            AssertionResult instance.
        """
        return AssertionResult(
            assertion_id=str(uuid.uuid4()),
            assertion_type=self.assertion_type,
            name=self.name,
            passed=passed,
            message=message,
            confidence=confidence,
            metadata=metadata or {},
        )

    def __repr__(self) -> str:
        """Return string representation of the assertion."""
        return f"<{self.__class__.__name__} name='{self.name}' type={self.assertion_type.value}>"