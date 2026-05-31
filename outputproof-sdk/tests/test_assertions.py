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
Tests for OutputProof assertions.
"""

import asyncio
import pytest
from outputproof.models import VerificationRequest
from outputproof.assertions.structural import (
    FileExistsAssertion,
    FunctionPresentAssertion,
    ContainsImportAssertion,
)
from outputproof.assertions.behavioral import OutputMatchesAssertion
from outputproof.assertions.contract import APIResponseShapeAssertion, HasKeysAssertion


@pytest.fixture
def sample_request():
    """Create a sample verification request."""
    return VerificationRequest(
        agent_id="test-agent",
        prompt="Create a user authentication function",
        output="""
import hashlib
from typing import Optional

def authenticate_user(username: str, password: str) -> bool:
    '''Authenticate a user with username and password.'''
    if not username or not password:
        return False
    
    # Hash the password
    hashed = hashlib.sha256(password.encode()).hexdigest()
    
    # In production, compare with stored hash
    return True

class UserManager:
    '''Manage user operations.'''
    pass
""",
    )


class TestFileExistsAssertion:
    """Tests for FileExistsAssertion."""

    @pytest.mark.asyncio
    async def test_file_exists_in_output(self, sample_request):
        """Test checking if file path exists in output."""
        assertion = FileExistsAssertion("auth.py", within_output=True)
        result = await assertion.evaluate(sample_request)

        # The output doesn't contain "auth.py"
        assert not result.passed
        assert result.assertion_type.value == "structural"

    @pytest.mark.asyncio
    async def test_file_exists_message(self, sample_request):
        """Test that the message is correct."""
        assertion = FileExistsAssertion("test.py", within_output=True)
        result = await assertion.evaluate(sample_request)

        assert "not found" in result.message.lower()


class TestFunctionPresentAssertion:
    """Tests for FunctionPresentAssertion."""

    @pytest.mark.asyncio
    async def test_function_present(self, sample_request):
        """Test checking if a function is defined."""
        assertion = FunctionPresentAssertion("authenticate_user")
        result = await assertion.evaluate(sample_request)

        assert result.passed
        assert "authenticate_user" in result.message

    @pytest.mark.asyncio
    async def test_function_not_present(self, sample_request):
        """Test checking for a non-existent function."""
        assertion = FunctionPresentAssertion("nonexistent_func")
        result = await assertion.evaluate(sample_request)

        assert not result.passed

    @pytest.mark.asyncio
    async def test_class_present(self, sample_request):
        """Test checking if a class is defined."""
        assertion = FunctionPresentAssertion("UserManager")
        # This should fail because UserManager is a class, not a function
        result = await assertion.evaluate(sample_request)
        # Actually, the regex might match "class UserManager"
        # Let's check the actual behavior
        assert not result.passed  # Because it looks for "def UserManager"


class TestContainsImportAssertion:
    """Tests for ContainsImportAssertion."""

    @pytest.mark.asyncio
    async def test_import_present(self, sample_request):
        """Test checking if an import is present."""
        assertion = ContainsImportAssertion("hashlib")
        result = await assertion.evaluate(sample_request)

        assert result.passed

    @pytest.mark.asyncio
    async def test_import_not_present(self, sample_request):
        """Test checking for a non-existent import."""
        assertion = ContainsImportAssertion("nonexistent_module")
        result = await assertion.evaluate(sample_request)

        assert not result.passed

    @pytest.mark.asyncio
    async def test_named_import(self, sample_request):
        """Test checking for a named import."""
        assertion = ContainsImportAssertion("typing", "Optional")
        result = await assertion.evaluate(sample_request)

        assert result.passed


class TestOutputMatchesAssertion:
    """Tests for OutputMatchesAssertion."""

    @pytest.mark.asyncio
    async def test_pattern_matches(self, sample_request):
        """Test checking if a pattern matches."""
        assertion = OutputMatchesAssertion(r"def\s+\w+\s*\(")
        result = await assertion.evaluate(sample_request)

        assert result.passed
        assert result.metadata["match_count"] >= 1

    @pytest.mark.asyncio
    async def test_pattern_not_matches(self, sample_request):
        """Test checking for a non-matching pattern."""
        assertion = OutputMatchesAssertion(r"function\s+\w+")
        result = await assertion.evaluate(sample_request)

        assert not result.passed


class TestAPIResponseShapeAssertion:
    """Tests for APIResponseShapeAssertion."""

    @pytest.mark.asyncio
    async def test_valid_response_shape(self):
        """Test validating a correct API response shape."""
        request = VerificationRequest(
            agent_id="test",
            prompt="Get user",
            output='{"status": "ok", "data": {}, "message": "success"}',
        )

        assertion = APIResponseShapeAssertion(
            expected_keys=["status", "data"],
            optional_keys=["message"],
        )
        result = await assertion.evaluate(request)

        assert result.passed

    @pytest.mark.asyncio
    async def test_missing_required_keys(self):
        """Test that missing required keys fail."""
        request = VerificationRequest(
            agent_id="test",
            prompt="Get user",
            output='{"status": "ok"}',
        )

        assertion = APIResponseShapeAssertion(
            expected_keys=["status", "data"],
        )
        result = await assertion.evaluate(request)

        assert not result.passed
        assert "data" in result.message

    @pytest.mark.asyncio
    async def test_invalid_json(self):
        """Test that invalid JSON fails."""
        request = VerificationRequest(
            agent_id="test",
            prompt="Get user",
            output="not json",
        )

        assertion = APIResponseShapeAssertion(expected_keys=["status"])
        result = await assertion.evaluate(request)

        assert not result.passed


class TestHasKeysAssertion:
    """Tests for HasKeysAssertion."""

    @pytest.mark.asyncio
    async def test_all_keys_present(self):
        """Test that all required keys are found."""
        request = VerificationRequest(
            agent_id="test",
            prompt="Get user",
            output='{"user_id": 1, "username": "john", "email": "john@example.com"}',
        )

        assertion = HasKeysAssertion(keys=["user_id", "username"])
        result = await assertion.evaluate(request)

        assert result.passed

    @pytest.mark.asyncio
    async def test_some_keys_missing(self):
        """Test that missing keys cause failure."""
        request = VerificationRequest(
            agent_id="test",
            prompt="Get user",
            output='{"user_id": 1}',
        )

        assertion = HasKeysAssertion(keys=["user_id", "username"])
        result = await assertion.evaluate(request)

        assert not result.passed

    @pytest.mark.asyncio
    async def test_any_key_sufficient(self):
        """Test that any key is sufficient when all_required=False."""
        request = VerificationRequest(
            agent_id="test",
            prompt="Get user",
            output='{"user_id": 1}',
        )

        assertion = HasKeysAssertion(
            keys=["user_id", "nonexistent"],
            all_required=False,
        )
        result = await assertion.evaluate(request)

        assert result.passed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])