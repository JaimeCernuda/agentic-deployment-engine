"""Gemini CLI backend implementation.

Uses Google's Gemini CLI as an agentic framework.
Gemini CLI supports MCP servers, tool use, and agentic workflows.

Note: Since Gemini CLI is invoked as a subprocess, we cannot use in-process
hooks like the Claude SDK. Instead, we use the `-o json` output format to
extract tool call information from the structured response, providing
visibility into internal tool execution from the CLI output.
"""

import asyncio
import json
import logging
import shutil
import sys
from collections.abc import AsyncIterator
from typing import Any

from ..core.exceptions import AgentBackendError, ConfigurationError
from ..observability.semantic import get_semantic_tracer
from .base import AgentBackend, BackendConfig, QueryResult

logger = logging.getLogger(__name__)

# On Windows, batch files (.cmd, .bat) need shell=True or explicit cmd.exe
IS_WINDOWS = sys.platform == "win32"


class GeminiCLIBackend(AgentBackend):
    """Backend using Google Gemini CLI as agent framework.

    Gemini CLI is Google's command-line tool for interacting with
    Gemini models, supporting agentic workflows and tool use.

    Prerequisites:
        - Gemini CLI installed (npm install -g @anthropic-ai/gemini-cli or similar)
        - Google Cloud authentication configured

    See: https://github.com/google-gemini/gemini-cli
    """

    def __init__(
        self,
        config: BackendConfig,
        model: str | None = None,
        yolo_mode: bool = True,
    ) -> None:
        """Initialize the Gemini CLI backend.

        Args:
            config: Backend configuration
            model: Gemini model to use (default: let CLI decide)
            yolo_mode: Auto-approve all tool calls (default: True for autonomous operation)
        """
        super().__init__(config)
        self.model = model
        self.yolo_mode = yolo_mode
        self._gemini_path: str | None = None

    @property
    def name(self) -> str:
        """Backend name for logging/identification."""
        return "gemini-cli"

    async def initialize(self) -> None:
        """Initialize the backend by verifying Gemini CLI is available."""
        if self._initialized:
            return

        # Find gemini CLI
        self._gemini_path = shutil.which("gemini")
        if not self._gemini_path:
            raise ConfigurationError(
                "Gemini CLI not found. Install it with: npm install -g @anthropic-ai/gemini-cli"
            )

        # Verify it works
        try:
            # On Windows, .cmd files need shell execution
            # Also pipe stdin to prevent CLI from waiting for interactive input
            if IS_WINDOWS:
                process = await asyncio.create_subprocess_shell(
                    f'"{self._gemini_path}" --version',
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                process = await asyncio.create_subprocess_exec(
                    self._gemini_path,
                    "--version",
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
            if process.returncode != 0:
                raise ConfigurationError(
                    f"Gemini CLI failed version check: {stderr.decode()}"
                )
            version = stdout.decode().strip()
            logger.info(f"Gemini CLI initialized: {version}")
        except TimeoutError as e:
            raise ConfigurationError("Gemini CLI version check timed out") from e
        except Exception as e:
            raise ConfigurationError(f"Failed to initialize Gemini CLI: {e}") from e

        self._initialized = True

    async def query(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> QueryResult:
        """Execute a query using Gemini CLI.

        Args:
            prompt: The query to execute
            context: Optional context (not used by Gemini CLI currently)

        Returns:
            QueryResult with response and metadata
        """
        await self.initialize()

        tracer = get_semantic_tracer()
        model_name = self.model or "gemini-default"

        # Build command
        cmd = [self._gemini_path, "-p", prompt, "-o", "json"]

        if self.model:
            cmd.extend(["-m", self.model])

        if self.yolo_mode:
            cmd.append("-y")

        # Add system prompt if configured
        if self.config.system_prompt:
            # Prepend system prompt to the query
            # Replace newlines with spaces for CLI compatibility
            clean_system_prompt = self.config.system_prompt.replace("\n", " ").strip()
            full_prompt = f"{clean_system_prompt} {prompt}"
            cmd[cmd.index("-p") + 1] = full_prompt

        logger.debug(f"Executing Gemini CLI: {' '.join(cmd[:3])}...")

        # Trace the user query
        with tracer.llm_message(
            role="user",
            content=prompt,
            model=model_name,
        ) as user_span:
            tracer.add_event(
                user_span,
                "gemini_cli_invoked",
                {"yolo_mode": self.yolo_mode},
            )

        try:
            # On Windows, .cmd files need shell execution
            # Pipe stdin to DEVNULL to prevent CLI from waiting for interactive input
            if IS_WINDOWS:
                # Join command for shell execution, escaping quotes in prompt
                cmd_str = " ".join(f'"{c}"' if " " in c or '"' in c else c for c in cmd)
                process = await asyncio.create_subprocess_shell(
                    cmd_str,
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=300,  # 5 minute timeout for complex queries
            )

            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                logger.error(f"Gemini CLI error: {error_msg}")
                raise AgentBackendError(self.name, f"CLI error: {error_msg}")

            # Parse JSON output
            output = stdout.decode()
            tool_calls = []
            try:
                result_data = json.loads(output)
                response = result_data.get("response", output)
                tool_calls = result_data.get("tool_calls", [])
                tool_count = len(tool_calls)
            except json.JSONDecodeError:
                # Fall back to raw output
                response = output
                tool_count = 0

            # Trace each tool call
            for tool_call in tool_calls:
                tool_name = tool_call.get("name", "unknown")
                tool_input = tool_call.get("input", {})
                with tracer.tool_call(tool_name, tool_input) as tool_span:
                    tracer.add_event(
                        tool_span,
                        "gemini_tool_executed",
                        {"result": str(tool_call.get("result", ""))[:200]},
                    )

            # Trace the response
            with tracer.llm_message(
                role="assistant",
                content=response,
                model=model_name,
            ) as response_span:
                tracer.add_event(
                    response_span,
                    "gemini_cli_completed",
                    {"tool_count": tool_count, "response_length": len(response)},
                )

            return QueryResult(
                response=response,
                messages_count=1,
                tools_used=tool_count,
                metadata={"context": context} if context else {},
            )

        except TimeoutError as e:
            raise AgentBackendError(self.name, "Query timed out after 5 minutes") from e
        except Exception as e:
            raise AgentBackendError(self.name, str(e), cause=e) from e

    async def query_stream(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> AsyncIterator[Any]:
        """Execute a streaming query using Gemini CLI.

        Uses stream-json output format for real-time responses.

        Args:
            prompt: The query to execute
            context: Optional context

        Yields:
            JSON objects as they are produced
        """
        await self.initialize()

        # Build command with streaming output
        cmd = [self._gemini_path, "-p", prompt, "-o", "stream-json"]

        if self.model:
            cmd.extend(["-m", self.model])

        if self.yolo_mode:
            cmd.append("-y")

        if self.config.system_prompt:
            full_prompt = f"{self.config.system_prompt}\n\n{prompt}"
            cmd[cmd.index("-p") + 1] = full_prompt

        logger.debug(f"Executing Gemini CLI (streaming): {' '.join(cmd[:3])}...")

        try:
            # On Windows, .cmd files need shell execution
            # Pipe stdin to DEVNULL to prevent CLI from waiting for interactive input
            if IS_WINDOWS:
                cmd_str = " ".join(f'"{c}"' if " " in c or '"' in c else c for c in cmd)
                process = await asyncio.create_subprocess_shell(
                    cmd_str,
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

            # Read streaming output line by line
            if process.stdout is None:
                raise AgentBackendError(self.name, "No stdout stream")

            while True:
                line = await process.stdout.readline()
                if not line:
                    break

                try:
                    data = json.loads(line.decode())
                    yield data
                except json.JSONDecodeError:
                    # Skip non-JSON lines
                    continue

            await process.wait()

            if process.returncode != 0:
                error_msg = ""
                if process.stderr is not None:
                    stderr_data = await process.stderr.read()
                    error_msg = stderr_data.decode().strip()
                logger.error(f"Gemini CLI streaming error: {error_msg}")
                raise AgentBackendError(self.name, f"CLI error: {error_msg}")

        except Exception as e:
            if not isinstance(e, AgentBackendError):
                raise AgentBackendError(self.name, str(e), cause=e) from e
            raise

    async def cleanup(self) -> None:
        """Cleanup resources."""
        self._initialized = False
        logger.info("Gemini CLI backend cleaned up")
