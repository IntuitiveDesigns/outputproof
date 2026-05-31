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

"""Tests for the GitHub Actions verification gate."""

import json

from click.testing import CliRunner

from outputproof.cli.main import cli
from outputproof.github_actions import GatePayload, build_gate_payload, format_step_summary
from outputproof.models import (
    AssertionResult,
    AssertionType,
    VerificationResult,
    VerificationVerdict,
)


def test_build_gate_payload_reads_explicit_files_and_github_prompt(tmp_path, monkeypatch):
    source = tmp_path / "src" / "auth.py"
    source.parent.mkdir()
    source.write_text("def authenticate_user():\n    return 'authenticated'\n", encoding="utf-8")
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps({"pull_request": {"title": "Create auth", "body": "Add login flow"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setenv("GITHUB_ACTOR", "dev-a")

    payload = build_gate_payload(
        output_files=[str(source)],
        agent_id="codex",
        developer_id="dev-a",
        task_type="auth",
        cwd=tmp_path,
    )

    assert "Pull request: Create auth" in payload.prompt
    assert "=== File: src/auth.py ===" in payload.output
    assert payload.changed_files == ["src/auth.py"]
    assert payload.metadata["agent_id"] == "codex"
    assert payload.metadata["developer_id"] == "dev-a"
    assert payload.metadata["task_type"] == "auth"


def test_format_step_summary_reports_failed_assertion():
    result = VerificationResult(
        request_id="req-1",
        verdict=VerificationVerdict.FAIL,
        confidence_score=0.0,
        assertion_results=[
            AssertionResult(
                assertion_id="assert-1",
                assertion_type=AssertionType.BEHAVIORAL,
                name="output_matches(authenticated)",
                passed=False,
                message="Expected at least one match",
            )
        ],
    )
    payload = GatePayload(
        prompt="Create auth",
        output="broken",
        changed_files=["src/auth.py"],
        skipped_files=[],
        metadata={},
    )

    summary = format_step_summary(result, payload)

    assert "## OutputProof Gate" in summary
    assert "**Verdict:** FAIL" in summary
    assert "| output_matches(authenticated) | FAIL | Expected at least one match |" in summary


def test_github_gate_cli_passes_with_explicit_output_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.delenv("OUTPUTPROOF_SERVER_URL", raising=False)
    monkeypatch.setattr(
        "outputproof.cli.main.append_verification",
        lambda result: tmp_path / "ignored.jsonl",
    )
    assertions = tmp_path / "assertions.yaml"
    assertions.write_text(
        """
assertions:
  - type: output_matches
    pattern: authenticated
""",
        encoding="utf-8",
    )
    output = tmp_path / "agent-output.txt"
    output.write_text("The user is authenticated.", encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        [
            "github-gate",
            "--assertions",
            str(assertions),
            "--output-file",
            str(output),
            "--prompt",
            "Create auth",
            "--agent-id",
            "codex",
            "--developer-id",
            "dev-a",
            "--task-type",
            "auth",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "PASSED" in result.output


def test_github_gate_cli_requires_assertions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "agent-output.txt"
    output.write_text("authenticated", encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        [
            "github-gate",
            "--output-file",
            str(output),
            "--prompt",
            "Create auth",
        ],
    )

    assert result.exit_code != 0
    assert "No assertion config found" in result.output
