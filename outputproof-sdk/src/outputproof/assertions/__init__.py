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
Assertions module for OutputProof.

This module provides a collection of assertion types that can be used to
verify AI agent output:

- Structural assertions: Check file existence, function presence, etc.
- Behavioral assertions: Run tests and check outcomes
- Semantic assertions: Use LLM to verify intent matching
- Contract assertions: Validate API shapes and schemas

Example:
    >>> from outputproof import assertions as a
    >>> assertions = [
    ...     a.file_exists("src/auth.py"),
    ...     a.function_present("authenticate_user"),
    ...     a.tests_pass("pytest tests/test_auth.py"),
    ...     a.semantic_match(intent="implement JWT auth"),
    ... ]
"""

from outputproof.assertions.base import Assertion
from outputproof.assertions.structural import (
    file_exists,
    function_present,
    class_present,
    contains_import,
    file_count,
    directory_exists,
)
from outputproof.assertions.behavioral import (
    tests_pass,
    command_succeeds,
    output_matches,
)
from outputproof.assertions.semantic import (
    semantic_match,
    intent_matches,
    quality_check,
)
from outputproof.assertions.contract import (
    api_response_shape,
    json_schema_valid,
    has_keys,
)


ASSERTION_FACTORIES = {
    "file_exists": file_exists,
    "function_present": function_present,
    "class_present": class_present,
    "contains_import": contains_import,
    "file_count": file_count,
    "directory_exists": directory_exists,
    "tests_pass": tests_pass,
    "command_succeeds": command_succeeds,
    "output_matches": output_matches,
    "semantic_match": semantic_match,
    "intent_matches": intent_matches,
    "quality_check": quality_check,
    "api_response_shape": api_response_shape,
    "json_schema_valid": json_schema_valid,
    "has_keys": has_keys,
}


def assertion_from_config(config: dict) -> Assertion:
    """Create an assertion from a YAML/JSON-friendly config mapping.

    Expected shape:
        {"type": "function_present", "function_name": "authenticate_user"}
    """
    assertion_config = dict(config)
    assertion_type = (
        assertion_config.pop("type", None)
        or assertion_config.pop("assertion", None)
        or assertion_config.pop("name", None)
    )
    if not assertion_type:
        raise ValueError("Assertion config requires a 'type' field")

    factory = ASSERTION_FACTORIES.get(str(assertion_type))
    if not factory:
        supported = ", ".join(sorted(ASSERTION_FACTORIES))
        raise ValueError(
            f"Unsupported assertion type '{assertion_type}'. Supported: {supported}"
        )

    if assertion_type == "contains_import" and "import_name" in assertion_config:
        assertion_config["name"] = assertion_config.pop("import_name")

    return factory(**assertion_config)

__all__ = [
    # Base
    "Assertion",
    "ASSERTION_FACTORIES",
    "assertion_from_config",
    # Structural
    "file_exists",
    "function_present",
    "class_present",
    "contains_import",
    "file_count",
    "directory_exists",
    # Behavioral
    "tests_pass",
    "command_succeeds",
    "output_matches",
    # Semantic
    "semantic_match",
    "intent_matches",
    "quality_check",
    # Contract
    "api_response_shape",
    "json_schema_valid",
    "has_keys",
]
