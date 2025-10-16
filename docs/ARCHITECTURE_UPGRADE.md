# A2A Architecture Upgrade

## Overview

This upgrade addresses both goals:
- **a)** SDK MCP A2A transport for efficient agent communication (no Bash/curl overhead)
- **b)** Dynamic agent discovery and configuration (reusable agents)

## New Components

### 1. SDK MCP A2A Transport (`src/a2a_transport.py`)

Provides efficient HTTP-based agent communication via SDK MCP tools.

**Tools:**
- `query_agent(agent_url, query)` - Query another agent via HTTP POST
- `discover_agent(agent_url)` - Discover agent capabilities via A2A protocol

**Benefits:**
- Direct httpx calls (faster than Bash/curl)
- Proper error handling and timeouts
- Formatted responses
- Based on proven `evaluation_a2a_transport` implementation

**Usage:**
```python
from src.a2a_transport import create_a2a_transport_server

a2a_server = create_a2a_transport_server()
# Add to agent via sdk_mcp_server parameter
```

**Tool Names (when used by agents):**
- `mcp__a2a_transport__query_agent`
- `mcp__a2a_transport__discover_agent`

### 2. Agent Registry (`src/agent_registry.py`)

Provides runtime agent discovery and dynamic system prompt generation.

**Key Features:**
- Discovers agents via `/.well-known/agent-configuration` endpoint
- Caches agent information (name, description, skills)
- Generates enhanced system prompts with agent details
- Supports multiple concurrent discoveries

**Usage:**
```python
from src.agent_registry import AgentRegistry

async with AgentRegistry() as registry:
    # Discover agents
    await registry.discover_multiple([
        "http://localhost:9001",
        "http://localhost:9002"
    ])

    # Generate enhanced prompt
    prompt = registry.generate_system_prompt(
        base_prompt="You are a coordinator.",
        agent_urls=["http://localhost:9001", "http://localhost:9002"]
    )
```

### 3. Enhanced BaseA2AAgent (`src/base_a2a_agent.py`)

**New Parameter:**
- `connected_agents: Optional[List[str]]` - List of agent URLs to discover and connect to

**New Behavior:**
- If `connected_agents` is provided:
  1. Creates AgentRegistry instance
  2. On `run()`, discovers all connected agents
  3. Enhances system prompt with agent information
  4. Updates ClaudeAgentOptions with new prompt

**Example:**
```python
class MyCoordinator(BaseA2AAgent):
    def __init__(self, port: int = 9000):
        super().__init__(
            name="Coordinator",
            description="Multi-agent coordinator",
            port=port,
            sdk_mcp_server=create_a2a_transport_server(),
            system_prompt="You are a coordinator.",
            connected_agents=[
                "http://localhost:9001",
                "http://localhost:9002"
            ]
        )
```

### 4. Updated Controller Agent (`agents/controller_agent.py`)

**Old Implementation:**
- Hardcoded agent endpoints in system prompt
- Used Bash tool with curl commands
- Not reusable for different agent configurations

**New Implementation:**
- SDK MCP A2A transport tools
- Dynamic agent discovery on startup
- Configurable via `connected_agents` parameter
- Generates system prompt from discovered agent capabilities

**Constructor:**
```python
def __init__(self, port: int = 9000, connected_agents: List[str] = None):
    # Defaults to Weather (9001) and Maps (9002) if not specified
    if connected_agents is None:
        connected_agents = [
            "http://localhost:9001",
            "http://localhost:9002"
        ]
    # ... creates A2A transport server and passes to BaseA2AAgent
```

## Benefits

### Performance (Goal a)
- **Before:** Bash/curl overhead for each A2A call
- **After:** Direct httpx async HTTP calls (same as `evaluation_a2a_transport`)
- Faster response times
- Better error handling
- No shell process overhead

### Reusability (Goal b)
- **Before:** Agents hardcoded with specific endpoints
- **After:** Agents configured at runtime with any endpoints

**Example:**
```python
# Single agent connection
weather_only = ControllerAgent(
    connected_agents=["http://localhost:9001"]
)

# Multiple agent connections
full_coordinator = ControllerAgent(
    connected_agents=[
        "http://localhost:9001",  # Weather
        "http://localhost:9002",  # Maps
        "http://localhost:9003",  # Travel
        "http://localhost:9004"   # Recommendations
    ]
)

# Different environment
production_controller = ControllerAgent(
    connected_agents=[
        "https://weather.prod.example.com",
        "https://maps.prod.example.com"
    ]
)
```

### Dynamic Discovery
- Agents automatically discover connected agent capabilities
- System prompts generated from actual agent skills
- No manual prompt engineering for agent connections
- Agents can be added/removed without code changes

## Architecture Comparison

