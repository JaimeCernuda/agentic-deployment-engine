# Clean MCP + A2A Multi-Agent System

This is a clean implementation that properly leverages claude-agent-sdk-python's framework with MCP SDK tools and A2A protocol for multi-agent coordination.

## 📚 Documentation

### Architecture Guides
- **[Multi-Agent Architectures](MULTI_AGENT_ARCHITECTURES.md)** - Complete reference for all architecture patterns (Hub-and-Spoke, Pipeline, Peer-to-Peer, Hierarchical, Blackboard, Marketplace, Event-Driven)
- **[Architecture Patterns Comparison](ARCHITECTURE_PATTERNS_COMPARISON.md)** - Quick visual reference and side-by-side comparison
- **[Architecture Visual Index](ARCHITECTURE_VISUAL_INDEX.md)** - Gallery of rendered diagrams (PNG images)
- **[Architecture Upgrade](ARCHITECTURE_UPGRADE.md)** - Technical documentation of current SDK MCP A2A transport implementation
- **[Images Directory](images/)** - 9 high-quality PNG diagrams + source mermaid files

### Development Guides
- **[Agentic Development Guide](agentic_development_guide.md)** - Complete guide for building agents with MCP SDK tools and A2A protocol
- **[MCP SDK Transport Deep Dive](mcp_sdk_transport_deep_dive.md)** - Technical deep dive on MCP SDK vs subprocess MCP implementations

## Architecture

```
Controller Agent (9000) → Weather Agent (9001) [MCP SDK Tools]
                       → Maps Agent (9002) [MCP SDK Tools]
```

- **MCP SDK Tools**: In-process Python functions decorated with `@tool` (10-100x faster than subprocess)
- **A2A Agents** (9001, 9002): Use claude-agent-sdk with MCP SDK server integration
- **Controller Agent** (9000): Coordinates via A2A protocol using HTTP/curl

## Key Features

✅ **MCP SDK Tools**: In-process Python functions (10-100x faster than subprocess MCP)
✅ **Clean A2A Inheritance**: BaseA2AAgent provides FastAPI server + Claude SDK integration
✅ **Proper SDK Usage**: MCP SDK servers configured via ClaudeAgentOptions
✅ **Real Network Architecture**: HTTP/JSON communication between agents
✅ **Dynamic Coordination**: Controller uses Claude SDK for planning and coordination

## Quick Start

```bash
# Install dependencies
uv sync

# Start all agents (includes MCP SDK tools)
uv run weather-agent &
uv run maps-agent &
uv run controller-agent &

# Wait for startup
sleep 15

# Run demo
uv run python demo_multi_agent.py

# Or run integration tests
./run_integration_tests.sh
```

## Testing

```bash
# Unit tests
python -m pytest tests/ -v

# Integration tests (requires agents running)
./run_integration_tests.sh

# View demo logs (proof of MCP and A2A execution)
cd logs/demo_multi_agent/
./verify_logs.sh
```

## Example Queries

- **Weather Agent** (port 9001): "What's the weather in Tokyo?"
- **Maps Agent** (port 9002): "How far is Tokyo from London?"
- **Controller Agent** (port 9000): "What's the weather in Tokyo and how far is it from London?"

## Verification & Proof

The `logs/demo_multi_agent/` directory contains clean logs proving both MCP SDK tools and A2A protocol work:

```bash
cd logs/demo_multi_agent/
./verify_logs.sh
```

**Key Evidence**:
- ✅ Weather Agent: 3 MCP SDK tool calls to `mcp__weather_agent__get_weather`
- ✅ Maps Agent: 3 MCP SDK tool calls to `mcp__maps_agent__get_distance`
- ✅ Controller Agent: 4 A2A curl calls coordinating other agents via HTTP

All logs show exact inputs/outputs, proving tools actually execute (no hallucination or workarounds).

See [DEMO_LOGS_SUMMARY.md](../DEMO_LOGS_SUMMARY.md) for complete details.