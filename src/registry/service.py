"""Dynamic Agent Registry Service.

HTTP service for runtime agent discovery and registration.
Agents self-register on startup and are automatically removed when unhealthy.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from src.config import settings

logger = logging.getLogger(__name__)


class AgentRegistration(BaseModel):
    """Agent registration request."""

    id: str = Field(..., description="Unique agent identifier")
    name: str = Field(..., description="Human-readable agent name")
    url: str = Field(..., description="Agent's base URL (e.g., http://localhost:9001)")
    description: str = Field(default="", description="Agent description")
    skills: list[dict[str, Any]] = Field(default_factory=list, description="Agent capabilities")
    tags: list[str] = Field(default_factory=list, description="Searchable tags")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class RegisteredAgent(BaseModel):
    """Registered agent with health tracking."""

    id: str
    name: str
    url: str
    description: str
    skills: list[dict[str, Any]]
    tags: list[str]
    metadata: dict[str, Any]
    registered_at: datetime
    last_seen: datetime
    health_status: str = "unknown"  # healthy, unhealthy, unknown
    consecutive_failures: int = 0


class AgentRegistry:
    """In-memory agent registry with health checking."""

    def __init__(
        self,
        health_check_interval: int = 30,
        unhealthy_threshold: int = 3,
        removal_threshold: int = 5,
    ):
        self._agents: dict[str, RegisteredAgent] = {}
        self._lock = asyncio.Lock()
        self._health_check_interval = health_check_interval
        self._unhealthy_threshold = unhealthy_threshold
        self._removal_threshold = removal_threshold
        self._health_check_task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start background health checking."""
        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info(
            f"Registry health checker started (interval={self._health_check_interval}s, "
            f"unhealthy_threshold={self._unhealthy_threshold}, "
            f"removal_threshold={self._removal_threshold})"
        )

    async def stop(self) -> None:
        """Stop background health checking."""
        self._running = False
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        logger.info("Registry health checker stopped")

    async def _health_check_loop(self) -> None:
        """Background loop to check agent health."""
        while self._running:
            try:
                await asyncio.sleep(self._health_check_interval)
                await self._check_all_agents()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")

    async def _check_all_agents(self) -> None:
        """Check health of all registered agents."""
        async with self._lock:
            agent_ids = list(self._agents.keys())

        to_remove: list[str] = []

        async with httpx.AsyncClient(timeout=5.0) as client:
            for agent_id in agent_ids:
                async with self._lock:
                    agent = self._agents.get(agent_id)
                    if not agent:
                        continue

                try:
                    response = await client.get(f"{agent.url}/health")
                    if response.status_code == 200:
                        async with self._lock:
                            if agent_id in self._agents:
                                self._agents[agent_id].health_status = "healthy"
                                self._agents[agent_id].last_seen = datetime.now(timezone.utc)
                                self._agents[agent_id].consecutive_failures = 0
                    else:
                        await self._record_failure(agent_id)
                except Exception as e:
                    logger.debug(f"Health check failed for {agent_id}: {e}")
                    await self._record_failure(agent_id)

                # Check if agent should be removed
                async with self._lock:
                    agent = self._agents.get(agent_id)
                    if agent and agent.consecutive_failures >= self._removal_threshold:
                        to_remove.append(agent_id)

        # Remove dead agents
        for agent_id in to_remove:
            await self.deregister(agent_id)
            logger.warning(f"Auto-removed dead agent: {agent_id}")

    async def _record_failure(self, agent_id: str) -> None:
        """Record a health check failure for an agent."""
        async with self._lock:
            if agent_id in self._agents:
                self._agents[agent_id].consecutive_failures += 1
                if self._agents[agent_id].consecutive_failures >= self._unhealthy_threshold:
                    self._agents[agent_id].health_status = "unhealthy"

    async def register(self, registration: AgentRegistration) -> RegisteredAgent:
        """Register or update an agent."""
        now = datetime.now(timezone.utc)

        async with self._lock:
            if registration.id in self._agents:
                # Update existing registration
                existing = self._agents[registration.id]
                existing.name = registration.name
                existing.url = registration.url
                existing.description = registration.description
                existing.skills = registration.skills
                existing.tags = registration.tags
                existing.metadata = registration.metadata
                existing.last_seen = now
                existing.health_status = "healthy"
                existing.consecutive_failures = 0
                logger.info(f"Updated agent registration: {registration.id}")
                return existing
            else:
                # New registration
                agent = RegisteredAgent(
                    id=registration.id,
                    name=registration.name,
                    url=registration.url,
                    description=registration.description,
                    skills=registration.skills,
                    tags=registration.tags,
                    metadata=registration.metadata,
                    registered_at=now,
                    last_seen=now,
                    health_status="healthy",
                    consecutive_failures=0,
                )
                self._agents[registration.id] = agent
                logger.info(f"New agent registered: {registration.id} at {registration.url}")
                return agent

    async def deregister(self, agent_id: str) -> bool:
        """Remove an agent from the registry."""
        async with self._lock:
            if agent_id in self._agents:
                del self._agents[agent_id]
                logger.info(f"Agent deregistered: {agent_id}")
                return True
            return False

    async def get_agent(self, agent_id: str) -> RegisteredAgent | None:
        """Get a specific agent by ID."""
        async with self._lock:
            return self._agents.get(agent_id)

    async def list_agents(self, healthy_only: bool = False) -> list[RegisteredAgent]:
        """List all registered agents."""
        async with self._lock:
            agents = list(self._agents.values())
            if healthy_only:
                agents = [a for a in agents if a.health_status == "healthy"]
            return agents

    async def search_agents(
        self,
        skill: str | None = None,
        tag: str | None = None,
        name: str | None = None,
        healthy_only: bool = True,
    ) -> list[RegisteredAgent]:
        """Search for agents by capability."""
        async with self._lock:
            results = list(self._agents.values())

        if healthy_only:
            results = [a for a in results if a.health_status == "healthy"]

        if skill:
            skill_lower = skill.lower()
            results = [
                a
                for a in results
                if any(
                    skill_lower in s.get("name", "").lower()
                    or skill_lower in s.get("description", "").lower()
                    or skill_lower in s.get("id", "").lower()
                    for s in a.skills
                )
            ]

        if tag:
            tag_lower = tag.lower()
            results = [a for a in results if any(tag_lower in t.lower() for t in a.tags)]

        if name:
            name_lower = name.lower()
            results = [a for a in results if name_lower in a.name.lower()]

        return results


