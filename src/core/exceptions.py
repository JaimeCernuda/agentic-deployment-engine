"""Custom exception hierarchy for the agentic deployment engine.

Provides structured exceptions with error codes and recovery hints.
"""


class AgentError(Exception):
    """Base exception for agent-related errors.

    Attributes:
        message: Human-readable error message.
        code: Machine-readable error code.
        recoverable: Whether the error is potentially recoverable.
    """

    def __init__(
        self,
        message: str,
        code: str,
        recoverable: bool = True,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.recoverable = recoverable

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"

    def to_dict(self) -> dict[str, str | bool]:
        """Convert exception to dictionary for JSON serialization.

        Returns:
            Dictionary with error details.
        """
        return {
            "error": self.code,
            "message": self.message,
            "recoverable": self.recoverable,
        }


class ConnectionError(AgentError):
    """Failed to connect to an agent.

    Raised when HTTP connection to an agent fails due to network issues,
    agent being down, or invalid URL.
    """

    def __init__(
        self,
        url: str,
        cause: Exception | None = None,
    ) -> None:
        message = f"Failed to connect to {url}"
        if cause:
            message += f": {cause}"
        super().__init__(message, "CONN_FAILED", recoverable=True)
        self.url = url
        self.cause = cause


class TimeoutError(AgentError):
    """Request timed out.

    Raised when an HTTP request exceeds the configured timeout.
    """

    def __init__(
        self,
        url: str,
        timeout: float,
    ) -> None:
        message = f"Request to {url} timed out after {timeout}s"
        super().__init__(message, "TIMEOUT", recoverable=True)
        self.url = url
        self.timeout = timeout


class SecurityError(AgentError):
    """Security validation failed.

    Raised when a security check fails, such as SSRF protection,
    authentication failure, or invalid API key.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, "SECURITY", recoverable=False)


class ConfigurationError(AgentError):
    """Invalid configuration.

    Raised when configuration is invalid or missing required values.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, "CONFIG", recoverable=False)


class AgentBackendError(AgentError):
    """Error from agent backend (Claude SDK, CrewAI, etc.).

    Raised when the underlying agentic framework encounters an error.
    """

    def __init__(
        self,
        backend: str,
        message: str,
        cause: Exception | None = None,
    ) -> None:
        full_message = f"[{backend}] {message}"
        if cause:
            full_message += f": {cause}"
        super().__init__(full_message, "BACKEND_ERROR", recoverable=True)
        self.backend = backend
        self.cause = cause


class DeploymentError(AgentError):
    """Error during agent deployment.

    Raised when deploying an agent fails due to SSH, Docker, or other issues.
    """

    def __init__(
        self,
        target: str,
        message: str,
        cause: Exception | None = None,
    ) -> None:
        full_message = f"Deployment to {target} failed: {message}"
        if cause:
            full_message += f": {cause}"
        super().__init__(full_message, "DEPLOY_ERROR", recoverable=True)
        self.target = target
        self.cause = cause


class DiscoveryError(AgentError):
    """Error during agent discovery.

    Raised when A2A agent discovery fails.
    """

    def __init__(
        self,
        url: str,
        cause: Exception | None = None,
    ) -> None:
        message = f"Failed to discover agent at {url}"
        if cause:
            message += f": {cause}"
        super().__init__(message, "DISCOVERY_ERROR", recoverable=True)
        self.url = url
        self.cause = cause


class ValidationError(AgentError):
    """Validation error for job definitions or configurations.

    Raised when input validation fails.
    """

    def __init__(
        self,
        field: str,
        message: str,
    ) -> None:
        full_message = f"Validation failed for '{field}': {message}"
        super().__init__(full_message, "VALIDATION", recoverable=False)
        self.field = field
