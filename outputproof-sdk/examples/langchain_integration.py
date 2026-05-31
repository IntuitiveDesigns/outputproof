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
LangChain integration example for OutputProof.

This example demonstrates how to use OutputProof with LangChain to verify
LLM output before it's returned to the application.
"""

from outputproof import assertions as a
from outputproof.integrations import LangChainCallback


def example_langchain_callback() -> None:
    """Demonstrate using OutputProof with LangChain."""
    print("=" * 60)
    print("LangChain Integration Example")
    print("=" * 60)

    try:
        from langchain.chains import LLMChain
        from langchain.prompts import PromptTemplate
        from langchain_community.llms import FakeListLLM

        # Create verification assertions
        assertions = [
            a.function_present("greet_user"),
            a.contains_import("typing"),
            a.output_matches(r"def\s+\w+\s*\("),
        ]

        # Create the OutputProof callback
        callback = LangChainCallback(
            assertions=assertions,
            agent_id="langchain-example",
            retry_on_fail=False,
            raise_on_fail=True,
        )

        # Create a simple prompt template
        prompt = PromptTemplate(
            input_variables=["task"],
            template="Write a Python function that does the following: {task}",
        )

        # Create a fake LLM for demonstration
        # In production, use a real LLM like ChatOpenAI or ChatAnthropic
        llm = FakeListLLM(
            responses=[
                """
import typing

def greet_user(name: str) -> str:
    '''Greet a user by name.'''
    return f"Hello, {name}! Welcome to our application."
"""
            ]
        )

        # Create the chain with the verification callback
        chain = LLMChain(
            llm=llm,
            prompt=prompt,
            callbacks=[callback],
        )

        # Run the chain
        print("\nRunning LangChain with verification...")
        result = chain.run(task="create a greeting function")

        print(f"\nResult: {result[:100]}...")
        print("\nVerification passed! Output was verified before returning.")

    except ImportError as e:
        print(f"\nLangChain not installed. Install with: pip install outputproof[langchain]")
        print(f"Error: {e}")
    except Exception as e:
        print(f"\nVerification failed: {e}")


def example_with_custom_assertions() -> None:
    """Demonstrate custom assertions with LangChain."""
    print("\n" + "=" * 60)
    print("Custom Assertions Example")
    print("=" * 60)

    try:
        from langchain.chains import LLMChain
        from langchain.prompts import PromptTemplate
        from langchain_community.llms import FakeListLLM

        # Custom assertions for code quality
        assertions = [
            # Check for docstrings
            a.output_matches(r'"""[\s\S]*?"""', min_occurrences=1),
            # Check for type hints
            a.output_matches(r":\s*(str|int|float|bool|list|dict|None)\b"),
            # Check that code is valid Python
            a.command_succeeds(
                command="python -c 'import ast; ast.parse(open(\"/dev/stdin\").read())'",
                timeout=10,
            ),
        ]

        callback = LangChainCallback(
            assertions=assertions,
            agent_id="quality-check",
            raise_on_fail=False,  # Don't raise, just log
        )

        prompt = PromptTemplate(
            input_variables=["topic"],
            template="Write a well-documented Python function about: {topic}",
        )

        llm = FakeListLLM(
            responses=[
                '''
def calculate_area(radius: float) -> float:
    """Calculate the area of a circle.
    
    Args:
        radius: The radius of the circle.
    
    Returns:
        The area of the circle.
    """
    import math
    return math.pi * radius ** 2
'''
            ]
        )

        chain = LLMChain(llm=llm, prompt=prompt, callbacks=[callback])
        result = chain.run(topic="calculating circle area")

        print(f"\nResult: {result[:100]}...")

    except ImportError:
        print("\nLangChain not installed. Install with: pip install outputproof[langchain]")
    except Exception as e:
        print(f"\nError: {e}")


def example_retry_behavior() -> None:
    """Demonstrate retry behavior on verification failure."""
    print("\n" + "=" * 60)
    print("Retry Behavior Example")
    print("=" * 60)

    try:
        from langchain.chains import LLMChain
        from langchain.prompts import PromptTemplate
        from langchain_community.llms import FakeListLLM

        # Assertions that will fail on first attempt
        assertions = [
            a.function_present("process_data"),
            a.contains_import("pandas"),
        ]

        callback = LangChainCallback(
            assertions=assertions,
            agent_id="retry-example",
            retry_on_fail=True,
            raise_on_fail=True,
        )

        prompt = PromptTemplate(
            input_variables=["task"],
            template="Write code for: {task}",
        )

        # First response fails verification, second passes
        llm = FakeListLLM(
            responses=[
                # First response - will fail (no pandas import)
                "def process_data(data): return data",
                # Second response - will pass
                "import pandas\ndef process_data(data): return pandas.DataFrame(data)",
            ]
        )

        chain = LLMChain(llm=llm, prompt=prompt, callbacks=[callback])

        print("\nRunning with retry enabled...")
        result = chain.run(task="process data with pandas")

        print(f"\nFinal result after retry: {result[:100]}...")

    except ImportError:
        print("\nLangChain not installed. Install with: pip install outputproof[langchain]")
    except Exception as e:
        print(f"\nError during retry: {e}")


if __name__ == "__main__":
    example_langchain_callback()
    example_with_custom_assertions()
    example_retry_behavior()

    print("\n" + "=" * 60)
    print("LangChain examples completed!")
    print("=" * 60)
