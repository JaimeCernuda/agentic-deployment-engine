# Security Documentation

This document describes the security features, configurations, and best practices for the Agentic Deployment Engine.

## Authentication

### API Key Authentication

The framework supports optional API key authentication for agent endpoints.

#### Configuration

Set the following environment variables:

```bash
# Enable authentication (default: false)
export AGENT_AUTH_REQUIRED=true

# Set the API key (required when auth is enabled)
export AGENT_API_KEY=your-secure-api-key-here
```

#### Usage

When authentication is enabled, include the API key in requests:

```bash
# Via header (recommended)
curl -H "X-API-Key: your-api-key" http://localhost:9000/query

# Via query parameter
curl "http://localhost:9000/query?api_key=your-api-key"
```

#### Best Practices

- Use strong, randomly generated API keys (minimum 32 characters)
- Rotate keys regularly
- Never commit API keys to version control
- Use different keys for different environments

## SSRF Protection

Server-Side Request Forgery (SSRF) protection prevents agents from making requests to unauthorized internal resources.

### Configuration

```bash
# Allowed hosts (comma-separated, supports wildcards)
export AGENT_ALLOWED_HOSTS=api.example.com,*.trusted-domain.com

# Allowed port range (default: 80,443,8000-9999)
export AGENT_ALLOWED_PORTS=80,443,8000-9999

# Block private IP ranges (default: true)
export AGENT_BLOCK_PRIVATE_IPS=true
```

### Protected Resources

By default, the following are blocked:

- Private IP ranges (10.x.x.x, 172.16-31.x.x, 192.168.x.x)
- Loopback addresses (127.x.x.x, ::1)
- Link-local addresses (169.254.x.x)
- Metadata endpoints (169.254.169.254)

### URL Validation

All outbound URLs are validated before requests are made:

```python
from src.auth import validate_url

# Raises ValueError if URL is not allowed
validate_url("https://api.example.com/data")
```

## SSH Security

### Host Key Verification

The SSH runner uses `RejectPolicy` by default, which prevents man-in-the-middle attacks by rejecting unknown host keys.

#### Adding New Hosts

Before deploying to a new host, add it to known_hosts:

```bash
# Scan and add host key
ssh-keyscan -H hostname >> ~/.ssh/known_hosts

# Verify the fingerprint matches expected value
ssh-keygen -lf ~/.ssh/known_hosts
```

#### Key-Based Authentication

Always prefer SSH keys over passwords:

```yaml
# In job definition
agents:
  - id: my-agent
    deployment:
      target: remote
      host: server.example.com
      ssh_key: ~/.ssh/id_ed25519  # Recommended
      # password: ...  # Avoid - triggers security warning
```

### Password Security

If passwords must be used:

- Passwords are stored as `SecretStr` (Pydantic) to prevent accidental logging
- A warning is logged when password authentication is configured
- Passwords are never written to log files or displayed in output

## Prompt Injection Defense

### Input Sanitization

User inputs are sanitized before being processed by agents:

```python
from src.auth import sanitize_prompt

# Removes potentially dangerous patterns
safe_input = sanitize_prompt(user_input)
```

### Protected Patterns

The sanitizer removes or escapes:

- System prompt override attempts (`[SYSTEM]`, `<|system|>`)
- Instruction injection markers
- Role impersonation attempts
- Unicode homoglyphs that could bypass filters

### Agent Isolation

- Each agent runs with a fixed system prompt set at initialization
- System prompts are immutable after agent creation
- Agents cannot modify their own permissions at runtime

## Shell Command Safety

### Environment Variable Escaping

All environment variables passed to remote processes are escaped using `shlex.quote()`:

```python
# Safe escaping prevents injection
env_str = " ".join([f"{k}={shlex.quote(v)}" for k, v in env_vars.items()])
```

### Path Sanitization

Working directories and file paths in shell commands are properly quoted:

```python
safe_workdir = shlex.quote(workdir)
cmd = f"cd {safe_workdir} && ..."
```

### Command Construction

- Never use string formatting with untrusted input in shell commands
- Always use `shlex.quote()` for dynamic values
- Prefer subprocess with list arguments over shell=True

## Secrets Management

### SecretStr for Sensitive Data

Sensitive fields use Pydantic's `SecretStr` type:

```python
from pydantic import SecretStr

class DeploymentConfig(BaseModel):
    password: SecretStr | None = None

# Access requires explicit call
actual_password = config.password.get_secret_value()
```

This prevents accidental exposure in:
- Log output
- Error messages
- Debug representations
- JSON serialization

### Environment Variables

Store secrets in environment variables, not configuration files:

```bash
# Good
export AGENT_API_KEY=secret-value

# Bad - don't put secrets in job YAML files
```

## Network Security

### TLS/HTTPS

For production deployments:

- Use HTTPS for all agent communication
- Configure TLS certificates properly
- Use secure cipher suites

### Port Restrictions

Agents bind to specific ports:

- Default range: 9000-9999
- Configure firewall rules to restrict access
- Use reverse proxy for external access

## Logging Security

### Sensitive Data Redaction

Logs automatically redact:

- API keys
- Passwords
- SSH key contents
- Bearer tokens

### Log File Permissions

Log files are created with restricted permissions:

```bash
chmod 600 logs/*.log  # Owner read/write only
```

## Security Checklist

Before deploying to production:

- [ ] API key authentication enabled
- [ ] Strong API keys generated
- [ ] SSRF protection configured
- [ ] SSH keys set up (no passwords)
- [ ] Known hosts verified
- [ ] TLS/HTTPS configured
- [ ] Firewall rules in place
- [ ] Log permissions restricted
- [ ] Secrets in environment variables (not files)
- [ ] Regular security updates scheduled

## Reporting Security Issues

If you discover a security vulnerability, please report it responsibly:

1. Do not open a public issue
2. Email the security team with details
3. Allow time for a fix before disclosure

## References

- [OWASP SSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- [SSH Security Best Practices](https://www.ssh.com/academy/ssh/security)
- [Pydantic SecretStr](https://docs.pydantic.dev/latest/concepts/types/#secret-types)