### Old Architecture
```
Controller Agent (port 9000)
├── System Prompt: Hardcoded endpoints + capabilities
└── Tools: ["Bash"]
    └── curl -X POST http://localhost:9001/query ...

Weather Agent (port 9001)
├── SDK MCP Server: weather tools
└── Tools: ["mcp__weather_agent__get_weather", ...]

Maps Agent (port 9002)
├── SDK MCP Server: maps tools
└── Tools: ["mcp__maps_agent__get_distance", ...]
```

**Issues:**
- Bash/curl overhead
- Hardcoded connections
- Not reusable

### New Architecture
```
Controller Agent (port 9000)
├── connected_agents: ["http://localhost:9001", "http://localhost:9002"]
├── On startup:
│   ├── Discover agent at http://localhost:9001 → Weather Agent
│   ├── Discover agent at http://localhost:9002 → Maps Agent
│   └── Generate system prompt with discovered capabilities
├── SDK MCP Server: A2A transport
└── Tools: ["mcp__a2a_transport__query_agent", "mcp__a2a_transport__discover_agent"]
    └── Direct httpx HTTP calls

Weather Agent (port 9001)
├── SDK MCP Server: weather tools
├── A2A Discovery: /.well-known/agent-configuration
└── Tools: ["mcp__weather_agent__get_weather", ...]

Maps Agent (port 9002)
├── SDK MCP Server: maps tools
├── A2A Discovery: /.well-known/agent-configuration
└── Tools: ["mcp__maps_agent__get_distance", ...]
```

**Benefits:**
- SDK MCP transport (faster)
- Dynamic discovery
- Reusable agents

## Usage

### Starting the System

```bash
# Install dependencies
cd clean_mcp_a2a
uv sync

# Start all agents (Weather, Maps, Controller)
uv run start-all

# Or start individually
uv run weather-agent    # Port 9001
uv run maps-agent       # Port 9002
uv run controller-agent # Port 9000
```

### Testing

```bash
# Run system test
uv run test-system

# Or query directly
curl -X POST http://localhost:9000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the weather in Tokyo?"}'
```

### Creating Custom Coordinators

```python
from src.base_a2a_agent import BaseA2AAgent
from src.a2a_transport import create_a2a_transport_server

class CustomCoordinator(BaseA2AAgent):
    def __init__(self, agent_urls: List[str]):
        super().__init__(
            name="Custom Coordinator",
            description="Coordinates custom agents",
            port=9000,
            sdk_mcp_server=create_a2a_transport_server(),
            system_prompt="You coordinate multiple specialized agents.",
            connected_agents=agent_urls  # Dynamic!
        )

    def _get_skills(self):
        return [{"id": "coordination", "name": "Coordination", ...}]

    def _get_allowed_tools(self):
        return ["mcp__a2a_transport__query_agent"]

# Use with any agents
coordinator = CustomCoordinator([
    "http://agent1.example.com",
    "http://agent2.example.com",
    "http://agent3.example.com"
])
```

## Migration Guide

### For Existing Controller Agents

**Before:**
```python
class ControllerAgent(BaseA2AAgent):
    def __init__(self, port: int = 9000):
        system_prompt = """Available agents:
- Weather: http://localhost:9001
  Use: curl -X POST http://localhost:9001/query ..."""

        super().__init__(
            name="Controller",
            port=port,
            sdk_mcp_server=None,
            system_prompt=system_prompt
        )

    def _get_allowed_tools(self):
        return ["Bash"]
```

**After:**
```python
class ControllerAgent(BaseA2AAgent):
    def __init__(self, port: int = 9000, connected_agents: List[str] = None):
        if connected_agents is None:
            connected_agents = ["http://localhost:9001"]

        super().__init__(
            name="Controller",
            port=port,
            sdk_mcp_server=create_a2a_transport_server(),
            system_prompt="Base prompt here.",
            connected_agents=connected_agents
        )

    def _get_allowed_tools(self):
        return ["mcp__a2a_transport__query_agent"]
```

### For New Agents

Just use the `connected_agents` parameter:
```python
my_agent = MyAgent(
    connected_agents=[
        "http://agent1.com",
        "http://agent2.com"
    ]
)
```

## Implementation Files

1. `src/a2a_transport.py` - SDK MCP A2A transport tools
2. `src/agent_registry.py` - Dynamic agent discovery and configuration
3. `src/base_a2a_agent.py` - Enhanced with `connected_agents` support
4. `agents/controller_agent.py` - Updated to use new architecture

## Next Steps

1. **Test the new system:**
   ```bash
   uv run start-all
   uv run test-system
   ```

2. **Create new coordinator agents** using the pattern above

3. **Add more specialized agents** (travel, recommendations, etc.) and connect them dynamically

4. **Monitor performance improvements** from SDK transport vs Bash/curl

## Notes

- Weather and Maps agents unchanged (already use SDK MCP)
- Only coordinator-type agents need updates
- Backward compatible - old agents still work
- Agent discovery happens once on startup (cached)
- System prompts auto-updated with agent capabilities
