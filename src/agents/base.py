"""
Base A2A Agent using claude-code-sdk properly.

Provides A2A capabilities with clean inheritance and dynamic agent connections.
"""

import asyncio
import atexit
import logging
import os
import signal
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import uvicorn
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from fastapi import Depends, FastAPI, Request
from pydantic import BaseModel

from ..backends import AgentBackend, BackendConfig
from ..config import settings
from ..observability import (
    extract_context,
    instrument_fastapi,
    setup_telemetry,
    shutdown_telemetry,
    traced_operation,
)
from ..security import PermissionPreset, filter_allowed_tools, verify_api_key
from .registry import AgentRegistry


def create_backend(config: BackendConfig) -> AgentBackend:
    """Create an agent backend based on configuration.

    Factory function that returns the appropriate backend based on
    the AGENT_BACKEND_TYPE environment variable.

    Args:
        config: Backend configuration

    Returns:
        An initialized AgentBackend instance

    Supported backends:
        - claude: Claude Agent SDK (default)
        - gemini: Gemini CLI
        - crewai: CrewAI with Ollama
    """
    backend_type = settings.backend_type.lower()

    if backend_type == "gemini":
        from ..backends.gemini_cli import GeminiCLIBackend

        return GeminiCLIBackend(config)

    elif backend_type == "crewai":
        from ..backends.crewai import CrewAIBackend

        return CrewAIBackend(
            config,
            ollama_model=settings.ollama_model,
            ollama_base_url=settings.ollama_base_url,
        )

    else:
        # Default: Claude SDK
        from ..backends.claude_sdk import ClaudeSDKBackend

        return ClaudeSDKBackend(config)


class QueryRequest(BaseModel):
    query: str
    context: dict[str, Any] = {}


class QueryResponse(BaseModel):
    response: str


