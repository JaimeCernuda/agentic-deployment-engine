# Agent Builder Quick Reference

This file provides a quick reference for building new agents using the claude-agent-sdk-python framework. For comprehensive documentation, see the files in the `docs/` directory.

## 📚 Full Documentation

- **[Agentic Development Guide](docs/agentic_development_guide.md)** (29KB)
  - Complete guide for building agents with MCP SDK tools
  - BaseA2AAgent pattern and inheritance
  - A2A protocol integration
  - Step-by-step agent creation
  - Working examples (Database Agent, SLURM Agent)
  - Best practices and troubleshooting

- **[MCP SDK Transport Deep Dive](docs/mcp_sdk_transport_deep_dive.md)** (22KB)
  - Technical architecture comparison
  - SDK vs subprocess MCP implementations
  - Performance characteristics (10-100x speedup)
  - Internal implementation details
  - When to use each approach

- **[System README](docs/README.md)**
  - Quick start instructions
  - Architecture overview
  - Testing and verification

## Quick Example: Creating a New Agent

When asked to create a new agent (e.g., "Create an agent with SLURM MCP tools"):

1. **Reference the guide**: `@docs/agentic_development_guide.md can you create an agent that has access to SLURM MCP tools?`

2. **Key components** you'll need:
   - MCP SDK tools file (`tools/slurm_tools.py`)
   - Agent class file (`agents/slurm_agent.py`)
   - Entry point in `pyproject.toml`
   - System prompt for the agent

3. **Pattern to follow**:
   ```python
   # tools/slurm_tools.py
   from claude_agent_sdk import tool

   @tool("submit_job", "Submit a SLURM job", {...})
   async def submit_job(args):
       # Implementation
       return {"content": [{"type": "text", "text": result}]}

   # agents/slurm_agent.py
   from src import BaseA2AAgent
   from tools.slurm_tools import submit_job, check_status
   from claude_agent_sdk import create_sdk_mcp_server

   class SlurmAgent(BaseA2AAgent):
       def __init__(self, port: int = 9003):
           server = create_sdk_mcp_server(
               name="slurm_agent",
               version="1.0.0",
               tools=[submit_job, check_status]
           )

           system_prompt = """You are a SLURM cluster management agent.
           Use your mcp__slurm_agent__* tools to manage jobs.
           NEVER use bash or code - only your MCP tools."""

           super().__init__(
               agent_name="slurm-agent",
               port=port,
               mcp_servers={"slurm_agent": server},
               allowed_tools=["mcp__slurm_agent__submit_job",
                            "mcp__slurm_agent__check_status"],
               system_prompt=system_prompt
           )
   ```

4. **Add to pyproject.toml**:
   ```toml
   [project.scripts]
   slurm-agent = "agents.slurm_agent:main"
   ```

## Testing Your Agent

```bash
# Unit test the tools
python -m pytest tests/ -v

# Run the agent
uv run slurm-agent &

# Test via HTTP
curl -X POST http://localhost:9003/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Submit a test job"}'

# Check logs
tail -f src/logs/slurm_agent.log
```

## Key Principles

1. **MCP SDK Tools are 10-100x faster** than subprocess MCP
2. **Tools must be async functions** decorated with `@tool`
3. **System prompts must forbid workarounds** (bash, code generation)
4. **Tool naming**: `mcp__<server_name>__<tool_name>`
5. **BaseA2AAgent provides**: FastAPI server, Claude SDK client, A2A endpoints, logging

## Proof of Concept

See `logs/demo_multi_agent/` for clean logs proving both MCP SDK tools and A2A protocol work in production.

Run `./logs/demo_multi_agent/verify_logs.sh` to see evidence of:
- Real MCP tool execution (exact inputs/outputs)
- A2A protocol communication (HTTP/JSON)
- Multi-agent coordination

## Repository Status

This implementation uses `claude-agent-sdk-python` from the **main branch** (not 0.1.0 release):
```toml
claude-agent-sdk = { git = "https://github.com/anthropics/claude-agent-sdk-python.git", branch = "main" }
```

All tests pass (10/10 unit, 13/13 integration). See [TEST_RESULTS.md](TEST_RESULTS.md) and [DEMO_LOGS_SUMMARY.md](DEMO_LOGS_SUMMARY.md).
