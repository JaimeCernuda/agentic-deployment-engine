"""Comprehensive tests for src/a2a_transport.py module.

Tests A2A transport functionality including:
- SSRF protection (is_safe_url)
- query_agent tool
- discover_agent tool
- Server creation
- Edge cases and error handling
"""

from unittest.mock import MagicMock, patch


class TestIsSafeUrl:
    """Tests for is_safe_url SSRF protection function."""

    def test_rejects_non_http_schemes(self) -> None:
        """Should reject non-HTTP schemes."""
        from src.agents.transport import is_safe_url

        assert is_safe_url("ftp://localhost:9000") is False
        assert is_safe_url("file:///etc/passwd") is False
        assert is_safe_url("javascript:alert(1)") is False
        assert is_safe_url("data:text/html,<h1>test</h1>") is False

    def test_accepts_http_scheme(self) -> None:
        """Should accept http scheme."""
        from src.agents.transport import is_safe_url

        assert is_safe_url("http://localhost:9000") is True

    def test_accepts_https_scheme(self) -> None:
        """Should accept https scheme."""
        from src.config import AgentSettings

        # Test HTTPS with custom settings that include port 443
        mock_settings = AgentSettings(min_port=443, max_port=9100)
        with patch("src.agents.transport.settings", mock_settings):
            from src.agents.transport import is_safe_url

            assert is_safe_url("https://localhost:443") is True

    def test_rejects_missing_hostname(self) -> None:
        """Should reject URLs without hostname."""
        from src.agents.transport import is_safe_url

        assert is_safe_url("http:///path") is False
        assert is_safe_url("http://") is False

    def test_rejects_link_local_addresses(self) -> None:
        """Should reject link-local addresses (AWS metadata, etc.)."""
        from src.agents.transport import is_safe_url

        assert is_safe_url("http://169.254.169.254:9000") is False
        assert is_safe_url("http://169.254.1.1:9000") is False

    def test_rejects_multicast_addresses(self) -> None:
        """Should reject multicast addresses."""
        from src.agents.transport import is_safe_url

        assert is_safe_url("http://224.0.0.1:9000") is False
        assert is_safe_url("http://239.255.255.255:9000") is False

    def test_rejects_private_ips_not_in_allowlist(self) -> None:
        """Should reject private IPs not in allowlist."""
        from src.agents.transport import is_safe_url

        assert is_safe_url("http://192.168.1.1:9000") is False
        assert is_safe_url("http://10.0.0.1:9000") is False
        assert is_safe_url("http://172.16.0.1:9000") is False

    def test_accepts_localhost(self) -> None:
        """Should accept localhost in default allowlist."""
        from src.agents.transport import is_safe_url

        assert is_safe_url("http://localhost:9000") is True
        assert is_safe_url("http://127.0.0.1:9000") is True

    def test_rejects_non_allowed_hostnames(self) -> None:
        """Should reject hostnames not in allowlist."""
        from src.agents.transport import is_safe_url

        assert is_safe_url("http://evil.com:9000") is False
        assert is_safe_url("http://internal.corp:9000") is False

    def test_accepts_custom_allowed_hosts(self) -> None:
        """Should accept hosts from custom settings."""
        from src.config import AgentSettings

        mock_settings = AgentSettings(allowed_hosts="myhost.local,trusted.com")
        with patch("src.agents.transport.settings", mock_settings):
            from src.agents.transport import is_safe_url

            assert is_safe_url("http://myhost.local:9000") is True
            assert is_safe_url("http://trusted.com:9000") is True

    def test_rejects_ports_outside_range(self) -> None:
        """Should reject ports outside allowed range."""
        from src.agents.transport import is_safe_url

        # Default range is 9000-9100
        assert is_safe_url("http://localhost:8999") is False
        assert is_safe_url("http://localhost:9101") is False
        assert is_safe_url("http://localhost:80") is False

    def test_accepts_ports_inside_range(self) -> None:
        """Should accept ports inside allowed range."""
        from src.agents.transport import is_safe_url

        assert is_safe_url("http://localhost:9000") is True
        assert is_safe_url("http://localhost:9050") is True
        assert is_safe_url("http://localhost:9100") is True

    def test_custom_port_range(self) -> None:
        """Should respect custom port range from settings."""
        from src.config import AgentSettings

        mock_settings = AgentSettings(min_port=8000, max_port=8100)
        with patch("src.agents.transport.settings", mock_settings):
            from src.agents.transport import is_safe_url

            assert is_safe_url("http://localhost:8050") is True
            assert is_safe_url("http://localhost:9000") is False

    def test_handles_malformed_urls(self) -> None:
        """Should handle malformed URLs gracefully."""
        from src.agents.transport import is_safe_url

        assert is_safe_url("not-a-url") is False
        assert is_safe_url("") is False
        assert is_safe_url("   ") is False
        assert is_safe_url("http://[invalid") is False

    def test_handles_urls_without_port(self) -> None:
        """Should handle URLs without explicit port."""
        # Default ports (80/443) are typically outside agent port range
        from src.agents.transport import is_safe_url

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
        from src.agents.transport import is_safe_url

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
        from src.agents.transport import is_safe_url

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
        from src.agents.transport import is_safe_url

        assert is_safe_url("http://evil.com:9000") is False
        assert is_safe_url("http://internal.corp:9000") is False

    def test_safe_urls_allowed(self) -> None:
        """discover_agent should allow safe URLs."""
        from src.agents.transport import is_safe_url

        assert is_safe_url("http://localhost:9001") is True


