"""Unit tests for the dynamic agent registry service."""

import pytest
from fastapi.testclient import TestClient

from src.registry.service import (
    AgentRegistration,
    AgentRegistry,
    app,
)


class TestAgentRegistration:
    """Tests for AgentRegistration model."""

    def test_creates_with_required_fields(self) -> None:
        """Should create registration with required fields only."""
        reg = AgentRegistration(
            id="test_agent",
            name="Test Agent",
            url="http://localhost:9001",
        )
        assert reg.id == "test_agent"
        assert reg.name == "Test Agent"
        assert reg.url == "http://localhost:9001"
        assert reg.description == ""
        assert reg.skills == []
        assert reg.tags == []
        assert reg.metadata == {}

    def test_creates_with_all_fields(self) -> None:
        """Should create registration with all fields."""
        reg = AgentRegistration(
            id="full_agent",
            name="Full Agent",
            url="http://localhost:9002",
            description="A fully configured agent",
            skills=[{"id": "skill1", "name": "Skill One"}],
            tags=["tag1", "tag2"],
            metadata={"custom": "value"},
        )
        assert reg.description == "A fully configured agent"
        assert len(reg.skills) == 1
        assert reg.tags == ["tag1", "tag2"]
        assert reg.metadata["custom"] == "value"


class TestAgentRegistry:
    """Tests for AgentRegistry class."""

    @pytest.fixture
    def registry(self) -> AgentRegistry:
        """Create a fresh registry for each test."""
        return AgentRegistry(
            health_check_interval=60,  # Long interval to prevent auto-checks
            unhealthy_threshold=3,
            removal_threshold=5,
        )

    @pytest.mark.asyncio
    async def test_register_new_agent(self, registry: AgentRegistry) -> None:
        """Should register a new agent."""
        reg = AgentRegistration(
            id="new_agent",
            name="New Agent",
            url="http://localhost:9001",
        )
        result = await registry.register(reg)

        assert result.id == "new_agent"
        assert result.name == "New Agent"
        assert result.health_status == "healthy"
        assert result.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_register_updates_existing(self, registry: AgentRegistry) -> None:
        """Should update existing registration."""
        reg1 = AgentRegistration(
            id="agent1",
            name="Agent V1",
            url="http://localhost:9001",
        )
        await registry.register(reg1)

        reg2 = AgentRegistration(
            id="agent1",
            name="Agent V2",
            url="http://localhost:9002",
        )
        result = await registry.register(reg2)

        assert result.name == "Agent V2"
        assert result.url == "http://localhost:9002"
        agents = await registry.list_agents()
        assert len(agents) == 1

    @pytest.mark.asyncio
    async def test_deregister_existing_agent(self, registry: AgentRegistry) -> None:
        """Should deregister an existing agent."""
        reg = AgentRegistration(
            id="to_remove",
            name="Remove Me",
            url="http://localhost:9001",
        )
        await registry.register(reg)

        result = await registry.deregister("to_remove")
        assert result is True

        agents = await registry.list_agents()
        assert len(agents) == 0

    @pytest.mark.asyncio
    async def test_deregister_nonexistent_agent(self, registry: AgentRegistry) -> None:
        """Should return False for nonexistent agent."""
        result = await registry.deregister("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_agent(self, registry: AgentRegistry) -> None:
        """Should get agent by ID."""
        reg = AgentRegistration(
            id="get_me",
            name="Get Me",
            url="http://localhost:9001",
        )
        await registry.register(reg)

        agent = await registry.get_agent("get_me")
        assert agent is not None
        assert agent.name == "Get Me"

    @pytest.mark.asyncio
    async def test_get_nonexistent_agent(self, registry: AgentRegistry) -> None:
        """Should return None for nonexistent agent."""
        agent = await registry.get_agent("nonexistent")
        assert agent is None

    @pytest.mark.asyncio
    async def test_list_agents(self, registry: AgentRegistry) -> None:
        """Should list all registered agents."""
        for i in range(3):
            reg = AgentRegistration(
                id=f"agent_{i}",
                name=f"Agent {i}",
                url=f"http://localhost:900{i}",
            )
            await registry.register(reg)

        agents = await registry.list_agents()
        assert len(agents) == 3

    @pytest.mark.asyncio
    async def test_list_agents_healthy_only(self, registry: AgentRegistry) -> None:
        """Should filter to healthy agents only."""
        reg1 = AgentRegistration(
            id="healthy",
            name="Healthy Agent",
            url="http://localhost:9001",
        )
        await registry.register(reg1)

        reg2 = AgentRegistration(
            id="unhealthy",
            name="Unhealthy Agent",
            url="http://localhost:9002",
        )
        await registry.register(reg2)

        # Manually mark as unhealthy
        registry._agents["unhealthy"].health_status = "unhealthy"

        agents = await registry.list_agents(healthy_only=True)
        assert len(agents) == 1
        assert agents[0].id == "healthy"

    @pytest.mark.asyncio
    async def test_search_by_skill(self, registry: AgentRegistry) -> None:
        """Should search agents by skill."""
        reg1 = AgentRegistration(
            id="weather",
            name="Weather Agent",
            url="http://localhost:9001",
            skills=[{"id": "weather", "name": "Weather Analysis"}],
        )
        await registry.register(reg1)

        reg2 = AgentRegistration(
            id="maps",
            name="Maps Agent",
            url="http://localhost:9002",
            skills=[{"id": "distance", "name": "Distance Calculation"}],
        )
        await registry.register(reg2)

        results = await registry.search_agents(skill="weather")
        assert len(results) == 1
        assert results[0].id == "weather"

    @pytest.mark.asyncio
    async def test_search_by_tag(self, registry: AgentRegistry) -> None:
        """Should search agents by tag."""
        reg1 = AgentRegistration(
            id="agent1",
            name="Agent 1",
            url="http://localhost:9001",
            tags=["python", "api"],
        )
        await registry.register(reg1)

        reg2 = AgentRegistration(
            id="agent2",
            name="Agent 2",
            url="http://localhost:9002",
            tags=["javascript", "frontend"],
        )
        await registry.register(reg2)

        results = await registry.search_agents(tag="python")
        assert len(results) == 1
        assert results[0].id == "agent1"

    @pytest.mark.asyncio
    async def test_search_by_name(self, registry: AgentRegistry) -> None:
        """Should search agents by name."""
        reg1 = AgentRegistration(
            id="weather",
            name="Weather Agent",
            url="http://localhost:9001",
        )
        await registry.register(reg1)

        reg2 = AgentRegistration(
            id="maps",
            name="Maps Agent",
            url="http://localhost:9002",
        )
        await registry.register(reg2)

        results = await registry.search_agents(name="weather")
        assert len(results) == 1
        assert results[0].id == "weather"

    @pytest.mark.asyncio
    async def test_record_failure(self, registry: AgentRegistry) -> None:
        """Should record health check failures."""
        reg = AgentRegistration(
            id="failing",
            name="Failing Agent",
            url="http://localhost:9001",
        )
        await registry.register(reg)

        # Record failures up to threshold
        for _ in range(3):
            await registry._record_failure("failing")

        agent = await registry.get_agent("failing")
        assert agent is not None
        assert agent.consecutive_failures == 3
        assert agent.health_status == "unhealthy"


class TestRegistryAPI:
    """Tests for registry FastAPI endpoints."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        # Reset the global registry for each test
        import src.registry.service as service

        service._registry = None
        return TestClient(app)

    def test_health_endpoint(self, client: TestClient) -> None:
        """Should return health status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "total_agents" in data

    def test_register_agent(self, client: TestClient) -> None:
        """Should register an agent."""
        response = client.post(
            "/agents/register",
            json={
                "id": "test_agent",
                "name": "Test Agent",
                "url": "http://localhost:9001",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test_agent"
        assert data["health_status"] == "healthy"

    def test_list_agents(self, client: TestClient) -> None:
        """Should list registered agents."""
        # Register an agent first
        client.post(
            "/agents/register",
            json={
                "id": "list_agent",
                "name": "List Agent",
                "url": "http://localhost:9001",
            },
        )

        response = client.get("/agents")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "list_agent"

    def test_get_agent(self, client: TestClient) -> None:
        """Should get agent by ID."""
        # Register an agent first
        client.post(
            "/agents/register",
            json={
                "id": "get_agent",
                "name": "Get Agent",
                "url": "http://localhost:9001",
            },
        )

        response = client.get("/agents/get_agent")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "get_agent"

    def test_get_nonexistent_agent(self, client: TestClient) -> None:
        """Should return 404 for nonexistent agent."""
        response = client.get("/agents/nonexistent")
        assert response.status_code == 404

    def test_deregister_agent(self, client: TestClient) -> None:
        """Should deregister an agent."""
        # Register an agent first
        client.post(
            "/agents/register",
            json={
                "id": "delete_agent",
                "name": "Delete Agent",
                "url": "http://localhost:9001",
            },
        )

        response = client.delete("/agents/delete_agent")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deregistered"

    def test_deregister_nonexistent_agent(self, client: TestClient) -> None:
        """Should return 404 for nonexistent agent."""
        response = client.delete("/agents/nonexistent")
        assert response.status_code == 404

    def test_search_agents(self, client: TestClient) -> None:
        """Should search agents."""
        # Register agents
        client.post(
            "/agents/register",
            json={
                "id": "search1",
                "name": "Search Agent",
                "url": "http://localhost:9001",
                "skills": [{"id": "test", "name": "Testing"}],
            },
        )

        response = client.get("/agents/search?skill=test")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
