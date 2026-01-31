"""Centralized configuration for the agentic deployment engine.

Uses pydantic-settings for environment variable loading and validation.
All settings can be overridden via environment variables with appropriate prefixes.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    """Settings for A2A agents.

    Environment variables:
        AGENT_HTTP_TIMEOUT: HTTP request timeout in seconds
        AGENT_DISCOVERY_TIMEOUT: Agent discovery timeout in seconds
        AGENT_API_KEY: API key for authentication
        AGENT_AUTH_REQUIRED: Whether API key auth is required
        AGENT_ALLOWED_HOSTS: Comma-separated list of allowed hosts
        AGENT_MIN_PORT: Minimum allowed agent port
        AGENT_MAX_PORT: Maximum allowed agent port
        AGENT_CLIENT_POOL_SIZE: SDK client pool size
        AGENT_OTEL_ENABLED: Enable OpenTelemetry
        AGENT_OTEL_ENDPOINT: OTLP collector endpoint
        AGENT_OTEL_PROTOCOL: OTLP protocol (grpc/http)
        AGENT_OTEL_SERVICE_NAME: Service name for traces
        AGENT_LOG_LEVEL: Logging level
        AGENT_LOG_JSON: Enable JSON log format
        AGENT_LOG_MAX_CONTENT_LENGTH: Max chars for log content
        AGENT_BACKEND_TYPE: Agent backend (claude, gemini, crewai)
        AGENT_OLLAMA_MODEL: Ollama model for CrewAI backend
        AGENT_OLLAMA_BASE_URL: Ollama API base URL
    """

    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Network settings
    http_timeout: float = Field(
        default=30.0,
        description="HTTP request timeout in seconds",
    )
    discovery_timeout: float = Field(
        default=10.0,
        description="Agent discovery timeout in seconds",
    )

    # Security settings
    api_key: str | None = Field(
        default=None,
        description="API key for authentication",
    )
    auth_required: bool = Field(
        default=False,
        description="Require API key authentication",
    )
    allowed_hosts: str = Field(
        default="localhost,127.0.0.1",
        description="Comma-separated list of allowed hosts for SSRF protection",
    )
    min_port: int = Field(
        default=9000,
        description="Minimum allowed agent port",
    )
    max_port: int = Field(
        default=9100,
        description="Maximum allowed agent port",
    )

    # Performance settings
    client_pool_size: int = Field(
        default=3,
        description="SDK client pool size",
    )

    # Observability settings
    otel_enabled: bool = Field(
        default=False,
        description="Enable OpenTelemetry tracing",
    )
    otel_endpoint: str = Field(
        default="http://localhost:4317",
        description="OTLP collector endpoint",
    )
    otel_protocol: str = Field(
        default="grpc",
        description="OTLP protocol (grpc/http)",
    )
    otel_service_name: str = Field(
        default="agentic-deployment-engine",
        description="Service name for traces",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )
    log_json: bool = Field(
        default=False,
        description="Enable JSON log format",
    )
    log_max_content_length: int = Field(
        default=2000,
        description="Max characters for log content (0=unlimited)",
    )

    # Semantic tracing settings
    semantic_tracing_enabled: bool = Field(
        default=False,
        description="Enable semantic tracing to JSON files",
    )
    semantic_trace_dir: str = Field(
        default="traces/",
        description="Directory for semantic trace JSON files",
    )

    # Backend settings
    backend_type: str = Field(
        default="claude",
        description="Agent backend: claude, gemini, crewai",
    )
    ollama_model: str = Field(
        default="llama3",
        description="Ollama model for CrewAI backend",
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama API base URL",
    )

    # Session settings for multi-turn conversations
    max_sessions: int = Field(
        default=100,
        description="Maximum number of sessions per agent",
    )
    session_ttl_seconds: int = Field(
        default=3600,
        description="Session time-to-live in seconds (default: 1 hour)",
    )
    max_history_messages: int = Field(
        default=20,
        description="Maximum conversation history messages to include in prompt",
    )

    def get_allowed_hosts_set(self) -> set[str]:
        """Get allowed hosts as a set.

        Returns:
            Set of allowed hostnames/IPs.
        """
        return {h.strip() for h in self.allowed_hosts.split(",") if h.strip()}

    def get_port_range(self) -> tuple[int, int]:
        """Get allowed port range.

        Returns:
            Tuple of (min_port, max_port).
        """
        return (self.min_port, self.max_port)


class DeploymentSettings(BaseSettings):
    """Settings for job deployment.

    Environment variables:
        DEPLOY_SSH_TIMEOUT: SSH connection timeout in seconds
        DEPLOY_HEALTH_CHECK_RETRIES: Number of health check retries
        DEPLOY_HEALTH_CHECK_INTERVAL: Interval between health checks in seconds
        DEPLOY_WORK_DIR: Working directory for deployments
    """

    model_config = SettingsConfigDict(
        env_prefix="DEPLOY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ssh_timeout: int = Field(
        default=30,
        description="SSH connection timeout in seconds",
    )
    health_check_retries: int = Field(
        default=5,
        description="Number of health check retries",
    )
    health_check_interval: float = Field(
        default=2.0,
        description="Interval between health checks in seconds",
    )
    work_dir: str = Field(
        default="/tmp/agent-deploy",
        description="Working directory for deployments",
    )


# Global settings instances - import these directly
settings = AgentSettings()
deploy_settings = DeploymentSettings()
