# Configuration

This document covers all configuration options for the Agentic Deployment Engine.

## Overview

Configuration is managed through environment variables. The framework uses [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) for validation and type conversion.

You can set variables:
- In a `.env` file in the project root
- As shell environment variables
- In your deployment configuration

## Agent settings

Agent settings control the behavior of A2A agents.

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_HTTP_TIMEOUT` | `30.0` | HTTP request timeout in seconds |
| `AGENT_DISCOVERY_TIMEOUT` | `10.0` | Agent discovery timeout in seconds |
| `AGENT_API_KEY` | `None` | API key for authentication |
| `AGENT_AUTH_REQUIRED` | `false` | Require API key authentication |
| `AGENT_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated allowed hosts for SSRF protection |
| `AGENT_MIN_PORT` | `9000` | Minimum allowed agent port |
| `AGENT_MAX_PORT` | `9100` | Maximum allowed agent port |
| `AGENT_CLIENT_POOL_SIZE` | `3` | SDK client pool size |

### Example

```bash
# .env file
AGENT_HTTP_TIMEOUT=60.0
AGENT_DISCOVERY_TIMEOUT=15.0
AGENT_AUTH_REQUIRED=true
AGENT_API_KEY=your-secret-api-key
```

## Security settings

Security-related configuration for authentication and SSRF protection.

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_API_KEY` | `None` | API key for authentication |
| `AGENT_AUTH_REQUIRED` | `false` | Require API key for all requests |
| `AGENT_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Allowed hosts (supports wildcards: `*.example.com`) |
| `AGENT_MIN_PORT` | `9000` | Minimum allowed port |
| `AGENT_MAX_PORT` | `9100` | Maximum allowed port |

### Enabling authentication

```bash
export AGENT_AUTH_REQUIRED=true
export AGENT_API_KEY=your-secret-key-here
```

With authentication enabled, include the API key in requests:

```bash
curl -H "X-API-Key: your-secret-key-here" http://localhost:9000/query
```

## Backend settings

Configure which LLM backend agents use.

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_BACKEND_TYPE` | `claude` | Backend type: `claude`, `gemini`, `crewai` |
| `AGENT_OLLAMA_MODEL` | `llama3` | Ollama model for CrewAI backend |
| `AGENT_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API base URL |

### Using Claude (default)

```bash
export AGENT_BACKEND_TYPE=claude
export ANTHROPIC_API_KEY=your-api-key
```

### Using Gemini

```bash
export AGENT_BACKEND_TYPE=gemini
export GOOGLE_API_KEY=your-api-key
```

### Using CrewAI with Ollama

```bash
export AGENT_BACKEND_TYPE=crewai
export AGENT_OLLAMA_MODEL=llama3.2
export AGENT_OLLAMA_BASE_URL=http://localhost:11434
```

## Observability settings

Configure logging and OpenTelemetry tracing.

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_LOG_LEVEL` | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `AGENT_LOG_JSON` | `false` | Enable JSON log format |
| `AGENT_LOG_MAX_CONTENT_LENGTH` | `2000` | Max chars for log content (0 = unlimited) |
| `AGENT_OTEL_ENABLED` | `false` | Enable OpenTelemetry tracing |
| `AGENT_OTEL_ENDPOINT` | `http://localhost:4317` | OTLP collector endpoint |
| `AGENT_OTEL_PROTOCOL` | `grpc` | OTLP protocol: `grpc` or `http` |
| `AGENT_OTEL_SERVICE_NAME` | `agentic-deployment-engine` | Service name for traces |

### Logging configuration

```bash
# Debug logging with JSON format
export AGENT_LOG_LEVEL=DEBUG
export AGENT_LOG_JSON=true
```

### OpenTelemetry setup

```bash
export AGENT_OTEL_ENABLED=true
export AGENT_OTEL_ENDPOINT=http://jaeger:4317
export AGENT_OTEL_PROTOCOL=grpc
export AGENT_OTEL_SERVICE_NAME=my-agent-system
```

## Deployment settings

Settings for the job deployment system.

| Variable | Default | Description |
|----------|---------|-------------|
| `DEPLOY_SSH_TIMEOUT` | `30` | SSH connection timeout in seconds |
| `DEPLOY_HEALTH_CHECK_RETRIES` | `5` | Number of health check retries |
| `DEPLOY_HEALTH_CHECK_INTERVAL` | `2.0` | Interval between health checks in seconds |
| `DEPLOY_WORK_DIR` | `/tmp/agent-deploy` | Working directory for deployments |

### Example

```bash
export DEPLOY_SSH_TIMEOUT=60
export DEPLOY_HEALTH_CHECK_RETRIES=10
export DEPLOY_HEALTH_CHECK_INTERVAL=3.0
```

## Environment file

Create a `.env` file in the project root:

```bash
# .env - Example configuration

# Security
AGENT_AUTH_REQUIRED=true
AGENT_API_KEY=your-secret-api-key

# Backend
AGENT_BACKEND_TYPE=claude
ANTHROPIC_API_KEY=sk-ant-...

# Logging
AGENT_LOG_LEVEL=INFO
AGENT_LOG_JSON=false
AGENT_LOG_MAX_CONTENT_LENGTH=2000

# Observability
AGENT_OTEL_ENABLED=false

# Deployment
DEPLOY_SSH_TIMEOUT=30
DEPLOY_HEALTH_CHECK_RETRIES=5
```

## Job-level configuration

Settings can also be specified in job YAML files:

```yaml
# job.yaml
environment:
  AGENT_LOG_LEVEL: DEBUG
  CUSTOM_VAR: value

agents:
  - id: my-agent
    deployment:
      environment:
        AGENT_SPECIFIC_VAR: value
```

Job-level variables override global settings.

## Accessing settings in code

```python
from src.config import settings, deploy_settings

# Agent settings
timeout = settings.http_timeout
api_key = settings.api_key
allowed_hosts = settings.get_allowed_hosts_set()
port_range = settings.get_port_range()

# Deployment settings
ssh_timeout = deploy_settings.ssh_timeout
work_dir = deploy_settings.work_dir
```

## Validation

Settings are validated at startup. Invalid values raise errors:

```python
from pydantic import ValidationError
from src.config import AgentSettings

try:
    # This would fail - invalid log level
    settings = AgentSettings(log_level="INVALID")
except ValidationError as e:
    print(e)
```

## See also

- [Security](security.md) - Security best practices
- [SSH deployment](ssh-deployment.md) - SSH-specific configuration
- [Troubleshooting](troubleshooting.md) - Configuration issues
