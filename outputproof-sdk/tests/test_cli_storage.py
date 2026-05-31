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
Tests for CLI assertion loading and local audit storage.
"""

from pathlib import Path
from uuid import uuid4

import pytest

from outputproof.cli.main import _sync_verification_to_server, load_assertions_from_yaml
from outputproof.models import (
    AssertionResult,
    AssertionType,
    VerificationResult,
    VerificationVerdict,
)
from outputproof.storage import append_verification, get_verification, load_verifications


def _local_test_path(filename: str) -> Path:
    """Return a stable workspace-local test path without pytest tmp fixtures."""
    directory = Path(__file__).resolve().parent / "_tmp"
    directory.mkdir(exist_ok=True)
    return directory / f"{uuid4().hex}-{filename}"


def test_load_assertions_from_yaml_mapping():
    config = _local_test_path("assertions.yaml")
    config.write_text(
        """
assertions:
  - type: output_matches
    pattern: authenticated
  - type: contains_import
    module: typing
    import_name: Optional
""",
        encoding="utf-8",
    )

    assertions = load_assertions_from_yaml(str(config))

    assert len(assertions) == 2
    assert assertions[0].name.startswith("output_matches")
    assert assertions[1].name == "contains_import(typing.Optional)"


def test_load_assertions_from_yaml_rejects_unknown_type():
    config = _local_test_path("assertions.yaml")
    config.write_text(
        """
assertions:
  - type: does_not_exist
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unsupported assertion type"):
        load_assertions_from_yaml(str(config))


def test_local_storage_round_trip():
    storage_path = _local_test_path("verifications.jsonl")
    result = VerificationResult(
        request_id="req-123",
        agent_id="agent-1",
        verdict=VerificationVerdict.PASS,
        confidence_score=1.0,
        assertion_results=[
            AssertionResult(
                assertion_id="assert-1",
                assertion_type=AssertionType.STRUCTURAL,
                name="file_exists",
                passed=True,
                message="File exists",
            )
        ],
    )

    append_verification(result, storage_path)

    records = load_verifications(storage_path)
    assert len(records) == 1
    assert records[0]["request_id"] == "req-123"
    assert records[0]["agent_id"] == "agent-1"
    assert get_verification("req-123", storage_path) == records[0]


def test_sync_verification_to_server_posts_result(monkeypatch):
    result = VerificationResult(
        request_id="req-sync",
        agent_id="agent-sync",
        verdict=VerificationVerdict.PASS,
        confidence_score=1.0,
        assertion_results=[],
    )
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

    def fake_post(url, json, timeout):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr("outputproof.cli.main.httpx.post", fake_post)

    assert _sync_verification_to_server(result, "http://127.0.0.1:8080/")
    assert calls == [
        {
            "url": "http://127.0.0.1:8080/api/verifications",
            "json": result.to_dict(),
            "timeout": 5.0,
        }
    ]


def test_sync_verification_to_server_skips_without_url(monkeypatch):
    result = VerificationResult(
        request_id="req-local",
        verdict=VerificationVerdict.PASS,
        confidence_score=1.0,
        assertion_results=[],
    )
    monkeypatch.delenv("OUTPUTPROOF_SERVER_URL", raising=False)

    assert not _sync_verification_to_server(result)
