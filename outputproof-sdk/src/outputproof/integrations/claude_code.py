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
Claude Code MCP integration for OutputProof.

This module provides an MCP server that intercepts Claude Code tool results
before they reach the user's shell, enabling verification of agent output.
"""

import json
import logging
from typing import Any, Optional
import uuid

from outputproof.models import (
    VerificationRequest,
    VerificationResult,
    RetryConfig,
)
from outputproof.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)


class ClaudeCodeMCP(BaseIntegration):
    """Claude Code MCP server for verification.

    This integration runs as an MCP server that intercepts tool results
    from Claude Code and verifies them before passing them to the user.

    Attributes:
        assertions: List of assertions to check against output.
        agent_id: Identifier for the agent.
        host: Host to bind the MCP server to.
        port: Port to bind the MCP server to.
    """

    def __init__(
        self,
        assertions: Optional[list] = None,
        agent_id: str = "claude_code",
        host: str = "127.0.0.1",
        port: int = 8888,
        judge_config: Optional[Any] = None,
        retry_on_fail: bool = False,
    ) -> None:
        """Initialize the Claude Code MCP integration.

        Args:
            assertions: List of assertions to check.
            agent_id: Identifier for this agent.
            host: Host to bind to.
            port: Port to bind to.
            judge_config: Optional LLM judge configuration.
            retry_on_fail: Whether to retry on failure.
        """
        super().__init__(name="claude_code", enabled=True)

        self.assertions = assertions or []
        self.agent_id = agent_id
        self.host = host
        self.port = port
        self.judge_config = judge_config
        self.retry_on_fail = retry_on_fail

        self._session_id: str = str(uuid.uuid4())
        self._current_prompt: Optional[str] = None

    async def intercept(
        self,
        prompt: str,
        output: str,
        context: Optional[dict[str, Any]] = None,
    ) -> VerificationResult:
        """Intercept and verify Claude Code output.

        Args:
            prompt: The original prompt.
            output: The agent's output.
            context: Additional context.

        Returns:
            VerificationResult.
        """
        from outputproof.core import Verifier
        from outputproof.judge import LLMJudge

        # Create verifier
        verifier = Verifier(
            assertions=self.assertions,
            judge_config=self.judge_config,
            retry_config=RetryConfig(enabled=self.retry_on_fail),
        )

        # Set judge if configured
        if self.judge_config:
            judge = LLMJudge(self.judge_config)
            verifier.set_judge(judge)

        # Run verification
        result = await verifier.verify(
            prompt=prompt,
            output=output,
            agent_id=self.agent_id,
            context=context,
        )

        return result

    async def on_verify_pass(
        self,
        request: VerificationRequest,
        result: VerificationResult,
    ) -> None:
        """Handle successful verification."""
        logger.info(f"Claude Code verification passed: {request.output_hash}")

    async def on_verify_fail(
        self,
        request: VerificationRequest,
        result: VerificationResult,
    ) -> None:
        """Handle failed verification."""
        logger.warning(f"Claude Code verification failed: {result.failed_assertions}")

    def get_mcp_config(self) -> dict[str, Any]:
        """Get MCP configuration for Claude Desktop.

        Returns:
            Configuration dictionary to add to Claude Desktop config.
        """
        return {
            "mcpServers": {
                "outputproof": {
                    "command": "outputproof",
                    "args": ["mcp", "--port", str(self.port)],
                }
            }
        }

    def start_server(self) -> None:
        """Start the MCP server.

        This method blocks and runs the MCP server.
        """
        logger.info(f"Starting Claude Code MCP server on {self.host}:{self.port}")

        # MCP server implementation would go here
        # For now, this is a placeholder for the full MCP implementation
        logger.warning("MCP server implementation is a placeholder")
        logger.info("Use 'outputproof mcp' CLI command to run the MCP server")

    @staticmethod
    def generate_corrective_prompt(
        original_prompt: str,
        output: str,
        result: VerificationResult,
    ) -> str:
        """Generate a corrective prompt for Claude Code retry.

        Args:
            original_prompt: The original user prompt.
            output: The agent's previous output.
            result: The verification result.

        Returns:
            A corrective prompt to guide the retry.
        """
        failed_assertions = "\n".join(
            f"- {a.name}: {a.message}" for a in result.failed_assertions
        )

        return f"""I need you to revise your previous work. Here's what was requested:

**Original Request:**
{original_prompt}

**Your Previous Output:**
{output[:1000]}...

**Verification Issues Found:**
{failed_assertions}

**Judge Feedback:**
{result.judge_explanation or "No additional feedback"}

Please revise your output to address these issues. Make sure to:
1. Fix all the verification failures
2. Maintain the original intent of the request
3. Test your changes if applicable

Provide the complete, corrected implementation."""


# MCP Server implementation (simplified)


class MCPServer:
    """Simple MCP server for Claude Code integration."""

    def __init__(self, integration: ClaudeCodeMCP) -> None:
        """Initialize the MCP server.

        Args:
            integration: The ClaudeCodeMCP integration instance.
        """
        self.integration = integration
        self._running = False

    async def start(self) -> None:
        """Start the MCP server."""
        self._running = True
        logger.info(f"MCP server starting on port {self.integration.port}")

        # In a full implementation, this would:
        # 1. Listen for MCP protocol connections
        # 2. Intercept tool_result messages
        # 3. Run verification
        # 4. Pass through or block based on results

        logger.info("MCP server running (placeholder implementation)")

    async def stop(self) -> None:
        """Stop the MCP server."""
        self._running = False
        logger.info("MCP server stopped")

    async def handle_message(self, message: dict[str, Any]) -> dict[str, Any]:
        """Handle an incoming MCP message.

        Args:
            message: The incoming message.

        Returns:
            The response message.
        """
        method = message.get("method", "")

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "serverInfo": {
                        "name": "outputproof",
                        "version": "1.1.0",
                    },
                },
            }

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {
                    "tools": [
                        {
                            "name": "verify",
                            "description": "Verify AI agent output",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "prompt": {"type": "string"},
                                    "output": {"type": "string"},
                                },
                                "required": ["prompt", "output"],
                            },
                        }
                    ]
                },
            }

        elif method == "tools/call":
            tool_name = message.get("params", {}).get("name", "")
            if tool_name == "verify":
                params = message.get("params", {}).get("arguments", {})
                result = await self.integration.intercept(
                    prompt=params.get("prompt", ""),
                    output=params.get("output", ""),
                )
                return {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result.to_dict(), indent=2),
                            }
                        ],
                    },
                }

        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}",
            },
        }
