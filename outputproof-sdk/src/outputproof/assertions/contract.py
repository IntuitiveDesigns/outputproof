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
Contract assertions for OutputProof.

These assertions validate API shapes, JSON schemas, and data contracts
in agent output.
"""

import json
from typing import Any, Optional

from outputproof.models import AssertionResult, AssertionType, VerificationRequest

from outputproof.assertions.base import Assertion


class APIResponseShapeAssertion(Assertion):
    """Assertion that validates the shape of an API response."""

    def __init__(
        self,
        expected_keys: list[str],
        optional_keys: Optional[list[str]] = None,
        allow_extra_keys: bool = True,
    ) -> None:
        """Initialize APIResponseShapeAssertion.

        Args:
            expected_keys: List of keys that must be present.
            optional_keys: List of keys that may be present but are not required.
            allow_extra_keys: Whether to allow keys not in the expected/optional lists.
        """
        self.expected_keys = expected_keys
        self.optional_keys = optional_keys or []
        self.allow_extra_keys = allow_extra_keys
        super().__init__(
            name=f"api_response_shape({len(expected_keys)} required keys)",
            assertion_type=AssertionType.CONTRACT,
            description=f"Validate API response has required keys: {expected_keys}",
        )

    async def evaluate(self, request: VerificationRequest) -> AssertionResult:
        """Evaluate the API response shape."""
        output = request.output.strip()

        # Try to parse as JSON
        try:
            data = json.loads(output)
        except json.JSONDecodeError as e:
            return self._create_result(
                passed=False,
                message=f"Output is not valid JSON: {str(e)}",
                confidence=0.0,
            )

        if not isinstance(data, dict):
            return self._create_result(
                passed=False,
                message="Output is not a JSON object",
                confidence=0.0,
            )

        # Check required keys
        missing_keys = [k for k in self.expected_keys if k not in data]
        if missing_keys:
            return self._create_result(
                passed=False,
                message=f"Missing required keys: {missing_keys}",
                metadata={"missing_keys": missing_keys, "found_keys": list(data.keys())},
            )

        # Check for unexpected keys if not allowed
        if not self.allow_extra_keys:
            all_allowed = set(self.expected_keys) | set(self.optional_keys)
            extra_keys = [k for k in data.keys() if k not in all_allowed]
            if extra_keys:
                return self._create_result(
                    passed=False,
                    message=f"Found unexpected keys: {extra_keys}",
                    metadata={"extra_keys": extra_keys},
                )

        return self._create_result(
            passed=True,
            message="API response shape is valid",
            metadata={"found_keys": list(data.keys())},
        )


class JSONSchemaValidAssertion(Assertion):
    """Assertion that validates output against a JSON schema."""

    def __init__(
        self,
        schema: dict[str, Any],
        strict: bool = True,
    ) -> None:
        """Initialize JSONSchemaValidAssertion.

        Args:
            schema: JSON schema to validate against.
            strict: If True, use strict validation. If False, use lenient validation.
        """
        self.schema = schema
        self.strict = strict
        super().__init__(
            name="json_schema_valid",
            assertion_type=AssertionType.CONTRACT,
            description="Validate output against JSON schema",
        )

    async def evaluate(self, request: VerificationRequest) -> AssertionResult:
        """Evaluate JSON schema validity."""
        output = request.output.strip()

        # Try to parse as JSON
        try:
            data = json.loads(output)
        except json.JSONDecodeError as e:
            return self._create_result(
                passed=False,
                message=f"Output is not valid JSON: {str(e)}",
                confidence=0.0,
            )

        # Basic schema validation (simplified - no external dependencies)
        passed, message = self._validate_schema(data, self.schema)

        return self._create_result(
            passed=passed,
            message=message,
            metadata={"schema_type": self.schema.get("type")},
        )

    def _validate_schema(
        self, data: Any, schema: dict[str, Any], path: str = ""
    ) -> tuple[bool, str]:
        """Simple JSON schema validation."""
        schema_type = schema.get("type")

        if schema_type == "object":
            if not isinstance(data, dict):
                return False, f"Expected object at {path}, got {type(data).__name__}"

            required = schema.get("required", [])
            properties = schema.get("properties", {})

            for key in required:
                if key not in data:
                    return False, f"Missing required property: {key}"

            for key, value in data.items():
                if key in properties:
                    valid, msg = self._validate_schema(
                        value, properties[key], f"{path}.{key}"
                    )
                    if not valid:
                        return False, msg

        elif schema_type == "array":
            if not isinstance(data, list):
                return False, f"Expected array at {path}, got {type(data).__name__}"

            items_schema = schema.get("items")
            if items_schema:
                for i, item in enumerate(data):
                    valid, msg = self._validate_schema(
                        item, items_schema, f"{path}[{i}]"
                    )
                    if not valid:
                        return False, msg

        elif schema_type == "string":
            if not isinstance(data, str):
                return False, f"Expected string at {path}, got {type(data).__name__}"

        elif schema_type == "number":
            if not isinstance(data, (int, float)):
                return False, f"Expected number at {path}, got {type(data).__name__}"

        elif schema_type == "boolean":
            if not isinstance(data, bool):
                return False, f"Expected boolean at {path}, got {type(data).__name__}"

        elif schema_type == "null":
            if data is not None:
                return False, f"Expected null at {path}, got {data}"

        return True, "Schema validation passed"


class HasKeysAssertion(Assertion):
    """Assertion that checks if output contains specific keys."""

    def __init__(
        self,
        keys: list[str],
        all_required: bool = True,
        nested: bool = False,
    ) -> None:
        """Initialize HasKeysAssertion.

        Args:
            keys: List of keys to check for.
            all_required: If True, all keys must be present. If False, any key is sufficient.
            nested: If True, search for keys in nested structures.
        """
        self.keys = keys
        self.all_required = all_required
        self.nested = nested
        super().__init__(
            name=f"has_keys({len(keys)} keys)",
            assertion_type=AssertionType.CONTRACT,
            description=f"Check that output contains keys: {keys}",
        )

    async def evaluate(self, request: VerificationRequest) -> AssertionResult:
        """Evaluate key presence."""
        output = request.output.strip()

        # Try to parse as JSON
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            # If not JSON, check for key-like patterns in text
            found_keys = []
            for key in self.keys:
                if f'"{key}"' in output or f"'{key}'" in output:
                    found_keys.append(key)

            if self.all_required:
                passed = len(found_keys) == len(self.keys)
            else:
                passed = len(found_keys) > 0

            return self._create_result(
                passed=passed,
                message=f"Found {len(found_keys)}/{len(self.keys)} keys in text",
                metadata={"found_keys": found_keys},
            )

        # Extract keys from JSON data
        if self.nested:
            all_keys = self._extract_all_keys(data)
        else:
            if isinstance(data, dict):
                all_keys = list(data.keys())
            else:
                all_keys = []

        found_keys = [k for k in self.keys if k in all_keys]

        if self.all_required:
            passed = len(found_keys) == len(self.keys)
            missing = [k for k in self.keys if k not in found_keys]
            message = (
                f"All {len(self.keys)} keys found"
                if passed
                else f"Missing keys: {missing}"
            )
        else:
            passed = len(found_keys) > 0
            message = f"Found {len(found_keys)}/{len(self.keys)} keys"

        return self._create_result(
            passed=passed,
            message=message,
            metadata={"found_keys": found_keys},
        )

    def _extract_all_keys(self, data: Any) -> list[str]:
        """Recursively extract all keys from nested data."""
        keys = []
        if isinstance(data, dict):
            keys.extend(data.keys())
            for value in data.values():
                keys.extend(self._extract_all_keys(value))
        elif isinstance(data, list):
            for item in data:
                keys.extend(self._extract_all_keys(item))
        return keys


# Factory functions for easy import


def api_response_shape(
    expected_keys: list[str],
    optional_keys: Optional[list[str]] = None,
    allow_extra_keys: bool = True,
) -> APIResponseShapeAssertion:
    """Create an APIResponseShapeAssertion.

    Args:
        expected_keys: List of keys that must be present.
        optional_keys: List of keys that may be present but are not required.
        allow_extra_keys: Whether to allow keys not in the expected/optional lists.

    Returns:
        APIResponseShapeAssertion instance.
    """
    return APIResponseShapeAssertion(expected_keys, optional_keys, allow_extra_keys)


def json_schema_valid(
    schema: dict[str, Any],
    strict: bool = True,
) -> JSONSchemaValidAssertion:
    """Create a JSONSchemaValidAssertion.

    Args:
        schema: JSON schema to validate against.
        strict: If True, use strict validation.

    Returns:
        JSONSchemaValidAssertion instance.
    """
    return JSONSchemaValidAssertion(schema, strict)


def has_keys(
    keys: list[str],
    all_required: bool = True,
    nested: bool = False,
) -> HasKeysAssertion:
    """Create a HasKeysAssertion.

    Args:
        keys: List of keys to check for.
        all_required: If True, all keys must be present.
        nested: If True, search for keys in nested structures.

    Returns:
        HasKeysAssertion instance.
    """
    return HasKeysAssertion(keys, all_required, nested)