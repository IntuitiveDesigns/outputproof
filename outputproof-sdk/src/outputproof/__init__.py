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
OutputProof - AI Agent Output Verification Platform

Infrastructure for trusting AI work product.

OutputProof provides a developer-first verification layer that sits between
AI agents and their downstream consumers — asserting, scoring, and logging
output correctness before results are trusted or acted upon.

Example:
    >>> from outputproof import verify, assertions as a
    >>>
    >>> @verify(
    ...     assertions=[
    ...         a.file_exists("src/auth.py"),
    ...         a.function_present("authenticate_user"),
    ...         a.tests_pass("pytest tests/test_auth.py"),
    ...     ],
    ...     retry_on_fail=True,
    ... )
    ... async def generate_auth_module(prompt: str):
    ...     return await claude_code_agent(prompt)
"""

from outputproof.core import verify, VerificationError
from outputproof.models import (
    VerificationRequest,
    VerificationResult,
    VerificationVerdict,
    AssertionMode,
    AssertionResult,
    AgentProfile,
    Policy,
)
from outputproof import assertions
from outputproof.judge import JudgeConfig, LLMJudge

__version__ = "1.0.0"
__author__ = "StreamKernel LLC"
__email__ = "steven.lopez@streamkernel.io"
__license__ = "Apache-2.0"

__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    # Core functionality
    "verify",
    "VerificationError",
    # Data models
    "VerificationRequest",
    "VerificationResult",
    "VerificationVerdict",
    "AssertionMode",
    "AssertionResult",
    "AgentProfile",
    "Policy",
    # Submodules
    "assertions",
    # Judge
    "JudgeConfig",
    "LLMJudge",
]
