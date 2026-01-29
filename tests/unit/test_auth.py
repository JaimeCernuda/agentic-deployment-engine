"""Comprehensive tests for src/auth.py module.

Tests authentication mechanisms including:
- API key generation and retrieval
- Key verification with timing attack protection
- FastAPI dependency integration
- ASGI middleware functionality
- Edge cases and error handling
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

# Mark all tests in this module
pytestmark = pytest.mark.asyncio


class TestGetApiKey:
    """Tests for get_api_key function."""

    def test_returns_none_when_auth_disabled(self) -> None:
        """Should return None when AGENT_AUTH_REQUIRED is not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Need to reimport to pick up env changes
            import importlib
            import src.auth
            importlib.reload(src.auth)

            result = src.auth.get_api_key()
            assert result is None

    def test_returns_none_when_auth_explicitly_disabled(self) -> None:
        """Should return None when AGENT_AUTH_REQUIRED is false."""
        with patch.dict(os.environ, {"AGENT_AUTH_REQUIRED": "false"}, clear=True):
            import importlib
            import src.auth
            importlib.reload(src.auth)

            result = src.auth.get_api_key()
            assert result is None

    def test_returns_key_from_environment(self) -> None:
        """Should return key from AGENT_API_KEY when auth is required."""
        with patch.dict(os.environ, {
            "AGENT_AUTH_REQUIRED": "true",
            "AGENT_API_KEY": "test-api-key-123"
        }, clear=True):
            import importlib
            import src.auth
            importlib.reload(src.auth)

            result = src.auth.get_api_key()
            assert result == "test-api-key-123"

    def test_generates_key_when_not_provided(self) -> None:
        """Should generate a temporary key when none provided."""
        with patch.dict(os.environ, {"AGENT_AUTH_REQUIRED": "true"}, clear=True):
            import importlib
            import src.auth
            importlib.reload(src.auth)

            result = src.auth.get_api_key()
            assert result is not None
            assert len(result) > 20  # Generated keys are long

    def test_auth_required_with_yes_value(self) -> None:
        """Should recognize 'yes' as auth required."""
        with patch.dict(os.environ, {
            "AGENT_AUTH_REQUIRED": "yes",
            "AGENT_API_KEY": "my-key"
        }, clear=True):
            import importlib
            import src.auth
            importlib.reload(src.auth)

            result = src.auth.get_api_key()
            assert result == "my-key"

    def test_auth_required_with_1_value(self) -> None:
        """Should recognize '1' as auth required."""
        with patch.dict(os.environ, {
            "AGENT_AUTH_REQUIRED": "1",
            "AGENT_API_KEY": "my-key"
        }, clear=True):
            import importlib
            import src.auth
            importlib.reload(src.auth)

            result = src.auth.get_api_key()
            assert result == "my-key"


class TestVerifyApiKeySync:
    """Tests for verify_api_key_sync function."""

    def test_returns_true_when_auth_disabled(self) -> None:
        """Should return True when auth is disabled."""
        with patch.dict(os.environ, {"AGENT_AUTH_REQUIRED": "false"}, clear=True):
            import importlib
            import src.auth
            importlib.reload(src.auth)

            result = src.auth.verify_api_key_sync("any-key")
            assert result is True

    def test_returns_false_for_empty_key(self) -> None:
        """Should return False for empty key when auth required."""
        with patch.dict(os.environ, {
            "AGENT_AUTH_REQUIRED": "true",
            "AGENT_API_KEY": "valid-key"
        }, clear=True):
            import importlib
            import src.auth
            importlib.reload(src.auth)

            result = src.auth.verify_api_key_sync("")
            assert result is False

    def test_returns_false_for_none_key(self) -> None:
        """Should return False for None key when auth required."""
        with patch.dict(os.environ, {
            "AGENT_AUTH_REQUIRED": "true",
            "AGENT_API_KEY": "valid-key"
        }, clear=True):
            import importlib
            import src.auth
            importlib.reload(src.auth)

            result = src.auth.verify_api_key_sync(None)  # type: ignore
            assert result is False

    def test_returns_true_for_valid_key(self) -> None:
        """Should return True for matching key."""
        with patch.dict(os.environ, {
            "AGENT_AUTH_REQUIRED": "true",
            "AGENT_API_KEY": "correct-key"
        }, clear=True):
            import importlib
            import src.auth
            importlib.reload(src.auth)

            result = src.auth.verify_api_key_sync("correct-key")
            assert result is True

    def test_returns_false_for_invalid_key(self) -> None:
        """Should return False for non-matching key."""
        with patch.dict(os.environ, {
            "AGENT_AUTH_REQUIRED": "true",
            "AGENT_API_KEY": "correct-key"
        }, clear=True):
            import importlib
            import src.auth
            importlib.reload(src.auth)

            result = src.auth.verify_api_key_sync("wrong-key")
            assert result is False

    def test_uses_constant_time_comparison(self) -> None:
        """Should use hmac.compare_digest for timing attack protection."""
        import hmac
        with patch.dict(os.environ, {
            "AGENT_AUTH_REQUIRED": "true",
            "AGENT_API_KEY": "valid-key"
        }, clear=True):
            import importlib
            import src.auth
            importlib.reload(src.auth)

            with patch.object(hmac, "compare_digest", return_value=True) as mock_compare:
                src.auth.verify_api_key_sync("test-key")
                mock_compare.assert_called_once_with("test-key", "valid-key")


