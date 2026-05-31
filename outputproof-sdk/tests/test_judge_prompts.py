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
Tests for judge prompt rendering and response parsing.
"""

import json
from types import SimpleNamespace

import pytest

from outputproof.judge.prompts import (
    CODE_REVIEW_PROMPT,
    DEFAULT_JUDGE_PROMPT,
    INTENT_MATCH_PROMPT,
    QUALITY_CHECK_PROMPT,
    RUBRIC_PROMPT,
    format_corrective_hints,
    format_rubric,
    render_prompt,
)
from outputproof.judge.scorer import LLMJudge
from outputproof.models import JudgeConfig


def test_render_prompt_uses_format_contract_for_json_examples():
    """Literal JSON braces should render cleanly after str.format interpolation."""
    prompt = render_prompt(
        CODE_REVIEW_PROMPT,
        prompt="Add a cache",
        output="diff --git a/cache.py b/cache.py",
        assertion_results="No assertions evaluated",
    )

    assert "{prompt}" not in prompt
    assert "{{" not in prompt
    assert '"score": 0.85' in prompt


def test_render_prompt_reports_missing_placeholders():
    """Missing template values should fail with an actionable error."""
    with pytest.raises(KeyError, match="Missing required prompt placeholder: output"):
        render_prompt(DEFAULT_JUDGE_PROMPT, prompt="Add tests", assertion_results="None")


def test_json_prompts_require_raw_json_only():
    """Each JSON prompt should explicitly reject markdown fences and preambles."""
    prompts = [
        DEFAULT_JUDGE_PROMPT,
        CODE_REVIEW_PROMPT,
        INTENT_MATCH_PROMPT,
        QUALITY_CHECK_PROMPT,
        RUBRIC_PROMPT,
    ]

    for prompt in prompts:
        assert "Return only the raw JSON object" in prompt
        assert "Do not include markdown" in prompt


def test_format_corrective_hints_normalizes_to_bullets():
    """Corrective hints should be structured before prompt injection."""
    assert format_corrective_hints("Fix the parser") == "- Fix the parser"
    assert format_corrective_hints(["1. Add tests", "- Fix lint"]) == (
        "- Add tests\n- Fix lint"
    )
    assert format_corrective_hints("") == "- Address all failed aspects."


def test_format_rubric_serializes_mapping_with_stable_keys():
    """Mapping rubrics become JSON so criteria keys stay predictable."""
    rubric = format_rubric(
        {
            "correctness": {"weight": 0.7, "description": "Works as requested"},
            "tests": {"weight": 0.3, "description": "Covers edge cases"},
        }
    )

    parsed = json.loads(rubric)
    assert list(parsed) == ["correctness", "tests"]
    assert parsed["correctness"]["weight"] == 0.7


def test_parse_response_accepts_rubric_schema():
    """Rubric responses should normalize overall_score to score for callers."""
    judge = LLMJudge(JudgeConfig())

    result = judge._parse_response(
        json.dumps(
            {
                "criteria_scores": {"correctness": 0.8},
                "overall_score": 0.75,
                "verdict": "PARTIAL",
                "explanation": "Mostly correct.",
            }
        )
    )

    assert result["score"] == 0.75
    assert result["criteria_scores"] == {"correctness": 0.8}
    assert result["verdict"] == "PARTIAL"


class _FakeOpenAICompletions:
    async def create(self, **kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content='{"score": 1.0}'))
            ]
        )


class _FakeOpenAIClient:
    chat = SimpleNamespace(completions=_FakeOpenAICompletions())


class _FakeAnthropicMessages:
    async def create(self, **kwargs):
        return SimpleNamespace(content=[SimpleNamespace(text='{"score": 0.9}')])


class _FakeAnthropicClient:
    messages = _FakeAnthropicMessages()


@pytest.mark.asyncio
async def test_call_llm_detects_openai_style_clients():
    judge = LLMJudge(JudgeConfig())

    response = await judge._call_llm(_FakeOpenAIClient(), "Evaluate this")

    assert response == '{"score": 1.0}'


@pytest.mark.asyncio
async def test_call_llm_detects_anthropic_style_clients():
    judge = LLMJudge(JudgeConfig())

    response = await judge._call_llm(_FakeAnthropicClient(), "Evaluate this")

    assert response == '{"score": 0.9}'
