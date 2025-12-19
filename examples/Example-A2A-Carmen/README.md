# Example-A2A-Carmen

A multi-agent system project created to understand and demonstrate the **Agent-to-Agent (A2A) protocol** in action. This example showcases how agents communicate, delegate tasks, and coordinate using A2A transport along with MCP (Model Context Protocol) for tool integration.

## Overview

This project implements a **hub-and-spoke architecture** where a General Agent acts as the central controller and orchestrator, coordinating with specialized agents to handle different types of queries. The General Agent can both answer general questions directly and intelligently delegate specialized tasks to the appropriate agent.

## Architecture

### Agents

#### General Agent (Controller)
- **Port:** 9001
- **Role:** Central orchestrator and entry point for all queries
- **Capabilities:**
  - Answers general knowledge questions directly
  - Discovers and delegates to specialized agents
  - Coordinates multi-agent workflows when tasks require multiple agents
  - Uses A2A transport tools to communicate with other agents

#### Specialized Agents

1. **Math Agent**
   - **Port:** 9002
   - **Skills:** Mathematical operations (addition, subtraction) and unit conversions (meters/kilometers, celsius/fahrenheit)
   - **Tools:**
     - `add` - Add two numbers
     - `subtract` - Subtract one number from another
     - `convert_units` - Convert between meters/kilometers and celsius/fahrenheit
   - **Tool Integration:** Uses MCP (Model Context Protocol) tools registered via `create_sdk_mcp_server`

2. **Finance Agent**
   - **Port:** 9003
   - **Skills:** Currency conversions and financial calculations
   - **Tools:**
     - `convert_currency` - Convert between USD, EUR, and GBP
     - `calculate_interest` - Calculate simple interest
     - `percentage_change` - Calculate percentage changes
   - **Tool Integration:** Uses MCP (Model Context Protocol) tools registered via `create_sdk_mcp_server`

3. **Search Agent**
   - **Port:** 9004
   - **Skills:** Web searches for current information and URL content retrieval
   - **Tools:**
     - `WebSearch` - Search the web using DuckDuckGo for current information
     - `WebFetch` - Fetch and analyze content from specific URLs
   - **Tool Integration:** Uses Claude SDK's built-in tools (not MCP). These tools are natively provided by the Claude Agent SDK and enabled through the `ClaudeAgentOptions` configuration with `allowed_tools`. No external MCP server registration is required.

### Communication Pattern

The system uses a **hub-and-spoke topology**:
- **Hub:** General Agent (orchestrator)
- **Spokes:** Math, Finance, and Search agents

```
         Math Agent (9002)
               |
Finance Agent (9003) --- General Agent (9001) --- [User Queries]
               |
         Search Agent (9004)
```

The General Agent discovers available agents at startup and uses the A2A protocol to query them when needed.

## Project Structure

```
Example-A2A-Carmen/
├── agents/                    # Agent implementations
│   ├── __init__.py
│   ├── general_agent.py      # Controller and orchestrator
│   ├── math_agent.py         # Math operations and conversions
│   ├── finance_agent.py      # Financial calculations
│   └── search_agent.py       # Web search capabilities
├── tools/                     # MCP tool implementations
│   ├── __init__.py
│   ├── math_tools.py         # Math operation tools
│   └── finance_tools.py      # Finance operation tools
├── deployment.yaml           # System configuration
├── run_agents.py            # Multi-agent orchestration runner
├── test_agents.py           # Test suite for the system
└── requirements.txt         # Python dependencies
```

## Configuration

The system is configured via `deployment.yaml`, which defines:
- Agent specifications (ID, type, module, port)
- Deployment strategy (sequential startup)
- Topology (hub-and-spoke)
- Health check settings

## Getting Started

### Prerequisites

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Running the System

Start all agents:
```bash
python run_agents.py
```

This will:
1. Start all specialized agents (Math, Finance, Search)
2. Start the General Agent with agent discovery
3. Verify connectivity and health of all agents
4. Display the entry point URL

### Testing

Run the test suite to verify the system:
```bash
python test_agents.py
```

The test suite includes:
- Direct queries to specialized agents
- General Agent knowledge questions
- Delegation tests (General Agent → Specialized Agents)
- Multi-agent orchestration (tasks requiring multiple agents)

### Example Queries

Send queries to the General Agent at `http://localhost:9001/query`:

**General Knowledge** (answered directly):
```bash
curl -X POST http://localhost:9001/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Who discovered gravity?"}'
```

**Math Operations** (delegated to Math Agent):
```bash
curl -X POST http://localhost:9001/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is 25 + 17?"}'
```

**Currency Conversion** (delegated to Finance Agent):
```bash
curl -X POST http://localhost:9001/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Convert 100 USD to EUR"}'
```

**Web Search** (delegated to Search Agent):
```bash
curl -X POST http://localhost:9001/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Search for latest AI news"}'
```

**Multi-Agent Task** (orchestrated across multiple agents):
```bash
curl -X POST http://localhost:9001/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Convert 100 USD to EUR and add 50 to the result"}'
```

## Key Technologies

- **A2A Protocol:** Agent-to-Agent communication protocol for inter-agent messaging
- **MCP (Model Context Protocol):** Tool integration framework for agent capabilities
- **Claude SDK:** AI agent framework with tool support


## Learning Objectives

This project demonstrates:
1. How A2A protocol enables agent communication
2. Hub-and-spoke architecture pattern for multi-agent systems
4. Task delegation and orchestration
5. Integration of MCP tools with A2A agents
6. Multi-agent workflow coordination

## Logs

Agent logs are stored in the `logs/` directory with separate stdout and stderr files for each agent:
- `math_stdout.log` / `math_stderr.log`
- `finance_stdout.log` / `finance_stderr.log`
- `search_stdout.log` / `search_stderr.log`
- `general_stdout.log` / `general_stderr.log`