class TestVerifyApiKeyAsync:
    """Tests for verify_api_key async FastAPI dependency."""

    async def test_returns_none_when_auth_disabled(self) -> None:
        """Should return None when auth is disabled."""
        with patch.dict(os.environ, {"AGENT_AUTH_REQUIRED": "false"}, clear=True):
            import importlib
            import src.auth
            importlib.reload(src.auth)

            result = await src.auth.verify_api_key(None, None)
            assert result is None

    async def test_raises_401_when_no_key_provided(self) -> None:
        """Should raise HTTPException 401 when no key provided."""
        with patch.dict(os.environ, {
            "AGENT_AUTH_REQUIRED": "true",
            "AGENT_API_KEY": "valid-key"
        }, clear=True):
            import importlib
            import src.auth
            importlib.reload(src.auth)

            with pytest.raises(HTTPException) as exc_info:
                await src.auth.verify_api_key(None, None)

            assert exc_info.value.status_code == 401
            assert "API key required" in exc_info.value.detail

    async def test_raises_401_for_invalid_key(self) -> None:
        """Should raise HTTPException 401 for invalid key."""
        with patch.dict(os.environ, {
            "AGENT_AUTH_REQUIRED": "true",
            "AGENT_API_KEY": "valid-key"
        }, clear=True):
            import importlib
            import src.auth
            importlib.reload(src.auth)

            with pytest.raises(HTTPException) as exc_info:
                await src.auth.verify_api_key("wrong-key", None)

            assert exc_info.value.status_code == 401
            assert "Invalid API key" in exc_info.value.detail

    async def test_accepts_valid_header_key(self) -> None:
        """Should accept valid key from header."""
        with patch.dict(os.environ, {
            "AGENT_AUTH_REQUIRED": "true",
            "AGENT_API_KEY": "valid-key"
        }, clear=True):
            import importlib
            import src.auth
            importlib.reload(src.auth)

            result = await src.auth.verify_api_key("valid-key", None)
            assert result == "valid-key"

    async def test_accepts_valid_query_key(self) -> None:
        """Should accept valid key from query parameter."""
        with patch.dict(os.environ, {
            "AGENT_AUTH_REQUIRED": "true",
            "AGENT_API_KEY": "valid-key"
        }, clear=True):
            import importlib
            import src.auth
            importlib.reload(src.auth)

            result = await src.auth.verify_api_key(None, "valid-key")
            assert result == "valid-key"

    async def test_header_key_takes_precedence(self) -> None:
        """Should use header key when both are provided."""
        with patch.dict(os.environ, {
            "AGENT_AUTH_REQUIRED": "true",
            "AGENT_API_KEY": "header-key"
        }, clear=True):
            import importlib
            import src.auth
            importlib.reload(src.auth)

            result = await src.auth.verify_api_key("header-key", "query-key")
            assert result == "header-key"


class TestOptionalApiKey:
    """Tests for optional_api_key function."""

    async def test_returns_none_when_no_key_provided(self) -> None:
        """Should return None when no key provided."""
        import importlib
        import src.auth
        importlib.reload(src.auth)

        result = await src.auth.optional_api_key(None, None)
        assert result is None

    async def test_returns_key_when_valid(self) -> None:
        """Should return key when valid."""
        with patch.dict(os.environ, {
            "AGENT_AUTH_REQUIRED": "true",
            "AGENT_API_KEY": "valid-key"
        }, clear=True):
            import importlib
            import src.auth
            importlib.reload(src.auth)

            result = await src.auth.optional_api_key("valid-key", None)
            assert result == "valid-key"

    async def test_returns_none_when_invalid(self) -> None:
        """Should return None when key is invalid."""
        with patch.dict(os.environ, {
            "AGENT_AUTH_REQUIRED": "true",
            "AGENT_API_KEY": "valid-key"
        }, clear=True):
            import importlib
            import src.auth
            importlib.reload(src.auth)

            result = await src.auth.optional_api_key("wrong-key", None)
            assert result is None


class TestHashApiKey:
    """Tests for hash_api_key function."""

    def test_returns_truncated_sha256_hash(self) -> None:
        """Should return first 16 chars of SHA-256 hash."""
        from src.auth import hash_api_key

        result = hash_api_key("test-key")
        assert len(result) == 16
        assert result.isalnum()  # Hex string

    def test_same_key_produces_same_hash(self) -> None:
        """Should produce consistent hashes."""
        from src.auth import hash_api_key

        hash1 = hash_api_key("my-api-key")
        hash2 = hash_api_key("my-api-key")
        assert hash1 == hash2

    def test_different_keys_produce_different_hashes(self) -> None:
        """Should produce different hashes for different keys."""
        from src.auth import hash_api_key

        hash1 = hash_api_key("key-one")
        hash2 = hash_api_key("key-two")
        assert hash1 != hash2


