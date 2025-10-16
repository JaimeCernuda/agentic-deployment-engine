"""Job monitor - monitor running agents."""

import asyncio
import httpx
from .models import DeployedJob


class JobMonitor:
    """Monitor deployed jobs."""

    async def monitor(self, deployed: DeployedJob, interval: int = 10):
        """Monitor job continuously.

        Args:
            deployed: Deployed job to monitor
            interval: Check interval in seconds
        """
        print(f"\n👁  Monitoring {deployed.job_id}")
        print(f"   Agents: {list(deployed.agents.keys())}")
        print(f"   Interval: {interval}s")
        print(f"   Press Ctrl+C to stop\n")

        try:
            while True:
                await asyncio.sleep(interval)

                print(f"Health check at {asyncio.get_event_loop().time():.0f}s:")

                all_healthy = True
                for agent_id in deployed.agents:
                    url = deployed.urls[agent_id]
                    status = await self._check_health(agent_id, url)

                    if status["healthy"]:
                        print(f"  ✓ {agent_id}: healthy")
                    else:
                        print(f"  ✗ {agent_id}: {status['error']}")
                        all_healthy = False

                if not all_healthy:
                    print("  ⚠️  Some agents are unhealthy")

                print()

        except KeyboardInterrupt:
            print("\n⏹  Monitoring stopped")

    async def _check_health(self, agent_id: str, url: str) -> dict:
        """Check health of a single agent.

        Args:
            agent_id: Agent ID
            url: Agent URL

        Returns:
            Dict with 'healthy' bool and optional 'error' string
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{url}/health", timeout=5.0)

                if response.status_code == 200:
                    return {"healthy": True}
                else:
                    return {
                        "healthy": False,
                        "error": f"HTTP {response.status_code}"
                    }

        except httpx.ConnectError:
            return {"healthy": False, "error": "connection refused"}

        except httpx.TimeoutException:
            return {"healthy": False, "error": "timeout"}

        except Exception as e:
            return {"healthy": False, "error": str(e)}
