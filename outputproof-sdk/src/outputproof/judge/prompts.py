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
Prompt templates for the LLM-as-Judge scorer.

This module contains various prompt templates used by the judge to evaluate
agent output in different scenarios.

All templates use Python ``str.format`` interpolation. Use ``render_prompt``
at call sites so missing placeholders fail clearly. Literal JSON braces inside
templates must be escaped as ``{{`` and ``}}``.
"""

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, Optional, TypedDict, Union


class DefaultJudgeResponse(TypedDict):
    """Response schema for DEFAULT_JUDGE_PROMPT."""

    score: float
    verdict: str
    explanation: str
    failed_aspects: list[str]
    corrective_hint: str


class CodeReviewResponse(TypedDict):
    """Response schema for CODE_REVIEW_PROMPT."""

    score: float
    verdict: str
    explanation: str
    issues: list[str]
    suggestions: list[str]


class IntentMatchResponse(TypedDict):
    """Response schema for INTENT_MATCH_PROMPT."""

    score: float
    match: bool
    explanation: str
    missing_aspects: list[str]


class QualityDimensions(TypedDict):
    """Dimension scores for QUALITY_CHECK_PROMPT."""

    readability: int
    structure: int
    error_handling: int
    documentation: int
    best_practices: int


class QualityCheckResponse(TypedDict):
    """Response schema for QUALITY_CHECK_PROMPT."""

    overall_score: float
    dimensions: QualityDimensions
    explanation: str
    improvements: list[str]


class RubricResponse(TypedDict):
    """Response schema for RUBRIC_PROMPT."""

    criteria_scores: dict[str, float]
    overall_score: float
    verdict: str
    explanation: str


def render_prompt(template: str, **kwargs: Any) -> str:
    """Render a prompt template using this module's ``str.format`` contract."""
    try:
        return template.format(**kwargs)
    except KeyError as exc:
        missing_key = exc.args[0]
        raise KeyError(f"Missing required prompt placeholder: {missing_key}") from exc
    except ValueError as exc:
        raise ValueError(
            "Invalid prompt template. Escape literal JSON braces as '{{' and '}}'."
        ) from exc


def format_corrective_hints(
    hints: Optional[Union[str, Sequence[str]]],
) -> str:
    """Normalize corrective hints into a non-empty Markdown bullet list."""
    if hints is None:
        return "- Address all failed aspects."

    if isinstance(hints, str):
        items = hints.splitlines()
    else:
        items = [str(hint) for hint in hints]

    normalized = []
    for item in items:
        stripped = item.strip()
        if stripped:
            normalized.append(re.sub(r"^(\d+[.)]|[-*])\s+", "", stripped))

    if not normalized:
        return "- Address all failed aspects."

    return "\n".join(f"- {item}" for item in normalized)


def format_rubric(rubric: Optional[Union[str, Mapping[str, Any]]]) -> str:
    """Normalize rubrics for prompt injection.

    Mapping keys become stable criterion names. Values may be plain descriptions
    or structured objects with fields such as ``description`` and ``weight``.
    """
    if rubric is None:
        return "No custom rubric supplied."
    if isinstance(rubric, Mapping):
        return json.dumps(rubric, indent=2, sort_keys=True)
    return str(rubric).strip() or "No custom rubric supplied."


# Used by: LLMJudge.score() when no custom rubric is supplied.
# Required kwargs: prompt, output, assertion_results
# Response schema: DefaultJudgeResponse
DEFAULT_JUDGE_PROMPT = """You are an AI code reviewer evaluating the output of an AI coding agent.

Your task is to assess whether the agent's output correctly addresses the given prompt.

## Input

**Original Prompt:**
{prompt}

**Agent Output:**
{output}

**Assertion Results:**
{assertion_results}

## Evaluation Criteria

1. **Correctness**: Does the output correctly implement what was requested?
2. **Completeness**: Is the output complete, or are there missing pieces?
3. **Quality**: Is the code well-structured, readable, and following best practices?
4. **Safety**: Are there any security concerns or potential bugs?

## Output Format

Respond with a JSON object matching this schema:
{{
    "score": 0.85,
    "verdict": "PASS",
    "explanation": "Brief assessment of the output.",
    "failed_aspects": [],
    "corrective_hint": ""
}}

Use `score` as a float between 0.0 and 1.0. Use `verdict` as one of "PASS",
"FAIL", or "PARTIAL". Return only the raw JSON object. Do not include markdown
code fences, preamble, or explanation outside the JSON structure.

## Response

"""

