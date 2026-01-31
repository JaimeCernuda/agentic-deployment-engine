# Troubleshooting

This guide covers common issues and their solutions.

## Agent startup issues

### Agent won't start - port in use

**Symptom:** Error message about address already in use.

**Solution:** Check what's using the port and either stop it or use a different port.

```bash
# Windows
netstat -ano | findstr :9001

# Linux/Mac
lsof -i :9001
```

To use a different port, modify the agent config:
```python
agent = WeatherAgent(port=9005)  # Use different port
```

### Agent won't start - missing dependencies

**Symptom:** ImportError or ModuleNotFoundError at startup.

**Solution:** Reinstall dependencies:

```bash
uv sync
```

If using a specific backend, ensure its dependencies are installed:
```bash
# For Gemini
pip install google-generativeai

# For CrewAI/Ollama
pip install crewai ollama
```

### Agent won't start - missing API key

**Symptom:** Error about missing API key or authentication.

**Solution:** Set the appropriate API key:

```bash
# Claude backend
export ANTHROPIC_API_KEY=your-api-key

# Gemini backend
export GOOGLE_API_KEY=your-api-key
```

## Connection issues

### Connection refused

**Symptom:** `ConnectionRefusedError` or `Connection refused` when querying an agent.

**Solutions:**

1. Verify the agent is running:
   ```bash
   curl http://localhost:9001/health
   ```

2. Check you're using the correct port

3. Ensure firewall allows the connection (especially on Windows)

4. For remote agents, verify SSH connectivity:
   ```bash
   ssh user@host "curl http://localhost:9001/health"
   ```

### Timeout errors

**Symptom:** Requests timeout before completing.

**Solutions:**

1. Increase timeout in configuration:
   ```bash
   export AGENT_HTTP_TIMEOUT=120.0
   ```

2. For complex queries, the LLM may need more time. Check agent logs for progress.

3. Verify the target agent is responsive:
   ```bash
   curl -v http://localhost:9001/health
   ```

### Agent discovery fails

**Symptom:** Controller can't find or connect to other agents.

**Solutions:**

1. Verify target agents are healthy:
   ```bash
   curl http://localhost:9001/.well-known/agent-configuration
   ```

2. Check network connectivity between agents

3. Increase discovery timeout:
   ```bash
   export AGENT_DISCOVERY_TIMEOUT=30.0
   ```

## Authentication issues

### 401 Unauthorized

**Symptom:** Requests return 401 status code.

**Solutions:**

1. If authentication is enabled, include the API key:
   ```bash
   curl -H "X-API-Key: your-api-key" http://localhost:9000/query
   ```

2. Verify the API key matches:
   ```bash
   echo $AGENT_API_KEY
   ```

3. If you don't want authentication, disable it:
   ```bash
   export AGENT_AUTH_REQUIRED=false
   ```

### 403 Forbidden - SSRF protection

**Symptom:** Requests blocked by SSRF protection.

**Solutions:**

1. Add the target host to allowed hosts:
   ```bash
   export AGENT_ALLOWED_HOSTS=localhost,127.0.0.1,api.example.com
   ```

2. For wildcards:
   ```bash
   export AGENT_ALLOWED_HOSTS=localhost,*.example.com
   ```

## SSH deployment issues

### Permission denied (publickey)

**Symptom:** SSH connection fails with publickey error.

**Solutions:**

1. Verify SSH key exists:
   ```bash
   ls -la ~/.ssh/id_rsa
   # or
   ls -la ~/.ssh/id_ed25519
   ```

2. Add public key to remote authorized_keys:
   ```bash
   ssh-copy-id user@remote-host
   ```

3. Test SSH connection manually:
   ```bash
   ssh user@remote-host "echo success"
   ```

### Host key verification failed

**Symptom:** Error about host key verification.

**Solution:** Add the host key to known_hosts:

```bash
ssh-keyscan -H remote-host >> ~/.ssh/known_hosts
```

### Remote agent not starting

**Symptom:** SSH connects but agent doesn't start.

**Solutions:**

