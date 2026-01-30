"""Abstract base class for agent backends.

Defines the interface that all agentic framework backends must implement.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BackendConfig:
    """Configuration for an agent backend.

    Attributes:
        name: Name of the agent using this backend.
        system_prompt: System prompt to configure the agent's behavior.
        allowed_tools: List of MCP tool names the agent can use.
        mcp_servers: MCP server configurations.
        extra_options: Backend-specific additional options.
    """

    name: str
    system_prompt: str | None = None
    allowed_tools: list[str] = field(default_factory=list)
    mcp_servers: dict[str, Any] = field(default_factory=dict)
    extra_options: dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryResult:
    """Result from a backend query.

    Attributes:
        response: The text response from the backend.
        messages_count: Number of messages in the conversation.
        tools_used: Number of tool calls made.
        metadata: Additional metadata from the query.
    """

    response: str
    messages_count: int = 0
    tools_used: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentBackend(ABC):
    """Abstract base for agentic framework backends.

    Implementations provide integration with specific agentic frameworks:
    - ClaudeSDKBackend: Claude Agent SDK (current)
    - CrewAIBackend: CrewAI framework (future)
    - GeminiCLIBackend: Gemini CLI (future)
    - OpenCodeBackend: Open Code (future)

    Lifecycle:
        1. Create backend with config
        2. Call initialize() before use
        3. Call query() or query_stream() for inference
        4. Call cleanup() when done
    """

    def __init__(self, config: BackendConfig) -> None:
        """Initialize the backend with configuration.

        Args:
            config: Backend configuration.
        """
        self.config = config
        self._initialized = False

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend name for logging/identification.

        Returns:
            Human-readable backend name.
        """
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the backend (create pools, connect, etc.).

        Called lazily on first use. Safe to call multiple times.
        """
        pass

    @abstractmethod
    async def query(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> QueryResult:
        """Execute a query against the backend.

        Args:
            prompt: The query to execute.
            context: Optional context (trace IDs, session info, etc.).

        Returns:
            QueryResult with response and metadata.

        Raises:
            AgentBackendError: If the backend encounters an error.
        """
        pass

    @abstractmethod
    async def query_stream(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> AsyncIterator[Any]:
        """Execute a streaming query.

        Yields messages as they arrive from the backend.

        Args:
            prompt: The query to execute.
            context: Optional context (trace IDs, session info, etc.).

        Yields:
            Message objects from the backend (format varies by backend).

        Raises:
            AgentBackendError: If the backend encounters an error.
        """
        # Make this a generator (required for abstract async generators)
        if False:
            yield

    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup backend resources.

        Call this when done with the backend to release connections,
        close pools, etc. Safe to call multiple times.
        """
        pass

    async def update_config(self, **kwargs: Any) -> None:
        """Update backend configuration.

        Default implementation recreates the backend. Override for
        more efficient updates if the backend supports hot-reloading.

        Args:
            **kwargs: Configuration fields to update.
        """
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

        # Recreate backend with new config
        await self.cleanup()
        await self.initialize()

    @property
    def is_initialized(self) -> bool:
        """Check if backend is initialized.

        Returns:
            True if initialize() has been called successfully.
        """
        return self._initialized
