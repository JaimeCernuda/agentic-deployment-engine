# SSH Testing Guide

## Quick Test: SSH to Localhost

### Option 1: Automated Setup (Recommended)

Run the setup script:
```bash
./setup_ssh_localhost.sh
```

This will:
1. Check if SSH server is installed
2. Generate SSH keys if needed
3. Configure passwordless authentication
4. Start SSH server
5. Test the connection

Then run the test:
```bash
uv run python test_ssh_localhost.py
```

### Option 2: Manual Setup

#### 1. Install SSH Server (if not installed)

```bash
sudo apt-get update
sudo apt-get install openssh-server
```

#### 2. Generate SSH Key (if you don't have one)

```bash
# Use existing key or generate new one
if [ ! -f ~/.ssh/id_rsa ]; then
    ssh-keygen -t rsa -b 4096 -N ""
fi
```

You already have keys (`id_ed25519`), so you can use those.

#### 3. Add Key to Authorized Keys

```bash
# Create authorized_keys if it doesn't exist
mkdir -p ~/.ssh
touch ~/.ssh/authorized_keys
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys

# Add your public key
cat ~/.ssh/id_ed25519.pub >> ~/.ssh/authorized_keys
```

#### 4. Start SSH Server

**For WSL:**
```bash
sudo service ssh start
```

**Or if you have systemd:**
```bash
sudo systemctl start ssh
sudo systemctl enable ssh
```

#### 5. Test SSH Connection

```bash
ssh localhost whoami
```

If it asks for a password, the key isn't set up correctly. It should log in without a password.

#### 6. Run the Test

```bash
uv run python test_ssh_localhost.py
```

### Option 3: Using Existing Host

If you have access to another machine with SSH, you can test there:

1. Edit `jobs/examples/ssh-multi-host.yaml`
2. Replace hostnames with your actual hosts
3. Run the test

```bash
# Edit the file to use your real hosts
vim jobs/examples/ssh-multi-host.yaml

# Test
uv run deploy validate jobs/examples/ssh-multi-host.yaml
uv run deploy start jobs/examples/ssh-multi-host.yaml
```

## Troubleshooting

### "Connection refused"

SSH server isn't running:
```bash
sudo service ssh start
# or
sudo systemctl start ssh
```

### "Permission denied (publickey)"

Keys not configured:
```bash
cat ~/.ssh/id_ed25519.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

### "Could not resolve hostname"

Check your hostname:
```bash
hostname
# Use the output in your job YAML
```

### Port 22 in use

Change SSH port in `/etc/ssh/sshd_config`:
```bash
sudo vim /etc/ssh/sshd_config
# Change: Port 2222
sudo service ssh restart
```

Then in your job YAML:
```yaml
deployment:
  target: remote
  host: localhost
  port: 2222
```

## WSL-Specific Notes

If you're running in WSL (which you are), you may need to:

1. **Start SSH manually each time:**
   ```bash
   sudo service ssh start
   ```

2. **Or configure WSL to auto-start SSH:**
   Create `/etc/wsl.conf`:
   ```ini
   [boot]
   command = service ssh start
   ```

3. **Check Windows Firewall:**
   WSL shares the Windows network stack, so ensure Windows Firewall allows SSH.

## Testing the SSH Deployment

Once SSH is set up, the test will:

1. ✅ Verify SSH connectivity
2. ✅ Load `jobs/examples/ssh-localhost.yaml`
3. ✅ Deploy 2 agents via SSH (weather, maps)
4. ✅ Deploy 1 agent locally (controller)
5. ✅ Verify health checks
6. ✅ Test A2A communication between local and SSH-deployed agents
7. ✅ Stop all agents and close SSH connections

## What Gets Tested

### Deployment Flow

```
Local Machine (Deployer)
    │
    ├─ SSH ──> localhost (Weather Agent on port 9101)
    │          - Connects via SSH
    │          - Creates working directory
    │          - Starts agent via nohup
    │          - Monitors health
    │
    ├─ SSH ──> localhost (Maps Agent on port 9102)
    │          - Same process
    │
    └─ Local --> Controller Agent (port 9100)
                - Runs locally
                - Connects to SSH-deployed agents
                - Tests A2A communication