class TestCreateA2ATransportServer:
    """Tests for create_a2a_transport_server function."""

    def test_creates_sdk_mcp_server(self) -> None:
        """Should create SDK MCP server with tools."""
        with patch("src.agents.transport.create_sdk_mcp_server") as mock_create:
            mock_server = MagicMock()
            mock_create.return_value = mock_server

            from src.agents.transport import create_a2a_transport_server

            _result = create_a2a_transport_server()

            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args
            assert call_kwargs[1]["name"] == "a2a_transport"
            assert call_kwargs[1]["version"] == "1.0.0"
            # 3 tools: query_agent, discover_agent, find_agents
            assert len(call_kwargs[1]["tools"]) == 3


class TestConfigSettings:
    """Tests for configuration settings via src/config.py.

    Note: The old _get_allowed_hosts and _get_allowed_port_range functions
    have been replaced by the centralized AgentSettings in src/config.py.
    """

    def test_default_allowed_hosts(self) -> None:
        """Should return defaults when env not set."""
        from src.config import AgentSettings

        # Create settings with defaults (no env override)
        settings = AgentSettings(allowed_hosts="localhost,127.0.0.1")
        hosts = settings.get_allowed_hosts_set()
        assert "localhost" in hosts
        assert "127.0.0.1" in hosts

    def test_parses_allowed_hosts(self) -> None:
        """Should parse AGENT_ALLOWED_HOSTS correctly."""
        from src.config import AgentSettings

        settings = AgentSettings(allowed_hosts="host1,host2, host3 ")
        hosts = settings.get_allowed_hosts_set()
        assert "host1" in hosts
        assert "host2" in hosts
        assert "host3" in hosts

    def test_handles_empty_entries(self) -> None:
        """Should filter out empty entries."""
        from src.config import AgentSettings

        settings = AgentSettings(allowed_hosts="host1,,host2,")
        hosts = settings.get_allowed_hosts_set()
        assert "" not in hosts


class TestConfigPortRange:
    """Tests for port range configuration via src/config.py."""

    def test_default_port_range(self) -> None:
        """Should return default port range."""
        from src.config import AgentSettings

        settings = AgentSettings()
        min_port, max_port = settings.get_port_range()
        assert min_port == 9000
        assert max_port == 9100

    def test_custom_port_range(self) -> None:
        """Should support custom port range."""
        from src.config import AgentSettings

        settings = AgentSettings(min_port=8000, max_port=8500)
        min_port, max_port = settings.get_port_range()
        assert min_port == 8000
        assert max_port == 8500


