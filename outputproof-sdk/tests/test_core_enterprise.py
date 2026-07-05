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
Tests for enterprise-grade core verification behavior.
"""

import sys

import pytest

from outputproof import assertions as a
from outputproof.assertions.base import Assertion
from outputproof.core import VerificationError, Verifier, verify
from outputproof.models import AssertionResult, AssertionType, VerificationRequest


class FixedAssertion(Assertion):
    """Test assertion with a fixed result."""

    def __init__(self, name: str, passed: bool) -> None:
        self._passed = passed
        super().__init__(name=name, assertion_type=AssertionType.STRUCTURAL)

    async def evaluate(self, request: VerificationRequest) -> AssertionResult:
        return self._create_result(
            passed=self._passed,
            message=f"{self.name} {'passed' if self._passed else 'failed'}",
        )


@pytest.mark.asyncio
async def test_assertion_mode_all_requires_every_assertion():
    verifier = Verifier(
        assertions=[
            a.output_matches("present"),
            a.output_matches("missing"),
        ],
        assertion_mode="all",
    )

    result = await verifier.verify("check output", "present", agent_id="agent")

    assert result.verdict.value == "FAIL"
    assert result.confidence_score == 0.5
    assert result.corrective_prompt is not None


@pytest.mark.asyncio
async def test_assertion_mode_all_fails_tampered_grounding_even_with_self_reported_flag():
    verifier = Verifier(
        assertions=[
            a.output_matches(r'"source_text_hashes_verified"\s*:\s*true'),
            a.command_succeeds(f'"{sys.executable}" -c "import sys; sys.exit(1)"'),
        ],
        assertion_mode="all",
        assertion_threshold=1.0,
    )

    result = await verifier.verify(
        "verify grounding",
        '{"source_text_hashes_verified": true, "hash_verified": true}',
        agent_id="agent",
    )

    assert result.verdict.value == "FAIL"
    assert result.confidence_score == 0.5
    assert [assertion.passed for assertion in result.assertion_results] == [True, False]


@pytest.mark.asyncio
async def test_assertion_mode_all_passes_clean_grounding():
    verifier = Verifier(
        assertions=[
            a.output_matches(r'"source_text_hashes_verified"\s*:\s*true'),
            a.command_succeeds(f'"{sys.executable}" -c "import sys; sys.exit(0)"'),
        ],
        assertion_mode="all",
        assertion_threshold=1.0,
    )

    result = await verifier.verify(
        "verify grounding",
        '{"source_text_hashes_verified": true, "hash_verified": true}',
        agent_id="agent",
    )

    assert result.verdict.value == "PASS"
    assert result.confidence_score == 1.0


@pytest.mark.asyncio
async def test_assertion_mode_any_passes_with_one_success():
    verifier = Verifier(
        assertions=[
            a.output_matches("present"),
            a.output_matches("missing"),
        ],
        assertion_mode="any",
    )

    result = await verifier.verify("check output", "present", agent_id="agent")

    assert result.verdict.value == "PASS"
    assert result.confidence_score == 0.5


@pytest.mark.asyncio
async def test_weighted_assertion_mode_uses_named_weights():
    verifier = Verifier(
        assertions=[
            FixedAssertion("critical", passed=True),
            FixedAssertion("minor", passed=False),
        ],
        assertion_mode="weighted",
        assertion_threshold=0.7,
        assertion_weights={"critical": 0.8, "minor": 0.2},
    )

    result = await verifier.verify("check output", "anything", agent_id="agent")

    assert result.verdict.value == "PASS"
    assert result.confidence_score == 0.8


@pytest.mark.asyncio
async def test_verifier_accepts_assertion_config_mappings():
    verifier = Verifier(assertions=[{"type": "output_matches", "pattern": "ok"}])

    result = await verifier.verify("check output", "ok", agent_id="agent")

    assert result.passed


@pytest.mark.asyncio
async def test_verify_decorator_retries_with_corrective_prompt(monkeypatch):
    calls = []

    async def no_sleep(delay: float) -> None:
        return None

    monkeypatch.setattr("outputproof.core.asyncio.sleep", no_sleep)

    @verify(
        assertions=[a.output_matches("fixed")],
        retry_on_fail=True,
        max_retries=1,
    )
    async def agent(prompt: str) -> str:
        calls.append(prompt)
        if "Failed Assertions" in prompt:
            return "fixed output"
        return "broken output"

    result = await agent("produce fixed output")

    assert result == "fixed output"
    assert len(calls) == 2
    assert "Please revise your previous output" in calls[1]


@pytest.mark.asyncio
async def test_verify_decorator_records_retry_history_on_failure(monkeypatch):
    async def no_sleep(delay: float) -> None:
        return None

    monkeypatch.setattr("outputproof.core.asyncio.sleep", no_sleep)

    @verify(
        assertions=[a.output_matches("fixed")],
        retry_on_fail=True,
        max_retries=1,
    )
    async def agent(prompt: str) -> str:
        return "still broken"

    with pytest.raises(VerificationError) as exc:
        await agent("produce fixed output")

    assert exc.value.result.retry_count == 1
    assert len(exc.value.result.retry_history) == 2
    assert exc.value.result.corrective_prompt is not None
