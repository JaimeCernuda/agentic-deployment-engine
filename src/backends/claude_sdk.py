"""Claude Agent SDK backend implementation.

Provides integration with the Claude Agent SDK for agentic inference.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from ..config import settings
from ..core.exceptions import AgentBackendError
from ..observability.semantic import get_semantic_tracer
from .base import AgentBackend, BackendConfig, QueryResult

logger = logging.getLogger(__name__)


class ClaudeSDKBackend(AgentBackend):
    """Backend implementation using Claude Agent SDK.

    Features:
    - Connection pooling for better performance
    - Automatic reconnection on failures
    - Support for MCP tool servers
    """

    def __init__(self, config: BackendConfig) -> None:
        """Initialize the Claude SDK backend.

        Args:
            config: Backend configuration.
        """
        super().__init__(config)
        self._pool: asyncio.Queue[ClaudeSDKClient] = asyncio.Queue(
            maxsize=settings.client_pool_size
        )
        self._pool_lock = asyncio.Lock()
        self._options: ClaudeAgentOptions | None = None

    @property
    def name(self) -> str:
        """Backend name for logging/identification."""
        return "claude-agent-sdk"

    async def initialize(self) -> None:
        """Initialize client pool with pre-connected clients.

        Creates a pool of SDK clients for concurrent query handling.
        Safe to call multiple times - subsequent calls are no-ops.
        """
        if self._initialized:
            return

        async with self._pool_lock:
            if self._initialized:
                return

            # Build ClaudeAgentOptions from config
            self._options = ClaudeAgentOptions(
                mcp_servers=self.config.mcp_servers,
                allowed_tools=self.config.allowed_tools,
                system_prompt=self.config.system_prompt,
                permission_mode="bypassPermissions",
                setting_sources=[],
                **self.config.extra_options,
            )

            # Create pooled clients
            pool_size = settings.client_pool_size
            created = 0

            for i in range(pool_size):
                try:
                    client = ClaudeSDKClient(self._options)
                    await client.connect()
                    await self._pool.put(client)
                    created += 1
                    logger.debug(f"Pool client {i + 1}/{pool_size} connected")
                except Exception as e:
                    logger.error(f"Failed to create pool client {i + 1}: {e}")
                    # Continue with fewer clients rather than failing entirely

            self._initialized = True
            logger.info(
                f"Claude SDK backend initialized with {created}/{pool_size} clients"
            )

    async def query(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> QueryResult:
        """Execute query using pooled client.

        Args:
            prompt: The query to execute.
            context: Optional context for tracing/attribution.

        Returns:
            QueryResult with response and metadata.

        Raises:
            AgentBackendError: If the query fails.
        """
        await self.initialize()

        client = await self._pool.get()
        tracer = get_semantic_tracer()
        tools_used_names: list[str] = []

        try:
            logger.debug(f"Executing query ({len(prompt)} chars)")
            await client.query(prompt)

            response = ""
            message_count = 0
            tool_count = 0

            async for message in client.receive_response():
                message_count += 1
                role = getattr(message, "role", "unknown")
                stop_reason = getattr(message, "stop_reason", None)

                content = getattr(message, "content", None)
                if content is not None:
                    # Build full content string for LLM message tracing
                    content_parts: list[str] = []
                    for block in content:
                        block_type = getattr(block, "type", None)
                        text = getattr(block, "text", None)
                        tool_name = getattr(block, "name", None)
                        tool_input = getattr(block, "input", None)

                        if text is not None:
                            response += text
                            content_parts.append(text)

                        if tool_name is not None:
                            # This is a tool_use block - trace the tool call
                            tool_count += 1
                            tools_used_names.append(tool_name)

                            # Serialize tool input for tracing
                            input_str = (
                                json.dumps(tool_input, default=str)
                                if tool_input
                                else "{}"
                            )
                            content_parts.append(
                                f"[tool_use: {tool_name}({input_str})]"
                            )

                            # Trace the tool call
                            with tracer.tool_call(tool_name, tool_input) as span:
                                tracer.add_event(
                                    span,
                                    "tool_invoked",
                                    {"block_type": block_type or "tool_use"},
                                )

                        # Handle tool_result blocks
                        if block_type == "tool_result":
                            tool_use_id = getattr(block, "tool_use_id", None)
                            tool_content = getattr(block, "content", None)
                            is_error = getattr(block, "is_error", False)

                            result_str = str(tool_content)[:200] if tool_content else ""
                            content_parts.append(f"[tool_result: {result_str}...]")

                            logger.debug(
                                f"Tool result for {tool_use_id}: "
                                f"{'error' if is_error else 'success'}"
                            )

                    # Trace the full LLM message
                    full_content = " ".join(content_parts) if content_parts else ""
                    with tracer.llm_message(
                        role=role,
                        content=full_content,
                        model="claude-agent-sdk",
                    ) as span:
                        tracer.add_event(
                            span,
                            "message_received",
                            {
                                "message_index": message_count,
                                "stop_reason": stop_reason,
                                "has_tool_use": tool_count > 0,
                            },
                        )

            logger.debug(
                f"Query complete: {message_count} messages, {tool_count} tools"
            )

            return QueryResult(
                response=response or "No response generated",
                messages_count=message_count,
                tools_used=tool_count,
                metadata={
                    "context": context,
                    "tools_used_names": tools_used_names,
                }
                if context or tools_used_names
                else {},
            )

        except Exception as e:
            logger.error(f"Query failed: {e}")
            raise AgentBackendError(self.name, str(e), cause=e) from e
        finally:
            await self._pool.put(client)

    async def query_stream(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> AsyncIterator[Any]:
        """Stream query results.

        Yields messages as they arrive from the SDK.

        Args:
            prompt: The query to execute.
            context: Optional context for tracing/attribution.

        Yields:
            Message objects from the Claude SDK.

        Raises:
            AgentBackendError: If the query fails.
        """
        await self.initialize()

        client = await self._pool.get()
        tracer = get_semantic_tracer()
        message_count = 0

        try:
            logger.debug(f"Executing streaming query ({len(prompt)} chars)")
            await client.query(prompt)

            async for message in client.receive_response():
                message_count += 1
                role = getattr(message, "role", "unknown")

                # Trace each streamed message
                content = getattr(message, "content", None)
                content_str = ""
                if content:
                    for block in content:
                        text = getattr(block, "text", None)
                        tool_name = getattr(block, "name", None)
                        if text:
                            content_str += text
                        if tool_name:
                            tool_input = getattr(block, "input", None)
                            content_str += f"[tool: {tool_name}]"
                            # Trace tool call in streaming mode
                            with tracer.tool_call(tool_name, tool_input):
                                pass  # Tool traced

                # Trace the LLM message
                with tracer.llm_message(
                    role=role,
                    content=content_str,
                    model="claude-agent-sdk",
                ) as span:
                    tracer.add_event(span, "stream_message", {"index": message_count})

                yield message

        except Exception as e:
            logger.error(f"Streaming query failed: {e}")
            raise AgentBackendError(self.name, str(e), cause=e) from e
        finally:
            await self._pool.put(client)

    async def cleanup(self) -> None:
        """Cleanup all pooled clients.

        Disconnects all clients and clears the pool. Safe to call
        multiple times.
        """
        if not self._initialized:
            return

        clients_closed = 0
        while not self._pool.empty():
            try:
                client = self._pool.get_nowait()
                await client.disconnect()
                clients_closed += 1
            except asyncio.QueueEmpty:
                break
            except Exception as e:
                logger.error(f"Error disconnecting client: {e}")

        self._initialized = False
        logger.info(f"Claude SDK backend cleaned up ({clients_closed} clients)")

    async def update_system_prompt(self, new_prompt: str) -> None:
        """Update the system prompt for new queries.

        This requires recreating the client pool with the new options.

        Args:
            new_prompt: The new system prompt.
        """
        self.config.system_prompt = new_prompt
        await self.cleanup()
        self._initialized = False
        await self.initialize()
