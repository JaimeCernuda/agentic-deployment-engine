# SSH Deployment Guide

Complete guide for deploying A2A agents to remote hosts via SSH.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [SSH Configuration](#ssh-configuration)
4. [Job Definition](#job-definition)
5. [Deployment Process](#deployment-process)
6. [Testing](#testing)
7. [Troubleshooting](#troubleshooting)
8. [Production Best Practices](#production-best-practices)

## Overview

The A2A Job System supports deploying agents to remote hosts via SSH. This enables:

- **Distributed Processing** - Spread workload across multiple machines
- **Resource Isolation** - Run agents on dedicated hardware
- **Geographic Distribution** - Deploy agents closer to data sources
- **Hybrid Deployments** - Mix local and remote agents

## Prerequisites

### On Your Local Machine

1. **SSH Client** (usually pre-installed on Linux/Mac)
   ```bash
   ssh -V
   ```

2. **Python Environment**
   ```bash
   uv sync  # Install all dependencies including paramiko
   ```

### On Remote Hosts

1. **SSH Server** running and accessible
   ```bash
   # Ubuntu/Debian
   sudo apt-get install openssh-server
   sudo systemctl start sshd
   sudo systemctl enable sshd

   # CentOS/RHEL
   sudo yum install openssh-server
   sudo systemctl start sshd
   sudo systemctl enable sshd
   ```

2. **Python 3.10+** installed
   ```bash
   python3 --version
   ```

3. **Required Python packages** (can be installed automatically or pre-installed)
   ```bash
   pip install fastapi uvicorn httpx pydantic a2a-sdk
   ```

4. **Agent code** deployed to remote host (same codebase as local)

## SSH Configuration

### Option 1: Passwordless SSH (Recommended)

#### Generate SSH Key (if you don't have one)

```bash
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"
# Press Enter to accept defaults
# Optionally set a passphrase
```

#### Copy Key to Remote Hosts

```bash
# For each remote host:
ssh-copy-id username@remote-host

# Or manually:
cat ~/.ssh/id_rsa.pub | ssh username@remote-host "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

#### Test Connection

```bash
ssh username@remote-host whoami
# Should login without password prompt
```

### Option 2: Custom SSH Key

```bash
# Generate a dedicated key for agent deployment
ssh-keygen -t rsa -b 4096 -f ~/.ssh/agent_deployment_key -N ''

# Copy to remote hosts
ssh-copy-id -i ~/.ssh/agent_deployment_key username@remote-host
```

**In job YAML:**
```yaml
deployment:
  target: remote
  host: remote-host
  ssh_key: ~/.ssh/agent_deployment_key
```

### Option 3: Password Authentication (Not Recommended)

**In job YAML:**
```yaml
deployment:
  target: remote
  host: remote-host
  user: username
  password: your-password  # Insecure! Use keys instead
```

⚠️ **Security Warning**: Password authentication is not recommended. Always use SSH keys for production.

## Job Definition

### Basic Remote Deployment

```yaml
agents:
  - id: my-agent
    type: MyAgent
    module: agents.my_agent
    config:
      port: 9001
    deployment:
      target: remote
      host: remote-host.example.com
      # Optional settings (with defaults):
      # user: <current-user>
      # ssh_key: ~/.ssh/id_rsa
      # port: 22
      # python: python3
      # workdir: ~/agents/<agent-id>
```

### Advanced Configuration

```yaml
agents:
  - id: weather
    type: WeatherAgent
    module: agents.weather_agent
    config:
      port: 9001
    deployment:
      target: remote
      host: 192.168.1.100
      user: agent-user            # Custom SSH user
      ssh_key: ~/.ssh/custom_key  # Custom SSH key
      port: 2222                  # Custom SSH port
      python: /usr/bin/python3.11 # Specific Python interpreter
      workdir: /opt/agents/weather # Custom working directory
      environment:
        LOG_LEVEL: DEBUG
        API_KEY: secret-key
```

### Multi-Host Deployment

```yaml
job:
  name: distributed-system
  version: 1.0.0

agents:
  # Agent on host 1
  - id: agent1
    module: agents.agent1
    config:
      port: 9001
    deployment:
      target: remote
      host: host1.example.com

  # Agent on host 2
  - id: agent2
    module: agents.agent2
    config:
      port: 9002
    deployment:
      target: remote
      host: host2.example.com

  # Coordinator on local machine
  - id: coordinator
    module: agents.coordinator
    config:
      port: 9000
    deployment:
      target: localhost

topology:
  type: hub-spoke
  hub: coordinator
  spokes: [agent1, agent2]
```

## Deployment Process

### 1. Prepare Remote Hosts

Ensure code is available on remote hosts:

```bash
# Option A: Use shared filesystem (NFS, etc.)
# Code automatically available

# Option B: Copy code to each host
rsync -avz --exclude 'logs' --exclude '__pycache__' \
  ./ username@remote-host:~/agents/

# Option C: Use git to pull code on remote hosts
ssh username@remote-host "cd ~/agents && git pull"
```

### 2. Validate Job Definition

```bash
uv run deploy validate jobs/my-job.yaml --verbose
```

### 3. Generate Deployment Plan

```bash
uv run deploy plan jobs/my-job.yaml
```

Review the plan to ensure:
- Agents are assigned to correct hosts
- URLs are resolved properly
- Deployment order makes sense

### 4. Deploy

```bash
uv run deploy start jobs/my-job.yaml
```

The deployer will:
1. SSH into each remote host
2. Create working directories
3. Start agents with proper environment
4. Wait for health checks
5. Set up connections according to topology

### 5. Monitor

```bash
# View agent status (placeholder - not yet implemented)
uv run deploy status my-job

# View logs (placeholder - not yet implemented)
uv run deploy logs my-job --agent agent1
```

## Testing

### Test SSH to Localhost

Perfect for testing SSH deployment without needing multiple machines:

```bash
# 1. Setup SSH to localhost
ssh-keygen -t rsa -N '' -f ~/.ssh/id_rsa
cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

# 2. Test connection
ssh localhost whoami

# 3. Run test deployment
uv run python test_ssh_deployment.py
```

### Validate Multi-Host Job

```bash
# Validate without deploying
uv run deploy validate jobs/examples/ssh-multi-host.yaml
uv run deploy plan jobs/examples/ssh-multi-host.yaml
```

## Troubleshooting

### SSH Connection Failures

**Problem**: `SSH connection failed`

**Solutions**:
```bash
# Test SSH manually
ssh -v username@remote-host

# Check SSH service on remote
ssh username@remote-host "systemctl status sshd"

# Verify SSH key permissions
chmod 600 ~/.ssh/id_rsa
chmod 644 ~/.ssh/id_rsa.pub
chmod 700 ~/.ssh
```

### Agent Fails to Start

**Problem**: Agent starts but immediately crashes

**Solutions**:
```bash
# Check remote logs
ssh username@remote-host "tail -100 ~/agents/agent-id/agent-id.log"

# Verify Python environment
ssh username@remote-host "python3 -m agents.weather_agent --help"

# Check if port is available
ssh username@remote-host "netstat -tuln | grep 9001"
```

### Module Import Errors

**Problem**: `ModuleNotFoundError` on remote host

**Solutions**:
```bash
# Ensure code is on remote host
ssh username@remote-host "ls -la ~/agents/"

# Install dependencies
ssh username@remote-host "cd ~/agents && pip install -r requirements.txt"

# Set PYTHONPATH if needed
deployment:
  environment:
    PYTHONPATH: /path/to/agents
```

### Port Conflicts

**Problem**: Port already in use on remote host

**Solutions**:
```bash
# Find what's using the port
ssh username@remote-host "sudo lsof -i :9001"

# Kill old process
ssh username@remote-host "sudo kill <PID>"

# Or use different port in job definition
config:
  port: 9101  # Use different port
```

### Health Check Timeouts

**Problem**: Agents start but health checks fail

**Solutions**:
```yaml
deployment:
  timeout: 90  # Increase timeout
  health_check:
    retries: 10  # More retries
    interval: 10  # More time between checks
```

## Production Best Practices

### 1. Security

✅ **DO**:
- Use SSH keys, never passwords
- Restrict SSH key permissions (600)
- Use dedicated deployment keys
- Rotate SSH keys periodically
- Use firewall rules to restrict access
- Run agents as non-root users

❌ **DON'T**:
- Store passwords in job files
- Use root user for deployment
- Commit SSH keys to git
- Disable host key checking in production

### 2. Resource Management

```yaml
# Specify resource limits
resources:
  cpu: 2.0
  memory: 4G

# Use dedicated hosts for resource-intensive agents
deployment:
  target: remote
  host: high-memory-host.example.com
```

### 3. Monitoring

```yaml
# Enable health checks
deployment:
  health_check:
    enabled: true
    interval: 30
    retries: 3

# Set appropriate timeouts
deployment:
  timeout: 120  # For slow-starting agents
```

### 4. Code Deployment

**Option A: Shared Filesystem**
```yaml
deployment:
  workdir: /mnt/shared/agents  # NFS mount
```

**Option B: Pre-deployment**
```bash
# Deploy code before running agents
for host in host1 host2 host3; do
  rsync -avz ./ username@$host:~/agents/
done
```

**Option C: Container Deployment**
```yaml
# Use containers instead for better isolation
deployment:
  target: container
  image: my-agent:latest
```

### 5. High Availability

```yaml
# Deploy redundant agents
agents:
  - id: weather-primary
    deployment:
      target: remote
      host: host1.example.com

  - id: weather-backup
    deployment:
      target: remote
      host: host2.example.com

# Use load balancing topology
topology:
  type: mesh  # Agents can failover to each other
```

### 6. Logging

```yaml
# Configure logging
environment:
  LOG_LEVEL: INFO
  LOG_FILE: /var/log/agents/my-agent.log

# Centralized logging
deployment:
  environment:
    SYSLOG_HOST: logs.example.com
```

## Example Workflows

### Development: Test Locally with SSH

```bash
# Test SSH deployment to localhost
uv run deploy start jobs/examples/ssh-localhost.yaml
```

### Staging: Deploy to Test Servers

```yaml
deployment:
  target: remote
  host: staging-server.example.com
environment:
  DEPLOYMENT_ENV: staging
```

### Production: Multi-Host Distributed

```yaml
# weather-host: Dedicated weather processing
# maps-host: Dedicated maps processing
# controller-host: Coordination and API
topology:
  type: hub-spoke
  hub: controller
  spokes: [weather, maps, travel, ...]
```

## SSH Configuration Reference

| Parameter | Default | Description |
|-----------|---------|-------------|
| `host` | *required* | Hostname or IP address |
| `user` | Current user | SSH username |
| `ssh_key` | `~/.ssh/id_rsa` | Path to SSH private key |
| `password` | None | SSH password (not recommended) |
| `port` | 22 | SSH port |
| `python` | `python3` | Python interpreter on remote host |
| `workdir` | `~/agents/<agent-id>` | Working directory on remote host |
| `environment` | `{}` | Additional environment variables |

## Next Steps

1. **Test locally**: Use `ssh-localhost.yaml` example
2. **Deploy to staging**: Use actual remote hosts
3. **Monitor and debug**: Check logs and health
4. **Scale to production**: Multi-host deployment
5. **Automate**: Integrate with CI/CD pipelines

## See Also

- [Job Specification](JOB_SPECIFICATION.md) - Complete job format
- [Deployment Engine](REFINED_ARCHITECTURE.md) - Architecture details
- [Examples](examples/) - More job examples
- [Quick Reference](QUICK_REFERENCE.md) - Command cheat sheet
