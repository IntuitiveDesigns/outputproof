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
Base integration class for OutputProof.

This module defines the abstract base class that all agent integrations inherit from.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

from outputproof.models import VerificationRequest, VerificationResult


class BaseIntegration(ABC):
    """Abstract base class for agent integrations.

    Each integration provides a way to intercept agent output and verify it
    before it reaches downstream consumers.

    Attributes:
        name: Name of the integration.
        enabled: Whether the integration is currently enabled.
    """

    def __init__(
        self,
        name: str,
        enabled: bool = True,
    ) -> None:
        """Initialize the integration.

        Args:
            name: Name of the integration.
            enabled: Whether the integration is enabled.
        """
        self.name = name
        self.enabled = enabled

    @abstractmethod
    async def intercept(
        self,
        prompt: str,
        output: str,
        context: Optional[dict[str, Any]] = None,
    ) -> VerificationResult:
        """Intercept agent output and verify it.

        Args:
            prompt: The original prompt given to the agent.
            output: The output produced by the agent.
            context: Additional context for verification.

        Returns:
            VerificationResult with the outcome.
        """
        pass

    @abstractmethod
    async def on_verify_pass(
        self,
        request: VerificationRequest,
        result: VerificationResult,
    ) -> None:
        """Handle successful verification.

        Args:
            request: The verification request.
            result: The verification result.
        """
        pass

    @abstractmethod
    async def on_verify_fail(
        self,
        request: VerificationRequest,
        result: VerificationResult,
    ) -> None:
        """Handle failed verification.

        Args:
            request: The verification request.
            result: The verification result.
        """
        pass

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<{self.__class__.__name__} name='{self.name}' enabled={self.enabled}>"