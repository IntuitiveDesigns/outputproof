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
Agent integrations for OutputProof.

This module provides integrations with popular AI agent frameworks:

- Claude Code (via MCP server)
- LangChain/LangGraph (callback handler)
- OpenAI Agents SDK (planned)
- Generic REST proxy (planned)

Example:
    >>> from outputproof.integrations import LangChainCallback
    >>> from langchain.chains import LLMChain
    >>>
    >>> callback = LangChainCallback(assertions=[...])
    >>> chain = LLMChain(llm=llm, prompt=prompt, callbacks=[callback])
"""

from outputproof.integrations.base import BaseIntegration
from outputproof.integrations.langchain import LangChainCallback
from outputproof.integrations.claude_code import ClaudeCodeMCP

__all__ = [
    "BaseIntegration",
    "LangChainCallback",
    "ClaudeCodeMCP",
]
