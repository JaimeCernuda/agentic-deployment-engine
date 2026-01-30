"""Tests for agent backend switching.

Verifies that the backend factory correctly creates backends
based on configuration and that each backend initializes properly.
"""

import os
import pytest

from src.backends.base import BackendConfig
from src.agents.base import create_backend

pytestmark = [pytest.mark.usability]


class TestBackendFactory:
    """Test the backend factory function."""

    def test_creates_claude_backend_by_default(self, monkeypatch):
        """Default backend should be Claude SDK."""
        monkeypatch.setenv("AGENT_BACKEND_TYPE", "claude")
        # Force reload of settings
        from src import config
        import importlib
        importlib.reload(config)

        backend_config = BackendConfig(name="test", system_prompt="Test")
        backend = create_backend(backend_config)

        assert backend.name == "claude-agent-sdk"
        assert backend.config.name == "test"

    def test_creates_gemini_backend_directly(self):
        """Gemini CLI backend should be creatable directly."""
        from src.backends.gemini_cli import GeminiCLIBackend

        backend_config = BackendConfig(name="test", system_prompt="Test")
        backend = GeminiCLIBackend(backend_config)

        assert backend.name == "gemini-cli"

    def test_creates_crewai_backend_directly(self):
        """CrewAI backend should be creatable directly."""
        from src.backends.crewai import CrewAIBackend

        backend_config = BackendConfig(name="test", system_prompt="Test")
        backend = CrewAIBackend(backend_config, ollama_model="llama3.2")

        assert backend.name == "crewai"
        assert backend.ollama_model == "llama3.2"

    def test_unknown_backend_defaults_to_claude(self, monkeypatch):
        """Unknown backend type should fall back to Claude."""
        monkeypatch.setenv("AGENT_BACKEND_TYPE", "unknown_backend")
        from src import config
        import importlib
        importlib.reload(config)

        backend_config = BackendConfig(name="test", system_prompt="Test")
        backend = create_backend(backend_config)

        assert backend.name == "claude-agent-sdk"


class TestGeminiCLIBackend:
    """Test Gemini CLI backend functionality."""

    def test_backend_instantiation(self):
        """Gemini CLI backend should instantiate correctly."""
        from src.backends.gemini_cli import GeminiCLIBackend

        config = BackendConfig(name="test-gemini", system_prompt="Test")
        backend = GeminiCLIBackend(config)

        assert backend.name == "gemini-cli"
        assert backend.yolo_mode is True  # Default
        assert backend.model is None  # Default

    def test_backend_with_custom_model(self):
        """Should accept custom model parameter."""
        from src.backends.gemini_cli import GeminiCLIBackend

        config = BackendConfig(name="test", system_prompt="Test")
        backend = GeminiCLIBackend(config, model="gemini-2.0-flash")

        assert backend.model == "gemini-2.0-flash"

    def test_backend_with_yolo_disabled(self):
        """Should accept yolo mode toggle."""
        from src.backends.gemini_cli import GeminiCLIBackend

        config = BackendConfig(name="test", system_prompt="Test")
        backend = GeminiCLIBackend(config, yolo_mode=False)

        assert backend.yolo_mode is False


class TestCrewAIBackend:
    """Test CrewAI backend functionality."""

    def test_backend_instantiation(self):
        """CrewAI backend should instantiate correctly."""
        from src.backends.crewai import CrewAIBackend

        config = BackendConfig(name="test-crew", system_prompt="Help user")
        backend = CrewAIBackend(config)

        assert backend.name == "crewai"
        assert backend.ollama_model == "llama3"  # Default
        assert backend.ollama_base_url == "http://localhost:11434"  # Default

    def test_backend_with_custom_ollama_model(self):
        """Should accept custom Ollama model."""
        from src.backends.crewai import CrewAIBackend

        config = BackendConfig(name="test", system_prompt="Test")
        backend = CrewAIBackend(config, ollama_model="llama3.2")

        assert backend.ollama_model == "llama3.2"

    def test_backend_with_custom_ollama_url(self):
        """Should accept custom Ollama URL."""
        from src.backends.crewai import CrewAIBackend

        config = BackendConfig(name="test", system_prompt="Test")
        backend = CrewAIBackend(config, ollama_base_url="http://ollama:11434")

        assert backend.ollama_base_url == "http://ollama:11434"


class TestBackendConfig:
    """Test backend configuration handling."""

    def test_config_with_all_fields(self):
        """BackendConfig should accept all fields."""
        config = BackendConfig(
            name="full-config",
            system_prompt="You are a helpful assistant",
            allowed_tools=["tool1", "tool2"],
            mcp_servers={"server1": {"type": "sdk"}},
            extra_options={"custom": "value"},
        )

        assert config.name == "full-config"
        assert config.system_prompt == "You are a helpful assistant"
        assert config.allowed_tools == ["tool1", "tool2"]
        assert "server1" in config.mcp_servers
        assert config.extra_options["custom"] == "value"

    def test_config_with_minimal_fields(self):
        """BackendConfig should work with just name."""
        config = BackendConfig(name="minimal")

        assert config.name == "minimal"
        assert config.system_prompt is None
        assert config.allowed_tools == []
        assert config.mcp_servers == {}
        assert config.extra_options == {}
