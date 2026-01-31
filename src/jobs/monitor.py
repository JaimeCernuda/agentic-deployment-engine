"""Health monitoring and auto-recovery for deployed agents.

Provides continuous health monitoring with configurable auto-restart
capabilities for agent processes that fail or become unresponsive.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class AgentHealthStatus(Enum):
    """Agent health status."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNREACHABLE = "unreachable"
    RESTARTING = "restarting"
    FAILED = "failed"  # Max restarts exceeded


@dataclass
class AgentHealth:
    """Health state for a single agent."""

    agent_id: str
    url: str
    status: AgentHealthStatus = AgentHealthStatus.HEALTHY
    last_check: float = field(default_factory=time.time)
    last_healthy: float = field(default_factory=time.time)
    consecutive_failures: int = 0
    restart_count: int = 0
    error_message: str | None = None


@dataclass
class MonitorConfig:
    """Configuration for health monitoring."""

    check_interval: float = 10.0  # Seconds between health checks
    timeout: float = 5.0  # HTTP timeout for health checks
    max_consecutive_failures: int = 3  # Failures before restart
    max_restarts: int = 5  # Max restart attempts before giving up
    restart_backoff_base: float = 2.0  # Exponential backoff base
    restart_backoff_max: float = 60.0  # Maximum backoff delay


