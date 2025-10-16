# SSH Test Ready - Complete Setup

## Current Status

✅ **SSH Implementation:** Fully complete and ready
✅ **Test Script:** Created (`test_ssh_localhost.py`)
✅ **SSH Keys:** Already configured in your system
✅ **Authorized Keys:** Set up (key added to `~/.ssh/authorized_keys`)

⚠️ **Needs:** SSH server to be started (requires sudo)

## Quick Start (2 Commands)

### 1. Start SSH Server

```bash
sudo service ssh start
```

### 2. Run Test

```bash
uv run python test_ssh_localhost.py
```

That's it! The test will deploy weather and maps agents via SSH to localhost, and a controller locally.

## What Will Happen

When you run the test, it will:

1. ✅ Check SSH connectivity to localhost
2. ✅ Load `jobs/examples/ssh-localhost.yaml`
3. ✅ Deploy 2 agents via SSH (weather on port 9101, maps on port 9102)
4. ✅ Deploy 1 agent locally (controller on port 9100)
5. ✅ Verify all agents are healthy
6. ✅ Test A2A communication (controller queries weather agent)
7. ✅ Verify remote processes are running
8. ✅ Stop all agents and close SSH connections

## Job Definition Being Used

File: `jobs/examples/ssh-localhost.yaml`

```yaml
job:
  name: ssh-localhost-test
  version: 1.0.0
  description: Test SSH deployment to localhost

agents:
  # Weather via SSH
  - id: weather
    type: WeatherAgent
    module: agents.weather_agent
    config:
      port: 9101
    deployment:
      target: remote
      host: localhost
      workdir: /tmp/agents/weather
      # Uses your current username automatically
      # Uses ~/.ssh/id_ed25519 automatically

  # Maps via SSH
  - id: maps
    type: MapsAgent
    module: agents.maps_agent
    config:
      port: 9102
    deployment:
      target: remote
      host: localhost
      workdir: /tmp/agents/maps

  # Controller local
  - id: controller
    type: ControllerAgent
    module: agents.controller_agent
    config:
      port: 9100
    deployment:
      target: localhost

topology:
  type: hub-spoke
  hub: controller
  spokes: [weather, maps]
```

## Expected Test Output

```
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
    Connecting to jcernuda@localhost:22...
    ✓ SSH connected
    Transferring code to /tmp/agents/weather...
    Starting remote process...
    ✓ Remote process started (PID: xxxxx)
  Deploying weather... ✓ http://localhost:9101

    Connecting to jcernuda@localhost:22...
    ✓ SSH connected
    Transferring code to /tmp/agents/maps...
    Starting remote process...
    ✓ Remote process started (PID: xxxxx)
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
   ✓ Query successful

7. Verifying remote processes on localhost...
   ✓ Remote agents are running

8. Keeping agents running for 5 seconds...

9. Stopping agents...
   ✓ Stopped

================================================================================
✅ SSH LOCALHOST DEPLOYMENT TEST COMPLETE
================================================================================
```

## Comparison: Local vs SSH Deployment

### Test Already Run (Local):
```bash
$ uv run python test_full_integration.py
```
- File: `jobs/examples/simple-weather.yaml`
- All agents on localhost via subprocess
- Ports: 9000, 9001, 9002
- ✅ PASSED

### Test Ready (SSH):
```bash
$ sudo service ssh start
$ uv run python test_ssh_localhost.py
```
- File: `jobs/examples/ssh-localhost.yaml`
- 2 agents via SSH, 1 local
- Ports: 9100, 9101, 9102 (different to avoid conflicts)
- ⏳ READY TO RUN

## For Your Cluster Testing

Once this works, you can deploy to your cluster with minimal changes:

```yaml
agents:
  - id: worker1
    deployment:
      target: remote
      host: node1.your-cluster.com
      # That's it! Uses your username and SSH keys automatically

  - id: worker2
    deployment:
      target: remote
      host: node2.your-cluster.com
```

Since you have:
- ✅ Passwordless SSH
- ✅ Unified usernames

It will work exactly the same way!

## Verification Commands

After the test runs, you can manually verify:

```bash
# Check remote processes
ssh localhost "ps aux | grep agent"

# Check remote logs
ssh localhost "tail /tmp/agents/weather/weather.log"
ssh localhost "tail /tmp/agents/maps/maps.log"

# Test health directly
curl http://localhost:9101/.well-known/agent-configuration
curl http://localhost:9102/.well-known/agent-configuration
```

## Cleanup

The test automatically cleans up, but if needed:

```bash
# Kill remote processes
ssh localhost "pkill -f agents.weather_agent"
ssh localhost "pkill -f agents.maps_agent"

# Remove temp directories
ssh localhost "rm -rf /tmp/agents"
```

## Next Steps

1. **Run SSH Test:**
   ```bash
   sudo service ssh start
   uv run python test_ssh_localhost.py
   ```

2. **Test on Your Cluster:**
   - Edit `jobs/examples/ssh-multi-host.yaml`
   - Replace example.com hostnames with your real cluster nodes
   - Deploy!

3. **Create Pipeline Test:** (for future)
   - Create agents for pipeline pattern
   - Test sequential processing
   - Verify data flow

## Files Created for You

- ✅ `test_ssh_localhost.py` - Main SSH test (mirrors local test)
- ✅ `setup_ssh_localhost.sh` - Automated SSH setup script
- ✅ `SSH_TESTING_GUIDE.md` - Comprehensive guide
- ✅ `SSH_TEST_READY.md` - This quick start guide
- ✅ `jobs/examples/ssh-localhost.yaml` - SSH job definition
- ✅ `jobs/examples/ssh-multi-host.yaml` - Multi-host template
- ✅ `jobs/SSH_DEPLOYMENT_GUIDE.md` - Full deployment documentation

## Summary

Everything is ready! Just run:

```bash
sudo service ssh start
uv run python test_ssh_localhost.py
```

This will verify that SSH deployment works exactly like local deployment, preparing you for cluster deployment with passwordless SSH and unified usernames.
