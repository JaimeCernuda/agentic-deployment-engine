"""Agent deployer - execute deployment plans."""

import asyncio
import httpx
import time
from typing import Dict
from .models import JobDefinition, DeploymentPlan, DeployedJob, AgentProcess
from .runners import LocalRunner


class AgentDeployer:
    """Deploy agents according to deployment plan."""

    def __init__(self):
        self.runners = {
            "localhost": LocalRunner(),
            # Add SSHRunner, DockerRunner later
        }

    async def deploy(self, job: JobDefinition, plan: DeploymentPlan) -> DeployedJob:
        """Execute deployment plan.

        Args:
            job: Job definition
            plan: Deployment plan from TopologyResolver

        Returns:
            DeployedJob with running agents
        """
        print(f"\n🚀 Deploying job: {job.job.name}")
        print(f"   Stages: {len(plan.stages)}")
        print(f"   Agents: {len(job.agents)}")
        print()

        deployed_agents: Dict[str, AgentProcess] = {}

        # Deploy stage by stage
        for stage_num, stage_agent_ids in enumerate(plan.stages, 1):
            print(f"📦 Stage {stage_num}/{len(plan.stages)}: {stage_agent_ids}")

            # Deploy all agents in this stage in parallel
            tasks = []
            for agent_id in stage_agent_ids:
                task = self._deploy_agent(job, agent_id, plan)
                tasks.append((agent_id, task))

            # Wait for all agents in stage to be ready
            for agent_id, task in tasks:
                agent_process = await task
                deployed_agents[agent_id] = agent_process

            print()

        print(f"✅ All agents deployed successfully!\n")

        return DeployedJob(
            job_id=job.job.name,
            definition=job,
            agents=deployed_agents,
            urls=plan.agent_urls,
            plan=plan
        )

    async def _deploy_agent(self, job: JobDefinition, agent_id: str, plan: DeploymentPlan) -> AgentProcess:
        """Deploy a single agent.

        Args:
            job: Job definition
            agent_id: Agent ID to deploy
            plan: Deployment plan

        Returns:
            AgentProcess
        """
        agent_config = job.get_agent(agent_id)
        if not agent_config:
            raise ValueError(f"Agent {agent_id} not found in job definition")

        # Get connected URLs for this agent
        connected_urls = plan.connections.get(agent_id, [])

        print(f"  🔨 Starting {agent_id}...")
        if connected_urls:
            print(f"     Connections: {len(connected_urls)}")

        # Select appropriate runner
        runner = self.runners.get(agent_config.deployment.target)
        if not runner:
            raise ValueError(f"No runner for deployment target: {agent_config.deployment.target}")

        # Start agent
        process = runner.start(agent_config, connected_urls)

        # Wait for health check
        agent_url = plan.agent_urls[agent_id]
        await self._wait_for_health(agent_url, agent_id, timeout=job.deployment.timeout)

        print(f"  ✓ {agent_id} healthy at {agent_url}")

        return AgentProcess(agent_id, process)

    async def _wait_for_health(self, agent_url: str, agent_id: str, timeout: int = 60):
        """Wait for agent health check to pass.

        Args:
            agent_url: Agent URL
            agent_id: Agent ID (for logging)
            timeout: Timeout in seconds

        Raises:
            TimeoutError: If agent doesn't become healthy in time
        """
        start = time.time()
        attempt = 0

        while time.time() - start < timeout:
            attempt += 1
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{agent_url}/health", timeout=5.0)
                    if response.status_code == 200:
                        return  # Success!

            except (httpx.ConnectError, httpx.TimeoutException):
                pass  # Not ready yet

            except Exception as e:
                print(f"     Health check error (attempt {attempt}): {e}")

            await asyncio.sleep(2)

        raise TimeoutError(
            f"Agent {agent_id} at {agent_url} failed to become healthy after {timeout}s"
        )