class HealthMonitor:
    """Monitors agent health and triggers auto-recovery.

    The monitor runs a background task that periodically checks agent health
    via HTTP health endpoints. When agents become unhealthy, it can trigger
    automatic restart via a callback.

    Usage:
        monitor = HealthMonitor(config, restart_callback=my_restart_fn)
        monitor.add_agent("weather", "http://localhost:9001")
        await monitor.start()
        # ... later ...
        await monitor.stop()
    """

    def __init__(
        self,
        config: MonitorConfig | None = None,
        restart_callback: Callable[[str, str], Any] | None = None,
        status_callback: Callable[[str, AgentHealthStatus], Any] | None = None,
    ):
        """Initialize health monitor.

        Args:
            config: Monitor configuration. Uses defaults if not provided.
            restart_callback: Async function(agent_id, url) to restart an agent.
            status_callback: Async function(agent_id, status) called on status change.
        """
        self.config = config or MonitorConfig()
        self.restart_callback = restart_callback
        self.status_callback = status_callback

        self._agents: dict[str, AgentHealth] = {}
        self._running = False
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    def add_agent(self, agent_id: str, url: str) -> None:
        """Add an agent to be monitored.

        Args:
            agent_id: Unique agent identifier.
            url: Agent's base URL (e.g., http://localhost:9001).
        """
        self._agents[agent_id] = AgentHealth(agent_id=agent_id, url=url)
        logger.info(f"Added agent to monitor: {agent_id} at {url}")

    def remove_agent(self, agent_id: str) -> bool:
        """Remove an agent from monitoring.

        Args:
            agent_id: Agent identifier.

        Returns:
            True if agent was removed, False if not found.
        """
        if agent_id in self._agents:
            del self._agents[agent_id]
            logger.info(f"Removed agent from monitor: {agent_id}")
            return True
        return False

    def get_health(self, agent_id: str) -> AgentHealth | None:
        """Get current health status for an agent.

        Args:
            agent_id: Agent identifier.

        Returns:
            AgentHealth if found, None otherwise.
        """
        return self._agents.get(agent_id)

    def get_all_health(self) -> dict[str, AgentHealth]:
        """Get health status for all monitored agents.

        Returns:
            Dictionary mapping agent_id to AgentHealth.
        """
        return dict(self._agents)

    async def start(self) -> None:
        """Start the health monitoring background task."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(
            f"Health monitor started (interval: {self.config.check_interval}s, "
            f"monitoring {len(self._agents)} agents)"
        )

    async def stop(self) -> None:
        """Stop the health monitoring background task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Health monitor stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop - runs until stopped."""
        while self._running:
            try:
                await self._check_all_agents()
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")

            await asyncio.sleep(self.config.check_interval)

    async def _check_all_agents(self) -> None:
        """Check health of all monitored agents."""
        tasks = [self._check_agent(agent_id) for agent_id in self._agents]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_agent(self, agent_id: str) -> None:
        """Check health of a single agent.

        Args:
            agent_id: Agent identifier.
        """
        async with self._lock:
            health = self._agents.get(agent_id)
            if not health:
                return

            # Skip if currently restarting
            if health.status == AgentHealthStatus.RESTARTING:
                return

            old_status = health.status
            health.last_check = time.time()

            try:
                async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                    response = await client.get(f"{health.url}/health")
                    if response.status_code == 200:
                        # Healthy
                        health.status = AgentHealthStatus.HEALTHY
                        health.consecutive_failures = 0
                        health.last_healthy = time.time()
                        health.error_message = None
                    else:
                        # Unhealthy response
                        health.status = AgentHealthStatus.UNHEALTHY
                        health.consecutive_failures += 1
                        health.error_message = f"HTTP {response.status_code}"

            except Exception as e:
                # Unreachable
                health.status = AgentHealthStatus.UNREACHABLE
                health.consecutive_failures += 1
                health.error_message = str(e)

            # Log status changes
            if health.status != old_status:
                logger.info(
                    f"Agent {agent_id} status: {old_status.value} -> {health.status.value}"
                )
                if self.status_callback:
                    try:
                        result = self.status_callback(agent_id, health.status)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        logger.error(f"Status callback error: {e}")

            # Check if restart is needed
            if (
                health.consecutive_failures >= self.config.max_consecutive_failures
                and health.status != AgentHealthStatus.FAILED
            ):
                await self._trigger_restart(agent_id)

    async def _trigger_restart(self, agent_id: str) -> None:
        """Trigger agent restart with backoff.

        Args:
            agent_id: Agent identifier.
        """
        health = self._agents.get(agent_id)
        if not health:
            return

        # Check if max restarts exceeded
        if health.restart_count >= self.config.max_restarts:
            health.status = AgentHealthStatus.FAILED
            logger.error(
                f"Agent {agent_id} failed: max restarts ({self.config.max_restarts}) exceeded"
            )
            return

        # Calculate backoff delay
        backoff = min(
            self.config.restart_backoff_base**health.restart_count,
            self.config.restart_backoff_max,
        )

        health.status = AgentHealthStatus.RESTARTING
        health.restart_count += 1
        logger.warning(
            f"Restarting agent {agent_id} (attempt {health.restart_count}/{self.config.max_restarts}, "
            f"backoff: {backoff:.1f}s)"
        )

        # Wait for backoff
        await asyncio.sleep(backoff)

        # Call restart callback
        if self.restart_callback:
            try:
                result = self.restart_callback(agent_id, health.url)
                if asyncio.iscoroutine(result):
                    await result
                logger.info(f"Restart callback completed for {agent_id}")
            except Exception as e:
                logger.error(f"Restart callback failed for {agent_id}: {e}")
                health.status = AgentHealthStatus.UNREACHABLE
                return

        # Reset failure count and mark as healthy (will be verified on next check)
        health.consecutive_failures = 0
        health.status = AgentHealthStatus.HEALTHY

    @property
    def is_running(self) -> bool:
        """Check if monitor is running."""
        return self._running

    def get_summary(self) -> dict[str, Any]:
        """Get summary of all agent health.

        Returns:
            Dictionary with health summary.
        """
        by_status: dict[str, list[str]] = {}
        for health in self._agents.values():
            status_name = health.status.value
            if status_name not in by_status:
                by_status[status_name] = []
            by_status[status_name].append(health.agent_id)

        return {
            "total_agents": len(self._agents),
            "by_status": by_status,
            "is_monitoring": self._running,
        }
