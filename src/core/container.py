"""Dependency injection container for the agentic deployment engine.

Provides centralized management of dependencies with lazy instantiation
and proper lifecycle management.

Usage:
    from src.container import container

    # Get settings
    settings = container.agent_settings()

    # Get a backend
    backend = container.claude_backend(config=my_config)

    # For testing, override dependencies
    container.agent_settings.override(mock_settings)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..config import AgentSettings, DeploymentSettings, deploy_settings, settings

if TYPE_CHECKING:
    from ..agents.registry import AgentRegistry
    from ..backends import AgentBackend, BackendConfig

logger = logging.getLogger(__name__)


class Container:
    """Simple dependency injection container.

    Provides factory methods and singletons for key components.
    Supports overriding for testing.

    This is a lightweight DI implementation that doesn't require
    the dependency-injector package. If more advanced DI features
    are needed, consider migrating to dependency-injector.
    """

    def __init__(self) -> None:
        """Initialize the container."""
        self._overrides: dict[str, Any] = {}
        self._singletons: dict[str, Any] = {}

    def override(self, name: str, value: Any) -> None:
        """Override a dependency for testing.

        Args:
            name: Name of the dependency to override.
            value: Value or factory to use instead.
        """
        self._overrides[name] = value

    def reset_overrides(self) -> None:
        """Reset all overrides."""
        self._overrides.clear()

    def reset_singletons(self) -> None:
        """Reset all cached singletons."""
        self._singletons.clear()

    def agent_settings(self) -> AgentSettings:
        """Get agent settings.

        Returns:
            AgentSettings instance.
        """
        if "agent_settings" in self._overrides:
            return self._overrides["agent_settings"]
        return settings

    def deploy_settings(self) -> DeploymentSettings:
        """Get deployment settings.

        Returns:
            DeploymentSettings instance.
        """
        if "deploy_settings" in self._overrides:
            return self._overrides["deploy_settings"]
        return deploy_settings

    def agent_registry(self) -> AgentRegistry:
        """Get agent registry singleton.

        Returns:
            AgentRegistry instance.
        """
        if "agent_registry" in self._overrides:
            return self._overrides["agent_registry"]

        if "agent_registry" not in self._singletons:
            from ..agents.registry import AgentRegistry

            self._singletons["agent_registry"] = AgentRegistry()

        return self._singletons["agent_registry"]

    def http_client(self, timeout: float | None = None) -> Any:
        """Create an HTTP client.

        Args:
            timeout: Optional timeout override.

        Returns:
            httpx.AsyncClient instance.
        """
        if "http_client" in self._overrides:
            return self._overrides["http_client"]

        import httpx

        actual_timeout = timeout or self.agent_settings().http_timeout
        return httpx.AsyncClient(timeout=actual_timeout)

    def claude_backend(self, config: BackendConfig) -> AgentBackend:
        """Create a Claude SDK backend.

        Args:
            config: Backend configuration.

        Returns:
            ClaudeSDKBackend instance.
        """
        if "claude_backend" in self._overrides:
            factory = self._overrides["claude_backend"]
            return factory(config)

        from ..backends import ClaudeSDKBackend

        return ClaudeSDKBackend(config)

    def backend_factory(self, backend_type: str, config: BackendConfig) -> AgentBackend:
        """Create a backend by type name.

        Args:
            backend_type: Backend type ('claude', 'crewai', 'gemini', 'opencode').
            config: Backend configuration.

        Returns:
            Backend instance.

        Raises:
            ValueError: If backend type is unknown.
        """
        if "backend_factory" in self._overrides:
            factory = self._overrides["backend_factory"]
            return factory(backend_type, config)

        if backend_type == "claude":
            from ..backends import ClaudeSDKBackend

            return ClaudeSDKBackend(config)
        elif backend_type == "crewai":
            from ..backends.crewai import CrewAIBackend

            agent_settings = self.agent_settings()
            return CrewAIBackend(
                config,
                ollama_model=agent_settings.ollama_model,
                ollama_base_url=agent_settings.ollama_base_url,
            )
        elif backend_type == "gemini":
            from ..backends.gemini_cli import GeminiCLIBackend

            return GeminiCLIBackend(config)
        else:
            raise ValueError(f"Unknown backend type: {backend_type}")


# Global container instance
container = Container()
