# Building agents

This guide teaches you how to create agents using the Claude Agent SDK with MCP tools and A2A protocol integration.

## Overview

Each agent in this framework consists of:

1. **MCP SDK tools** - Python functions that Claude can call
2. **MCP server** - Packages tools for the agent
3. **Agent class** - Inherits from `BaseA2AAgent`
4. **Entry point** - Script in `pyproject.toml`

## Quick example

Here's a minimal agent that provides weather information:

```python
# examples/tools/weather_tools.py
from claude_agent_sdk import tool

@tool("get_weather", "Get current weather for a location", {"location": str})
async def get_weather(args):
    location = args.get("location", "").lower()
    return {
        "content": [{
            "type": "text",
            "text": f"Weather in {location}: 22°C, Sunny"
        }]
    }
```

```python
# examples/agents/weather_agent.py
from src import BaseA2AAgent
from claude_agent_sdk import create_sdk_mcp_server
from examples.tools.weather_tools import get_weather

class WeatherAgent(BaseA2AAgent):
    def __init__(self, port: int = 9001):
        server = create_sdk_mcp_server(
            name="weather_agent",
            version="1.0.0",
            tools=[get_weather]
        )

        super().__init__(
            name="Weather Agent",
            description="Provides weather information",
            port=port,
            sdk_mcp_server=server,
            system_prompt="You are a Weather Agent. Use mcp__weather_agent__get_weather to answer weather queries."
        )

    def _get_skills(self) -> list:
        return [{
            "id": "weather_query",
            "name": "Weather Query",
            "description": "Get current weather"
        }]

    def _get_allowed_tools(self) -> list[str]:
        return ["mcp__weather_agent__get_weather"]

def main():
    agent = WeatherAgent()
    agent.run()

if __name__ == "__main__":
    main()
```

## Creating MCP tools

Tools are async Python functions decorated with `@tool`:

```python
from claude_agent_sdk import tool

@tool(
    "tool_name",           # Unique identifier
    "Tool description",    # What it does (shown to Claude)
    {"param": str}         # Input schema
)
async def my_tool(args: dict) -> dict:
    # Extract parameters
    param = args.get("param")

    # Your logic here
    result = f"Processed: {param}"

    # Return in MCP format
    return {
        "content": [{
            "type": "text",
            "text": result
        }]
    }
```

### Input schemas

```python
# Simple types
{"location": str}
{"count": int}
{"temperature": float}
{"enabled": bool}

# Multiple parameters
{"origin": str, "destination": str}

# Complex schema (JSON Schema format)
{
    "type": "object",
    "properties": {
        "location": {"type": "string"},
        "radius": {"type": "number", "minimum": 0}
    },
    "required": ["location"]
}
```

### Error handling

Return errors with `is_error: True`:

```python
@tool("divide", "Divide two numbers", {"a": float, "b": float})
async def divide(args):
    b = args.get("b")
    if b == 0:
        return {
            "content": [{"type": "text", "text": "Error: Division by zero"}],
            "is_error": True
        }
    return {
        "content": [{"type": "text", "text": f"Result: {args['a'] / b}"}]
    }
```

### Tool naming convention

When registered with an MCP server, tools become:

```
mcp__<server_name>__<tool_name>
```

Examples:
- Server: `weather_agent`, Tool: `get_weather` → `mcp__weather_agent__get_weather`
- Server: `maps_agent`, Tool: `get_distance` → `mcp__maps_agent__get_distance`

## Creating the agent class

Inherit from `BaseA2AAgent` and implement required methods:

```python
from src import BaseA2AAgent
from claude_agent_sdk import create_sdk_mcp_server

class MyAgent(BaseA2AAgent):
    def __init__(self, port: int = 9003):
        # Create MCP server with tools
        server = create_sdk_mcp_server(
            name="my_agent",  # Must match naming convention
            version="1.0.0",
            tools=[tool1, tool2]
        )

        # System prompt guides Claude's behavior
        system_prompt = """You are My Agent.

        Use these MCP tools:
        - mcp__my_agent__tool1: Description
        - mcp__my_agent__tool2: Description

        DO NOT use Bash or generate code - only use the tools."""

        super().__init__(
            name="My Agent",
            description="What this agent does",
            port=port,
            sdk_mcp_server=server,
            system_prompt=system_prompt
        )

    def _get_skills(self) -> list:
        """Define A2A capabilities for discovery."""
        return [{
            "id": "my_skill",
            "name": "My Skill",
            "description": "What this skill does",
            "tags": ["tag1"],
            "examples": ["Example query"]
        }]

    def _get_allowed_tools(self) -> list[str]:
        """List tools Claude can use."""
        return [
            "mcp__my_agent__tool1",
            "mcp__my_agent__tool2"
        ]
```

### System prompt guidelines

A good system prompt:

1. Identifies the agent's role
2. Lists all MCP tools with full names
3. Provides usage instructions
4. Explicitly forbids workarounds

