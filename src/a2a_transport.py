"""
SDK MCP A2A Transport Tool.

Provides query_agent tool for efficient HTTP-based A2A communication.
Based on evaluation_a2a_transport SDK implementation.
"""
from claude_agent_sdk import tool, create_sdk_mcp_server
import httpx
from typing import Dict, Any


@tool("query_agent", "Query another agent via A2A protocol", {"agent_url": str, "query": str})
async def query_agent(args: Dict[str, Any]) -> Dict[str, Any]:
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
            "content": [{
                "type": "text",
                "text": "Error: agent_url is required"
            }],
            "is_error": True
        }

    if not query:
        return {
            "content": [{
                "type": "text",
                "text": "Error: query is required"
            }],
            "is_error": True
        }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{agent_url}/query",
                json={"query": query}
            )
            response.raise_for_status()
            result = response.json()

            return {
                "content": [{
                    "type": "text",
                    "text": result.get("response", "No response")
                }]
            }
    except httpx.TimeoutException:
        return {
            "content": [{
                "type": "text",
                "text": f"Error: Request to {agent_url} timed out"
            }],
            "is_error": True
        }
    except httpx.HTTPStatusError as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error: HTTP {e.response.status_code} from {agent_url}"
            }],
            "is_error": True
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error querying {agent_url}: {str(e)}"
            }],
            "is_error": True
        }


@tool("discover_agent", "Discover agent capabilities via A2A protocol", {"agent_url": str})
async def discover_agent(args: Dict[str, Any]) -> Dict[str, Any]:
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
            "content": [{
                "type": "text",
                "text": "Error: agent_url is required"
            }],
            "is_error": True
        }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
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

            return {
                "content": [{
                    "type": "text",
                    "text": result_text
                }]
            }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error discovering {agent_url}: {str(e)}"
            }],
            "is_error": True
        }


def create_a2a_transport_server():
    """Create SDK MCP server with A2A transport tools.

    Returns:
        SDK MCP server configured with query_agent and discover_agent tools
    """
    return create_sdk_mcp_server(
        name="a2a_transport",
        version="1.0.0",
        tools=[query_agent, discover_agent]
    )
