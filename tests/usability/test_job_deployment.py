"""Test job deployment system.

This is an end-to-end test that deploys and tests the job system.
Requires Claude SDK to be properly configured.

Run with: uv run pytest -m e2e
"""

import asyncio

import httpx
import pytest

from src.jobs.deployer import AgentDeployer
from src.jobs.loader import JobLoader
from src.jobs.resolver import TopologyResolver

# Mark all tests in this module as e2e tests
pytestmark = pytest.mark.usability


async def test_deployment():
    """Test deploying simple-weather.yaml job."""
    print("=" * 80)
    print("Testing Job Deployment System")
    print("=" * 80)

    # 1. Load job
    print("\n1. Loading job definition...")
    loader = JobLoader()
    job = loader.load("jobs/examples/simple-weather.yaml")
    print(f"   ✓ Loaded: {job.job.name} v{job.job.version}")
    print(f"   ✓ Agents: {len(job.agents)}")
    print(f"   ✓ Topology: {job.topology.type}")

    # 2. Generate plan
    print("\n2. Generating deployment plan...")
    resolver = TopologyResolver()
    plan = resolver.resolve(job)
    print(f"   ✓ Stages: {len(plan.stages)}")
    for idx, stage in enumerate(plan.stages):
        print(f"      Stage {idx + 1}: {', '.join(stage)}")

    # 3. Deploy
    print("\n3. Deploying agents...")
    deployer = AgentDeployer()
    deployed_job = await deployer.deploy(job, plan)
    print(f"   ✓ Deployed: {deployed_job.job_id}")
    print(f"   ✓ Status: {deployed_job.status}")

    # 4. Test health
    print("\n4. Testing agent health...")
    async with httpx.AsyncClient() as client:
        for agent_id, agent in deployed_job.agents.items():
            try:
                response = await client.get(
                    f"{agent.url}/.well-known/agent-configuration", timeout=5.0
                )
                if response.status_code == 200:
                    print(f"   ✓ {agent_id} ({agent.url}): healthy")
                else:
                    print(
                        f"   ✗ {agent_id} ({agent.url}): status {response.status_code}"
                    )
            except Exception as e:
                print(f"   ✗ {agent_id} ({agent.url}): {e}")

    # 5. Test query to controller
    print("\n5. Testing controller query...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "http://localhost:9000/query",
                json={"query": "What's the weather in Tokyo?"},
                timeout=30.0,
            )
            if response.status_code == 200:
                result = response.json()
                print("   ✓ Query successful")
                print(f"   Response: {result.get('response', 'N/A')[:200]}...")
            else:
                print(f"   ✗ Query failed: {response.status_code}")
        except Exception as e:
            print(f"   ✗ Query error: {e}")

    # 6. Wait a bit to keep agents running
    print("\n6. Agents running. Waiting 5 seconds...")
    await asyncio.sleep(5)

    # 7. Cleanup
    print("\n7. Stopping agents...")
    await deployer.stop(deployed_job)
    print("   ✓ Agents stopped")

    print("\n" + "=" * 80)
    print("Test complete!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_deployment())
