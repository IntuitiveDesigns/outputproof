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
Structural assertions for OutputProof.

These assertions check the structure of agent output, such as whether files exist,
functions are present, or imports are included.
"""

import ast
import os
import re
from pathlib import Path
from typing import Optional

from outputproof.models import AssertionResult, AssertionType, VerificationRequest

from outputproof.assertions.base import Assertion


class FileExistsAssertion(Assertion):
    """Assertion that checks if a file exists in the output or filesystem."""

    def __init__(self, path: str, within_output: bool = False) -> None:
        """Initialize FileExistsAssertion.

        Args:
            path: Path to the file to check.
            within_output: If True, check if the path is mentioned in the output.
        """
        self.path = path
        self.within_output = within_output
        super().__init__(
            name=f"file_exists({path})",
            assertion_type=AssertionType.STRUCTURAL,
            description=f"Check that file '{path}' exists",
        )

    async def evaluate(self, request: VerificationRequest) -> AssertionResult:
        """Evaluate if the file exists."""
        if self.within_output:
            # Check if the path is mentioned in the output
            exists = self.path in request.output
            message = (
                f"File path '{self.path}' found in output"
                if exists
                else f"File path '{self.path}' not found in output"
            )
        else:
            # Check if the file actually exists on filesystem
            exists = os.path.exists(self.path)
            message = (
                f"File '{self.path}' exists"
                if exists
                else f"File '{self.path}' does not exist"
            )
        return self._create_result(passed=exists, message=message)


class FunctionPresentAssertion(Assertion):
    """Assertion that checks if a function is defined in the output."""

    def __init__(
        self,
        function_name: str,
        search_in_output: bool = True,
        file_path: Optional[str] = None,
    ) -> None:
        """Initialize FunctionPresentAssertion.

        Args:
            function_name: Name of the function to look for.
            search_in_output: If True, search in the agent output text.
            file_path: If provided, search in this file instead of output.
        """
        self.function_name = function_name
        self.search_in_output = search_in_output
        self.file_path = file_path
        super().__init__(
            name=f"function_present({function_name})",
            assertion_type=AssertionType.STRUCTURAL,
            description=f"Check that function '{function_name}' is defined",
        )

    async def evaluate(self, request: VerificationRequest) -> AssertionResult:
        """Evaluate if the function is present."""
        if self.file_path:
            if not os.path.exists(self.file_path):
                return self._create_result(
                    passed=False,
                    message=f"File '{self.file_path}' does not exist",
                )
            with open(self.file_path, "r") as f:
                content = f.read()
        else:
            content = request.output

        # Try AST parsing first for accurate detection
        try:
            tree = ast.parse(content)
            found = any(
                isinstance(node, ast.FunctionDef) and node.name == self.function_name
                for node in ast.walk(tree)
            )
        except SyntaxError:
            # Fall back to regex search
            pattern = rf"def\s+{re.escape(self.function_name)}\s*\("
            found = bool(re.search(pattern, content))

        message = (
            f"Function '{self.function_name}' is defined"
            if found
            else f"Function '{self.function_name}' is not defined"
        )
        return self._create_result(passed=found, message=message)


class ClassPresentAssertion(Assertion):
    """Assertion that checks if a class is defined in the output."""

    def __init__(
        self,
        class_name: str,
        search_in_output: bool = True,
        file_path: Optional[str] = None,
    ) -> None:
        """Initialize ClassPresentAssertion.

        Args:
            class_name: Name of the class to look for.
            search_in_output: If True, search in the agent output text.
            file_path: If provided, search in this file instead of output.
        """
        self.class_name = class_name
        self.search_in_output = search_in_output
        self.file_path = file_path
        super().__init__(
            name=f"class_present({class_name})",
            assertion_type=AssertionType.STRUCTURAL,
            description=f"Check that class '{class_name}' is defined",
        )

    async def evaluate(self, request: VerificationRequest) -> AssertionResult:
        """Evaluate if the class is present."""
        if self.file_path:
            if not os.path.exists(self.file_path):
                return self._create_result(
                    passed=False,
                    message=f"File '{self.file_path}' does not exist",
                )
            with open(self.file_path, "r") as f:
                content = f.read()
        else:
            content = request.output

        try:
            tree = ast.parse(content)
            found = any(
                isinstance(node, ast.ClassDef) and node.name == self.class_name
                for node in ast.walk(tree)
            )
        except SyntaxError:
            pattern = rf"class\s+{re.escape(self.class_name)}\s*[:\(]"
            found = bool(re.search(pattern, content))

        message = (
            f"Class '{self.class_name}' is defined"
            if found
            else f"Class '{self.class_name}' is not defined"
        )
        return self._create_result(passed=found, message=message)


class ContainsImportAssertion(Assertion):
    """Assertion that checks if a specific import is present."""

    def __init__(
        self,
        module: str,
        import_name: Optional[str] = None,
        search_in_output: bool = True,
    ) -> None:
        """Initialize ContainsImportAssertion.

        Args:
            module: The module to import from.
            import_name: Specific name to import (e.g., 'json' from 'import json').
            search_in_output: If True, search in the agent output text.
        """
        self.module = module
        self.import_name = import_name
        self.search_in_output = search_in_output
        name_str = f"{module}.{import_name}" if import_name else module
        super().__init__(
            name=f"contains_import({name_str})",
            assertion_type=AssertionType.STRUCTURAL,
            description=f"Check that import '{module}' is present",
        )

    async def evaluate(self, request: VerificationRequest) -> AssertionResult:
        """Evaluate if the import is present."""
        content = request.output

        if self.import_name:
            pattern = rf"from\s+{re.escape(self.module)}\s+import\s+.*{re.escape(self.import_name)}"
        else:
            pattern = rf"import\s+{re.escape(self.module)}"

        found = bool(re.search(pattern, content))
        if self.import_name:
            import_display = f"{self.import_name} from {self.module}"
        else:
            import_display = self.module
        message = (
            f"Import '{import_display}' is present"
            if found
            else f"Import '{import_display}' is not present"
        )
        return self._create_result(passed=found, message=message)


class FileCountAssertion(Assertion):
    """Assertion that checks the number of files in a directory."""

    def __init__(
        self,
        directory: str,
        min_count: Optional[int] = None,
        max_count: Optional[int] = None,
        exact_count: Optional[int] = None,
        pattern: str = "*",
    ) -> None:
        """Initialize FileCountAssertion.

        Args:
            directory: Directory to count files in.
            min_count: Minimum number of files expected.
            max_count: Maximum number of files expected.
            exact_count: Exact number of files expected.
            pattern: Glob pattern to match files.
        """
        self.directory = directory
        self.min_count = min_count
        self.max_count = max_count
        self.exact_count = exact_count
        self.pattern = pattern
        super().__init__(
            name=f"file_count({directory})",
            assertion_type=AssertionType.STRUCTURAL,
            description=f"Check file count in '{directory}'",
        )

    async def evaluate(self, request: VerificationRequest) -> AssertionResult:
        """Evaluate the file count."""
        if not os.path.exists(self.directory):
            return self._create_result(
                passed=False,
                message=f"Directory '{self.directory}' does not exist",
            )

        path = Path(self.directory)
        files = list(path.glob(self.pattern))
        count = len(files)

        passed = True
        if self.exact_count is not None:
            passed = count == self.exact_count
        else:
            if self.min_count is not None:
                passed = passed and count >= self.min_count
            if self.max_count is not None:
                passed = passed and count <= self.max_count

        message = f"Found {count} files in '{self.directory}'"
        return self._create_result(passed=passed, message=message)


class DirectoryExistsAssertion(Assertion):
    """Assertion that checks if a directory exists."""

    def __init__(self, path: str) -> None:
        """Initialize DirectoryExistsAssertion.

        Args:
            path: Path to the directory to check.
        """
        self.path = path
        super().__init__(
            name=f"directory_exists({path})",
            assertion_type=AssertionType.STRUCTURAL,
            description=f"Check that directory '{path}' exists",
        )

    async def evaluate(self, request: VerificationRequest) -> AssertionResult:
        """Evaluate if the directory exists."""
        exists = os.path.isdir(self.path)
        message = (
            f"Directory '{self.path}' exists"
            if exists
            else f"Directory '{self.path}' does not exist"
        )
        return self._create_result(passed=exists, message=message)


# Factory functions for easy import


def file_exists(path: str, within_output: bool = False) -> FileExistsAssertion:
    """Create a FileExistsAssertion.

    Args:
        path: Path to the file to check.
        within_output: If True, check if the path is mentioned in the output.

    Returns:
        FileExistsAssertion instance.
    """
    return FileExistsAssertion(path, within_output)


def function_present(
    function_name: str,
    search_in_output: bool = True,
    file_path: Optional[str] = None,
) -> FunctionPresentAssertion:
    """Create a FunctionPresentAssertion.

    Args:
        function_name: Name of the function to look for.
        search_in_output: If True, search in the agent output text.
        file_path: If provided, search in this file instead of output.

    Returns:
        FunctionPresentAssertion instance.
    """
    return FunctionPresentAssertion(function_name, search_in_output, file_path)


def class_present(
    class_name: str,
    search_in_output: bool = True,
    file_path: Optional[str] = None,
) -> ClassPresentAssertion:
    """Create a ClassPresentAssertion.

    Args:
        class_name: Name of the class to look for.
        search_in_output: If True, search in the agent output text.
        file_path: If provided, search in this file instead of output.

    Returns:
        ClassPresentAssertion instance.
    """
    return ClassPresentAssertion(class_name, search_in_output, file_path)


def contains_import(
    module: str,
    name: Optional[str] = None,
    search_in_output: bool = True,
) -> ContainsImportAssertion:
    """Create a ContainsImportAssertion.

    Args:
        module: The module to import from.
        name: Specific name to import.
        search_in_output: If True, search in the agent output text.

    Returns:
        ContainsImportAssertion instance.
    """
    return ContainsImportAssertion(module, name, search_in_output)


def file_count(
    directory: str,
    min_count: Optional[int] = None,
    max_count: Optional[int] = None,
    exact_count: Optional[int] = None,
    pattern: str = "*",
) -> FileCountAssertion:
    """Create a FileCountAssertion.

    Args:
        directory: Directory to count files in.
        min_count: Minimum number of files expected.
        max_count: Maximum number of files expected.
        exact_count: Exact number of files expected.
        pattern: Glob pattern to match files.

    Returns:
        FileCountAssertion instance.
    """
    return FileCountAssertion(directory, min_count, max_count, exact_count, pattern)


def directory_exists(path: str) -> DirectoryExistsAssertion:
    """Create a DirectoryExistsAssertion.

    Args:
        path: Path to the directory to check.

    Returns:
        DirectoryExistsAssertion instance.
    """
    return DirectoryExistsAssertion(path)