"""Shared pytest fixtures for the test suite.

Provides reusable fixtures for testing A2A agents, transport, and deployment.
"""

import os
import socket

# Add project root to path
import sys
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def get_free_port() -> int:
    """Get a free port on localhost.

    Returns:
        An available port number.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


@pytest.fixture
def free_port() -> int:
    """Fixture providing a free port."""
    return get_free_port()


@pytest.fixture
def mock_agent_config() -> dict:
    """Standard mock agent configuration for testing.

    Returns:
        Dictionary with standard agent config values.
    """
    return {
        "id": "test-agent",
        "type": "TestAgent",
        "module": "agents.test_agent",
        "config": {"port": 9999},
        "deployment": {
            "target": "localhost",
            "environment": {"TEST_VAR": "test_value"},
        },
    }


@pytest.fixture
def agent_info_data() -> dict:
    """Sample AgentInfo data for testing.

    Returns:
        Dictionary mimicking agent configuration endpoint response.
    """
    return {
        "name": "Test Agent",
        "description": "A test agent for unit testing",
        "url": "http://localhost:9999",
        "version": "1.0.0",
        "capabilities": {"streaming": True, "push_notifications": False},
        "skills": [
            {
                "id": "test-skill",
                "name": "Test Skill",
                "description": "A test skill",
                "examples": ["Do something", "Test this"],
            }
        ],
    }


@pytest.fixture
def temp_job_file(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary job YAML file for testing.

    Args:
        tmp_path: pytest's temporary directory fixture.

    Yields:
        Path to the temporary job file.
    """
    job_content = """
job:
  name: test-job
  version: "1.0.0"
  description: Test job for unit testing

agents:
  - id: test-agent-1
    type: TestAgent
    module: agents.test_agent
    config:
      port: 9001
    deployment:
      target: localhost

topology:
  type: hub-spoke
  hub: test-agent-1
  spokes: []

deployment:
  strategy: sequential
  timeout: 30
"""
    job_file = tmp_path / "test_job.yaml"
    job_file.write_text(job_content)
    yield job_file


@pytest.fixture
def mock_httpx_client() -> MagicMock:
    """Mock httpx.AsyncClient for testing HTTP operations.

    Returns:
        MagicMock configured as an async context manager.
    """
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": "test response"}
    mock_response.raise_for_status = MagicMock()

    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    return mock_client


@pytest.fixture
def env_with_auth() -> Generator[None, None, None]:
    """Set up environment with authentication enabled.

    Yields:
        None. Environment is cleaned up after test.
    """
    original_auth = os.environ.get("AGENT_AUTH_REQUIRED")
    original_key = os.environ.get("AGENT_API_KEY")

    os.environ["AGENT_AUTH_REQUIRED"] = "true"
    os.environ["AGENT_API_KEY"] = "test-api-key-12345"

    yield

    # Restore original values
    if original_auth is None:
        os.environ.pop("AGENT_AUTH_REQUIRED", None)
    else:
        os.environ["AGENT_AUTH_REQUIRED"] = original_auth

    if original_key is None:
        os.environ.pop("AGENT_API_KEY", None)
    else:
        os.environ["AGENT_API_KEY"] = original_key


@pytest.fixture
def env_without_auth() -> Generator[None, None, None]:
    """Set up environment with authentication disabled.

    Yields:
        None. Environment is cleaned up after test.
    """
    original_auth = os.environ.get("AGENT_AUTH_REQUIRED")
    original_key = os.environ.get("AGENT_API_KEY")

    os.environ.pop("AGENT_AUTH_REQUIRED", None)
    os.environ.pop("AGENT_API_KEY", None)

    yield

    # Restore original values
    if original_auth is not None:
        os.environ["AGENT_AUTH_REQUIRED"] = original_auth
    if original_key is not None:
        os.environ["AGENT_API_KEY"] = original_key


@pytest.fixture
def mock_claude_sdk_client() -> MagicMock:
    """Mock ClaudeSDKClient for testing without actual API calls.

    Returns:
        MagicMock configured to simulate Claude SDK behavior.
    """
    mock_client = MagicMock()
    mock_client.connect = AsyncMock()
    mock_client.disconnect = AsyncMock()
    mock_client.query = AsyncMock()

    async def mock_receive_response():
        """Simulate response stream."""
        mock_message = MagicMock()
        mock_message.role = "assistant"
        mock_block = MagicMock()
        mock_block.text = "Test response from mock client"
        mock_message.content = [mock_block]
        mock_message.stop_reason = "end_turn"
        yield mock_message

    mock_client.receive_response = mock_receive_response

    return mock_client


@pytest.fixture
def project_root() -> Path:
    """Get the project root directory.

    Returns:
        Path to project root.
    """
    return Path(__file__).parent.parent


@pytest.fixture
def sample_urls() -> dict:
    """Sample URLs for testing SSRF protection.

    Returns:
        Dictionary of URL categories for testing.
    """
    return {
        "safe": [
            "http://localhost:9001",
            "http://127.0.0.1:9050",
            "http://localhost:9100",
        ],
        "unsafe_metadata": [
            "http://169.254.169.254/latest/meta-data/",  # AWS metadata
            "http://169.254.169.254:80/",
        ],
        "unsafe_internal": [
            "http://192.168.1.1:80/admin",
            "http://10.0.0.1:8080/",
        ],
        "unsafe_protocol": [
            "file:///etc/passwd",
            "ftp://localhost:21/",
        ],
        "unsafe_port": [
            "http://localhost:80/",  # Outside default range
            "http://localhost:8888/",
        ],
    }