class BaseA2AAgent(ABC):
    """
    Base A2A Agent providing clean A2A inheritance.

    Uses claude-code-sdk properly with MCP server configuration.
    """

    def __init__(
        self,
        name: str,
        description: str,
        port: int,
        sdk_mcp_server=None,
        system_prompt: str | None = None,
        connected_agents: list[str] | None = None,
        permission_preset: PermissionPreset = PermissionPreset.FULL_ACCESS,
        custom_permission_rules: list[str] | None = None,
        host: str = "localhost",
        backend: AgentBackend | None = None,
    ):
        self.name = name
        self.description = description
        self.port = port
        self.host = host
        self.connected_agents = connected_agents or []
        self.agent_registry = AgentRegistry() if connected_agents else None
        self.permission_preset = permission_preset
        self.custom_permission_rules = custom_permission_rules

        # System prompt - immutable after initialization for thread safety
        # Use _base_system_prompt for the original, _active_system_prompt for current
        self._base_system_prompt = system_prompt or self._get_default_system_prompt()
        self._active_system_prompt: str = self._base_system_prompt
        self._options_lock = asyncio.Lock()  # Protects claude_options updates

        # Setup logging - use job-based directory if JOB_ID is set, otherwise cwd/logs
        job_id = os.environ.get("JOB_ID")
        agent_id = os.environ.get("AGENT_ID", name.lower().replace(" ", "_"))
        if job_id:
            # Job deployment: logs go to logs/jobs/<job_id>/
            log_dir = Path.cwd() / "logs" / "jobs" / job_id
        else:
            # Standalone run: logs go to logs/agents/
            log_dir = Path.cwd() / "logs" / "agents"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{agent_id}.log"

        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # Clear existing handlers to avoid duplicates
        self.logger.handlers.clear()

        # File handler with detailed formatting (UTF-8 for emoji support)
        fh = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        fh.setLevel(logging.DEBUG)

        # Console handler (use stdout, not stderr)
        # Wrap stdout with UTF-8 encoding for Windows compatibility
        if sys.platform == "win32":
            # Windows console may not support UTF-8 by default
            import io

            utf8_stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace"
            )
            ch = logging.StreamHandler(utf8_stdout)
        else:
            ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)

        # Detailed formatter for file logs
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
        )
        # Simple formatter for console
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        fh.setFormatter(file_formatter)
        ch.setFormatter(console_formatter)

        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

        self.logger.info(f"Initializing {name} on port {port}")
        self.logger.info(f"Log file: {log_file}")

        # Configure claude-code-sdk with SDK MCP server
        mcp_servers = {}
        if sdk_mcp_server:
            server_key = self.name.lower().replace(" ", "_")
            mcp_servers[server_key] = sdk_mcp_server
            self.logger.debug(f"SDK MCP server configured with key: {server_key}")
            self.logger.debug(
                f"SDK server type: {sdk_mcp_server.get('type') if isinstance(sdk_mcp_server, dict) else type(sdk_mcp_server)}"
            )

            # Log SDK server tools if available
            if isinstance(sdk_mcp_server, dict) and "instance" in sdk_mcp_server:
                server_instance = sdk_mcp_server["instance"]
                if hasattr(server_instance, "list_tools"):
                    self.logger.debug("SDK MCP server has list_tools method")

        allowed_tools = self._get_allowed_tools()
        # Filter tools based on permission preset
        if permission_preset != PermissionPreset.FULL_ACCESS:
            allowed_tools = filter_allowed_tools(
                allowed_tools, permission_preset, custom_permission_rules
            )
        self.logger.debug(f"Allowed tools: {allowed_tools}")
        self.logger.debug(f"Permission preset: {permission_preset.value}")
        self.logger.debug(
            f"System prompt ({len(self._active_system_prompt)} chars):\n{self._active_system_prompt}"
        )

        # Use bypassPermissions mode for autonomous agent operation
        # This allows agents to use their tools without interactive user approval
        # setting_sources=[] prevents external settings from overriding permission_mode
        self.claude_options = ClaudeAgentOptions(
            mcp_servers=mcp_servers,
            allowed_tools=allowed_tools,
            system_prompt=self._active_system_prompt,
            permission_mode="bypassPermissions",
            setting_sources=[],
        )

        # Client pool for connection reuse (P1-1 fix)
        # Creating a fresh client per query is 10-100x slower
        self._pool_size = settings.client_pool_size
        self._client_pool: asyncio.Queue[ClaudeSDKClient] = asyncio.Queue(
            maxsize=self._pool_size
        )
        self._pool_initialized = False
        self._pool_lock = asyncio.Lock()
        self.claude_client: ClaudeSDKClient | None = None  # Backwards compat

        # Backend abstraction (optional - if not provided, use factory)
        if backend:
            self._backend = backend
        else:
            backend_config = BackendConfig(
                name=name,
                system_prompt=self._active_system_prompt,
                allowed_tools=allowed_tools,
                mcp_servers=mcp_servers,
            )
            self._backend = create_backend(backend_config)
            self.logger.info(f"Using backend: {self._backend.name}")

        # Create A2A endpoints
        self.app = FastAPI(title=name, description=description)
        self._setup_routes()

        # Instrument FastAPI for tracing
        instrument_fastapi(self.app)

        # Track cleanup state
        self._cleanup_done = False

        # Register cleanup handlers for graceful shutdown
        atexit.register(self._sync_cleanup)
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _setup_routes(self):
        """Setup A2A discovery and query endpoints."""

        @self.app.get("/.well-known/agent-configuration")
        async def agent_card():
            return {
                "name": self.name,
                "description": self.description,
                "url": f"http://{self.host}:{self.port}",
                "version": "1.0.0",
                "capabilities": {"streaming": True, "push_notifications": False},
                "default_input_modes": ["text"],
                "default_output_modes": ["text"],
                "skills": self._get_skills(),
            }

        @self.app.get("/health")
        async def health():
            return {"status": "healthy", "agent": self.name}

        @self.app.post("/query", response_model=QueryResponse)
        async def query(
            http_request: Request,
            body: QueryRequest,
            api_key: str | None = Depends(verify_api_key),
        ):
            """Query endpoint with optional API key authentication.

            Authentication is controlled by AGENT_AUTH_REQUIRED env var.
            If set to 'true', requests must include X-API-Key header or
            api_key query parameter matching AGENT_API_KEY.
            """
            # Extract trace context from incoming headers for distributed tracing
            # This links the incoming request to the parent trace
            _ = extract_context(dict(http_request.headers))

            # Create child span for this query
            with traced_operation(
                "handle_query",
                {"agent.name": self.name, "query.length": str(len(body.query))},
            ):
                response = await self._handle_query(body.query)
                return QueryResponse(response=response)

    async def _initialize_pool(self) -> None:
        """Initialize the client pool with pre-connected clients.

        This is called lazily on first query to avoid blocking startup.
        """
        async with self._pool_lock:
            if self._pool_initialized:
                return

            self.logger.info(
                f"Initializing client pool with {self._pool_size} clients..."
            )

            for i in range(self._pool_size):
                try:
                    client = ClaudeSDKClient(self.claude_options)
                    await client.connect()
                    await self._client_pool.put(client)
                    self.logger.debug(
                        f"Pool client {i + 1}/{self._pool_size} connected"
                    )
                except Exception as e:
                    self.logger.error(f"Failed to create pool client {i + 1}: {e}")
                    # Continue with fewer clients rather than failing entirely

            self._pool_initialized = True
            self.logger.info(
                f"Client pool initialized with {self._client_pool.qsize()} clients"
            )

    async def _get_pooled_client(self) -> ClaudeSDKClient:
        """Get a client from the pool, initializing if needed.

        Returns:
            A connected ClaudeSDKClient from the pool.
        """
        await self._initialize_pool()

        # Get client from pool (blocks if pool is empty)
        client = await self._client_pool.get()
        self.logger.debug(
            f"Got client from pool ({self._client_pool.qsize()} remaining)"
        )
        return client

    async def _return_client(self, client: ClaudeSDKClient) -> None:
        """Return a client to the pool.

        Args:
            client: The client to return to the pool.
        """
        await self._client_pool.put(client)
        self.logger.debug(
            f"Returned client to pool ({self._client_pool.qsize()} available)"
        )

    async def _get_claude_client(self) -> ClaudeSDKClient:
        """Get claude-code-sdk client (legacy method, uses pool now)."""
        return await self._get_pooled_client()

    async def _handle_query(self, query: str) -> str:
        """Handle query using pooled claude-code-sdk client.

        Uses connection pooling for 10-100x better performance than
        creating a fresh client per query.
        """
        self.logger.info(f"Handling query: {query}")
        self.logger.debug(f"Query length: {len(query)} chars")

        client = None
        try:
            # Get a pre-connected client from the pool
            client = await self._get_pooled_client()
            self.logger.debug("Using pooled client for query")

            self.logger.debug("Sending query to Claude...")
            await client.query(query)

            response = ""
            message_count = 0
            tool_use_count = 0

            self.logger.debug("Receiving response...")
            async for message in client.receive_response():
                message_count += 1
                message_type = type(message).__name__
                self.logger.debug(f"Message {message_count}: {message_type}")

                # Log message details based on type (using getattr for type safety)
                role = getattr(message, "role", None)
                if role is not None:
                    self.logger.debug(f"  Role: {role}")

                content = getattr(message, "content", None)
                if content is not None:
                    for i, block in enumerate(content):
                        block_type = type(block).__name__
                        self.logger.debug(f"  Content block {i}: {block_type}")

                        text = getattr(block, "text", None)
                        if text is not None:
                            # Use configurable truncation (0 = unlimited)
                            max_len = settings.log_max_content_length
                            if max_len > 0 and len(text) > max_len:
                                text_preview = text[:max_len] + "..."
                            else:
                                text_preview = text
                            self.logger.debug(f"    Text: {text_preview}")
                            response += text

                        tool_name = getattr(block, "name", None)
                        if tool_name is not None:
                            tool_use_count += 1
                            self.logger.debug(f"    Tool: {tool_name}")
                            tool_input = getattr(block, "input", None)
                            if tool_input is not None:
                                self.logger.debug(f"    Input: {tool_input}")

                        # Log tool results (success or error)
                        tool_use_id = getattr(block, "tool_use_id", None)
                        if tool_use_id is not None:
                            self.logger.debug(f"    Tool Result for: {tool_use_id}")
                            result_content = getattr(block, "content", None)
                            if result_content is not None:
                                self.logger.debug(
                                    f"    Result content: {result_content}"
                                )
                            is_error = getattr(block, "is_error", None)
                            if is_error is not None:
                                self.logger.debug(f"    Is error: {is_error}")

                stop_reason = getattr(message, "stop_reason", None)
                if stop_reason is not None:
                    self.logger.debug(f"  Stop reason: {stop_reason}")

            self.logger.info(
                f"Query completed. Messages: {message_count}, "
                f"Tools used: {tool_use_count}, Response: {len(response)} chars"
            )
            return response or "No response generated"

        except Exception as e:
            self.logger.error(f"Error handling query: {e}", exc_info=True)
            return f"Error: {str(e)}"

        finally:
            # Always return client to pool
            if client:
                await self._return_client(client)

    @abstractmethod
    def _get_skills(self) -> list[dict[str, Any]]:
        """Define agent skills for A2A discovery."""
        pass

    @abstractmethod
    def _get_allowed_tools(self) -> list[str]:
        """Define allowed tools for claude-code-sdk."""
        pass

    @property
    def system_prompt(self) -> str:
        """Get the active system prompt (read-only for thread safety).

        Returns:
            The current active system prompt.
        """
        return self._active_system_prompt

    def _get_default_system_prompt(self) -> str:
        """Get default system prompt for this agent."""
        return f"""You are {self.name}, {self.description}.

You have access to specialized tools for your domain. Use them to provide accurate and helpful responses.
Always be concise and professional in your responses."""

    async def _discover_agents(self) -> None:
        """Discover connected agents and update system prompt.

        Thread-safe: Uses a lock when updating claude_options.
        """
        if not self.agent_registry or not self.connected_agents:
            return

        self.logger.info(
            f"Discovering {len(self.connected_agents)} connected agents..."
        )
        discovered = await self.agent_registry.discover_multiple(self.connected_agents)
        self.logger.info(f"Successfully discovered {len(discovered)} agents")

        # Generate updated system prompt with discovered agent info
        new_system_prompt = self.agent_registry.generate_system_prompt(
            self._base_system_prompt, self.connected_agents
        )

        # Thread-safe update of claude_options
        async with self._options_lock:
            self._active_system_prompt = new_system_prompt
            self.claude_options = ClaudeAgentOptions(
                mcp_servers=self.claude_options.mcp_servers,
                allowed_tools=self.claude_options.allowed_tools,
                system_prompt=self._active_system_prompt,
                permission_mode="bypassPermissions",
                setting_sources=[],
            )

        self.logger.debug(
            f"Updated system prompt ({len(self._active_system_prompt)} chars)"
        )

    def run(self):
        """Run the A2A agent."""
        # Setup telemetry if enabled
        if settings.otel_enabled:
            setup_telemetry(
                service_name=f"{settings.otel_service_name}.{self.name}",
                endpoint=settings.otel_endpoint,
                protocol=settings.otel_protocol,
                enabled=True,
            )
            self.logger.info("OpenTelemetry tracing enabled")

        # Discover agents before starting server if configured
        if self.connected_agents:
            self.logger.info("Discovering agents before startup...")
            asyncio.run(self._discover_agents())

        uvicorn.run(self.app, host="0.0.0.0", port=self.port)

    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals gracefully.

        Args:
            signum: Signal number received
            frame: Current stack frame
        """
        signal_name = signal.Signals(signum).name
        self.logger.info(f"Received {signal_name}, initiating graceful shutdown...")
        self._sync_cleanup()
        sys.exit(0)

    def _sync_cleanup(self) -> None:
        """Synchronous cleanup wrapper for atexit and signal handlers."""
        if self._cleanup_done:
            return

        try:
            # Create new event loop if needed (atexit may not have one)
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            loop.run_until_complete(self.cleanup())
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    async def cleanup(self) -> None:
        """Cleanup resources asynchronously.

        Closes SDK clients, agent registry connections, and logging handlers.
        Safe to call multiple times.
        """
        if self._cleanup_done:
            return

        self._cleanup_done = True
        self.logger.info("Cleaning up agent resources...")

        # Cleanup backend
        if hasattr(self, "_backend") and self._backend:
            try:
                await self._backend.cleanup()
                self.logger.debug("Backend cleaned up")
            except Exception as e:
                self.logger.error(f"Error cleaning up backend: {e}")

        # Cleanup all clients in the pool (legacy)
        clients_closed = 0
        while not self._client_pool.empty():
            try:
                client = self._client_pool.get_nowait()
                await client.disconnect()
                clients_closed += 1
            except asyncio.QueueEmpty:
                break
            except Exception as e:
                self.logger.error(f"Error disconnecting pool client: {e}")

        if clients_closed > 0:
            self.logger.debug(f"Closed {clients_closed} pooled clients")

        # Cleanup legacy client if exists
        if self.claude_client:
            try:
                await self.claude_client.disconnect()
                self.logger.debug("Legacy Claude SDK client disconnected")
            except Exception as e:
                self.logger.error(f"Error disconnecting Claude client: {e}")
            self.claude_client = None

        # Cleanup agent registry
        if self.agent_registry:
            try:
                await self.agent_registry.cleanup()
                self.logger.debug("Agent registry cleaned up")
            except Exception as e:
                self.logger.error(f"Error cleaning up agent registry: {e}")

        # Shutdown telemetry
        shutdown_telemetry()

        self.logger.info("Agent cleanup complete")
