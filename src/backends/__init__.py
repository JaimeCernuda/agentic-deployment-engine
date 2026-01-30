"""Agent backend abstraction layer.

Provides a unified interface for different agentic frameworks:
- Claude Agent SDK (default)
- Gemini CLI (requires gemini CLI installed)
- CrewAI (requires crewai optional dep and Ollama)

Set AGENT_BACKEND_TYPE env var to switch backends: claude, gemini, crewai
"""

from .base import AgentBackend, BackendConfig, QueryResult
from .claude_sdk import ClaudeSDKBackend

__all__ = [
    "AgentBackend",
    "BackendConfig",
    "QueryResult",
    "ClaudeSDKBackend",
]
