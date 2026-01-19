# Context Management A2A - Context Management Experiment

This project implements an A2A (Agent-to-Agent) agent specifically designed to evaluate how the A2A protocol manages context **natively**, without introducing custom logic for information retention or processing.

## Experiment Objective

Empirically evaluate what information remains accessible in the agent's **active context** across different scenarios, without forcing:
- Explicit data retention
- Information prioritization
- Context summarization or compression
- External memory mechanisms

## Test Scenarios

### Scenario 1 — Long text in prompt

| Step | Action |
|------|--------|
| 1 | User sends a very long text with irrelevant information ("filler") |
| 2 | Within the text, the user's name appears **exactly once** |
| 3 | One or more unrelated interaction turns occur (same `context_id`) |
| 4 | User asks: **"What is my name?"** |

**Objective:** Determine if the name remains accessible in context after dilution with irrelevant information and additional turns.

### Scenario 2 — Name inside a file

| Step | Action |
|------|--------|
| 1 | User sends a file (txt, md, or pdf) containing only their name |
| 2 | The name is **NOT** mentioned in the prompt text |
| 3 | One or more unrelated interaction turns occur (same `context_id`) |
| 4 | User asks: **"What is my name?"** |

**Objective:** Evaluate whether information contained in attached files is integrated and remains in the active context the same way as direct prompt text.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Context Management A2A                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   ContextTestAgent                        │   │
│  │                                                           │   │
│  │  • Implements A2A protocol with context_id/task_id       │   │
│  │  • In-memory TaskStore for message history               │   │
│  │  • No MCP tools (pure conversational agent)              │   │
│  │  • No system prompt (zero interference)                  │   │
│  │  • No custom retention logic                             │   │
│  │                                                           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    A2A Protocol Layer                     │   │
│  │                                                           │   │
│  │  • context_id: Groups messages from the same conversation│   │
│  │  • task_id: Identifies each individual task              │   │
│  │  • history: Message history within the context           │   │
│  │  • InMemoryTaskStore: Stores tasks indexed by context    │   │
│  │                                                           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## A2A Context Management Flow

```
Client                              Agent (ContextTestAgent)
  │                                         │
  │  POST /query                            │
  │  {query: "Hi, my name is Carmen",       │
  │   context_id: null}                     │
  │────────────────────────────────────────►│
  │                                         │
  │                                         │ Generate context_id: "ctx-abc123"
  │                                         │ Create task_id: "task-001"
  │                                         │ Store in TaskStore
  │                                         │
  │  {response: "Hello Carmen!",            │
  │   context_id: "ctx-abc123",             │
  │   task_id: "task-001"}                  │
  │◄────────────────────────────────────────│
  │                                         │
  │  POST /query                            │
  │  {query: "What is 2+2?",                │
  │   context_id: "ctx-abc123"}  ◄── SAME   │
  │────────────────────────────────────────►│
  │                                         │
  │                                         │ Create task_id: "task-002"
  │                                         │ Get history from context
  │                                         │ Build prompt with ALL messages
  │                                         │
  │  {response: "4",                        │
  │   context_id: "ctx-abc123",             │
  │   task_id: "task-002"}                  │
  │◄────────────────────────────────────────│
  │                                         │
  │  POST /query                            │
  │  {query: "What is my name?",            │
  │   context_id: "ctx-abc123"}  ◄── SAME   │
  │────────────────────────────────────────►│
  │                                         │
  │                                         │ Get ALL history from context
  │                                         │ (includes "my name is Carmen")
  │                                         │
  │  {response: "Your name is Carmen",      │
  │   context_id: "ctx-abc123",             │
  │   task_id: "task-003"}                  │
  │◄────────────────────────────────────────│
```

## Project Structure

```
Context Management A2A/
├── agents/
│   ├── __init__.py
│   └── context_agent.py       # Agent with A2A context management
├── logs/                       # Execution logs
├── CONTEXT_MANAGEMENT.md       # Technical A2A protocol documentation
├── deployment.yaml             # Deployment configuration
├── requirements.txt            # Python dependencies
├── run_agents.py               # Script to start the agent
├── test_context.py             # Test suite with context_id support
└── README.md                   # This file
```

## Prerequisites

- Python 3.10+
- Main project dependencies (`agentic-deployment-engine`)
- Claude Agent SDK configured

## Installation

1. **Navigate to the experiment directory:**
```bash
cd "examples/Context Management A2A"
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

## Usage

### 1. Start the Agent

```bash
python run_agents.py
```

The agent will start on port **9010** by default.

**Expected output:**
```
Starting Context Test Agent on port 9010...
This agent tests A2A native context management.
  - Uses context_id to group conversations
  - Uses task_id to track individual tasks
  - Maintains in-memory message history per context
  - NO system prompt (pure native behavior)
