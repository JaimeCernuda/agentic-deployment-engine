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

from ..backends.base import AgentBackend, BackendConfig
from ..config import settings
from ..core.container import container
from ..observability import (
    extract_context,
    get_semantic_tracer,
    instrument_fastapi,
    setup_telemetry,
    shutdown_telemetry,
    traced_operation,
)
from ..security import PermissionPreset, filter_allowed_tools, verify_api_key
from .registry import AgentRegistry
from .sessions import SessionManager


class QueryRequest(BaseModel):
    """Request model for agent queries.

    Supports multi-turn conversations via session_id.
    """

    query: str
    session_id: str | None = None  # Optional session for multi-turn context
    context: dict[str, Any] = {}  # Additional context metadata


class QueryResponse(BaseModel):
    """Response model for agent queries."""

    response: str
    session_id: str | None = None  # Session ID for continuing conversation


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
        mcp_servers: dict[str, Any] | None = None,
        system_prompt: str | None = None,
        connected_agents: list[str] | None = None,
        permission_preset: PermissionPreset = PermissionPreset.FULL_ACCESS,
        custom_permission_rules: list[str] | None = None,
        host: str = "localhost",
        backend: AgentBackend | None = None,
        registry_url: str | None = None,
    ):
        self.name = name
        self.description = description
        self.port = port
        self.host = host
        self.connected_agents = connected_agents or []
        self.agent_registry = AgentRegistry() if connected_agents else None
        self.permission_preset = permission_preset
        self.custom_permission_rules = custom_permission_rules

        # Dynamic registry for self-registration
        self.registry_url = registry_url or os.environ.get("AGENT_REGISTRY_URL")
        self._agent_id = self.name.lower().replace(" ", "_")

        # Session manager for multi-turn conversations
        self.session_manager = SessionManager(
            max_sessions=settings.max_sessions,
            session_ttl_seconds=settings.session_ttl_seconds,
        )

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

        # Detailed formatter for file logs
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
        )
        fh.setFormatter(file_formatter)
        self.logger.addHandler(fh)

        # Console handler - skip in test environments (pytest captures stdout)
        # which causes "I/O operation on closed file" errors during cleanup
        if "pytest" not in sys.modules:
            ch = logging.StreamHandler(sys.stdout)
            ch.setLevel(logging.INFO)
            console_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            ch.setFormatter(console_formatter)
            self.logger.addHandler(ch)

        self.logger.info(f"Initializing {name} on port {port}")
        self.logger.info(f"Log file: {log_file}")

        # Configure claude-code-sdk with MCP servers
        # Start with any externally provided MCP servers (stdio, sse, etc.)
        all_mcp_servers = dict(mcp_servers) if mcp_servers else {}

        # Add in-process SDK MCP server if provided
        if sdk_mcp_server:
            server_key = self.name.lower().replace(" ", "_")
            all_mcp_servers[server_key] = sdk_mcp_server
            self.logger.debug(f"SDK MCP server configured with key: {server_key}")
            self.logger.debug(
                f"SDK server type: {sdk_mcp_server.get('type') if isinstance(sdk_mcp_server, dict) else type(sdk_mcp_server)}"
            )

            # Log SDK server tools if available
            if isinstance(sdk_mcp_server, dict) and "instance" in sdk_mcp_server:
                server_instance = sdk_mcp_server["instance"]
                if hasattr(server_instance, "list_tools"):
                    self.logger.debug("SDK MCP server has list_tools method")

        # Log external MCP servers
        for key, config in all_mcp_servers.items():
            if isinstance(config, dict) and config.get("type") != "sdk":
                self.logger.debug(
                    f"External MCP server configured: {key} (type: {config.get('type')})"
                )

        allowed_tools = self._get_allowed_tools()
        # Permission presets control access to external tools (Read, Write, Bash, etc.)
        # but should NOT filter out the agent's own MCP tools - those are core functionality.
        # Agent's MCP tools follow the pattern: mcp__<server_name>__<tool_name>
        if permission_preset != PermissionPreset.FULL_ACCESS:
            # Separate agent's own MCP tools from external tools
            agent_mcp_tools = [t for t in allowed_tools if t.startswith("mcp__")]
            external_tools = [t for t in allowed_tools if not t.startswith("mcp__")]

            # Only filter external tools based on permission preset
            filtered_external = filter_allowed_tools(
                external_tools, permission_preset, custom_permission_rules
            )

            # Combine: agent's MCP tools (always allowed) + filtered external tools
            allowed_tools = agent_mcp_tools + filtered_external
            self.logger.debug(
                f"Permission preset {permission_preset.value}: "
                f"kept {len(agent_mcp_tools)} MCP tools, "
                f"filtered external tools to {len(filtered_external)}"
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
            mcp_servers=all_mcp_servers,
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

        # Backend abstraction (optional - if not provided, use DI container)
        if backend:
            self._backend = backend
        else:
            backend_config = BackendConfig(
                name=name,
                system_prompt=self._active_system_prompt,
                allowed_tools=allowed_tools,
                mcp_servers=all_mcp_servers,  # Use all_mcp_servers which includes SDK MCP server
            )
            self._backend = container.backend_factory(
                settings.backend_type, backend_config
            )
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

            Supports multi-turn conversations via session_id in request body.
            """
            # Extract trace context from incoming headers for distributed tracing
            # This links the incoming request to the parent trace
            _ = extract_context(dict(http_request.headers))

            # Get or create session for multi-turn context
            session = self.session_manager.get_or_create_session(body.session_id)

            # Semantic tracing - agent level query handling
            semantic_tracer = get_semantic_tracer()

            # Continue parent trace if propagated via A2A headers
            parent_trace_id = http_request.headers.get("x-semantic-trace-id")
            if parent_trace_id:
                semantic_tracer.continue_trace(parent_trace_id)
            with semantic_tracer.query_handling(
                agent_name=self.name,
                query=body.query,
                session_id=session.session_id,
                history_length=len(session.messages),
            ) as sem_span:
                # Capture the user query as an LLM message span
                with semantic_tracer.llm_message(
                    role="user",
                    content=body.query,
                    model="user-input",
                ):
                    pass  # Span captures the user's incoming query

                # Create child span for this query with session tracking
                with traced_operation(
                    "handle_query",
                    {
                        "agent.name": self.name,
                        "query.length": str(len(body.query)),
                        "session.id": session.session_id,
                        "session.message_count": str(len(session.messages)),
                    },
                ):
                    # Add user message to session history
                    session.add_message("user", body.query)

                    # Get conversation history for context
                    history = session.get_history_for_prompt(
                        max_messages=settings.max_history_messages
                    )

                    # Handle query with session context
                    response = await self._handle_query(body.query, history)

                    # Add assistant response to session history
                    session.add_message("assistant", response)

                    # Record response details on semantic span
                    sem_span.attributes["response.length"] = len(response)
                    sem_span.attributes["response.preview"] = response[:200]

                    return QueryResponse(
                        response=response,
                        session_id=session.session_id,
                    )

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

    async def _handle_query(self, query: str, history: str = "") -> str:
        """Handle query using the configured backend.

        Dispatches to the appropriate backend (Claude SDK, CrewAI, Gemini)
        based on AGENT_BACKEND_TYPE configuration.

        Args:
            query: The user's query string.
            history: Optional conversation history for multi-turn context.

        Returns:
            The assistant's response string.
        """
        self.logger.info(f"Handling query: {query}")
        self.logger.debug(f"Query length: {len(query)} chars")
        if history:
            self.logger.debug(f"Using conversation history ({len(history)} chars)")

        # Build the full query with conversation history context
        if history:
            full_query = f"{history}\n\n[Current Query]: {query}"
        else:
            full_query = query

        try:
            # Use the configured backend for query execution
            self.logger.debug(f"Sending query via {self._backend.name} backend...")
            result = await self._backend.query(full_query)

            self.logger.info(
                f"Query completed. Messages: {result.messages_count}, "
                f"Tools used: {result.tools_used}, Response: {len(result.response)} chars"
            )
            return result.response

        except Exception as e:
            self.logger.error(f"Error handling query: {e}", exc_info=True)
            return f"Error: {str(e)}"

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

            # Update backend config with new system prompt
            # The backend's initialize() is called lazily on first query,
            # so updating the config here ensures it uses discovered agent URLs
            if hasattr(self._backend, "config") and hasattr(
                self._backend.config, "system_prompt"
            ):
                self._backend.config.system_prompt = self._active_system_prompt
                self.logger.debug(
                    "Backend config updated with discovered agents system prompt"
                )

        self.logger.debug(
            f"Updated system prompt ({len(self._active_system_prompt)} chars)"
        )

    async def _register_with_registry(self) -> bool:
        """Register this agent with the dynamic registry service.

        Returns:
            True if registration succeeded, False otherwise.
        """
        if not self.registry_url:
            return False

        import httpx

        agent_url = f"http://{self.host}:{self.port}"
        registration_data = {
            "id": self._agent_id,
            "name": self.name,
            "url": agent_url,
            "description": self.description,
            "skills": self._get_skills(),
            "tags": [s.get("id", "") for s in self._get_skills()],
            "metadata": {
                "port": self.port,
                "host": self.host,
                "permission_preset": self.permission_preset.value,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.registry_url}/agents/register",
                    json=registration_data,
                )
                if response.status_code == 200:
                    self.logger.info(f"Registered with registry at {self.registry_url}")
                    return True
                else:
                    self.logger.warning(
                        f"Registry registration failed: {response.status_code} - {response.text}"
                    )
                    return False
        except Exception as e:
            self.logger.warning(f"Could not register with registry: {e}")
            return False

    async def _deregister_from_registry(self) -> bool:
        """Deregister this agent from the dynamic registry service.

        Returns:
            True if deregistration succeeded, False otherwise.
        """
        if not self.registry_url:
            return False

        import httpx

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.delete(
                    f"{self.registry_url}/agents/{self._agent_id}"
                )
                if response.status_code == 200:
                    self.logger.info("Deregistered from registry")
                    return True
                else:
                    self.logger.debug(
                        f"Registry deregistration: {response.status_code}"
                    )
                    return False
        except Exception as e:
            self.logger.debug(f"Could not deregister from registry: {e}")
            return False

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

        # Semantic tracing for agent lifecycle
        semantic_tracer = get_semantic_tracer()
        with semantic_tracer.agent_lifecycle(
            agent_id=self.name.lower().replace(" ", "_"),
            agent_name=self.name,
            action="start",
            port=self.port,
            host=self.host,
        ) as lifecycle_span:
            semantic_tracer.add_event(
                lifecycle_span,
                "agent_initializing",
                {
                    "backend": self._backend.name
                    if hasattr(self, "_backend")
                    else "unknown",
                    "connected_agents": len(self.connected_agents),
                },
            )

            # Discover agents before starting server if configured
            if self.connected_agents:
                self.logger.info("Discovering agents before startup...")
                asyncio.run(self._discover_agents())
                semantic_tracer.add_event(
                    lifecycle_span,
                    "agents_discovered",
                    {"count": len(self.connected_agents)},
                )

            # Register with dynamic registry if configured
            if self.registry_url:
                registered = asyncio.run(self._register_with_registry())
                semantic_tracer.add_event(
                    lifecycle_span,
                    "registry_registration",
                    {"success": registered, "registry_url": self.registry_url},
                )

            semantic_tracer.add_event(
                lifecycle_span,
                "server_starting",
                {"host": "0.0.0.0", "port": self.port},
            )

        # Configure uvicorn logging to use our logger (stdout, not stderr)
        log_config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - uvicorn - %(levelname)s - %(message)s",
                },
            },
            "handlers": {
                "default": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                },
            },
            "loggers": {
                "uvicorn": {
                    "handlers": ["default"],
                    "level": "INFO",
                    "propagate": False,
                },
                "uvicorn.error": {
                    "handlers": ["default"],
                    "level": "INFO",
                    "propagate": False,
                },
                "uvicorn.access": {
                    "handlers": ["default"],
                    "level": "WARNING",
                    "propagate": False,
                },
            },
        }
        uvicorn.run(self.app, host="0.0.0.0", port=self.port, log_config=log_config)

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

        # Deregister from dynamic registry if configured
        if self.registry_url:
            await self._deregister_from_registry()

        # Semantic tracing for agent shutdown
        semantic_tracer = get_semantic_tracer()
        with semantic_tracer.agent_lifecycle(
            agent_id=self.name.lower().replace(" ", "_"),
            agent_name=self.name,
            action="stop",
            port=self.port,
            host=self.host,
        ) as lifecycle_span:
            # Cleanup backend
            if hasattr(self, "_backend") and self._backend:
                try:
                    await self._backend.cleanup()
                    self.logger.debug("Backend cleaned up")
                    semantic_tracer.add_event(lifecycle_span, "backend_cleaned_up", {})
                except Exception as e:
                    self.logger.error(f"Error cleaning up backend: {e}")

            # Cleanup all clients in the pool (legacy)
            # Note: Claude SDK clients may throw cancel scope errors when disconnected
            # from a different task than they were created in. This is expected during
            # shutdown and we simply clear the pool - clients will be garbage collected.
            clients_closed = 0
            while not self._client_pool.empty():
                try:
                    client = self._client_pool.get_nowait()
                    await client.disconnect()
                    clients_closed += 1
                except asyncio.QueueEmpty:
                    break
                except RuntimeError as e:
                    # Cancel scope errors are expected when cleanup runs in different task
                    if "cancel scope" in str(e).lower():
                        clients_closed += 1  # Client will be GC'd
                        self.logger.debug(f"Client cleanup deferred to GC: {e}")
                    else:
                        self.logger.error(f"Error disconnecting pool client: {e}")
                except Exception as e:
                    self.logger.warning(f"Error disconnecting pool client: {e}")

            if clients_closed > 0:
                self.logger.debug(f"Closed {clients_closed} pooled clients")
                semantic_tracer.add_event(
                    lifecycle_span,
                    "pool_cleaned_up",
                    {"clients_closed": clients_closed},
                )

            # Cleanup legacy client if exists
            if self.claude_client:
                try:
                    await self.claude_client.disconnect()
                    self.logger.debug("Legacy Claude SDK client disconnected")
                except RuntimeError as e:
                    # Cancel scope errors are expected when cleanup runs in different task
                    if "cancel scope" in str(e).lower():
                        self.logger.debug(f"Client cleanup deferred to GC: {e}")
                    else:
                        self.logger.error(f"Error disconnecting Claude client: {e}")
                except Exception as e:
                    self.logger.warning(f"Error disconnecting Claude client: {e}")
                self.claude_client = None

            # Cleanup agent registry
            if self.agent_registry:
                try:
                    await self.agent_registry.cleanup()
                    self.logger.debug("Agent registry cleaned up")
                    semantic_tracer.add_event(lifecycle_span, "registry_cleaned_up", {})
                except Exception as e:
                    self.logger.error(f"Error cleaning up agent registry: {e}")

            # Shutdown telemetry
            shutdown_telemetry()

            self.logger.info("Agent cleanup complete")
