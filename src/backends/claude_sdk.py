"""Claude Agent SDK backend implementation.

Provides integration with the Claude Agent SDK for agentic inference.
Uses SDK hooks for true internal observability of the agentic loop.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookContext,
    HookMatcher,
    PostToolUseHookInput,
    PreToolUseHookInput,
)

from ..config import settings
from ..core.exceptions import AgentBackendError
from ..observability.semantic import SpanData, get_semantic_tracer
from .base import AgentBackend, BackendConfig, QueryResult

logger = logging.getLogger(__name__)


# Track active tool spans for correlation between PreToolUse and PostToolUse
_active_tool_spans: dict[str, SpanData] = {}


async def _pre_tool_use_hook(
    hook_input: PreToolUseHookInput,
    matcher: str | None,
    context: HookContext,
) -> dict[str, Any]:
    """Hook called BEFORE each tool use inside the agentic loop.

    This fires INSIDE the loop, giving us visibility into the agent's
    internal reasoning and tool selection.

    Args:
        hook_input: Contains tool_name, tool_input, session_id, etc.
        matcher: Optional tool name matcher that triggered this hook.
        context: Hook context with signal for cancellation.

    Returns:
        Empty dict to continue normal execution.
    """
    tracer = get_semantic_tracer()
    tool_name = hook_input["tool_name"]
    tool_input = hook_input.get("tool_input", {})

    # Create a span for this tool call
    span = tracer._create_span(
        name=f"tool:{tool_name}",
        level="agent",
        category="tool_call",
        attributes={
            "tool.name": tool_name,
            "tool.input": json.dumps(tool_input, default=str)[:500]
            if tool_input
            else None,
            "hook.type": "PreToolUse",
            "session.id": hook_input.get("session_id"),
        },
    )

    # Store span for correlation with PostToolUse
    span_key = f"{hook_input.get('session_id', 'default')}:{tool_name}"
    _active_tool_spans[span_key] = span

    logger.debug(f"[HOOK] PreToolUse: {tool_name}")

    return {}


async def _post_tool_use_hook(
    hook_input: PostToolUseHookInput,
    matcher: str | None,
    context: HookContext,
) -> dict[str, Any]:
    """Hook called AFTER each tool use inside the agentic loop.

    This fires INSIDE the loop, giving us the tool's actual result
    before the agent processes it.

    Args:
        hook_input: Contains tool_name, tool_input, tool_response, session_id, etc.
        matcher: Optional tool name matcher that triggered this hook.
        context: Hook context with signal for cancellation.

    Returns:
        Empty dict to continue normal execution.
    """
    tracer = get_semantic_tracer()
    tool_name = hook_input["tool_name"]
    tool_response = hook_input.get("tool_response")

    # Find and finish the span from PreToolUse
    span_key = f"{hook_input.get('session_id', 'default')}:{tool_name}"
    span = _active_tool_spans.pop(span_key, None)

    if span:
        # Record the tool result
        tracer.record_tool_result(span, tool_response, success=True)
        tracer._finish_span(span)
    else:
        # Create a new span if we missed the PreToolUse (shouldn't happen normally)
        with tracer.tool_call(tool_name, hook_input.get("tool_input")) as span:
            tracer.record_tool_result(span, tool_response, success=True)

    result_str = str(tool_response)[:100] if tool_response else "None"
    logger.debug(f"[HOOK] PostToolUse: {tool_name} returned: {result_str}...")

    return {}


def _create_tracing_hooks() -> dict[str, list[HookMatcher]]:
    """Create SDK hooks for semantic tracing inside the agentic loop.

    Returns:
        Dictionary of hook type -> list of HookMatcher for ClaudeAgentOptions.
    """
    # Note: Type ignores needed because SDK hook types are more restrictive
    # than what we need. The hooks work correctly at runtime.
    return {
        "PreToolUse": [
            HookMatcher(
                matcher=None,  # Match all tools
                hooks=[_pre_tool_use_hook],  # type: ignore[list-item]
            )
        ],
        "PostToolUse": [
            HookMatcher(
                matcher=None,  # Match all tools
                hooks=[_post_tool_use_hook],  # type: ignore[list-item]
            )
        ],
    }


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

            # Build ClaudeAgentOptions from config with tracing hooks
            # The hooks fire INSIDE the agentic loop for true internal visibility
            self._options = ClaudeAgentOptions(
                mcp_servers=self.config.mcp_servers,
                allowed_tools=self.config.allowed_tools,
                system_prompt=self.config.system_prompt,
                permission_mode="bypassPermissions",
                setting_sources=[],
                hooks=_create_tracing_hooks(),  # type: ignore[arg-type]  # SDK hooks for internal tracing
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

            # Wrap entire LLM call in inference span for proper timing
            import time

            with tracer.llm_inference(
                model="claude-agent-sdk",
                prompt_length=len(prompt),
            ) as inference_span:
                inference_start = time.perf_counter()
                ttft_ms: float | None = None

                await client.query(prompt)

                response = ""
                message_count = 0
                tool_count = 0
                # Token usage tracking (from ResultMessage)
                input_tokens: int | None = None
                output_tokens: int | None = None
                total_cost_usd: float | None = None

                async for message in client.receive_response():
                    # Record time-to-first-token on first message
                    if ttft_ms is None:
                        ttft_ms = (time.perf_counter() - inference_start) * 1000

                    message_count += 1
                    stop_reason = getattr(message, "stop_reason", None)

                    # Capture token usage from ResultMessage (final message)
                    # SDK may return usage in different formats; capture what's available
                    usage = getattr(message, "usage", None)
                    if usage and isinstance(usage, dict):
                        # Try standard fields first, fall back to cache fields
                        input_tokens = usage.get(
                            "input_tokens", usage.get("cache_read_input_tokens")
                        )
                        output_tokens = usage.get("output_tokens")
                    cost = getattr(message, "total_cost_usd", None)
                    if cost is not None:
                        total_cost_usd = cost

                    content = getattr(message, "content", None)
                    if content is not None:
                        # Build content summary for framework-level tracing
                        # (detailed tool tracing is handled by SDK hooks inside the loop)
                        content_parts: list[str] = []
                        has_tool_use = False
                        has_tool_result = False

                        for block in content:
                            block_type = getattr(block, "type", None)
                            text = getattr(block, "text", None)
                            tool_name = getattr(block, "name", None)

                            if text is not None:
                                response += text
                                content_parts.append(text)

                            if tool_name is not None:
                                # Track tool usage at framework level
                                # (internal tool execution is traced by PreToolUse/PostToolUse hooks)
                                tool_count += 1
                                tools_used_names.append(tool_name)
                                content_parts.append(f"[tool:{tool_name}]")
                                has_tool_use = True

                            if block_type == "tool_result":
                                tool_content = getattr(block, "content", None)
                                result_preview = (
                                    str(tool_content)[:50] if tool_content else ""
                                )
                                content_parts.append(f"[result:{result_preview}...]")
                                has_tool_result = True

                        # Infer role from content structure
                        # SDK receive_response() returns assistant messages
                        if has_tool_result:
                            role = "tool_result"
                        elif has_tool_use:
                            role = "assistant_tool_use"
                        else:
                            role = "assistant"

                        # Framework-level: trace each LLM message in response stream
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
                                    "tool_count": tool_count,
                                },
                            )

                # Record LLM response metrics on inference span
                tracer.record_llm_response(
                    inference_span,
                    response_length=len(response),
                    message_count=message_count,
                    tool_count=tool_count,
                    time_to_first_token_ms=ttft_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_cost_usd=total_cost_usd,
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

                # Build content summary for framework-level tracing
                # (internal tool execution is traced by SDK hooks)
                content = getattr(message, "content", None)
                content_str = ""
                has_tool_use = False
                has_tool_result = False

                if content:
                    for block in content:
                        text = getattr(block, "text", None)
                        tool_name = getattr(block, "name", None)
                        block_type = getattr(block, "type", None)
                        if text:
                            content_str += text
                        if tool_name:
                            content_str += f"[tool:{tool_name}]"
                            has_tool_use = True
                        if block_type == "tool_result":
                            has_tool_result = True

                # Infer role from content structure
                if has_tool_result:
                    role = "tool_result"
                elif has_tool_use:
                    role = "assistant_tool_use"
                else:
                    role = "assistant"

                # Framework-level: trace the streamed LLM message
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