class TestAuthMiddleware:
    """Tests for AuthMiddleware ASGI middleware."""

    def test_init_with_default_excluded_paths(self) -> None:
        """Should initialize with default excluded paths."""
        from src.auth import AuthMiddleware

        app = MagicMock()
        middleware = AuthMiddleware(app)

        assert "/health" in middleware.excluded_paths
        assert "/.well-known/" in middleware.excluded_paths
        assert "/docs" in middleware.excluded_paths

    def test_init_with_custom_excluded_paths(self) -> None:
        """Should accept custom excluded paths."""
        from src.auth import AuthMiddleware

        app = MagicMock()
        middleware = AuthMiddleware(app, excluded_paths=["/custom", "/other"])

        assert middleware.excluded_paths == ["/custom", "/other"]

    async def test_passes_non_http_requests(self) -> None:
        """Should pass through non-HTTP requests."""
        from src.auth import AuthMiddleware

        app = AsyncMock()
        middleware = AuthMiddleware(app)

        scope = {"type": "websocket"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        app.assert_called_once_with(scope, receive, send)

    async def test_passes_excluded_paths(self) -> None:
        """Should pass through excluded paths without auth."""
        from src.auth import AuthMiddleware

        app = AsyncMock()
        middleware = AuthMiddleware(app)

        scope = {"type": "http", "path": "/health"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        app.assert_called_once()

    async def test_passes_when_auth_disabled(self) -> None:
        """Should pass through when auth is disabled."""
        with patch.dict(os.environ, {"AGENT_AUTH_REQUIRED": "false"}, clear=True):
            import importlib
            import src.auth
            importlib.reload(src.auth)

            app = AsyncMock()
            middleware = src.auth.AuthMiddleware(app)

            scope = {"type": "http", "path": "/api/query", "headers": [], "query_string": b""}
            receive = AsyncMock()
            send = AsyncMock()

            await middleware(scope, receive, send)
            app.assert_called_once()

    async def test_returns_401_when_no_key(self) -> None:
        """Should return 401 when no API key provided."""
        with patch.dict(os.environ, {
            "AGENT_AUTH_REQUIRED": "true",
            "AGENT_API_KEY": "valid-key"
        }, clear=True):
            import importlib
            import src.auth
            importlib.reload(src.auth)

            app = AsyncMock()
            middleware = src.auth.AuthMiddleware(app)

            scope = {"type": "http", "path": "/api/query", "headers": [], "query_string": b""}
            receive = AsyncMock()
            send = AsyncMock()

            await middleware(scope, receive, send)

            # Should have sent 401 response
            calls = send.call_args_list
            assert len(calls) == 2
            assert calls[0][0][0]["status"] == 401

    async def test_accepts_valid_header_key(self) -> None:
        """Should accept valid key from header."""
        with patch.dict(os.environ, {
            "AGENT_AUTH_REQUIRED": "true",
            "AGENT_API_KEY": "valid-key"
        }, clear=True):
            import importlib
            import src.auth
            importlib.reload(src.auth)

            app = AsyncMock()
            middleware = src.auth.AuthMiddleware(app)

            scope = {
                "type": "http",
                "path": "/api/query",
                "headers": [(b"x-api-key", b"valid-key")],
                "query_string": b""
            }
            receive = AsyncMock()
            send = AsyncMock()

            await middleware(scope, receive, send)
            app.assert_called_once()

    async def test_accepts_valid_query_key(self) -> None:
        """Should accept valid key from query string."""
        with patch.dict(os.environ, {
            "AGENT_AUTH_REQUIRED": "true",
            "AGENT_API_KEY": "valid-key"
        }, clear=True):
            import importlib
            import src.auth
            importlib.reload(src.auth)

            app = AsyncMock()
            middleware = src.auth.AuthMiddleware(app)

            scope = {
                "type": "http",
                "path": "/api/query",
                "headers": [],
                "query_string": b"api_key=valid-key"
            }
            receive = AsyncMock()
            send = AsyncMock()

            await middleware(scope, receive, send)
            app.assert_called_once()

    async def test_handles_query_string_with_multiple_params(self) -> None:
        """Should extract api_key from complex query strings."""
        with patch.dict(os.environ, {
            "AGENT_AUTH_REQUIRED": "true",
            "AGENT_API_KEY": "valid-key"
        }, clear=True):
            import importlib
            import src.auth
            importlib.reload(src.auth)

            app = AsyncMock()
            middleware = src.auth.AuthMiddleware(app)

            scope = {
                "type": "http",
                "path": "/api/query",
                "headers": [],
                "query_string": b"foo=bar&api_key=valid-key&baz=qux"
            }
            receive = AsyncMock()
            send = AsyncMock()

            await middleware(scope, receive, send)
            app.assert_called_once()
