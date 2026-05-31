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
Behavioral assertions for OutputProof.

These assertions check the behavior of agent output, such as running tests
or executing commands and checking their outcomes.
"""

import asyncio
import re
import subprocess
from typing import Optional

from outputproof.models import AssertionResult, AssertionType, VerificationRequest

from outputproof.assertions.base import Assertion


class TestsPassAssertion(Assertion):
    """Assertion that runs tests and checks if they pass."""

    def __init__(
        self,
        test_command: str = "pytest",
        test_path: Optional[str] = None,
        timeout: int = 60,
        expect_pass: bool = True,
    ) -> None:
        """Initialize TestsPassAssertion.

        Args:
            test_command: The test command to run (e.g., 'pytest', 'npm test').
            test_path: Path to the test file or directory.
            timeout: Timeout in seconds for the test command.
            expect_pass: Whether tests are expected to pass.
        """
        self.test_command = test_command
        self.test_path = test_path
        self.timeout = timeout
        self.expect_pass = expect_pass
        super().__init__(
            name=f"tests_pass({test_command})",
            assertion_type=AssertionType.BEHAVIORAL,
            description=f"Run '{test_command}' and check if tests pass",
        )

    async def evaluate(self, request: VerificationRequest) -> AssertionResult:
        """Evaluate by running the test command."""
        command = self.test_command
        if self.test_path:
            command = f"{self.test_command} {self.test_path}"

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return self._create_result(
                    passed=False,
                    message=f"Test command timed out after {self.timeout}s",
                    confidence=0.0,
                )

            return_code = process.returncode
            passed = (return_code == 0) == self.expect_pass

            if passed:
                message = f"Tests passed as expected"
            else:
                output = stderr.decode() if stderr else stdout.decode()
                # Truncate long output
                if len(output) > 500:
                    output = output[:500] + "..."
                message = f"Tests failed:\n{output}"

            return self._create_result(
                passed=passed,
                message=message,
                metadata={
                    "return_code": return_code,
                    "command": command,
                },
            )

        except Exception as e:
            return self._create_result(
                passed=False,
                message=f"Failed to run test command: {str(e)}",
                confidence=0.0,
            )


class CommandSucceedsAssertion(Assertion):
    """Assertion that runs a command and checks if it succeeds."""

    def __init__(
        self,
        command: str,
        expected_exit_code: int = 0,
        timeout: int = 30,
        check_output: Optional[str] = None,
    ) -> None:
        """Initialize CommandSucceedsAssertion.

        Args:
            command: The command to run.
            expected_exit_code: Expected exit code from the command.
            timeout: Timeout in seconds for the command.
            check_output: Regex pattern to check in the command output.
        """
        self.command = command
        self.expected_exit_code = expected_exit_code
        self.timeout = timeout
        self.check_output = check_output
        super().__init__(
            name=f"command_succeeds({command[:30]}...)",
            assertion_type=AssertionType.BEHAVIORAL,
            description=f"Run command and check exit code",
        )

    async def evaluate(self, request: VerificationRequest) -> AssertionResult:
        """Evaluate by running the command."""
        try:
            process = await asyncio.create_subprocess_shell(
                self.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return self._create_result(
                    passed=False,
                    message=f"Command timed out after {self.timeout}s",
                    confidence=0.0,
                )

            return_code = process.returncode
            exit_code_match = return_code == self.expected_exit_code

            output_match = True
            if self.check_output:
                output = (stdout + stderr).decode()
                output_match = bool(re.search(self.check_output, output))

            passed = exit_code_match and output_match

            if passed:
                message = f"Command succeeded with exit code {return_code}"
            else:
                reasons = []
                if not exit_code_match:
                    reasons.append(
                        f"expected exit code {self.expected_exit_code}, "
                        f"got {return_code}"
                    )
                if not output_match:
                    reasons.append("output did not match expected pattern")
                message = f"Command failed: {', '.join(reasons)}"

            return self._create_result(
                passed=passed,
                message=message,
                metadata={
                    "return_code": return_code,
                    "command": self.command,
                },
            )

        except Exception as e:
            return self._create_result(
                passed=False,
                message=f"Failed to run command: {str(e)}",
                confidence=0.0,
            )


class OutputMatchesAssertion(Assertion):
    """Assertion that checks if the output matches a pattern."""

    def __init__(
        self,
        pattern: str,
        search_in_output: bool = True,
        case_sensitive: bool = True,
        min_occurrences: int = 1,
    ) -> None:
        """Initialize OutputMatchesAssertion.

        Args:
            pattern: Regex pattern to search for.
            search_in_output: If True, search in the agent output text.
            case_sensitive: Whether the search is case-sensitive.
            min_occurrences: Minimum number of matches expected.
        """
        self.pattern = pattern
        self.search_in_output = search_in_output
        self.case_sensitive = case_sensitive
        self.min_occurrences = min_occurrences
        super().__init__(
            name=f"output_matches({pattern[:30]}...)",
            assertion_type=AssertionType.BEHAVIORAL,
            description=f"Check output matches pattern '{pattern}'",
        )

    async def evaluate(self, request: VerificationRequest) -> AssertionResult:
        """Evaluate if the output matches the pattern."""
        content = request.output

        flags = 0 if self.case_sensitive else re.IGNORECASE
        matches = re.findall(self.pattern, content, flags)
        count = len(matches)

        passed = count >= self.min_occurrences

        if passed:
            message = f"Found {count} match(es) for pattern"
        else:
            message = (
                f"Expected at least {self.min_occurrences} match(es), "
                f"found {count}"
            )

        return self._create_result(
            passed=passed,
            message=message,
            metadata={
                "match_count": count,
                "pattern": self.pattern,
            },
        )


# Factory functions for easy import


def tests_pass(
    test_command: str = "pytest",
    test_path: Optional[str] = None,
    timeout: int = 60,
    expect_pass: bool = True,
) -> TestsPassAssertion:
    """Create a TestsPassAssertion.

    Args:
        test_command: The test command to run.
        test_path: Path to the test file or directory.
        timeout: Timeout in seconds for the test command.
        expect_pass: Whether tests are expected to pass.

    Returns:
        TestsPassAssertion instance.
    """
    return TestsPassAssertion(test_command, test_path, timeout, expect_pass)


def command_succeeds(
    command: str,
    expected_exit_code: int = 0,
    timeout: int = 30,
    check_output: Optional[str] = None,
) -> CommandSucceedsAssertion:
    """Create a CommandSucceedsAssertion.

    Args:
        command: The command to run.
        expected_exit_code: Expected exit code from the command.
        timeout: Timeout in seconds for the command.
        check_output: Regex pattern to check in the command output.

    Returns:
        CommandSucceedsAssertion instance.
    """
    return CommandSucceedsAssertion(command, expected_exit_code, timeout, check_output)


def output_matches(
    pattern: str,
    search_in_output: bool = True,
    case_sensitive: bool = True,
    min_occurrences: int = 1,
) -> OutputMatchesAssertion:
    """Create an OutputMatchesAssertion.

    Args:
        pattern: Regex pattern to search for.
        search_in_output: If True, search in the agent output text.
        case_sensitive: Whether the search is case-sensitive.
        min_occurrences: Minimum number of matches expected.

    Returns:
        OutputMatchesAssertion instance.
    """
    return OutputMatchesAssertion(
        pattern, search_in_output, case_sensitive, min_occurrences
    )