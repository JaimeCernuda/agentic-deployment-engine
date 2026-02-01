"""Dynamic Agent Registry module.

Provides runtime agent discovery and registration for dynamic workflows.

Usage:
    # Start registry service
    uv run registry --port 8500

    # Or programmatically
    from src.registry import run_registry, AgentRegistry
    run_registry(port=8500)
"""

from src.registry.service import (
    AgentRegistration,
    AgentRegistry,
    RegisteredAgent,
    app,
    get_registry,
    main,
    run_registry,
)

__all__ = [
    "AgentRegistration",
    "AgentRegistry",
    "RegisteredAgent",
    "app",
    "get_registry",
    "main",
    "run_registry",
]
