"""Test SSH deployment (requires SSH server setup)."""

import asyncio
import os
from pathlib import Path
from src.jobs.loader import JobLoader
from src.jobs.resolver import TopologyResolver
from src.jobs.deployer import AgentDeployer


def check_ssh_available():
    """Check if SSH to localhost is available."""
    import subprocess
    try:
        result = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=2", "localhost", "whoami"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


async def test_ssh_deployment():
    """Test deploying agents via SSH to localhost."""
    print("=" * 80)
    print("Testing SSH Deployment")
    print("=" * 80)

    # Check SSH availability
    print("\n1. Checking SSH setup...")
    if not check_ssh_available():
        print("   ✗ SSH to localhost not available")
        print("\n   To enable SSH deployment testing:")
        print("   1. Install SSH server:")
        print("      sudo apt-get install openssh-server  (Ubuntu/Debian)")
        print("      sudo yum install openssh-server      (CentOS/RHEL)")
        print("   2. Start SSH service:")
        print("      sudo systemctl start sshd")
        print("   3. Setup passwordless SSH:")
        print("      ssh-keygen -t rsa -N '' -f ~/.ssh/id_rsa")
        print("      cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys")
        print("      chmod 600 ~/.ssh/authorized_keys")
        print("   4. Test connection:")
        print("      ssh localhost whoami")
        print("\n   Skipping SSH deployment test.")
        return

    print("   ✓ SSH to localhost available")

    # Load job
    print("\n2. Loading SSH job definition...")
    loader = JobLoader()
    job = loader.load("jobs/examples/ssh-localhost.yaml")
    print(f"   ✓ Loaded: {job.job.name}")

    # Generate plan
    print("\n3. Generating deployment plan...")
    resolver = TopologyResolver()
    plan = resolver.resolve(job)
    print(f"   ✓ Stages: {len(plan.stages)}")
    for idx, stage in enumerate(plan.stages):
        print(f"      Stage {idx + 1}: {', '.join(stage)}")

    # Deploy
    print("\n4. Deploying agents via SSH...")
    deployer = AgentDeployer()
    deployed_job = await deployer.deploy(job, plan)
    print(f"   ✓ Deployed: {deployed_job.job_id}")

    # Test health
    print("\n5. Testing agent health...")
    import httpx
    async with httpx.AsyncClient() as client:
        for agent_id, agent in deployed_job.agents.items():
            try:
                response = await client.get(
                    f"{agent.url}/.well-known/agent-configuration",
                    timeout=5.0
                )
                if response.status_code == 200:
                    print(f"   ✓ {agent_id} ({agent.url}): healthy")
                else:
                    print(f"   ✗ {agent_id} ({agent.url}): status {response.status_code}")
            except Exception as e:
                print(f"   ✗ {agent_id} ({agent.url}): {e}")

    # Wait
    print("\n6. Agents running. Waiting 5 seconds...")
    await asyncio.sleep(5)

    # Cleanup
    print("\n7. Stopping agents...")
    await deployer.stop(deployed_job)

    # Close SSH connections
    if "remote" in deployer.runners:
        deployer.runners["remote"].close_all()

    print("   ✓ Agents stopped")

    print("\n" + "=" * 80)
    print("SSH deployment test complete!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_ssh_deployment())
