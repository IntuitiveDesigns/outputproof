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
Basic verification example for OutputProof.

This example demonstrates how to use OutputProof to verify AI agent output
using the core verification API.
"""

import asyncio

from outputproof import verify, assertions as a, VerificationError
from outputproof.core import Verifier
from outputproof.models import RetryConfig


async def example_basic_verification() -> None:
    """Demonstrate basic verification with assertions."""
    print("=" * 60)
    print("Basic Verification Example")
    print("=" * 60)

    # Create a verifier with assertions
    verifier = Verifier(
        assertions=[
            a.file_exists("src/auth.py", within_output=True),
            a.function_present("authenticate_user"),
            a.contains_import("jwt"),
        ],
        retry_config=RetryConfig(enabled=False),
    )

    # Simulated agent output
    prompt = "Create a JWT authentication module"
    output = """
# File: src/auth.py
import jwt
from datetime import datetime, timedelta, timezone

def authenticate_user(username: str, password: str) -> str:
    '''Authenticate a user and return a JWT token.'''
    # Verify credentials
    if not validate_credentials(username, password):
        return None
    
    # Generate token
    token = jwt.encode({
        'username': username,
        'exp': datetime.now(timezone.utc) + timedelta(hours=1)
    }, 'secret-key')
    
    return token
"""

    # Run verification
    result = await verifier.verify(
        prompt=prompt,
        output=output,
        agent_id="example-agent",
    )

    print(f"\nVerdict: {result.verdict.value}")
    print(f"Confidence: {result.confidence_score:.2%}")
    print(f"\nAssertion Results:")
    for assertion in result.assertion_results:
        status = "PASS" if assertion.passed else "FAIL"
        print(f"  [{status}] {assertion.name}: {assertion.message}")


async def example_decorator_usage() -> None:
    """Demonstrate using the @verify decorator."""
    print("\n" + "=" * 60)
    print("Decorator Usage Example")
    print("=" * 60)

    # Define a function with verification
    @verify(
        assertions=[
            a.function_present("calculate_sum"),
            a.tests_pass("echo 'tests passed'"),
        ],
        retry_on_fail=False,
        agent_id="math-agent",
    )
    async def generate_math_function(prompt: str) -> str:
        """Simulated agent that generates math functions."""
        # In reality, this would call an AI agent
        return """
def calculate_sum(numbers: list) -> float:
    '''Calculate the sum of a list of numbers.'''
    return sum(numbers)
"""

    try:
        result = await generate_math_function("Create a sum function")
        print(f"\nFunction generated successfully!")
        print(f"Output: {result[:100]}...")
    except VerificationError as e:
        print(f"\nVerification failed!")
        print(f"Error: {e}")


async def example_with_judge() -> None:
    """Demonstrate verification with LLM-as-Judge."""
    print("\n" + "=" * 60)
    print("LLM-as-Judge Example")
    print("=" * 60)

    from outputproof.judge import LLMJudge, JudgeConfig

    # Configure the judge (using a local model for demo)
    judge_config = JudgeConfig(
        model="claude-haiku-4-5",
        api_key="demo-key",  # In production, use real API key
        use_local=False,
    )

    # Create verifier with judge
    verifier = Verifier(
        assertions=[
            a.semantic_match(intent="implement user authentication"),
        ],
        judge_config=judge_config,
        retry_config=RetryConfig(enabled=False),
    )

    # Note: This would require actual LLM API access
    print("\nLLM-as-Judge verification requires API access.")
    print("Configure with real API key to use this feature.")


async def example_contract_assertions() -> None:
    """Demonstrate contract assertions for API responses."""
    print("\n" + "=" * 60)
    print("Contract Assertions Example")
    print("=" * 60)

    verifier = Verifier(
        assertions=[
            a.api_response_shape(
                expected_keys=["status", "data", "message"],
                optional_keys=["error_code"],
            ),
            a.has_keys(["user_id", "username", "email"], nested=True),
        ],
        retry_config=RetryConfig(enabled=False),
    )

    # Simulated API response
    output = """
{
    "status": "success",
    "data": {
        "user_id": "12345",
        "username": "john_doe",
        "email": "john@example.com"
    },
    "message": "User retrieved successfully"
}
"""

    result = await verifier.verify(
        prompt="Get user profile",
        output=output,
        agent_id="api-agent",
    )

    print(f"\nVerdict: {result.verdict.value}")
    for assertion in result.assertion_results:
        status = "PASS" if assertion.passed else "FAIL"
        print(f"  [{status}] {assertion.name}: {assertion.message}")


async def main() -> None:
    """Run all examples."""
    await example_basic_verification()
    await example_decorator_usage()
    await example_with_judge()
    await example_contract_assertions()

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
