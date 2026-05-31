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

"""Helpers for running OutputProof as a GitHub Actions pull request gate."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from outputproof.models import VerificationResult

DEFAULT_ASSERTION_FILES = (
    ".outputproof/github-gate.yaml",
    ".outputproof/assertions.yaml",
    "outputproof/assertions.yaml",
)

DEFAULT_EXCLUDE_PATTERNS = (
    ".git/**",
    ".github/**",
    ".outputproof/**",
    "**/__pycache__/**",
    "**/.mypy_cache/**",
    "**/.pytest_cache/**",
    "**/.ruff_cache/**",
    "**/.venv/**",
    "**/build/**",
    "**/dist/**",
    "**/node_modules/**",
)

DEFAULT_MAX_FILE_BYTES = 256 * 1024


@dataclass
class GatePayload:
    """Text and metadata submitted to the verifier from a GitHub Actions run."""

    prompt: str
    output: str
    changed_files: list[str]
    skipped_files: list[str]
    metadata: dict[str, Any]


def resolve_assertion_paths(
    configured_paths: Sequence[str],
    cwd: Path | None = None,
) -> list[str]:
    """Resolve explicit or conventional assertion config paths."""
    base = cwd or Path.cwd()
    if configured_paths:
        return [str((base / path).resolve()) for path in configured_paths]

    found = []
    for candidate in DEFAULT_ASSERTION_FILES:
        path = base / candidate
        if path.exists():
            found.append(str(path.resolve()))
    return found


def default_base_ref() -> str:
    """Infer the Git comparison base from GitHub Actions environment variables."""
    configured = os.getenv("OUTPUTPROOF_BASE_REF", "").strip()
    if configured:
        return configured

    github_base = os.getenv("GITHUB_BASE_REF", "").strip()
    if github_base:
        return f"origin/{github_base}"

    return "HEAD~1"


def collect_changed_files(
    base_ref: str | None = None,
    include_patterns: Sequence[str] = (),
    exclude_patterns: Sequence[str] = (),
    cwd: Path | None = None,
) -> list[str]:
    """Return changed text-candidate paths for the current Git checkout."""
    base = base_ref or default_base_ref()
    root = cwd or Path.cwd()
    args = ["diff", "--name-only", "--diff-filter=ACMRT", f"{base}...HEAD"]
    try:
        output = _run_git(args, root)
    except RuntimeError:
        output = _run_git(["diff", "--name-only", "--diff-filter=ACMRT", base, "HEAD"], root)

    all_excludes = [*DEFAULT_EXCLUDE_PATTERNS, *exclude_patterns]
    paths = []
    for line in output.splitlines():
        path = line.strip().replace("\\", "/")
        if not path:
            continue
        if include_patterns and not _matches_any(path, include_patterns):
            continue
        if _matches_any(path, all_excludes):
            continue
        if (root / path).is_file():
            paths.append(path)
    return paths


def build_gate_payload(
    prompt: str | None = None,
    prompt_file: str | None = None,
    output_files: Sequence[str] = (),
    base_ref: str | None = None,
    include_patterns: Sequence[str] = (),
    exclude_patterns: Sequence[str] = (),
    agent_id: str | None = None,
    developer_id: str | None = None,
    task_type: str | None = None,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    cwd: Path | None = None,
) -> GatePayload:
    """Create a verification payload from explicit files or the PR diff."""
    root = cwd or Path.cwd()
    selected_files = (
        [_normalize_relative_path(path, root) for path in output_files]
        if output_files
        else collect_changed_files(
            base_ref=base_ref,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
            cwd=root,
        )
    )

    output, skipped = read_files_as_output(selected_files, root, max_file_bytes)
    resolved_prompt = resolve_prompt(prompt=prompt, prompt_file=prompt_file, cwd=root)
    resolved_agent_id = (
        agent_id
        or os.getenv("OUTPUTPROOF_AGENT_ID")
        or os.getenv("GITHUB_ACTOR")
        or "github-actions"
    )
    resolved_developer_id = (
        developer_id
        or os.getenv("OUTPUTPROOF_DEVELOPER_ID")
        or os.getenv("GITHUB_ACTOR")
        or "unknown"
    )
    resolved_task_type = task_type or os.getenv("OUTPUTPROOF_TASK_TYPE") or "code_generation"

    metadata = {
        "source": "github_actions",
        "agent_id": resolved_agent_id,
        "developer_id": resolved_developer_id,
        "task_type": resolved_task_type,
        "changed_files": selected_files,
        "skipped_files": skipped,
        "github": github_metadata(base_ref=base_ref or default_base_ref()),
    }

    return GatePayload(
        prompt=resolved_prompt,
        output=output,
        changed_files=selected_files,
        skipped_files=skipped,
        metadata=metadata,
    )


def read_files_as_output(
    files: Sequence[str],
    cwd: Path | None = None,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> tuple[str, list[str]]:
    """Read selected files into one deterministic verification output string."""
    root = cwd or Path.cwd()
    sections = []
    skipped = []
    for relative_path in files:
        path = root / relative_path
        if not path.is_file():
            skipped.append(f"{relative_path} (missing)")
            continue
        if path.stat().st_size > max_file_bytes:
            skipped.append(f"{relative_path} (larger than {max_file_bytes} bytes)")
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            skipped.append(f"{relative_path} (not UTF-8 text)")
            continue

        sections.append(
            f"=== File: {relative_path} ===\n"
            f"{content.rstrip()}\n"
            f"=== End File: {relative_path} ==="
        )

    if not sections:
        return "No changed text files were available for verification.", skipped

    file_list = "\n".join(f"- {path}" for path in files)
    return f"Changed files:\n{file_list}\n\n" + "\n\n".join(sections), skipped


def resolve_prompt(
    prompt: str | None = None,
    prompt_file: str | None = None,
    cwd: Path | None = None,
) -> str:
    """Resolve the prompt text used by the verification request."""
    if prompt:
        return prompt

    if prompt_file:
        path = (cwd or Path.cwd()) / prompt_file
        return path.read_text(encoding="utf-8").strip()

    event_prompt = prompt_from_github_event()
    if event_prompt:
        return event_prompt

    return "Verify the changed files in this GitHub Actions run."


def prompt_from_github_event() -> str | None:
    """Extract useful PR or commit context from the GitHub event payload."""
    event_path = os.getenv("GITHUB_EVENT_PATH", "").strip()
    if not event_path:
        return None

    path = Path(event_path)
    if not path.exists():
        return None

    try:
        event = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None

    pull_request = event.get("pull_request")
    if isinstance(pull_request, dict):
        title = str(pull_request.get("title") or "").strip()
        body = str(pull_request.get("body") or "").strip()
        if title or body:
            return f"Pull request: {title}\n\n{body}".strip()

    head_commit = event.get("head_commit")
    if isinstance(head_commit, dict):
        message = str(head_commit.get("message") or "").strip()
        if message:
            return f"Commit: {message}"

    return None


def github_metadata(base_ref: str) -> dict[str, str | None]:
    """Collect GitHub Actions metadata without requiring GitHub-only imports."""
    server_url = os.getenv("GITHUB_SERVER_URL")
    repository = os.getenv("GITHUB_REPOSITORY")
    run_id = os.getenv("GITHUB_RUN_ID")
    run_url = (
        f"{server_url}/{repository}/actions/runs/{run_id}"
        if server_url and repository and run_id
        else None
    )
    return {
        "event_name": os.getenv("GITHUB_EVENT_NAME"),
        "repository": repository,
        "workflow": os.getenv("GITHUB_WORKFLOW"),
        "run_id": run_id,
        "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
        "run_url": run_url,
        "actor": os.getenv("GITHUB_ACTOR"),
        "sha": os.getenv("GITHUB_SHA"),
        "ref": os.getenv("GITHUB_REF"),
        "head_ref": os.getenv("GITHUB_HEAD_REF"),
        "base_ref": base_ref,
    }


def format_step_summary(result: VerificationResult, payload: GatePayload) -> str:
    """Format a GitHub Actions job summary for the verification result."""
    verdict = result.verdict.value
    status = "passed" if result.passed else "failed"
    passed_count = sum(1 for assertion in result.assertion_results if assertion.passed)
    total_count = len(result.assertion_results)
    lines = [
        "## OutputProof Gate",
        "",
        f"**Verdict:** {verdict}",
        f"**Status:** Verification {status}.",
        f"**Confidence:** {result.confidence_score:.2f}",
        f"**Assertions:** {passed_count}/{total_count} passed",
        f"**Changed files:** {len(payload.changed_files)}",
    ]

    if payload.skipped_files:
        skipped = ", ".join(_escape_markdown(item) for item in payload.skipped_files[:5])
        extra = len(payload.skipped_files) - 5
        suffix = f" and {extra} more" if extra > 0 else ""
        lines.append(f"**Skipped files:** {skipped}{suffix}")

    if result.assertion_results:
        lines.extend(
            [
                "",
                "| Assertion | Status | Message |",
                "| --- | --- | --- |",
            ]
        )
        for assertion in result.assertion_results:
            assertion_status = "PASS" if assertion.passed else "FAIL"
            message = assertion.message.replace("\n", " ").strip()
            if len(message) > 180:
                message = message[:177] + "..."
            lines.append(
                "| "
                f"{_escape_markdown(assertion.name)} | "
                f"{assertion_status} | "
                f"{_escape_markdown(message)} |"
            )

    if result.corrective_prompt and not result.passed:
        corrective = result.corrective_prompt.strip()
        if len(corrective) > 1000:
            corrective = corrective[:997] + "..."
        lines.extend(
            [
                "",
                "<details>",
                "<summary>Corrective prompt</summary>",
                "",
                "```text",
                corrective,
                "```",
                "</details>",
            ]
        )

    return "\n".join(lines) + "\n"


def append_step_summary(summary_path: str | None, markdown: str) -> None:
    """Append markdown to GitHub's step summary file when available."""
    if not summary_path:
        return
    path = Path(summary_path)
    with open(path, "a", encoding="utf-8") as file:
        file.write(markdown)


def _run_git(args: Sequence[str], cwd: Path) -> str:
    process = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        raise RuntimeError(process.stderr.strip() or "git command failed")
    return process.stdout


def _normalize_relative_path(path: str, cwd: Path) -> str:
    candidate = Path(path)
    if candidate.is_absolute():
        try:
            candidate = candidate.relative_to(cwd)
        except ValueError:
            return candidate.as_posix()
    return candidate.as_posix()


def _matches_any(path: str, patterns: Sequence[str]) -> bool:
    return any(_matches_pattern(path, pattern) for pattern in patterns)


def _matches_pattern(path: str, pattern: str) -> bool:
    normalized = pattern.replace("\\", "/")
    if normalized.endswith("/**"):
        prefix = normalized[:-3].rstrip("/")
        return path == prefix or path.startswith(f"{prefix}/")
    return fnmatch(path, normalized) or fnmatch(Path(path).name, normalized)


def _escape_markdown(value: str) -> str:
    return value.replace("|", "\\|")
