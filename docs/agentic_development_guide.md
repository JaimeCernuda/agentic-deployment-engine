# Agentic Development Guide
## Building Multi-Agent Systems with Claude Agent SDK & A2A Protocol

This guide teaches you how to create sophisticated agents using the Claude Agent SDK with MCP tools and A2A protocol integration. After reading this, you'll be able to build new agents by asking Claude: *"With the knowledge of @agentic_development_guide.md, can you create an agent that has access to an SLURM MCP?"*

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Agent Anatomy](#agent-anatomy)
3. [Creating MCP SDK Tools](#creating-mcp-sdk-tools)
4. [Building a Base Agent](#building-a-base-agent)
5. [A2A Protocol Integration](#a2a-protocol-integration)
6. [Complete Examples](#complete-examples)
7. [Step-by-Step Agent Creation](#step-by-step-agent-creation)
8. [Testing Your Agent](#testing-your-agent)

---

## Architecture Overview

### The Multi-Agent Ecosystem

Our system uses three key technologies:

1. **Claude Agent SDK** - Python SDK for creating agents powered by Claude
2. **MCP SDK Tools** - In-process Python functions that agents can call
3. **A2A Protocol** - HTTP-based communication between agents

```
┌─────────────────────────────────────────────────────────┐
│                   Your Agent System                      │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────┐     ┌──────────────┐                  │
│  │ Weather Agent│     │  Maps Agent  │                  │
│  │ Port: 9001   │     │ Port: 9002   │                  │
│  ├──────────────┤     ├──────────────┤                  │
│  │ MCP SDK Tools│     │ MCP SDK Tools│                  │
│  │ - get_weather│     │ - get_distance│                 │
│  │ - get_locations│   │ - get_cities │                  │
│  └──────┬───────┘     └──────┬───────┘                  │
│         │                    │                           │
│         │    A2A Protocol    │                           │
│         │   (HTTP + JSON)    │                           │
│         │                    │                           │
│  ┌──────┴────────────────────┴───────┐                  │
│  │      Controller Agent              │                  │
│  │      Port: 9000                    │                  │
│  │      Uses: Bash + curl             │                  │
│  └────────────────────────────────────┘                  │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

### Component Layers

1. **MCP Tools Layer** - Python functions decorated with `@tool`
2. **Agent Layer** - FastAPI servers with Claude SDK integration
3. **A2A Layer** - HTTP endpoints for agent discovery and communication

---

## Agent Anatomy

Every agent has four essential components:

### 1. MCP SDK Tools (Optional for base agents)

Python functions that Claude can call:

```python
from claude_agent_sdk import tool

@tool("get_weather", "Get current weather for a location", {"location": str, "units": str})
async def get_weather(args):
    """Tool implementation - this runs in-process."""
    location = args.get("location", "").lower()
    # Your logic here
    return {
        "content": [{
            "type": "text",
            "text": f"Weather in {location}: 22°C, Sunny"
        }]
    }
```

### 2. MCP Server Registration

Tools are packaged into an SDK MCP server:

```python
from claude_agent_sdk import create_sdk_mcp_server

weather_server = create_sdk_mcp_server(
    name="weather_agent",  # Must match agent name pattern
    version="1.0.0",
    tools=[get_weather, get_locations]  # List of @tool decorated functions
)
```

### 3. Agent Class

Inherits from `BaseA2AAgent` and configures everything:

```python
from src.base_a2a_agent import BaseA2AAgent

class WeatherAgent(BaseA2AAgent):
    def __init__(self, port: int = 9001):
        # Custom system prompt
        system_prompt = """You are a Weather Agent.

        You MUST use these MCP SDK tools:
        - mcp__weather_agent__get_weather
        - mcp__weather_agent__get_locations

        DO NOT use Bash or generate code - only use the tools."""

        super().__init__(
            name="Weather Agent",
            description="Provides weather information",
            port=port,
            sdk_mcp_server=weather_server,  # Attach MCP server
            system_prompt=system_prompt
        )

    def _get_skills(self):
        """Define A2A capabilities."""
        return [{
            "id": "weather_query",
            "name": "Weather Query",
            "description": "Get current weather",
            "tags": ["weather"],
            "examples": ["What's the weather in Tokyo?"]
        }]

    def _get_allowed_tools(self):
        """List tools Claude can use."""
        return [
            "mcp__weather_agent__get_weather",
            "mcp__weather_agent__get_locations"
        ]
```

### 4. Entry Point

```python
def main():
    agent = WeatherAgent()
    print("Starting Weather Agent on port 9001...")
    agent.run()

if __name__ == "__main__":
    main()
```

---

## Creating MCP SDK Tools

### Tool Definition Pattern

```python
from claude_agent_sdk import tool
from typing import Dict, Any

@tool(
    "tool_name",           # Unique identifier
    "Tool description",    # What it does (for Claude)
    {"param": type}        # Input schema
)
async def tool_function(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tool implementation.

    Args:
        args: Dictionary with parameters from input schema

    Returns:
        Dictionary with 'content' key containing response
    """
    # Extract parameters
    param_value = args.get("param")

    # Your logic here
    result = f"Processed: {param_value}"

    # Return in MCP format
    return {
        "content": [{
            "type": "text",
            "text": result
        }]
    }
```

### Input Schema Types

```python
# Simple types
{"location": str}
{"temperature": float}
{"count": int}
{"enabled": bool}

# Multiple parameters
{
    "origin": str,
    "destination": str,
    "units": str
}

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

### Error Handling in Tools

```python
@tool("divide", "Divide two numbers", {"a": float, "b": float})
async def divide(args):
    a = args.get("a")
    b = args.get("b")

    if b == 0:
        return {
            "content": [{
                "type": "text",
                "text": "Error: Division by zero"
            }],
            "is_error": True
        }

    return {
        "content": [{
            "type": "text",
            "text": f"Result: {a / b}"
        }]
    }
```

### Tool Naming Convention

When tools are registered with an SDK MCP server, they become:

```
mcp__<server_name>__<tool_name>

Examples:
- Server: "weather_agent", Tool: "get_weather" → "mcp__weather_agent__get_weather"
- Server: "slurm_agent", Tool: "submit_job" → "mcp__slurm_agent__submit_job"
```

**Important**: The server name must match `self.name.lower().replace(" ", "_")` in your agent class.

---

## Building a Base Agent

### The BaseA2AAgent Class

Located in `src/base_a2a_agent.py`, this provides:
- FastAPI server setup
- Claude SDK client management
- A2A discovery endpoints
- Logging infrastructure

### Required Methods

```python
class YourAgent(BaseA2AAgent):
    def _get_skills(self) -> List[Dict[str, Any]]:
        """Define what this agent can do (for A2A discovery)."""
        return [{
            "id": "unique_skill_id",
            "name": "Human Readable Name",
            "description": "What this skill does",
            "tags": ["tag1", "tag2"],
            "examples": [
                "Example query 1",
                "Example query 2"
            ]
        }]

    def _get_allowed_tools(self) -> List[str]:
        """List all tools this agent can use."""
        return [
            "mcp__your_agent__tool1",
            "mcp__your_agent__tool2",
            # Or for coordination agents:
            "Bash"  # For curl commands
        ]
```

### System Prompt Guidelines

A good system prompt:

1. **Identifies the agent's role**
2. **Lists available MCP tools with full names**
3. **Provides usage instructions**
4. **Explicitly forbids workarounds**

```python
system_prompt = """You are a SLURM Agent specialized in HPC job management.

**IMPORTANT: You MUST use the SDK MCP tools available to you:**
- `mcp__slurm_agent__submit_job`: Submit a job to SLURM
- `mcp__slurm_agent__check_status`: Check job status
- `mcp__slurm_agent__cancel_job`: Cancel a running job
- `mcp__slurm_agent__list_queues`: List available queues

**How to respond to queries:**
1. When asked to submit a job, use mcp__slurm_agent__submit_job
2. When asked about job status, use mcp__slurm_agent__check_status
3. Always validate job IDs before operations

**DO NOT:**
- Use the Bash tool to run sbatch, squeue, or scancel directly
- Try to SSH or connect to clusters manually
- Generate Python code to interact with SLURM
- Make assumptions about job status - always check with tools

**ALWAYS:**
- Use the MCP tools for all SLURM operations
- Validate parameters before calling tools
- Provide clear feedback from tool results
"""
```

---

## A2A Protocol Integration

### Discovery Endpoint

Every agent automatically exposes:

```
GET /.well-known/agent-configuration
```

Returns:
```json
{
    "name": "Weather Agent",
    "description": "Provides weather information",
    "url": "http://localhost:9001",
    "version": "1.0.0",
    "capabilities": {
        "streaming": true,
        "push_notifications": false
    },
    "default_input_modes": ["text"],
    "default_output_modes": ["text"],
    "skills": [
        {
            "id": "weather_query",
            "name": "Weather Query",
            "description": "Get current weather",
            "tags": ["weather"],
            "examples": ["What's the weather in Tokyo?"]
        }
    ]
}
```

### Query Endpoint

```
POST /query
Content-Type: application/json

{
    "query": "What's the weather in Tokyo?",
    "context": {}  // Optional
}
```

Response:
```json
{
    "response": "The current weather in Tokyo is 22.5°C with partly cloudy skies..."
}
```

### Health Endpoint

```
GET /health
```

Returns:
```json
{
    "status": "healthy",
    "agent": "Weather Agent"
}
```

### Creating a Coordinator Agent

Coordinator agents use curl to communicate with other agents:

```python
class ControllerAgent(BaseA2AAgent):
    def __init__(self, port: int = 9000):
        system_prompt = """You are a Controller Agent.

        Available agents:
        - Weather Agent: http://localhost:9001
        - Maps Agent: http://localhost:9002

        Use curl to query agents:
        curl -X POST http://localhost:9001/query -H "Content-Type: application/json" -d '{"query": "your query"}'

        You have access to the Bash tool for curl commands."""

        super().__init__(
            name="Controller Agent",
            description="Multi-agent coordinator",
            port=port,
            sdk_mcp_server=None,  # No MCP tools, uses Bash
            system_prompt=system_prompt
        )

    def _get_allowed_tools(self):
        return ["Bash"]  # For curl commands
```

---

## Complete Examples

### Example 1: Database Agent

```python
# File: tools/database_tools.py
from claude_agent_sdk import tool
import sqlite3

@tool("query_db", "Execute SELECT query", {"sql": str})
async def query_db(args):
    """Execute a SELECT query on the database."""
    sql = args.get("sql", "")

    # Validate it's a SELECT
    if not sql.strip().upper().startswith("SELECT"):
        return {
            "content": [{"type": "text", "text": "Error: Only SELECT queries allowed"}],
            "is_error": True
        }

    try:
        # Execute query (in real implementation, use proper connection pooling)
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(sql)
        results = cursor.fetchall()
        conn.close()

        return {
            "content": [{
                "type": "text",
                "text": f"Query results: {results}"
            }]
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {str(e)}"}],
            "is_error": True
        }

@tool("list_tables", "List all tables", {})
async def list_tables(args):
    """List all tables in the database."""
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()

    return {
        "content": [{
            "type": "text",
            "text": f"Tables: {', '.join(tables)}"
        }]
    }
```

```python
# File: agents/database_agent.py
from claude_agent_sdk import create_sdk_mcp_server
from src.base_a2a_agent import BaseA2AAgent
from tools.database_tools import query_db, list_tables

class DatabaseAgent(BaseA2AAgent):
    def __init__(self, port: int = 9003):
        db_server = create_sdk_mcp_server(
            name="database_agent",
            version="1.0.0",
            tools=[query_db, list_tables]
        )

        system_prompt = """You are a Database Agent.

        MCP SDK Tools:
        - mcp__database_agent__query_db: Execute SELECT queries
        - mcp__database_agent__list_tables: List all tables

        Always use these tools - never write SQL code directly."""

        super().__init__(
            name="Database Agent",
            description="SQL database query agent",
            port=port,
            sdk_mcp_server=db_server,
            system_prompt=system_prompt
        )

    def _get_skills(self):
        return [{
            "id": "database_query",
            "name": "Database Query",
            "description": "Query SQL database",
            "tags": ["database", "sql"],
            "examples": ["Show me all users", "List tables"]
        }]

    def _get_allowed_tools(self):
        return [
            "mcp__database_agent__query_db",
            "mcp__database_agent__list_tables"
        ]

def main():
    agent = DatabaseAgent()
    agent.run()

if __name__ == "__main__":
    main()
```

### Example 2: SLURM HPC Agent

```python
# File: tools/slurm_tools.py
from claude_agent_sdk import tool
import subprocess

@tool("submit_job", "Submit job to SLURM", {
    "script_path": str,
    "job_name": str,
    "partition": str
})
async def submit_job(args):
    """Submit a job to SLURM cluster."""
    script_path = args.get("script_path")
    job_name = args.get("job_name")
    partition = args.get("partition", "general")

    cmd = f"sbatch --job-name={job_name} --partition={partition} {script_path}"

    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            # Extract job ID from output
            output = result.stdout.strip()
            return {
                "content": [{
                    "type": "text",
                    "text": f"Job submitted successfully: {output}"
                }]
            }
        else:
            return {
                "content": [{
                    "type": "text",
                    "text": f"Error submitting job: {result.stderr}"
                }],
                "is_error": True
            }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {str(e)}"}],
            "is_error": True
        }

@tool("check_status", "Check job status", {"job_id": str})
async def check_status(args):
    """Check the status of a SLURM job."""
    job_id = args.get("job_id")

    cmd = f"squeue -j {job_id}"

    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return {
            "content": [{
                "type": "text",
                "text": f"Job status:\n{result.stdout}"
            }]
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {str(e)}"}],
            "is_error": True
        }

@tool("list_queues", "List available queues", {})
async def list_queues(args):
    """List all available SLURM partitions."""
    cmd = "sinfo -o '%P'"

    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return {
            "content": [{
                "type": "text",
                "text": f"Available queues:\n{result.stdout}"
            }]
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {str(e)}"}],
            "is_error": True
        }
```

```python
# File: agents/slurm_agent.py
from claude_agent_sdk import create_sdk_mcp_server
from src.base_a2a_agent import BaseA2AAgent
from tools.slurm_tools import submit_job, check_status, list_queues

class SlurmAgent(BaseA2AAgent):
    def __init__(self, port: int = 9004):
        slurm_server = create_sdk_mcp_server(
            name="slurm_agent",
            version="1.0.0",
            tools=[submit_job, check_status, list_queues]
        )

        system_prompt = """You are a SLURM Agent for HPC job management.

        MCP SDK Tools:
        - mcp__slurm_agent__submit_job: Submit jobs (requires script_path, job_name, partition)
        - mcp__slurm_agent__check_status: Check job status (requires job_id)
        - mcp__slurm_agent__list_queues: List available partitions

        DO NOT use Bash to run sbatch, squeue, or other SLURM commands.
        ALWAYS use the MCP tools above."""

        super().__init__(
            name="SLURM Agent",
            description="HPC job management via SLURM",
            port=port,
            sdk_mcp_server=slurm_server,
            system_prompt=system_prompt
        )

    def _get_skills(self):
        return [
            {
                "id": "job_submission",
                "name": "Job Submission",
                "description": "Submit jobs to SLURM",
                "tags": ["slurm", "hpc", "submit"],
                "examples": ["Submit my job script", "Run job on GPU partition"]
            },
            {
                "id": "job_monitoring",
                "name": "Job Monitoring",
                "description": "Check job status",
                "tags": ["slurm", "status"],
                "examples": ["Check job 12345", "What's the status of my job?"]
            }
        ]

    def _get_allowed_tools(self):
        return [
            "mcp__slurm_agent__submit_job",
            "mcp__slurm_agent__check_status",
            "mcp__slurm_agent__list_queues"
        ]

def main():
    agent = SlurmAgent()
    print("Starting SLURM Agent on port 9004...")
    agent.run()

if __name__ == "__main__":
    main()
```

---

## Step-by-Step Agent Creation

Follow these steps to create a new agent:

### Step 1: Define Your Tools

Create `tools/your_tools.py`:

```python
from claude_agent_sdk import tool

@tool("your_tool_name", "Description", {"param": str})
async def your_tool(args):
    # Implementation
    return {
        "content": [{"type": "text", "text": "result"}]
    }
```

### Step 2: Create Agent Class

Create `agents/your_agent.py`:

```python
from claude_agent_sdk import create_sdk_mcp_server
from src.base_a2a_agent import BaseA2AAgent
from tools.your_tools import your_tool

class YourAgent(BaseA2AAgent):
    def __init__(self, port: int = 9005):
        server = create_sdk_mcp_server(
            name="your_agent",  # Must match name pattern
            version="1.0.0",
            tools=[your_tool]
        )

        system_prompt = """..."""

        super().__init__(
            name="Your Agent",
            description="...",
            port=port,
            sdk_mcp_server=server,
            system_prompt=system_prompt
        )

    def _get_skills(self):
        return [...]

    def _get_allowed_tools(self):
        return ["mcp__your_agent__your_tool_name"]
```

### Step 3: Add Entry Point

In `pyproject.toml`:

```toml
[project.scripts]
your-agent = "agents.your_agent:main"
```

Add main function to agent file:

```python
def main():
    agent = YourAgent()
    print(f"Starting Your Agent on port 9005...")
    agent.run()

if __name__ == "__main__":
    main()
```

### Step 4: Update Package Structure

Ensure you have:
```
your_project/
├── tools/
│   ├── __init__.py
│   └── your_tools.py
├── agents/
│   ├── __init__.py
│   └── your_agent.py
├── src/
│   ├── __init__.py
│   └── base_a2a_agent.py
└── pyproject.toml
```

### Step 5: Install and Run

```bash
uv sync
uv run your-agent
```

---

## Testing Your Agent

### 1. Unit Test Your Tools

```python
# tests/test_your_tools.py
import pytest
from tools.your_tools import your_tool

@pytest.mark.asyncio
async def test_your_tool():
    result = await your_tool.handler({"param": "value"})
    assert "content" in result
    assert result["content"][0]["type"] == "text"
```

### 2. Test Agent Endpoints

```python
# tests/test_your_agent.py
import pytest
import httpx

@pytest.mark.asyncio
async def test_agent_health():
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:9005/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

@pytest.mark.asyncio
async def test_agent_discovery():
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:9005/.well-known/agent-configuration")
        assert response.status_code == 200
        config = response.json()
        assert config["name"] == "Your Agent"

@pytest.mark.asyncio
async def test_agent_query():
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "http://localhost:9005/query",
            json={"query": "test query"}
        )
        assert response.status_code == 200
        result = response.json()
        assert "response" in result
```

### 3. Verify MCP Tool Calls

Check logs to ensure tools are being called:

```bash
tail -f src/logs/your_agent.log | grep "Tool: mcp__your_agent"
```

You should see:
```
Tool: mcp__your_agent__your_tool_name
Input: {'param': 'value'}
Result content: [{'type': 'text', 'text': '...'}]
```

---

## Project Structure Template

```
my_agent_project/
├── tools/
│   ├── __init__.py          # Empty or exports
│   ├── weather_tools.py     # Weather MCP tools
│   └── slurm_tools.py       # SLURM MCP tools
├── agents/
│   ├── __init__.py
│   ├── weather_agent.py
│   ├── slurm_agent.py
│   └── controller_agent.py
├── src/
│   ├── __init__.py
│   └── base_a2a_agent.py    # Base class for all agents
├── tests/
│   ├── test_unit.py         # Unit tests for tools
│   └── test_integration.py  # Integration tests
├── logs/
│   └── demo_multi_agent/    # Demo run logs
├── pyproject.toml           # Dependencies and scripts
└── README.md
```

---

## Common Patterns

### Pattern 1: Tool with External API

```python
import httpx

@tool("fetch_data", "Fetch from external API", {"endpoint": str})
async def fetch_data(args):
    endpoint = args.get("endpoint")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(endpoint)
            response.raise_for_status()
            return {
                "content": [{
                    "type": "text",
                    "text": f"Data: {response.json()}"
                }]
            }
        except Exception as e:
            return {
                "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                "is_error": True
            }
```

### Pattern 2: Tool with File Operations

```python
from pathlib import Path

@tool("read_file", "Read file contents", {"path": str})
async def read_file(args):
    path = Path(args.get("path"))

    if not path.exists():
        return {
            "content": [{"type": "text", "text": f"File not found: {path}"}],
            "is_error": True
        }

    try:
        content = path.read_text()
        return {
            "content": [{
                "type": "text",
                "text": f"File contents:\n{content}"
            }]
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {str(e)}"}],
            "is_error": True
        }
```

### Pattern 3: Tool with State Management

```python
# Shared state across tool calls
_job_cache = {}

@tool("cache_job", "Cache job result", {"job_id": str, "result": str})
async def cache_job(args):
    job_id = args.get("job_id")
    result = args.get("result")

    _job_cache[job_id] = result

    return {
        "content": [{
            "type": "text",
            "text": f"Cached result for job {job_id}"
        }]
    }

@tool("get_cached_job", "Get cached job", {"job_id": str})
async def get_cached_job(args):
    job_id = args.get("job_id")

    if job_id in _job_cache:
        return {
            "content": [{
                "type": "text",
                "text": f"Result: {_job_cache[job_id]}"
            }]
        }
    else:
        return {
            "content": [{"type": "text", "text": "Job not found"}],
            "is_error": True
        }
```

---

## Best Practices

### 1. Tool Design
- ✅ One tool = one responsibility
- ✅ Clear, descriptive names
- ✅ Comprehensive error handling
- ✅ Return structured data
- ❌ Don't make tools do too much
- ❌ Don't mix concerns (e.g., data fetching + processing)

### 2. System Prompts
- ✅ List all tools with full names
- ✅ Provide usage examples
- ✅ Explicitly forbid workarounds
- ✅ Define expected behavior
- ❌ Don't be vague about tool names
- ❌ Don't forget to mention units/formats

### 3. Error Handling
- ✅ Validate inputs
- ✅ Use try/except blocks
- ✅ Return `is_error: True` for failures
- ✅ Provide helpful error messages
- ❌ Don't let exceptions crash the agent
- ❌ Don't return empty responses

### 4. Testing
- ✅ Test tools independently
- ✅ Test agent endpoints
- ✅ Verify MCP tools are called (check logs)
- ✅ Test A2A communication
- ❌ Don't assume tools work without testing
- ❌ Don't skip integration tests

---

## Troubleshooting

### "Tool not being called"

Check:
1. Tool name in `_get_allowed_tools()` matches `mcp__<server>__<tool>`
2. System prompt mentions the tool
3. Server name matches agent name pattern
4. Tool is in the `tools` list when creating server

### "Agent not responding to A2A"

Check:
1. Port is not blocked
2. Agent is running (`curl http://localhost:PORT/health`)
3. Discovery endpoint works (`curl http://localhost:PORT/.well-known/agent-configuration`)
4. Query endpoint accepts POST requests

### "MCP server not connecting"

Check:
1. SDK MCP server is passed to `super().__init__()`
2. Server name matches `self.name.lower().replace(" ", "_")`
3. Tools are decorated with `@tool`
4. Tools return correct format

---

## Example Usage with Claude

After creating this guide, you can ask Claude:

> "With the knowledge of @agentic_development_guide.md, can you create an agent that has access to a SLURM MCP for submitting and monitoring HPC jobs?"

Claude will:
1. Create MCP tools in `tools/slurm_tools.py`
2. Create agent class in `agents/slurm_agent.py`
3. Write appropriate system prompt
4. Add entry point
5. Create unit tests

This makes agent development fast, consistent, and maintainable.

---

## Summary

**To create a new agent:**

1. **Define MCP tools** with `@tool` decorator
2. **Create MCP server** with `create_sdk_mcp_server()`
3. **Subclass BaseA2AAgent** and implement required methods
4. **Write system prompt** that lists tools and forbids workarounds
5. **Add entry point** in `pyproject.toml`
6. **Test** unit, integration, and A2A endpoints

**Key principles:**
- MCP SDK tools run in-process (no subprocess overhead)
- System prompts must explicitly list tools and forbid alternatives
- A2A protocol enables multi-agent coordination
- Always verify tools are called (check logs)

Now you're ready to build sophisticated multi-agent systems! 🚀
