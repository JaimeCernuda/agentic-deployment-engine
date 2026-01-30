"""Authentication module for A2A agents.

Provides API key authentication for securing agent endpoints.
"""

import hashlib
import hmac
import logging
import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader, APIKeyQuery

from ..config import settings

logger = logging.getLogger(__name__)

# API Key header and query parameter names
API_KEY_HEADER_NAME = "X-API-Key"
API_KEY_QUERY_NAME = "api_key"

# Security schemes
api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)
api_key_query = APIKeyQuery(name=API_KEY_QUERY_NAME, auto_error=False)


def get_api_key() -> str | None:
    """Get API key from configuration or generate a new one.

    The key is retrieved from AGENT_API_KEY environment variable via settings.
    If not set and AGENT_AUTH_REQUIRED is true, a new key is generated
    and logged (for development purposes only).

    Returns:
        API key string, or None if auth is disabled.
    """
    # Check if auth is required
    if not settings.auth_required:
        return None

    key = settings.api_key

    if not key:
        # Generate a new key for development
        key = secrets.token_urlsafe(32)
        logger.warning(
            f"No AGENT_API_KEY set. Generated temporary key: {key}\n"
            f"Set AGENT_API_KEY environment variable to persist."
        )

    return key


def verify_api_key_sync(api_key: str) -> bool:
    """Verify API key synchronously.

    Uses constant-time comparison to prevent timing attacks.

    Args:
        api_key: The API key to verify.

    Returns:
        True if valid, False otherwise.
    """
    expected_key = get_api_key()

    if expected_key is None:
        # Auth not required
        return True

    if not api_key:
        return False

    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(api_key, expected_key)


async def verify_api_key(
    header_key: str | None = Security(api_key_header),
    query_key: str | None = Security(api_key_query),
) -> str | None:
    """FastAPI dependency to verify API key from header or query.

    Checks X-API-Key header first, then api_key query parameter.
    Raises 401 if auth is required but key is invalid.

    Args:
        header_key: API key from header.
        query_key: API key from query parameter.

    Returns:
        The valid API key, or None if auth is disabled.

    Raises:
        HTTPException: 401 if authentication fails.
    """
    expected_key = get_api_key()

    # If no key configured, auth is disabled
    if expected_key is None:
        return None

    # Try header first, then query
    provided_key = header_key or query_key

    if not provided_key:
        logger.warning("API request without authentication")
        raise HTTPException(
            status_code=401,
            detail="API key required. Provide via X-API-Key header or api_key query parameter.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if not verify_api_key_sync(provided_key):
        logger.warning("Invalid API key attempted")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return provided_key


async def optional_api_key(
    header_key: str | None = Security(api_key_header),
    query_key: str | None = Security(api_key_query),
) -> str | None:
    """FastAPI dependency for optional API key verification.

    Unlike verify_api_key, this doesn't raise an error if no key is provided.
    Useful for endpoints that should work with or without auth.

    Args:
        header_key: API key from header.
        query_key: API key from query parameter.

    Returns:
        The valid API key if provided and valid, None otherwise.
    """
    provided_key = header_key or query_key

    if not provided_key:
        return None

    if verify_api_key_sync(provided_key):
        return provided_key

    return None


def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage or logging.

    Uses SHA-256 to create a one-way hash of the key.
    Useful for logging key usage without exposing the actual key.

    Args:
        api_key: The API key to hash.

    Returns:
        Hex digest of the hashed key (first 16 chars for brevity).
    """
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


class AuthMiddleware:
    """ASGI middleware for API key authentication.

    Use this for global authentication across all endpoints.
    For selective authentication, use the verify_api_key dependency instead.
    """

    def __init__(self, app, excluded_paths: list[str] | None = None):
        """Initialize auth middleware.

        Args:
            app: ASGI application.
            excluded_paths: Paths to exclude from auth (e.g., ["/health", "/.well-known/"]).
        """
        self.app = app
        self.excluded_paths = excluded_paths or [
            "/health",
            "/.well-known/",
            "/docs",
            "/openapi.json",
        ]

    async def __call__(self, scope, receive, send):
        """Process request."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # Check if path is excluded
        for excluded in self.excluded_paths:
            if path.startswith(excluded):
                await self.app(scope, receive, send)
                return

        # Check authentication
        expected_key = get_api_key()

        if expected_key is None:
            # Auth not required
            await self.app(scope, receive, send)
            return

        # Extract API key from headers
        headers = dict(scope.get("headers", []))
        header_key = headers.get(b"x-api-key", b"").decode()

        # Extract from query string
        query_string = scope.get("query_string", b"").decode()
        query_key = ""
        for param in query_string.split("&"):
            if param.startswith("api_key="):
                query_key = param[8:]
                break

        provided_key = header_key or query_key

        if not provided_key or not verify_api_key_sync(provided_key):
            # Return 401
            response = {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"www-authenticate", b"ApiKey"),
                ],
            }
            await send(response)
            await send(
                {
                    "type": "http.response.body",
                    "body": b'{"detail": "API key required"}',
                }
            )
            return

        await self.app(scope, receive, send)