```

### 2. Run the Tests

In a **separate terminal**, run the tests:

#### Run both scenarios
```bash
python test_context.py --mode all --name "Carmen"
```

#### Scenario 1 only (long text)
```bash
python test_context.py --mode scenario1 --name "Carmen"
```

#### Scenario 2 only (file)
```bash
python test_context.py --mode scenario2 --name "Carmen"
```

#### Interactive mode
```bash
python test_context.py --mode interactive
```

**Interactive mode commands:**
- `/new` - Start a new context (new conversation)
- `/context` - Show current context info (tasks, messages)
- `/quit` - Exit interactive mode

### 3. Available Parameters

| Parameter | Description | Default value |
|-----------|-------------|---------------|
| `--mode` | Execution mode: `all`, `scenario1`, `scenario2`, `interactive` | `all` |
| `--name` | User name for tests | `Carmen` |
| `--url` | Agent URL | `http://localhost:9010` |

### 4. Manual Queries with Context

**First message (creates new context):**
```bash
curl -X POST http://localhost:9010/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Hello, my name is Carmen"}'
```

**Response:**
```json
{
  "response": "Hello Carmen!",
  "context_id": "ctx-abc123def456",
  "task_id": "task-xyz789",
  "task": {...}
}
```

**Follow-up message (same context):**
```bash
curl -X POST http://localhost:9010/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is my name?", "context_id": "ctx-abc123def456"}'
```

**Get context info:**
```bash
curl http://localhost:9010/context/ctx-abc123def456
```

## Agent Design Principles

The `ContextTestAgent` strictly follows these principles to ensure valid evaluation:

### What the agent does NOT do

| Restriction | Justification |
|-------------|---------------|
| No system prompt | Zero interference with native model behavior |
| Does not use external persistent memory | Evaluates only A2A in-memory context |
| Does not use embeddings or vector stores | Avoids semantic retrieval mechanisms |
| Does not implement relevance logic | Does not decide what information is "important" |
| Does not infer absent information | Only responds with explicit data in context |
| Does not execute actions without prompt | Purely reactive behavior |

### What the agent DOES do

| Behavior | Description |
|----------|-------------|
| Implements A2A context_id | Groups messages from the same conversation |
| Implements A2A task_id | Tracks individual tasks within a context |
| Maintains InMemoryTaskStore | Stores all messages per context |
| Builds conversation prompts | Sends full history to model on each turn |
| Responds to queries | Based exclusively on active A2A context |

## Interpreting Results

### Positive Result (Name recalled)

```
SCENARIO 1 RESULT:
Context ID: ctx-scenario1-abc12345
Expected name: Carmen
Agent could RECALL the name
```

**Interpretation:** Native A2A context maintains information accessible across conversation turns.

### Negative Result (Name not recalled)

```
SCENARIO 1 RESULT:
Context ID: ctx-scenario1-abc12345
Expected name: Carmen
Agent could NOT recall the name
```

**Interpretation:** Information was lost from active context. Possible causes:
- Context token limit reached
- Previous messages truncated by the model
- Attached file not integrated into message history

## Metrics to Observe

| Metric | Description |
|--------|-------------|
| **Retention rate** | % of times the name is correctly remembered |
| **Degradation by turns** | How the number of intermediate turns affects retention |
| **Volume impact** | Effect of "filler" text size |
| **Text/file parity** | Difference between scenarios 1 and 2 |
| **Tasks per context** | Number of tasks created in each scenario |
| **Messages per context** | Total messages stored in context history |

## Agent Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/query` | POST | Send query with optional `context_id` |
| `/message/send` | POST | A2A standard message send endpoint |
| `/context/{context_id}` | GET | Get context info (tasks, messages) |
| `/health` | GET | Check agent status |
| `/.well-known/agent-configuration` | GET | Agent Card (A2A discovery) |

## Logs and Debugging

Logs are stored in the `logs/` directory:

```bash
# View agent logs in real time
tail -f logs/context_test_agent.log

# View runner logs
tail -f logs/context_test_stdout.log

# View errors
cat logs/context_test_stderr.log
```

## References

- [A2A Protocol Specification](https://a2a-protocol.org/latest/specification/)
- [A2A Python SDK](https://github.com/a2aproject/a2a-python)
- [A2A Protocol: Tasks vs Messages](https://discuss.google.dev/t/a2a-protocol-demystifying-tasks-vs-messages/255879)
- [CONTEXT_MANAGEMENT.md](./CONTEXT_MANAGEMENT.md) - Detailed technical documentation

## Troubleshooting

### Agent does not start

```bash
# Verify port is not in use
netstat -an | grep 9010

# Review error logs
cat logs/context_test_stderr.log
```

### Module import error

```bash
# Make sure you are in the correct directory
cd "examples/Context Management A2A"

# Verify PYTHONPATH
export PYTHONPATH="../../:$PYTHONPATH"
python run_agents.py
```

### Tests fail due to timeout

```bash
# Increase timeout in queries
python test_context.py --mode all --name "Test"
# Timeouts are configured at 120 seconds
```

### Context not being maintained

Check that you are passing the `context_id` from the first response to subsequent queries:

```python
# First query - get context_id
response1 = send_query("Hello, my name is Carmen")
context_id = response1["context_id"]

# Follow-up queries - use same context_id
response2 = send_query("What is 2+2?", context_id=context_id)
response3 = send_query("What is my name?", context_id=context_id)
```

---

**Version:** 1.1.0
**Last updated:** January 2025
