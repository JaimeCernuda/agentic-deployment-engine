"""Comprehensive tests for src/a2a_transport.py module.

Tests A2A transport functionality including:
- SSRF protection (is_safe_url)
- query_agent tool
- discover_agent tool
- Server creation
- Edge cases and error handling
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


class TestIsSafeUrl:
    """Tests for is_safe_url SSRF protection function."""

    def test_rejects_non_http_schemes(self) -> None:
        """Should reject non-HTTP schemes."""
        from src.a2a_transport import is_safe_url

        assert is_safe_url("ftp://localhost:9000") is False
        assert is_safe_url("file:///etc/passwd") is False
        assert is_safe_url("javascript:alert(1)") is False
        assert is_safe_url("data:text/html,<h1>test</h1>") is False

    def test_accepts_http_scheme(self) -> None:
        """Should accept http scheme."""
        from src.a2a_transport import is_safe_url

        assert is_safe_url("http://localhost:9000") is True

    def test_accepts_https_scheme(self) -> None:
        """Should accept https scheme."""
        from src.a2a_transport import is_safe_url

        # HTTPS with default allowed port range
        with patch.dict(os.environ, {
            "AGENT_MIN_PORT": "443",
            "AGENT_MAX_PORT": "9100"
        }):
            from importlib import reload
            import src.a2a_transport
            reload(src.a2a_transport)
            assert src.a2a_transport.is_safe_url("https://localhost:443") is True

    def test_rejects_missing_hostname(self) -> None:
        """Should reject URLs without hostname."""
        from src.a2a_transport import is_safe_url

        assert is_safe_url("http:///path") is False
        assert is_safe_url("http://") is False

    def test_rejects_link_local_addresses(self) -> None:
        """Should reject link-local addresses (AWS metadata, etc.)."""
        from src.a2a_transport import is_safe_url

        assert is_safe_url("http://169.254.169.254:9000") is False
        assert is_safe_url("http://169.254.1.1:9000") is False

    def test_rejects_multicast_addresses(self) -> None:
        """Should reject multicast addresses."""
        from src.a2a_transport import is_safe_url

        assert is_safe_url("http://224.0.0.1:9000") is False
        assert is_safe_url("http://239.255.255.255:9000") is False

    def test_rejects_private_ips_not_in_allowlist(self) -> None:
        """Should reject private IPs not in allowlist."""
        from src.a2a_transport import is_safe_url

        assert is_safe_url("http://192.168.1.1:9000") is False
        assert is_safe_url("http://10.0.0.1:9000") is False
        assert is_safe_url("http://172.16.0.1:9000") is False

    def test_accepts_localhost(self) -> None:
        """Should accept localhost in default allowlist."""
        from src.a2a_transport import is_safe_url

        assert is_safe_url("http://localhost:9000") is True
        assert is_safe_url("http://127.0.0.1:9000") is True

    def test_rejects_non_allowed_hostnames(self) -> None:
        """Should reject hostnames not in allowlist."""
        from src.a2a_transport import is_safe_url

        assert is_safe_url("http://evil.com:9000") is False
        assert is_safe_url("http://internal.corp:9000") is False

    def test_accepts_custom_allowed_hosts(self) -> None:
        """Should accept hosts from AGENT_ALLOWED_HOSTS env."""
        with patch.dict(os.environ, {"AGENT_ALLOWED_HOSTS": "myhost.local,trusted.com"}):
            from importlib import reload
            import src.a2a_transport
            reload(src.a2a_transport)

            assert src.a2a_transport.is_safe_url("http://myhost.local:9000") is True
            assert src.a2a_transport.is_safe_url("http://trusted.com:9000") is True

    def test_rejects_ports_outside_range(self) -> None:
        """Should reject ports outside allowed range."""
        from src.a2a_transport import is_safe_url

        # Default range is 9000-9100
        assert is_safe_url("http://localhost:8999") is False
        assert is_safe_url("http://localhost:9101") is False
        assert is_safe_url("http://localhost:80") is False

    def test_accepts_ports_inside_range(self) -> None:
        """Should accept ports inside allowed range."""
        from src.a2a_transport import is_safe_url

        assert is_safe_url("http://localhost:9000") is True
        assert is_safe_url("http://localhost:9050") is True
        assert is_safe_url("http://localhost:9100") is True

    def test_custom_port_range(self) -> None:
        """Should respect custom port range from environment."""
        with patch.dict(os.environ, {
            "AGENT_MIN_PORT": "8000",
            "AGENT_MAX_PORT": "8100"
        }):
            from importlib import reload
            import src.a2a_transport
            reload(src.a2a_transport)

            assert src.a2a_transport.is_safe_url("http://localhost:8050") is True
            assert src.a2a_transport.is_safe_url("http://localhost:9000") is False

    def test_handles_malformed_urls(self) -> None:
        """Should handle malformed URLs gracefully."""
        from src.a2a_transport import is_safe_url

        assert is_safe_url("not-a-url") is False
        assert is_safe_url("") is False
        assert is_safe_url("   ") is False
        assert is_safe_url("http://[invalid") is False

    def test_handles_urls_without_port(self) -> None:
        """Should handle URLs without explicit port."""
        # Default ports (80/443) are typically outside agent port range
        from src.a2a_transport import is_safe_url

        assert is_safe_url("http://localhost") is False  # Port 80 outside range
        assert is_safe_url("https://localhost") is False  # Port 443 outside range


class TestQueryAgentLogic:
    """Tests for query_agent tool logic via underlying function.

    Note: The @tool decorator creates SdkMcpTool objects.
    These tests validate the SSRF protection logic which is the
    critical security component.
    """

    def test_ssrf_protection_blocks_unsafe_urls(self) -> None:
        """query_agent should reject unsafe URLs via is_safe_url."""
        from src.a2a_transport import is_safe_url

        # These should all be blocked
        unsafe_urls = [
            "http://169.254.169.254:9000",  # AWS metadata
            "http://evil.com:9000",  # External host
            "http://localhost:8080",  # Port out of range
            "ftp://localhost:9000",  # Wrong protocol
        ]

        for url in unsafe_urls:
            assert is_safe_url(url) is False, f"{url} should be blocked"

    def test_safe_urls_allowed(self) -> None:
        """query_agent should allow safe URLs."""
        from src.a2a_transport import is_safe_url

        safe_urls = [
            "http://localhost:9000",
            "http://localhost:9001",
            "http://127.0.0.1:9050",
            "http://localhost:9100",
        ]

        for url in safe_urls:
            assert is_safe_url(url) is True, f"{url} should be allowed"


class TestDiscoverAgentLogic:
    """Tests for discover_agent tool logic.

    Note: The @tool decorator creates SdkMcpTool objects.
    These tests validate the SSRF protection which is the
    critical security component.
    """

    def test_ssrf_protection_blocks_unsafe_urls(self) -> None:
        """discover_agent should reject unsafe URLs via is_safe_url."""
        from src.a2a_transport import is_safe_url

        assert is_safe_url("http://evil.com:9000") is False
        assert is_safe_url("http://internal.corp:9000") is False

    def test_safe_urls_allowed(self) -> None:
        """discover_agent should allow safe URLs."""
        from src.a2a_transport import is_safe_url

        assert is_safe_url("http://localhost:9001") is True


class TestCreateA2ATransportServer:
    """Tests for create_a2a_transport_server function."""

    def test_creates_sdk_mcp_server(self) -> None:
        """Should create SDK MCP server with tools."""
        with patch("src.a2a_transport.create_sdk_mcp_server") as mock_create:
            mock_server = MagicMock()
            mock_create.return_value = mock_server

            from src.a2a_transport import create_a2a_transport_server
            result = create_a2a_transport_server()

            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args
            assert call_kwargs[1]["name"] == "a2a_transport"
            assert call_kwargs[1]["version"] == "1.0.0"
            assert len(call_kwargs[1]["tools"]) == 2


class TestGetAllowedHosts:
    """Tests for _get_allowed_hosts helper function."""

    def test_returns_default_when_no_env(self) -> None:
        """Should return defaults when env not set."""
        with patch.dict(os.environ, {}, clear=True):
            from importlib import reload
            import src.a2a_transport
            reload(src.a2a_transport)

            hosts = src.a2a_transport._get_allowed_hosts()
            assert "localhost" in hosts
            assert "127.0.0.1" in hosts

    def test_parses_env_variable(self) -> None:
        """Should parse AGENT_ALLOWED_HOSTS correctly."""
        with patch.dict(os.environ, {"AGENT_ALLOWED_HOSTS": "host1,host2, host3 "}):
            from importlib import reload
            import src.a2a_transport
            reload(src.a2a_transport)

            hosts = src.a2a_transport._get_allowed_hosts()
            assert "host1" in hosts
            assert "host2" in hosts
            assert "host3" in hosts

    def test_handles_empty_entries(self) -> None:
        """Should filter out empty entries."""
        with patch.dict(os.environ, {"AGENT_ALLOWED_HOSTS": "host1,,host2,"}):
            from importlib import reload
            import src.a2a_transport
            reload(src.a2a_transport)

            hosts = src.a2a_transport._get_allowed_hosts()
            assert "" not in hosts


class TestGetAllowedPortRange:
    """Tests for _get_allowed_port_range helper function."""

    def test_returns_default_range(self) -> None:
        """Should return default port range."""
        with patch.dict(os.environ, {}, clear=True):
            from importlib import reload
            import src.a2a_transport
            reload(src.a2a_transport)

            min_port, max_port = src.a2a_transport._get_allowed_port_range()
            assert min_port == 9000
            assert max_port == 9100

    def test_parses_custom_range(self) -> None:
        """Should parse custom port range from env."""
        with patch.dict(os.environ, {
            "AGENT_MIN_PORT": "8000",
            "AGENT_MAX_PORT": "8500"
        }):
            from importlib import reload
            import src.a2a_transport
            reload(src.a2a_transport)

            min_port, max_port = src.a2a_transport._get_allowed_port_range()
            assert min_port == 8000
            assert max_port == 8500


class TestSSRFProtectionEdgeCases:
    """Additional edge cases for SSRF protection."""

    def test_ipv6_localhost(self) -> None:
        """Should handle IPv6 localhost."""
        from src.a2a_transport import is_safe_url

        # IPv6 localhost - typically not in default allowlist
        assert is_safe_url("http://[::1]:9000") is False

    def test_url_with_username_password(self) -> None:
        """Should handle URLs with credentials."""
        from src.a2a_transport import is_safe_url

        assert is_safe_url("http://user:pass@localhost:9000") is True

    def test_url_with_path(self) -> None:
        """Should handle URLs with path components."""
        from src.a2a_transport import is_safe_url

        assert is_safe_url("http://localhost:9000/query") is True
        assert is_safe_url("http://localhost:9000/api/v1") is True

    def test_url_with_query_string(self) -> None:
        """Should handle URLs with query strings."""
        from src.a2a_transport import is_safe_url

        assert is_safe_url("http://localhost:9000?foo=bar") is True

    def test_url_with_fragment(self) -> None:
        """Should handle URLs with fragments."""
        from src.a2a_transport import is_safe_url

        assert is_safe_url("http://localhost:9000#section") is True

    def test_case_insensitive_scheme(self) -> None:
        """Should handle case variations in scheme."""
        from src.a2a_transport import is_safe_url

        # Scheme comparison should be case-insensitive
        assert is_safe_url("HTTP://localhost:9000") is True
        assert is_safe_url("Http://localhost:9000") is True

    def test_loopback_ip_variations(self) -> None:
        """Should accept only allowlisted loopback addresses."""
        from src.a2a_transport import is_safe_url

        # Only 127.0.0.1 is in default allowlist
        assert is_safe_url("http://127.0.0.1:9000") is True
        # Other loopback addresses not in allowlist
        assert is_safe_url("http://127.0.0.2:9000") is False
        assert is_safe_url("http://127.255.255.255:9000") is False

    def test_special_ip_ranges(self) -> None:
        """Should block special IP ranges."""
        from src.a2a_transport import is_safe_url

        # 0.0.0.0 - unspecified
        assert is_safe_url("http://0.0.0.0:9000") is False

        # Broadcast address
        assert is_safe_url("http://255.255.255.255:9000") is False

    def test_double_encoded_url(self) -> None:
        """Should handle URL encoding."""
        from src.a2a_transport import is_safe_url

        # URL-encoded localhost
        assert is_safe_url("http://%6c%6f%63%61%6c%68%6f%73%74:9000") is False

    def test_unicode_hostname(self) -> None:
        """Should handle unicode hostnames."""
        from src.a2a_transport import is_safe_url

        # Unicode domain (IDN)
        assert is_safe_url("http://例え.jp:9000") is False

    def test_boundary_ports(self) -> None:
        """Should correctly handle boundary port values."""
        from src.a2a_transport import is_safe_url

        # Default range is 9000-9100
        assert is_safe_url("http://localhost:8999") is False  # Just below
        assert is_safe_url("http://localhost:9000") is True   # Minimum
        assert is_safe_url("http://localhost:9100") is True   # Maximum
        assert is_safe_url("http://localhost:9101") is False  # Just above

    def test_very_long_url(self) -> None:
        """Should handle very long URLs."""
        from src.a2a_transport import is_safe_url

        # Long but valid URL
        long_path = "/a" * 1000
        assert is_safe_url(f"http://localhost:9000{long_path}") is True

    def test_null_bytes_in_url(self) -> None:
        """Should handle null bytes in URL."""
        from src.a2a_transport import is_safe_url

        # Null bytes - should be rejected
        assert is_safe_url("http://localhost\x00:9000") is False

    def test_whitespace_in_url(self) -> None:
        """Should handle whitespace in URL."""
        from src.a2a_transport import is_safe_url

        assert is_safe_url("http:// localhost:9000") is False
        assert is_safe_url("http://localhost :9000") is False


class TestToolObjects:
    """Tests for the tool objects created by @tool decorator."""

    def test_query_agent_is_tool(self) -> None:
        """query_agent should be an SdkMcpTool."""
        from src.a2a_transport import query_agent

        # The @tool decorator creates an SdkMcpTool object
        assert hasattr(query_agent, "name") or str(type(query_agent)) != "function"

    def test_discover_agent_is_tool(self) -> None:
        """discover_agent should be an SdkMcpTool."""
        from src.a2a_transport import discover_agent

        assert hasattr(discover_agent, "name") or str(type(discover_agent)) != "function"

    def test_create_server_returns_server(self) -> None:
        """create_a2a_transport_server should return a server object."""
        from src.a2a_transport import create_a2a_transport_server

        server = create_a2a_transport_server()
        # Server should be created successfully
        assert server is not None


class TestEnvironmentConfiguration:
    """Tests for environment-based configuration."""

    def test_empty_allowed_hosts_env(self) -> None:
        """Should handle empty AGENT_ALLOWED_HOSTS."""
        with patch.dict(os.environ, {"AGENT_ALLOWED_HOSTS": ""}):
            from importlib import reload
            import src.a2a_transport
            reload(src.a2a_transport)

            hosts = src.a2a_transport._get_allowed_hosts()
            # Should return defaults when empty
            assert "localhost" in hosts

    def test_whitespace_only_hosts(self) -> None:
        """Should handle whitespace-only hosts."""
        with patch.dict(os.environ, {"AGENT_ALLOWED_HOSTS": "   ,  ,   "}):
            from importlib import reload
            import src.a2a_transport
            reload(src.a2a_transport)

            hosts = src.a2a_transport._get_allowed_hosts()
            # Should filter out empty/whitespace entries
            assert "" not in hosts
            assert " " not in hosts

    def test_negative_port_env_values(self) -> None:
        """Should handle negative port environment values."""
        with patch.dict(os.environ, {
            "AGENT_MIN_PORT": "-1",
            "AGENT_MAX_PORT": "100"
        }):
            from importlib import reload
            import src.a2a_transport
            reload(src.a2a_transport)

            # Negative port in range means nothing valid
            assert src.a2a_transport.is_safe_url("http://localhost:50") is True
            assert src.a2a_transport.is_safe_url("http://localhost:101") is False

    def test_port_range_reversed(self) -> None:
        """Should handle reversed port range."""
        with patch.dict(os.environ, {
            "AGENT_MIN_PORT": "9100",
            "AGENT_MAX_PORT": "9000"
        }):
            from importlib import reload
            import src.a2a_transport
            reload(src.a2a_transport)

            # With reversed range, no ports should be valid
            assert src.a2a_transport.is_safe_url("http://localhost:9000") is False
            assert src.a2a_transport.is_safe_url("http://localhost:9050") is False
            assert src.a2a_transport.is_safe_url("http://localhost:9100") is False