1. Check Python is available on remote:
   ```bash
   ssh user@remote "which python3"
   ```

2. Verify the project is synced to remote:
   ```bash
   ssh user@remote "ls /path/to/project"
   ```

3. Check remote logs:
   ```bash
   ssh user@remote "tail -f /tmp/agent-deploy/agent.log"
   ```

## Job deployment issues

### Validation fails

**Symptom:** `uv run deploy validate` reports errors.

**Solutions:**

1. Check YAML syntax (use a YAML validator)

2. Ensure all required fields are present:
   - `job.name`, `job.version`, `job.description`
   - `agents[].id`, `agents[].type`, `agents[].module`
   - `agents[].config.port`
   - `topology.type`

3. Verify agent IDs are unique

4. Check for port conflicts on same host

### DAG cycle detected

**Symptom:** Validation error about cyclic dependencies.

**Solution:** Review your DAG connections. A → B → C → A is a cycle. Remove one connection to break the cycle.

### Health checks failing

**Symptom:** Agents deploy but health checks fail.

**Solutions:**

1. Increase health check timeout and retries:
   ```yaml
   deployment:
     health_check:
       timeout: 10
       retries: 5
       interval: 3
   ```

2. Check agent logs for startup errors

3. Verify port is accessible from deployment machine

## Logging and debugging

### Enable debug logging

```bash
export AGENT_LOG_LEVEL=DEBUG
```

### View agent logs

When running individual agents, logs are written to `src/logs/`. When using job deployment, logs are in `logs/jobs/<job-id>/`:

```bash
# Individual agent logs
tail -f src/logs/weather_agent.log

# Job deployment logs (using CLI)
uv run deploy logs my-job --tail 100

# Or directly:
tail -f logs/jobs/my-job-20260130-120000/controller.log

# Search for errors
grep -i error logs/jobs/my-job-*/*.log
```

### Log content truncated

If log content appears truncated, increase the limit:

```bash
export AGENT_LOG_MAX_CONTENT_LENGTH=5000  # or 0 for unlimited
```

### Enable JSON logging

For structured log analysis:

```bash
export AGENT_LOG_JSON=true
```

## Performance issues

### Slow tool calls

**Symptom:** Agent responses are slow.

**Solutions:**

1. Use SDK MCP tools (in-process) instead of subprocess MCP:
   ```python
   # Fast: SDK MCP
   server = create_sdk_mcp_server(name="fast", tools=[my_tool])

   # Slower: subprocess MCP (stdio)
   # Avoid if possible
   ```

2. Check external API latency if tools call external services

3. Review Claude's tool usage in logs - too many tool calls slow responses

### High memory usage

**Solutions:**

1. Reduce client pool size:
   ```bash
   export AGENT_CLIENT_POOL_SIZE=1
   ```

2. Use appropriate log content limits:
   ```bash
   export AGENT_LOG_MAX_CONTENT_LENGTH=1000
   ```

## Getting help

### Check agent status

```bash
# Health check
curl http://localhost:9001/health

# Full configuration
curl http://localhost:9001/.well-known/agent-configuration
```

### Collect diagnostics

When reporting issues, include:

1. Error message and stack trace
2. Agent logs (`src/logs/*.log`)
3. Configuration (environment variables)
4. Job YAML (if using job deployment)
5. Python and package versions:
   ```bash
   python --version
   uv pip list | grep -E "(claude|fastapi|pydantic)"
   ```

### Common error messages

| Error | Likely cause | Solution |
|-------|--------------|----------|
| `ANTHROPIC_API_KEY not set` | Missing API key | Set `ANTHROPIC_API_KEY` |
| `Connection refused` | Agent not running | Start the agent |
| `Address already in use` | Port conflict | Use different port |
| `Tool not found` | Tool not registered | Check `_get_allowed_tools()` |
| `Timeout` | Slow response | Increase timeout |

## See also

- [Configuration](configuration.md) - All configuration options
- [Security](security.md) - Security settings
- [SSH deployment](ssh-deployment.md) - SSH troubleshooting
