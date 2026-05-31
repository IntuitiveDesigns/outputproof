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
LLM-as-Judge module for OutputProof.

This module provides the LLM-as-Judge scorer that uses a secondary LLM
to evaluate agent output semantically. It supports multiple backends
including Anthropic Claude, OpenAI, and local models via Ollama.

Example:
    >>> from outputproof.judge import LLMJudge, JudgeConfig
    >>>
    >>> config = JudgeConfig(
    ...     model="claude-haiku-4-5",
    ...     api_key="your-api-key",
    ... )
    >>> judge = LLMJudge(config)
    >>> result = await judge.score(request, assertion_results)
"""

from outputproof.judge.scorer import LLMJudge
from outputproof.judge.prompts import (
    DEFAULT_JUDGE_PROMPT,
    CODE_REVIEW_PROMPT,
    INTENT_MATCH_PROMPT,
    QUALITY_CHECK_PROMPT,
    CORRECTIVE_PROMPT_TEMPLATE,
    RUBRIC_PROMPT,
    format_corrective_hints,
    format_rubric,
    render_prompt,
)
from outputproof.models import JudgeConfig

__all__ = [
    "LLMJudge",
    "JudgeConfig",
    "DEFAULT_JUDGE_PROMPT",
    "CODE_REVIEW_PROMPT",
    "INTENT_MATCH_PROMPT",
    "QUALITY_CHECK_PROMPT",
    "CORRECTIVE_PROMPT_TEMPLATE",
    "RUBRIC_PROMPT",
    "format_corrective_hints",
    "format_rubric",
    "render_prompt",
]