```

### Key Features Verified

- ✅ SSH connection pooling (reuses connections)
- ✅ Passwordless authentication (uses your existing keys)
- ✅ Remote process management (start via nohup)
- ✅ Environment variable propagation
- ✅ Health checking remote agents
- ✅ A2A communication across deployment types
- ✅ Graceful shutdown (kills remote processes)
- ✅ SSH connection cleanup

## Expected Output

```bash
$ uv run python test_ssh_localhost.py

================================================================================
SSH LOCALHOST DEPLOYMENT TEST
================================================================================

1. Checking SSH connectivity...
   ✓ SSH to localhost is working

2. Loading job: jobs/examples/ssh-localhost.yaml
   ✓ Job: ssh-localhost-test
   ✓ Agents: 3
     - weather: remote (host=localhost)
     - maps: remote (host=localhost)
     - controller: localhost (host=N/A)

3. Generating deployment plan...
   ✓ Stages: 2
     Stage 1: weather, maps
     Stage 2: controller

4. Deploying agents via SSH...
   (This will SSH into localhost and start agents remotely)
    Connecting to jcernuda@localhost:22...
    ✓ SSH connected
    Transferring code to /tmp/agents/weather...
    Starting remote process...
    ✓ Remote process started (PID: 12345)
  Deploying weather... ✓ http://localhost:9101
    Connecting to jcernuda@localhost:22...
    ✓ SSH connected (reusing connection)
    Transferring code to /tmp/agents/maps...
    Starting remote process...
    ✓ Remote process started (PID: 12346)
  Deploying maps... ✓ http://localhost:9102
  Deploying controller... ✓ http://localhost:9100

5. Health checks...
   ✓ weather (http://localhost:9101)
     Name: Weather Agent (SSH)
   ✓ maps (http://localhost:9102)
     Name: Maps Agent (SSH)
   ✓ controller (http://localhost:9100)
     Name: Controller Agent (Local)

6. Testing controller → weather agent communication...
   (Controller is local, weather/maps are via SSH)
   ✓ Query successful
   Response preview: The current weather in Tokyo is...

7. Verifying remote processes on localhost...
   ✓ Remote agents are running on localhost:
     - PID 12345: python -m agents.weather_agent
     - PID 12346: python -m agents.maps_agent

8. Keeping agents running for 5 seconds...

9. Stopping agents...
   ✓ SSH connections closed
   ✓ Stopped

================================================================================
✅ SSH LOCALHOST DEPLOYMENT TEST COMPLETE
================================================================================

Verified:
  ✓ SSH connectivity to localhost
  ✓ Job loading and validation
  ✓ Deployment plan generation
  ✓ SSH deployment (2 agents via SSH, 1 local)
  ✓ Remote process startup
  ✓ Health checks (all healthy)
  ✓ A2A communication (local ↔ SSH agents)
  ✓ Process management (start/stop)

🎉 SSH deployment is fully functional!
```

## Next Steps

After verifying SSH works locally:

1. **Test with Real Cluster:**
   - Update `jobs/examples/ssh-multi-host.yaml` with your cluster hosts
   - Ensure passwordless SSH is configured across cluster
   - Verify unified usernames
   - Deploy!

2. **Create Production Jobs:**
   ```yaml
   agents:
     - id: worker1
       deployment:
         target: remote
         host: node1.cluster.local
         # user defaults to current user
         # ssh_key defaults to ~/.ssh/id_rsa
   ```

3. **Monitor Deployment:**
   - Check logs in `/tmp/agents/<agent-id>/<agent-id>.log` on remote hosts
   - Use `uv run deploy status` (when implemented)
   - SSH into nodes to verify: `ssh node1 'ps aux | grep agent'`

## Files

- **Test Script:** `test_ssh_localhost.py`
- **Setup Script:** `setup_ssh_localhost.sh`
- **Job Definition:** `jobs/examples/ssh-localhost.yaml`
- **Multi-host Example:** `jobs/examples/ssh-multi-host.yaml`
- **Full Guide:** `jobs/SSH_DEPLOYMENT_GUIDE.md`