# Global registry instance
_registry: AgentRegistry | None = None


def get_registry() -> AgentRegistry:
    """Get the global registry instance."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry(
            health_check_interval=getattr(settings, "registry_health_check_interval", 30),
            unhealthy_threshold=getattr(settings, "registry_unhealthy_threshold", 3),
            removal_threshold=getattr(settings, "registry_removal_threshold", 5),
        )
    return _registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage registry lifecycle."""
    registry = get_registry()
    await registry.start()
    yield
    await registry.stop()


# Create FastAPI app
app = FastAPI(
    title="Agent Registry Service",
    description="Dynamic agent discovery and registration service",
    version="1.0.0",
    lifespan=lifespan,
)


@app.post("/agents/register", response_model=RegisteredAgent)
async def register_agent(registration: AgentRegistration) -> RegisteredAgent:
    """Register a new agent or update existing registration."""
    registry = get_registry()
    return await registry.register(registration)


@app.delete("/agents/{agent_id}")
async def deregister_agent(agent_id: str) -> dict[str, str]:
    """Remove an agent from the registry."""
    registry = get_registry()
    if await registry.deregister(agent_id):
        return {"status": "deregistered", "agent_id": agent_id}
    raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")


@app.get("/agents", response_model=list[RegisteredAgent])
async def list_agents(healthy_only: bool = Query(False, description="Only return healthy agents")) -> list[RegisteredAgent]:
    """List all registered agents."""
    registry = get_registry()
    return await registry.list_agents(healthy_only=healthy_only)


@app.get("/agents/search", response_model=list[RegisteredAgent])
async def search_agents(
    skill: str | None = Query(None, description="Search by skill/capability"),
    tag: str | None = Query(None, description="Search by tag"),
    name: str | None = Query(None, description="Search by agent name"),
    healthy_only: bool = Query(True, description="Only return healthy agents"),
) -> list[RegisteredAgent]:
    """Search for agents by capability."""
    registry = get_registry()
    return await registry.search_agents(skill=skill, tag=tag, name=name, healthy_only=healthy_only)


@app.get("/agents/{agent_id}", response_model=RegisteredAgent)
async def get_agent(agent_id: str) -> RegisteredAgent:
    """Get details about a specific agent."""
    registry = get_registry()
    agent = await registry.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
    return agent


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Registry service health check."""
    registry = get_registry()
    agents = await registry.list_agents()
    healthy = sum(1 for a in agents if a.health_status == "healthy")
    return {
        "status": "healthy",
        "total_agents": len(agents),
        "healthy_agents": healthy,
        "unhealthy_agents": len(agents) - healthy,
    }


def run_registry(host: str = "0.0.0.0", port: int = 8500) -> None:
    """Run the registry service."""
    import uvicorn

    logger.info(f"Starting Agent Registry on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


def main() -> None:
    """CLI entry point for the registry service."""
    import argparse

    parser = argparse.ArgumentParser(description="Dynamic Agent Registry Service")
    parser.add_argument(
        "--port", "-p", type=int, default=8500, help="Port to listen on (default: 8500)"
    )
    parser.add_argument(
        "--host", "-H", type=str, default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)"
    )
    args = parser.parse_args()

    print(f"Starting Agent Registry on {args.host}:{args.port}")
    print("Endpoints:")
    print(f"  POST   http://{args.host}:{args.port}/agents/register - Register agent")
    print(f"  DELETE http://{args.host}:{args.port}/agents/{{id}}   - Deregister agent")
    print(f"  GET    http://{args.host}:{args.port}/agents          - List all agents")
    print(f"  GET    http://{args.host}:{args.port}/agents/search   - Search agents")
    print(f"  GET    http://{args.host}:{args.port}/health          - Health check")
    print()

    run_registry(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
