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

---

## Task Lifecycle and Context Management

This project includes **two implementations** of the multi-agent system:

### 1. Basic Implementation (Original)
Located in `agents/*_agent.py` files

### 2. A2A Task-Based Implementation (Extended)
Located in `agents/*_agent_task.py` files, implements full A2A Protocol v1.0 with:

#### **Task Lifecycle Management**

Tasks progress through defined states according to the A2A Protocol specification:

```
SUBMITTED      → Task created, not yet started
    ↓
WORKING        → Actively processing
    ↓
INPUT_REQUIRED → Needs user input (paused)
AUTH_REQUIRED  → Needs authentication (paused)
    ↓
COMPLETED      → Successfully finished ✅
FAILED         → Failed with error ❌
CANCELLED      → Cancelled by user/system ❌
REJECTED       → Cannot be processed ❌
```

**Key Features:**
- **Task Immutability**: Once a task reaches a terminal state (COMPLETED, FAILED, CANCELLED, REJECTED), it cannot be modified
- **Task Refinement**: New tasks can reference previous tasks via `referenceTaskIds` for iterative workflows
- **Task Artifacts**: Completed tasks include artifacts (results) that can be referenced by subsequent tasks

#### **Context Management**

The `contextId` groups multiple tasks and messages, providing conversation continuity:

```python
contextId = "ctx-conversation-123"
├─ Task 1: "Calculate 100 + 50" → COMPLETED (result: 150)
├─ Task 2: "Convert that to EUR" → COMPLETED (references Task 1)
└─ Task 3: "Add 25 to it" → WORKING (references Task 2)
```

**Benefits:**
- Multi-turn conversations with memory
- Task refinement and iteration
- Complete audit trail of conversation history
- Agent can access previous results in same context

#### **JSON-RPC 2.0 Protocol**

Communication uses JSON-RPC 2.0 as specified by A2A Protocol:

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "query",
  "params": {
    "query": "Calculate 25 + 17",
    "context_id": "ctx-math-001",
    "task_id": "task-001"
  },
  "id": 1
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "task": {
      "task_id": "task-001",
      "context_id": "ctx-math-001",
      "status": {
        "state": "completed",
        "message": "Task completed successfully"
      },
      "artifacts": [{
        "name": "math_result.txt",
        "content": "The result is 42",
        "content_type": "text/plain"
      }]
    },
    "response": "The result is 42"
  },
  "id": 1
}
```

#### **Architecture Components**

The task-based implementation uses:

1. **BaseA2ATaskAgent** (`src/base_a2a_task_agent.py`)
   - Extension of `BaseA2AAgent` with task lifecycle support
   - Implements JSON-RPC 2.0 endpoints
   - Manages task store and conversation history

2. **AgentExecutor** (in `executors/` directory)
   - Implements task execution logic for each agent
   - Uses `TaskUpdater` for state management
   - Handles task cancellation

3. **InMemoryTaskStore**
   - Stores tasks and maintains context relationships
   - Enforces task immutability rules
   - Provides task lookup and context queries

4. **TaskUpdater Helper**
   - Simplifies task lifecycle transitions
   - Methods: `submit()`, `start_work()`, `complete()`, `fail()`, `cancel()`

#### **Running Task-Based Agents**

Start individual task-based agents:
```bash
# Math Agent with task support
python agents/math_agent_task.py

# Finance Agent with task support
python agents/finance_agent_task.py

# Search Agent with task support
python agents/search_agent_task.py

# General Agent with task support
python agents/general_agent_task.py
```

#### **Testing Task-Based System**

**Basic Tests** (`test_agents.py`) - Uses JSON-RPC 2.0 format:

```bash
python test_agents.py
```

Tests include:
- ✅ Direct queries to specialized agents
- ✅ General agent delegation
- ✅ Multi-agent orchestration
- ✅ JSON-RPC 2.0 protocol format

**Task Lifecycle Tests** (`test_task_lifecycle.py`) - Comprehensive task and context testing:

```bash
python test_task_lifecycle.py
```

Tests include:
- ✅ **Test 1: Task State Transitions** - Verifies SUBMITTED → WORKING → COMPLETED lifecycle
- ✅ **Test 2: Context Persistence** - Multi-turn conversations with shared context
- ✅ **Test 3: Task Refinement** - Using `referenceTaskIds` for iterative tasks
- ✅ **Test 4: Task Immutability** - Terminal states cannot be modified
- ✅ **Test 5: Multi-Agent Orchestration** - Complex workflows across agents
- ✅ **Test 6: Error Handling** - Graceful failure with FAILED state

Run with custom URL:
```bash
python test_task_lifecycle.py --url http://localhost:9001
```

#### **Comparison: Basic vs Task-Based**

| Feature | Basic Implementation | Task-Based Implementation |
|---------|---------------------|---------------------------|
| **Protocol** | Simple JSON | JSON-RPC 2.0 |
| **State Management** | ❌ Stateless | ✅ Full task lifecycle |
| **Context** | ❌ No persistence | ✅ Multi-turn conversations |
| **Refinement** | ❌ Not supported | ✅ Task references |
| **Artifacts** | ❌ Text only | ✅ Typed artifacts |
| **Audit Trail** | ❌ No history | ✅ Complete task history |
| **A2A Compliance** | ⚠️ Partial | ✅ Full A2A Protocol v1.0 |

#### **Example: Multi-Turn Conversation**

```bash
# Task 1: Initial calculation
curl -X POST http://localhost:9001/query \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "query",
    "params": {
      "query": "Convert 100 USD to EUR",
      "context_id": "ctx-finance-session",
      "task_id": "task-001"
    },
    "id": 1
  }'

# Response: Task completed with result "85 EUR"

# Task 2: Refinement (references previous task)
curl -X POST http://localhost:9001/query \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "query",
    "params": {
      "query": "Add 50 to that",
      "context_id": "ctx-finance-session",
      "task_id": "task-002",
      "reference_task_ids": ["task-001"]
    },
    "id": 2
  }'

# Response: Task completed with result "135 EUR"
```

#### **Reference Documentation**

For complete implementation details, see:
- [A2A Protocol Specification](https://a2a-protocol.org/latest/specification/)
- [A2A_LIFE_OF_TASK_IMPLEMENTATION_GUIDE.md](A2A_LIFE_OF_TASK_IMPLEMENTATION_GUIDE.md) - Implementation guide
- [base_a2a_task_agent.py](base_a2a_task_agent.py) - Base agent implementation

---

## Learning Objectives

This project demonstrates:
1. How A2A protocol enables agent communication
2. Hub-and-spoke architecture pattern for multi-agent systems
3. Task lifecycle management (SUBMITTED → WORKING → COMPLETED)
4. Context management for multi-turn conversations
5. Task delegation and orchestration
6. Integration of MCP tools with A2A agents
7. Multi-agent workflow coordination
8. JSON-RPC 2.0 protocol implementation

## Logs

Agent logs are stored in the `logs/` directory with separate stdout and stderr files for each agent:
- `math_stdout.log` / `math_stderr.log`
- `finance_stdout.log` / `finance_stderr.log`
- `search_stdout.log` / `search_stderr.log`
- `general_stdout.log` / `general_stderr.log`


