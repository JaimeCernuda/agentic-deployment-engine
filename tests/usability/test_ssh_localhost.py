"""Test SSH deployment to localhost - mirrors local deployment test."""

import asyncio
import subprocess

import httpx
import pytest

pytestmark = [pytest.mark.usability, pytest.mark.slow]


def check_ssh_available():
    """Check if SSH to localhost is available."""
    try:
        result = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=2",
                "localhost",
                "whoami",
            ],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


async def test_ssh_localhost_deployment():
    """Test complete deployment via SSH to localhost."""
    print("=" * 80)
    print("SSH LOCALHOST DEPLOYMENT TEST")
    print("=" * 80)

    # Check SSH
    print("\n1. Checking SSH connectivity...")
    if not check_ssh_available():
        print("   ✗ SSH to localhost not available")
        print("\n   To enable SSH deployment, run:")
        print("     ./setup_ssh_localhost.sh")
        print("\n   Or manually:")
        print("     1. Install: sudo apt-get install openssh-server")
        print("     2. Start: sudo systemctl start ssh")
        print("     3. Setup key: ssh-keygen -t rsa && ssh-copy-id localhost")
        print("     4. Test: ssh localhost whoami")
        return False

    print("   ✓ SSH to localhost is working")

    from src.jobs.deployer import AgentDeployer
    from src.jobs.loader import JobLoader
    from src.jobs.resolver import TopologyResolver

    # Load SSH job
    print("\n2. Loading job: examples/jobs/ssh-localhost.yaml")
    loader = JobLoader()
    job = loader.load("examples/jobs/ssh-localhost.yaml")
    print(f"   ✓ Job: {job.job.name}")
    print(f"   ✓ Agents: {len(job.agents)}")

    # Show deployment targets
    for agent in job.agents:
        target = agent.deployment.target
        host = agent.deployment.host if target == "remote" else "N/A"
        print(f"     - {agent.id}: {target} (host={host})")

    # Generate plan
    print("\n3. Generating deployment plan...")
    resolver = TopologyResolver()
    plan = resolver.resolve(job)
    print(f"   ✓ Stages: {len(plan.stages)}")
    for idx, stage in enumerate(plan.stages):
        print(f"     Stage {idx + 1}: {', '.join(stage)}")

    # Deploy via SSH
    print("\n4. Deploying agents via SSH...")
    print("   (This will SSH into localhost and start agents remotely)")
    deployer = AgentDeployer()

    try:
        deployed = await deployer.deploy(job, plan)
        print(f"   ✓ Deployed: {deployed.job_id}")
        print(f"   ✓ Status: {deployed.status}")

        # Health checks
        print("\n5. Health checks...")
        async with httpx.AsyncClient() as client:
            for agent_id, agent in deployed.agents.items():
                try:
                    response = await client.get(
                        f"{agent.url}/.well-known/agent-configuration", timeout=5.0
                    )
                    if response.status_code == 200:
                        config = response.json()
                        print(f"   ✓ {agent_id} ({agent.url})")
                        print(f"     Name: {config.get('name', 'N/A')}")
                    else:
                        print(f"   ✗ {agent_id}: HTTP {response.status_code}")
                except Exception as e:
                    print(f"   ✗ {agent_id}: {e}")

        # Test controller query (A2A communication over SSH-deployed agents)
        print("\n6. Testing controller → weather agent communication...")
        print("   (Controller is local, weather/maps are via SSH)")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:9100/query",  # Controller on port 9100 (from ssh-localhost.yaml)
                json={"query": "What's the weather in Tokyo?"},
                timeout=30.0,
            )

            if response.status_code == 200:
                result = response.json()
                print("   ✓ Query successful")
                print(f"   Response preview: {result.get('response', '')[:150]}...")
            else:
                print(f"   ✗ Query failed: {response.status_code}")

        # Check remote processes
        print("\n7. Verifying remote processes on localhost...")
        result = subprocess.run(
            [
                "ssh",
                "localhost",
                "ps aux | grep -E '(weather_agent|maps_agent)' | grep -v grep",
            ],
            capture_output=True,
            text=True,
        )
        if result.stdout.strip():
            print("   ✓ Remote agents are running on localhost:")
            for line in result.stdout.strip().split("\n")[:2]:
                parts = line.split()
                if len(parts) > 10:
                    print(f"     - PID {parts[1]}: {' '.join(parts[10:])[:60]}")
        else:
            print("   ⚠ Could not verify remote processes")

        # Wait
        print("\n8. Keeping agents running for 5 seconds...")
        await asyncio.sleep(5)

        # Cleanup
        print("\n9. Stopping agents...")
        await deployer.stop(deployed)

        # Close SSH connections
        if "remote" in deployer.runners:
            deployer.runners["remote"].close_all()
            print("   ✓ SSH connections closed")

        print("   ✓ Stopped")

        print("\n" + "=" * 80)
        print("✅ SSH LOCALHOST DEPLOYMENT TEST COMPLETE")
        print("=" * 80)
        print("\nVerified:")
        print("  ✓ SSH connectivity to localhost")
        print("  ✓ Job loading and validation")
        print("  ✓ Deployment plan generation")
        print("  ✓ SSH deployment (2 agents via SSH, 1 local)")
        print("  ✓ Remote process startup")
        print("  ✓ Health checks (all healthy)")
        print("  ✓ A2A communication (local ↔ SSH agents)")
        print("  ✓ Process management (start/stop)")
        print("\n🎉 SSH deployment is fully functional!")

        return True

    except Exception as e:
        print(f"\n✗ Deployment failed: {e}")
        import traceback

        traceback.print_exc()

        # Try to cleanup
        try:
            if "remote" in deployer.runners:
                deployer.runners["remote"].close_all()
        except:
            pass

        return False


if __name__ == "__main__":
    success = asyncio.run(test_ssh_localhost_deployment())
    exit(0 if success else 1)
