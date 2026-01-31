"""
SDK MCP A2A Transport Tool.

Provides query_agent tool for efficient HTTP-based A2A communication.
Based on evaluation_a2a_transport SDK implementation.
"""

import ipaddress
import logging
from typing import Any
from urllib.parse import urlparse

import httpx
from claude_agent_sdk import create_sdk_mcp_server, tool

from ..config import settings
from ..observability.semantic import get_current_agent_name, get_semantic_tracer
from ..observability.telemetry import inject_context, traced_operation
from .registry import get_agent_name_by_url

logger = logging.getLogger(__name__)


def is_safe_url(url: str) -> bool:
    """Validate URL is safe to request (SSRF protection).

    Args:
        url: URL to validate

    Returns:
        True if URL is safe to request, False otherwise
    """
    try:
        parsed = urlparse(url)

        # Must be http or https
        if parsed.scheme not in ("http", "https"):
            return False

        # Must have a hostname
        hostname = parsed.hostname
        if not hostname:
            return False

        allowed_hosts = settings.get_allowed_hosts_set()
        port_range = settings.get_port_range()

        # Check if it's an IP address
        try:
            ip = ipaddress.ip_address(hostname)
            # Block dangerous IP ranges (AWS metadata, link-local, etc.)
            if ip.is_link_local:  # 169.254.x.x - AWS metadata, etc.
                return False
            if ip.is_multicast:
                return False
            # For private/loopback IPs, must be in allowlist
            if ip.is_private or ip.is_loopback:
                if hostname not in allowed_hosts and str(ip) not in allowed_hosts:
                    return False
        except ValueError:
            # Not an IP address, it's a hostname
            if hostname not in allowed_hosts:
                return False

        # Check port
        port = parsed.port
        if port is None:
            port = 443 if parsed.scheme == "https" else 80
        if not (port_range[0] <= port <= port_range[1]):
            return False

        return True
    except Exception:
        return False


@tool(
    "query_agent",
    "Query another agent via A2A protocol",
    {"agent_url": str, "query": str},
)
async def query_agent(args: dict[str, Any]) -> dict[str, Any]:
    """Query another agent via direct HTTP POST to /query endpoint.

    Args:
        args: Dictionary containing:
            - agent_url: Base URL of the agent (e.g., "http://localhost:9001")
            - query: Question to ask the agent

    Returns:
        Dict with content array containing agent's response
    """
    agent_url = args.get("agent_url", "")
    query = args.get("query", "")

    if not agent_url:
        return {
            "content": [{"type": "text", "text": "Error: agent_url is required"}],
            "is_error": True,
        }

    if not query:
        return {
            "content": [{"type": "text", "text": "Error: query is required"}],
            "is_error": True,
        }

    # SSRF Protection: Validate URL before making request
    if not is_safe_url(agent_url):
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: Invalid or blocked agent URL. Only allowed hosts/ports permitted.",
                }
            ],
            "is_error": True,
        }

    # Semantic tracing for A2A message exchange
    semantic_tracer = get_semantic_tracer()

    # Get source agent from context (set by query_handling)
    source_agent = get_current_agent_name() or "unknown"

    # Resolve target agent name from URL (falls back to hostname:port if not found)
    target_agent = get_agent_name_by_url(agent_url) or urlparse(agent_url).netloc

    with semantic_tracer.a2a_message(
        source_agent=source_agent,
        target_agent=target_agent,
        query=query,
    ) as sem_span:
        # Trace the outgoing request
        with traced_operation("query_agent", {"agent.url": agent_url}):
            try:
                # Inject trace context into headers (both OTEL and semantic)
                headers = {"Content-Type": "application/json"}
                inject_context(headers)

                # Propagate semantic trace_id for cross-agent correlation
                trace_id = semantic_tracer.get_trace_id()
                if trace_id:
                    headers["X-Semantic-Trace-Id"] = trace_id

                async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
                    response = await client.post(
                        f"{agent_url}/query",
                        json={"query": query},
                        headers=headers,
                    )
                    response.raise_for_status()
                    result = response.json()

                    response_text = result.get("response", "No response")

                    # Record response on semantic span
                    semantic_tracer.record_a2a_response(
                        sem_span,
                        response=response_text,
                        status_code=response.status_code,
                    )

                    return {"content": [{"type": "text", "text": response_text}]}
            except httpx.TimeoutException:
                sem_span.status = "error"
                sem_span.error_message = "Request timed out"
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error: Request to {agent_url} timed out",
                        }
                    ],
                    "is_error": True,
                }
            except httpx.HTTPStatusError as e:
                sem_span.status = "error"
                sem_span.error_message = f"HTTP {e.response.status_code}"
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error: HTTP {e.response.status_code} from {agent_url}",
                        }
                    ],
                    "is_error": True,
                }
            except Exception as e:
                sem_span.status = "error"
                sem_span.error_message = str(e)
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error querying {agent_url}: {str(e)}",
                        }
                    ],
                    "is_error": True,
                }


@tool(
    "discover_agent", "Discover agent capabilities via A2A protocol", {"agent_url": str}
)
async def discover_agent(args: dict[str, Any]) -> dict[str, Any]:
    """Discover agent capabilities via /.well-known/agent-configuration endpoint.

    Args:
        args: Dictionary containing:
            - agent_url: Base URL of the agent (e.g., "http://localhost:9001")

    Returns:
        Dict with content array containing agent configuration
    """
    agent_url = args.get("agent_url", "")

    if not agent_url:
        return {
            "content": [{"type": "text", "text": "Error: agent_url is required"}],
            "is_error": True,
        }

    # SSRF Protection: Validate URL before making request
    if not is_safe_url(agent_url):
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: Invalid or blocked agent URL. Only allowed hosts/ports permitted.",
                }
            ],
            "is_error": True,
        }

    with traced_operation("discover_agent", {"agent.url": agent_url}):
        try:
            async with httpx.AsyncClient(timeout=settings.discovery_timeout) as client:
                response = await client.get(
                    f"{agent_url}/.well-known/agent-configuration"
                )
                response.raise_for_status()
                config = response.json()

                # Format the configuration nicely
                name = config.get("name", "Unknown")
                description = config.get("description", "No description")
                skills = config.get("skills", [])

                result_text = f"Agent: {name}\nDescription: {description}\n\nSkills:\n"
                for skill in skills:
                    skill_name = skill.get("name", "Unknown")
                    skill_desc = skill.get("description", "")
                    result_text += f"- {skill_name}: {skill_desc}\n"

                return {"content": [{"type": "text", "text": result_text}]}
        except Exception as e:
            return {
                "content": [
                    {"type": "text", "text": f"Error discovering {agent_url}: {str(e)}"}
                ],
                "is_error": True,
            }


def create_a2a_transport_server(name: str | None = None):
    """Create SDK MCP server with A2A transport tools.

    Args:
        name: Optional server name. If not provided, defaults to "a2a_transport".
              This name is used in tool naming: mcp__<name>__<tool_name>.
              For correct tool permissions, this should match the dictionary key
              used when registering the server (typically agent_name.lower().replace(" ", "_")).

    Returns:
        SDK MCP server configured with query_agent and discover_agent tools
    """
    server_name = name or "a2a_transport"
    return create_sdk_mcp_server(
        name=server_name, version="1.0.0", tools=[query_agent, discover_agent]
    )