# Used by: callers that need detailed review findings instead of retry hints.
# Required kwargs: prompt, output, assertion_results
# Response schema: CodeReviewResponse
CODE_REVIEW_PROMPT = """You are a senior software engineer conducting a code review.

Review the following code changes produced by an AI coding agent.

## Original Request

{prompt}

## Code Changes

{output}

## Assertion Results

{assertion_results}

## Review Guidelines

1. **Functionality**: Does the code do what it's supposed to do?
2. **Correctness**: Are there any bugs or logical errors?
3. **Style**: Does the code follow language conventions and style guides?
4. **Maintainability**: Is the code easy to understand and modify?
5. **Testing**: Are there appropriate tests? Do they cover edge cases?
6. **Security**: Are there any security vulnerabilities?
7. **Performance**: Are there any obvious performance issues?

## Output Format

Respond with a JSON object matching this schema:
{{
    "score": 0.85,
    "verdict": "PARTIAL",
    "explanation": "Detailed review summary.",
    "issues": ["Specific issue found."],
    "suggestions": ["Specific improvement to make."]
}}

Use `score` as a float between 0.0 and 1.0. Use `verdict` as one of "PASS",
"FAIL", or "PARTIAL". Return only the raw JSON object. Do not include markdown
code fences, preamble, or explanation outside the JSON structure.

## Review

"""

# Used by: semantic intent matching workflows.
# Required kwargs: intent, prompt, output
# Response schema: IntentMatchResponse
INTENT_MATCH_PROMPT = """You are evaluating whether an AI agent's output matches the intended goal.

## Intended Goal

{intent}

## Original Prompt

{prompt}

## Agent Output

{output}

## Evaluation

Rate how well the agent's output achieves the intended goal on a scale of 0.0 to 1.0.

Consider:
- Does the output address all aspects of the intent?
- Is the implementation correct and complete?
- Are there any misunderstandings of the intent?

## Output Format

Respond with a JSON object matching this schema:
{{
    "score": 0.85,
    "match": true,
    "explanation": "Explanation of how well the output matches the intent.",
    "missing_aspects": []
}}

Use `score` as a float between 0.0 and 1.0. Return only the raw JSON object.
Do not include markdown code fences, preamble, or explanation outside the JSON
structure.

## Evaluation

"""

# Used by: standalone quality checks of generated code.
# Required kwargs: output
# Response schema: QualityCheckResponse
QUALITY_CHECK_PROMPT = """You are evaluating the overall quality of AI-generated code.

## Code

{output}

## Quality Criteria

Rate the code on the following dimensions (1-5 scale each):
1. Readability
2. Structure and organization
3. Error handling
4. Documentation
5. Best practices adherence

## Output Format

Respond with a JSON object matching this schema:
{{
    "overall_score": 0.85,
    "dimensions": {{
        "readability": 4,
        "structure": 4,
        "error_handling": 3,
        "documentation": 4,
        "best_practices": 4
    }},
    "explanation": "Detailed quality assessment.",
    "improvements": ["Specific improvement to make."]
}}

Use `overall_score` as a float between 0.0 and 1.0. Dimension scores must be
integers from 1 to 5. Return only the raw JSON object. Do not include markdown
code fences, preamble, or explanation outside the JSON structure.

## Assessment

"""

# Used by: LLMJudge.generate_corrective_prompt().
# Required kwargs: original_prompt, previous_output, verification_results,
# failed_assertions, judge_explanation, corrective_hints
# `corrective_hints` should be rendered with format_corrective_hints().
CORRECTIVE_PROMPT_TEMPLATE = """Based on the verification results, here are the
issues that need to be addressed:

## Original Request
{original_prompt}

## Previous Output
{previous_output}

## Verification Results
{verification_results}

## Failed Assertions
{failed_assertions}

## Judge Feedback
{judge_explanation}

## Instructions

Please revise your output to address the issues identified above. Specifically:
{corrective_hints}

Provide a complete, corrected implementation that passes all verification checks."""

# Used by: LLMJudge.score() when a custom rubric is supplied.
# Required kwargs: prompt, output, rubric
# Response schema: RubricResponse
# `rubric` should be rendered with format_rubric().
RUBRIC_PROMPT = """You are evaluating AI-generated output against a specific rubric.

## Prompt
{prompt}

## Output
{output}

## Rubric
{rubric}

Rubric format expectations:
- If the rubric is a JSON object, use its top-level keys exactly as criterion
  names in `criteria_scores`.
- If the rubric is prose or a list, infer stable, concise criterion names and
  use those names consistently in `criteria_scores`.
- If weights are provided, use them when calculating `overall_score`.

## Evaluation

Score each criterion and provide an overall assessment.

## Output Format

Respond with a JSON object matching this schema:
{{
    "criteria_scores": {{
        "correctness": 0.85
    }},
    "overall_score": 0.85,
    "verdict": "PASS",
    "explanation": "Detailed explanation."
}}

Use all score values as floats between 0.0 and 1.0. Use `verdict` as one of
"PASS", "FAIL", or "PARTIAL". Return only the raw JSON object. Do not include markdown
code fences, preamble, or explanation outside the JSON structure.

## Evaluation

"""