```python
system_prompt = """You are a SLURM Agent specialized in HPC job management.

**Available MCP tools:**
- `mcp__slurm_agent__submit_job`: Submit a job to SLURM
- `mcp__slurm_agent__check_status`: Check job status

**DO NOT:**
- Use the Bash tool to run sbatch directly
- Generate Python code to interact with SLURM
- Make assumptions - always check with tools

**ALWAYS:**
- Use the MCP tools for all SLURM operations
- Validate parameters before calling tools
"""
```

## Adding the entry point

In `pyproject.toml`:

```toml
[project.scripts]
my-agent = "examples.agents.my_agent:main"
```

Then run with:

```bash
uv run my-agent
```

## A2A protocol endpoints

Every agent automatically exposes:

### Health endpoint
```
GET /health
→ {"status": "healthy", "agent": "My Agent"}
```

### Discovery endpoint
```
GET /.well-known/agent-configuration
→ {
    "name": "My Agent",
    "description": "...",
    "skills": [...],
    ...
  }
```

### Query endpoint
```
POST /query
Content-Type: application/json
{"query": "Your question"}
→ {"response": "Agent's answer"}
```

## Creating a coordinator agent

Coordinators use the A2A transport to query other agents:

```python
from src import BaseA2AAgent
from src.agents.transport import create_a2a_transport

class ControllerAgent(BaseA2AAgent):
    def __init__(self, port: int = 9000):
        # Create A2A transport for agent communication
        a2a_server = create_a2a_transport()

        super().__init__(
            name="Controller Agent",
            description="Multi-agent coordinator",
            port=port,
            sdk_mcp_server=a2a_server,
            system_prompt="""You coordinate other agents.

            Use mcp__a2a_transport__query_agent to query agents:
            - Weather: http://localhost:9001
            - Maps: http://localhost:9002
            """
        )

    def _get_allowed_tools(self) -> list[str]:
        return [
            "mcp__a2a_transport__query_agent",
            "mcp__a2a_transport__discover_agent"
        ]
```

## Testing your agent

### Unit test tools

```python
# tests/unit/test_my_tools.py
import pytest
from examples.tools.my_tools import my_tool

@pytest.mark.asyncio
async def test_my_tool():
    result = await my_tool({"param": "value"})
    assert "content" in result
    assert result["content"][0]["type"] == "text"
```

### Integration test agent

```python
# tests/integration/test_my_agent.py
import pytest
import httpx

@pytest.mark.asyncio
async def test_agent_health():
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:9003/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

@pytest.mark.asyncio
async def test_agent_query():
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "http://localhost:9003/query",
            json={"query": "test query"}
        )
        assert response.status_code == 200
```

### Verify tool usage in logs

```bash
# Check that tools are being called
grep "Tool: mcp__my_agent" src/logs/my_agent.log

# Verify tool inputs
grep "Input:" src/logs/my_agent.log | tail -5
```

## Common patterns

### External API tool

```python
import httpx

@tool("fetch_data", "Fetch from API", {"endpoint": str})
async def fetch_data(args):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(args["endpoint"])
            response.raise_for_status()
            return {
                "content": [{"type": "text", "text": str(response.json())}]
            }
        except Exception as e:
            return {
                "content": [{"type": "text", "text": f"Error: {e}"}],
                "is_error": True
            }
```

### File operations tool

```python
from pathlib import Path

@tool("read_file", "Read file contents", {"path": str})
async def read_file(args):
    path = Path(args["path"])
    if not path.exists():
        return {
            "content": [{"type": "text", "text": f"File not found: {path}"}],
            "is_error": True
        }
    return {
        "content": [{"type": "text", "text": path.read_text()}]
    }
```

### Tool with state

```python
_cache = {}

@tool("cache_set", "Set cache value", {"key": str, "value": str})
async def cache_set(args):
    _cache[args["key"]] = args["value"]
    return {"content": [{"type": "text", "text": "Cached"}]}

@tool("cache_get", "Get cache value", {"key": str})
async def cache_get(args):
    value = _cache.get(args["key"], "Not found")
    return {"content": [{"type": "text", "text": value}]}
```

## Best practices

### Tool design
- One tool = one responsibility
- Clear, descriptive names
- Comprehensive error handling
- Return structured data

### System prompts
- List all tools with full names
- Provide usage examples
- Explicitly forbid workarounds
- Define expected behavior

### Testing
- Test tools independently
- Test agent endpoints
- Verify MCP tools are called (check logs)
- Test A2A communication

## Troubleshooting

### Tool not being called

Check:
1. Tool name in `_get_allowed_tools()` matches `mcp__<server>__<tool>`
2. System prompt mentions the tool
3. Server name matches `name.lower().replace(" ", "_")`
4. Tool is in the `tools` list when creating server

### Agent not responding to A2A

Check:
1. Port is not blocked
2. Agent is running: `curl http://localhost:PORT/health`
3. Discovery works: `curl http://localhost:PORT/.well-known/agent-configuration`

### MCP server not connecting

Check:
1. SDK MCP server is passed to `super().__init__()`
2. Server name follows naming convention
3. Tools are decorated with `@tool`
4. Tools return correct format

## See also

- [Architecture](architecture.md) - System design patterns
- [MCP transport](mcp-transport.md) - Transport internals
- [Testing](testing.md) - Test guide
- [Configuration](configuration.md) - Settings reference