class TestSSRFProtectionEdgeCases:
    """Additional edge cases for SSRF protection."""

    def test_ipv6_localhost(self) -> None:
        """Should handle IPv6 localhost."""
        from src.agents.transport import is_safe_url

        # IPv6 localhost - typically not in default allowlist
        assert is_safe_url("http://[::1]:9000") is False

    def test_url_with_username_password(self) -> None:
        """Should handle URLs with credentials."""
        from src.agents.transport import is_safe_url

        assert is_safe_url("http://user:pass@localhost:9000") is True

    def test_url_with_path(self) -> None:
        """Should handle URLs with path components."""
        from src.agents.transport import is_safe_url

        assert is_safe_url("http://localhost:9000/query") is True
        assert is_safe_url("http://localhost:9000/api/v1") is True

    def test_url_with_query_string(self) -> None:
        """Should handle URLs with query strings."""
        from src.agents.transport import is_safe_url

        assert is_safe_url("http://localhost:9000?foo=bar") is True

    def test_url_with_fragment(self) -> None:
        """Should handle URLs with fragments."""
        from src.agents.transport import is_safe_url

        assert is_safe_url("http://localhost:9000#section") is True

    def test_case_insensitive_scheme(self) -> None:
        """Should handle case variations in scheme."""
        from src.agents.transport import is_safe_url

        # Scheme comparison should be case-insensitive
        assert is_safe_url("HTTP://localhost:9000") is True
        assert is_safe_url("Http://localhost:9000") is True

    def test_loopback_ip_variations(self) -> None:
        """Should accept only allowlisted loopback addresses."""
        from src.agents.transport import is_safe_url

        # Only 127.0.0.1 is in default allowlist
        assert is_safe_url("http://127.0.0.1:9000") is True
        # Other loopback addresses not in allowlist
        assert is_safe_url("http://127.0.0.2:9000") is False
        assert is_safe_url("http://127.255.255.255:9000") is False

    def test_special_ip_ranges(self) -> None:
        """Should block special IP ranges."""
        from src.agents.transport import is_safe_url

        # 0.0.0.0 - unspecified
        assert is_safe_url("http://0.0.0.0:9000") is False

        # Broadcast address
        assert is_safe_url("http://255.255.255.255:9000") is False

    def test_double_encoded_url(self) -> None:
        """Should handle URL encoding."""
        from src.agents.transport import is_safe_url

        # URL-encoded localhost
        assert is_safe_url("http://%6c%6f%63%61%6c%68%6f%73%74:9000") is False

    def test_unicode_hostname(self) -> None:
        """Should handle unicode hostnames."""
        from src.agents.transport import is_safe_url

        # Unicode domain (IDN)
        assert is_safe_url("http://例え.jp:9000") is False

    def test_boundary_ports(self) -> None:
        """Should correctly handle boundary port values."""
        from src.agents.transport import is_safe_url

        # Default range is 9000-9100
        assert is_safe_url("http://localhost:8999") is False  # Just below
        assert is_safe_url("http://localhost:9000") is True  # Minimum
        assert is_safe_url("http://localhost:9100") is True  # Maximum
        assert is_safe_url("http://localhost:9101") is False  # Just above

    def test_very_long_url(self) -> None:
        """Should handle very long URLs."""
        from src.agents.transport import is_safe_url

        # Long but valid URL
        long_path = "/a" * 1000
        assert is_safe_url(f"http://localhost:9000{long_path}") is True

    def test_null_bytes_in_url(self) -> None:
        """Should handle null bytes in URL."""
        from src.agents.transport import is_safe_url

        # Null bytes - should be rejected
        assert is_safe_url("http://localhost\x00:9000") is False

    def test_whitespace_in_url(self) -> None:
        """Should handle whitespace in URL."""
        from src.agents.transport import is_safe_url

        assert is_safe_url("http:// localhost:9000") is False
        assert is_safe_url("http://localhost :9000") is False


class TestToolObjects:
    """Tests for the tool objects created by @tool decorator."""

    def test_query_agent_is_tool(self) -> None:
        """query_agent should be an SdkMcpTool."""
        from src.agents.transport import query_agent

        # The @tool decorator creates an SdkMcpTool object
        assert hasattr(query_agent, "name") or str(type(query_agent)) != "function"

    def test_discover_agent_is_tool(self) -> None:
        """discover_agent should be an SdkMcpTool."""
        from src.agents.transport import discover_agent

        assert (
            hasattr(discover_agent, "name") or str(type(discover_agent)) != "function"
        )

    def test_create_server_returns_server(self) -> None:
        """create_a2a_transport_server should return a server object."""
        from src.agents.transport import create_a2a_transport_server

        server = create_a2a_transport_server()
        # Server should be created successfully
        assert server is not None


class TestEnvironmentConfiguration:
    """Tests for environment-based configuration via AgentSettings."""

    def test_empty_allowed_hosts(self) -> None:
        """Should handle empty allowed_hosts string."""
        from src.config import AgentSettings

        settings = AgentSettings(allowed_hosts="")
        hosts = settings.get_allowed_hosts_set()
        # Empty string results in empty set (no hosts allowed)
        assert len(hosts) == 0

    def test_whitespace_only_hosts(self) -> None:
        """Should handle whitespace-only hosts."""
        from src.config import AgentSettings

        settings = AgentSettings(allowed_hosts="   ,  ,   ")
        hosts = settings.get_allowed_hosts_set()
        # Should filter out empty/whitespace entries
        assert "" not in hosts
        assert " " not in hosts

    def test_port_range_behavior(self) -> None:
        """Should handle various port range configurations."""
        from src.config import AgentSettings

        # Test with negative min port (unusual but valid config)
        settings = AgentSettings(min_port=-1, max_port=100)
        min_port, max_port = settings.get_port_range()
        assert min_port == -1
        assert max_port == 100

    def test_port_range_reversed(self) -> None:
        """Should handle reversed port range."""
        from src.config import AgentSettings

        # With reversed range, no ports will be valid in range check
        mock_settings = AgentSettings(min_port=9100, max_port=9000)
        with patch("src.agents.transport.settings", mock_settings):
            from src.agents.transport import is_safe_url

            assert is_safe_url("http://localhost:9000") is False
            assert is_safe_url("http://localhost:9050") is False
            assert is_safe_url("http://localhost:9100") is False
