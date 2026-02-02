# Interactive CLI Guide

The interactive CLI provides a REPL (Read-Eval-Print Loop) interface for conversational interaction with deployed agents.

## Quick Start

```bash
# 1. Deploy a job
uv run deploy start examples/jobs/simple-weather-workflow.yaml

# 2. Start an interactive chat session
uv run deploy chat simple-weather-workflow

# 3. Chat with the agent
[You] > What's the weather in Tokyo?
[weather] Weather in Tokyo is 22.5°C, partly cloudy...

[You] > /quit
```

## Chat Command

Start an interactive chat session with a running job:

```bash
uv run deploy chat <job-name> [options]
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--agent` | `-a` | Specific agent to chat with (default: entry point) |
| `--session` | `-s` | Resume existing session by ID |
| `--timeout` | `-t` | Query timeout in seconds (default: 120) |

### Examples

```bash
# Chat with job entry point
uv run deploy chat my-job

# Chat with specific agent
uv run deploy chat my-job --agent weather

# Resume previous session
uv run deploy chat my-job --session abc123-def456

# Custom timeout
uv run deploy chat my-job --timeout 300
```

## Slash Commands

While in a chat session, these commands are available:

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/agents` | List available agents in the job |
| `/session` | Show current session info (ID, messages, created) |
| `/clear` | Start new session (clear conversation history) |
| `/quit` | Exit chat (also: `/exit`, `/q`, Ctrl+C, Ctrl+D) |

### Example Session

```
$ uv run deploy chat research-assistant

┌─────────────────── Interactive Chat ───────────────────┐
│ Chat Session                                            │
│                                                         │
│ Job: research-assistant                                 │
│ Agent: coordinator (http://localhost:9000)              │
│ Session: a1b2c3d4...                                    │
│                                                         │
│ Type /help for commands, /quit to exit                  │
└─────────────────────────────────────────────────────────┘

[You] > What can you help me with?

[coordinator]
I'm a research assistant that can help you with:
- Weather information for major cities
- Distance calculations between locations
- General research queries

[You] > /agents

┌────────────────── Available Agents ──────────────────┐
│ Agent       │ URL                    │ Current      │
├─────────────┼────────────────────────┼──────────────┤
│ coordinator │ http://localhost:9000  │ ✓            │
│ weather     │ http://localhost:9001  │              │
│ maps        │ http://localhost:9002  │              │
└─────────────┴────────────────────────┴──────────────┘

[You] > /session

┌─────────────────── Session Info ───────────────────┐
│ Session ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890   │
│ Job: research-assistant                             │
│ Agent: coordinator                                  │
│ Messages: 2                                         │
│ Created: 2026-02-01 12:00:00                       │
└─────────────────────────────────────────────────────┘

[You] > /quit
Session saved. Goodbye!
```

## Session Management

Sessions persist conversation history across multiple chat invocations.

### List Sessions

```bash
# List all sessions
uv run deploy sessions list

# Filter by job
uv run deploy sessions list my-job

# Limit results
uv run deploy sessions list --limit 10
```

### View Session Details

```bash
# Show session info and recent messages
uv run deploy sessions show <session-id>

# Show more messages
uv run deploy sessions show <session-id> --messages 20
```

### Delete Sessions

```bash
# Delete specific session (with confirmation)
uv run deploy sessions delete <session-id>

# Force delete (no confirmation)
uv run deploy sessions delete <session-id> --force
```

### Clear Sessions

```bash
# Clear all sessions (with confirmation)
uv run deploy sessions clear

# Force clear
uv run deploy sessions clear --force

# Clear sessions older than 24 hours
uv run deploy sessions clear --older-than 24h

# Clear sessions older than 7 days
uv run deploy sessions clear --older-than 7d --force
```

## Session Persistence

Sessions are stored as JSON files in `.sessions/` directory:

```
.sessions/
├── a1b2c3d4-e5f6-7890-abcd-ef1234567890.json
├── b2c3d4e5-f6a7-8901-bcde-f23456789012.json
└── .chat_history  # readline history
```

Each session file contains:
- `session_id`: Unique identifier
- `job_id`: Associated job name
- `agent_id`: Agent being chatted with
- `messages`: Array of user/assistant messages with timestamps
- `created_at`: Session creation time
- `last_accessed`: Last activity time

## Multi-Turn Conversations

Sessions maintain context across multiple exchanges:

```bash
# First interaction
$ uv run deploy chat my-job --session my-convo
[You] > My name is Alice and I work on AI research.
[agent] Nice to meet you, Alice! How can I help with your AI research?

[You] > /quit

# Later, resume the session
$ uv run deploy chat my-job --session my-convo
Resuming session: my-convo...

[You] > What did I tell you about myself?
[agent] You mentioned that your name is Alice and you work on AI research.
```

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Send message |
| `Ctrl+C` | Exit and save session |
| `Ctrl+D` | Exit and save session (EOF) |
| `Up/Down` | Navigate history (readline) |
| `Ctrl+R` | Reverse search history |

## Tips

1. **Use sessions for context**: When working on multi-step tasks, use the same session ID to maintain context.

2. **Tab completion**: Readline provides basic tab completion for paths.

3. **History**: Chat history persists in `.sessions/.chat_history` and is shared across sessions.

4. **Timeout tuning**: For complex queries, increase timeout with `--timeout 300`.

5. **Direct agent access**: Use `--agent` to bypass the coordinator and talk directly to specialized agents.

## Troubleshooting

### "Job not found"
- Ensure the job is deployed: `uv run deploy list`
- Check job status: `uv run deploy status <job-name>`

### "Job is not running"
- Start the job: `uv run deploy start <job-file>`
- Or restart if stopped: `uv run deploy start <job-file>`

### "Request timed out"
- Increase timeout: `--timeout 300`
- Check agent health: `uv run deploy status <job-name>`

### "Agent not found"
- List available agents: `/agents` command or `uv run deploy status <job-name>`

## Related Commands

- `uv run deploy query <job> "<message>"` - One-shot query (non-interactive)
- `uv run deploy start <job-file>` - Deploy a job
- `uv run deploy status <job>` - Check job status
- `uv run deploy list` - List running jobs
