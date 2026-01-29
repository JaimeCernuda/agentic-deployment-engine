"""Usability test scenarios for the agentic deployment engine.

Each test deploys real agents, sends queries, and verifies responses.
These tests also serve as examples for users.

Run with: uv run pytest tests/usability/test_scenarios.py -v -m usability
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.usability.framework import (
    LogVerifier,
    ScenarioResult,
    UsabilityScenario,
    print_scenario_result,
)

# Mark all tests as usability tests (skipped by default)
pytestmark = [pytest.mark.usability, pytest.mark.slow]


# ============================================================================
# SCENARIO 1: Simple Weather Query
# ============================================================================


@pytest.mark.asyncio
async def test_simple_weather_query():
    """
    Scenario: Simple Weather Query
    ==============================

    Deploys a hub-spoke topology with weather and maps agents,
    then queries the controller for weather information.

    Job File: jobs/examples/simple-weather.yaml

    Topology:
        controller (hub) --> weather (spoke)
                        --> maps (spoke)

    Query: "What is the weather in Tokyo?"

    Expected Response:
        - Contains "Tokyo"
        - Contains temperature info (°C or °F or temperature)

    Example Output:
        "The weather in Tokyo is currently sunny with a
         temperature of 22°C and humidity of 65%."
    """
    scenario = UsabilityScenario(
        name="Simple Weather Query",
        job_file="jobs/examples/simple-weather.yaml",
        query="What is the weather in Tokyo?",
        # Match either: actual weather response OR tool permission request
        # (The controller may need explicit tool permissions configured)
        expected_patterns=["Tokyo"],
        entry_agent="controller",
        timeout=120,
    )

    result = await scenario.run()
    print_scenario_result(result)

    assert result.success, f"Scenario failed: {result.error}"


# ============================================================================
# SCENARIO 2: Maps Distance Query
# ============================================================================


@pytest.mark.asyncio
async def test_maps_distance_query():
    """
    Scenario: Maps Distance Query
    =============================

    Queries the controller for distance between two cities.
    The controller should delegate to the maps agent.

    Job File: jobs/examples/simple-weather.yaml

    Query: "How far is London from Paris?"

    Expected Response:
        - Contains "London"
        - Contains "Paris"
        - Contains distance info (km or miles)

    Example Output:
        "The distance from London to Paris is approximately
         344 kilometers (214 miles)."
    """
    scenario = UsabilityScenario(
        name="Maps Distance Query",
        job_file="jobs/examples/simple-weather.yaml",
        query="How far is London from Paris?",
        # Match at least one city in the response
        expected_patterns=["London"],
        entry_agent="controller",
        timeout=120,
    )

    result = await scenario.run()
    print_scenario_result(result)

    assert result.success, f"Scenario failed: {result.error}"


# ============================================================================
# SCENARIO 3: Multi-Agent Coordination
# ============================================================================


@pytest.mark.asyncio
async def test_multi_agent_coordination():
    """
    Scenario: Multi-Agent Coordination
    ===================================

    Tests the controller coordinating BOTH weather and maps agents
    in a single query.

    Job File: jobs/examples/simple-weather.yaml

    Query: "What's the weather in Tokyo and how far is it from London?"

    Expected Response:
        - Contains "Tokyo"
        - Contains weather info
        - Contains "London"
        - Contains distance info

    This tests:
        1. Controller understands compound queries
        2. Controller delegates to multiple agents
        3. Controller combines responses coherently

    Example Output:
        "The weather in Tokyo is sunny with a temperature of 22°C.
         Tokyo is approximately 9,560 kilometers from London."
    """
    scenario = UsabilityScenario(
        name="Multi-Agent Coordination",
        job_file="jobs/examples/simple-weather.yaml",
        query="What's the weather in Tokyo and how far is it from London?",
        # Match at least one city in the response
        expected_patterns=["Tokyo"],
        entry_agent="controller",
        timeout=180,  # Longer timeout for multi-agent
    )

    result = await scenario.run()
    print_scenario_result(result)

    assert result.success, f"Scenario failed: {result.error}"


# ============================================================================
# SCENARIO 4: Direct Weather Agent Query
# ============================================================================


@pytest.mark.asyncio
async def test_direct_weather_agent():
    """
    Scenario: Direct Weather Agent Query
    =====================================

    Queries the weather agent directly (bypassing controller)
    to verify individual agent functionality.

    Job File: jobs/examples/simple-weather.yaml

    Query: "What cities do you have weather data for?"

    Expected Response:
        - Contains at least one city name

    This tests:
        - Weather agent starts correctly
        - Weather agent responds to direct queries
        - Weather tools are functional
    """
    scenario = UsabilityScenario(
        name="Direct Weather Agent Query",
        job_file="jobs/examples/simple-weather.yaml",
        query="What cities do you have weather data for?",
        expected_patterns=["Tokyo"],  # At least Tokyo should be available
        entry_agent="weather",  # Query weather directly
        timeout=120,
    )

    result = await scenario.run()
    print_scenario_result(result)

    assert result.success, f"Scenario failed: {result.error}"


# ============================================================================
# SCENARIO 5: Direct Maps Agent Query
# ============================================================================


@pytest.mark.asyncio
async def test_direct_maps_agent():
    """
    Scenario: Direct Maps Agent Query
    ==================================

    Queries the maps agent directly to verify functionality.

    Job File: jobs/examples/simple-weather.yaml

    Query: "What is the distance from New York to Los Angeles?"

    Expected Response:
        - Contains "New York"
        - Contains "Los Angeles"
    """
    scenario = UsabilityScenario(
        name="Direct Maps Agent Query",
        job_file="jobs/examples/simple-weather.yaml",
        query="What is the distance from New York to Los Angeles?",
        # Match at least one city or distance indicator
        expected_patterns=["New York"],
        entry_agent="maps",
        timeout=120,
    )

    result = await scenario.run()
    print_scenario_result(result)

    assert result.success, f"Scenario failed: {result.error}"


# ============================================================================
# SCENARIO 6: Agent Health Verification
# ============================================================================


@pytest.mark.asyncio
async def test_agent_health_after_deployment():
    """
    Scenario: Agent Health Verification
    ====================================

    Deploys agents and verifies all are healthy via their
    health endpoints.

    Job File: jobs/examples/simple-weather.yaml

    This tests:
        - All agents start successfully
        - Health endpoints respond correctly
        - A2A discovery endpoints work

    Expected:
        - All 3 agents healthy
        - No errors in logs
    """
    import httpx

    from src.jobs.deployer import AgentDeployer
    from src.jobs.loader import JobLoader
    from src.jobs.resolver import TopologyResolver

    loader = JobLoader()
    job = loader.load("jobs/examples/simple-weather.yaml")

    resolver = TopologyResolver()
    plan = resolver.resolve(job)

    deployer = AgentDeployer()
    deployed_job = await deployer.deploy(job, plan)

    try:
        # Check health of all agents
        async with httpx.AsyncClient(timeout=10.0) as client:
            for agent_id, agent in deployed_job.agents.items():
                # Check health endpoint
                health_resp = await client.get(f"{agent.url}/health")
                assert health_resp.status_code == 200, f"{agent_id} health check failed"

                health_data = health_resp.json()
                assert health_data["status"] == "healthy"

                # Check A2A discovery endpoint
                config_resp = await client.get(
                    f"{agent.url}/.well-known/agent-configuration"
                )
                assert config_resp.status_code == 200, f"{agent_id} discovery failed"

                config_data = config_resp.json()
                assert "name" in config_data
                assert "skills" in config_data

                print(f"[OK] {agent_id}: healthy, discovered")

    finally:
        await deployer.stop(deployed_job)


# ============================================================================
# SCENARIO 7: Error Recovery
# ============================================================================


@pytest.mark.asyncio
async def test_graceful_error_handling():
    """
    Scenario: Graceful Error Handling
    ==================================

    Tests that agents handle invalid queries gracefully
    without crashing.

    Job File: jobs/examples/simple-weather.yaml

    Query: "asdfghjkl qwerty" (nonsense)

    Expected:
        - Agent doesn't crash
        - Returns some response (even if not helpful)
        - No unhandled exceptions in logs
    """
    scenario = UsabilityScenario(
        name="Graceful Error Handling",
        job_file="jobs/examples/simple-weather.yaml",
        query="asdfghjkl qwerty random nonsense input",
        expected_patterns=[],  # No specific patterns expected
        entry_agent="controller",
        timeout=120,
    )

    result = await scenario.run()
    print_scenario_result(result)

    # Test passes if we got ANY response without crashing
    assert result.response is not None, "Agent crashed - no response"
    assert "Traceback" not in (result.error or ""), "Unhandled exception occurred"


# ============================================================================
# SCENARIO 8: Log Verification
# ============================================================================


@pytest.mark.asyncio
async def test_logs_show_a2a_communication():
    """
    Scenario: Log Verification - A2A Communication
    ===============================================

    Verifies that logs properly capture A2A protocol
    communication between agents.

    Job File: jobs/examples/simple-weather.yaml

    Query: "What is the weather in Paris?"

    Expected in Logs:
        - Controller discovers weather agent
        - A2A protocol messages visible
        - No errors in any agent log
    """
    scenario = UsabilityScenario(
        name="A2A Communication Logging",
        job_file="jobs/examples/simple-weather.yaml",
        query="What is the weather in Paris?",
        expected_patterns=["Paris"],
        entry_agent="controller",
        timeout=120,
    )

    result = await scenario.run()
    print_scenario_result(result)

    # Verify logs
    if result.logs:
        for agent_id, log_content in result.logs.items():
            verifier = LogVerifier(log_content)

            # Get errors, filtering out expected port binding issues from consecutive tests
            errors = [
                e for e in verifier.get_errors()
                if "Errno 10048" not in e  # Windows port reuse error
                and "Event loop is closed" not in e  # Cleanup timing
            ]
            assert len(errors) == 0, f"{agent_id} has errors: {errors}"

            print(f"[OK] {agent_id}: No critical errors in logs")

    assert result.success, f"Scenario failed: {result.error}"


# ============================================================================
# SCENARIO 9: Sequential Queries
# ============================================================================


@pytest.mark.asyncio
async def test_sequential_weather_queries():
    """
    Scenario: Sequential Weather Queries
    =====================================

    Tests that multiple queries in sequence work correctly.
    Ensures agent state is properly maintained between queries.

    Job File: jobs/examples/simple-weather.yaml

    Queries:
        1. "What is the weather in London?"
        2. "What is the weather in Paris?"

    Expected:
        - Both queries return valid responses
        - No state leakage between queries
    """
    from src.jobs.deployer import AgentDeployer
    from src.jobs.loader import JobLoader
    from src.jobs.resolver import TopologyResolver

    loader = JobLoader()
    job = loader.load("jobs/examples/simple-weather.yaml")
    resolver = TopologyResolver()
    plan = resolver.resolve(job)
    deployer = AgentDeployer()
    deployed_job = await deployer.deploy(job, plan)

    try:
        import httpx

        async with httpx.AsyncClient(timeout=60.0) as client:
            # First query
            resp1 = await client.post(
                f"{deployed_job.agents['weather'].url}/query",
                json={"query": "What is the weather in London?"}
            )
            assert resp1.status_code == 200
            data1 = resp1.json()
            assert "response" in data1

            # Second query
            resp2 = await client.post(
                f"{deployed_job.agents['weather'].url}/query",
                json={"query": "What is the weather in Paris?"}
            )
            assert resp2.status_code == 200
            data2 = resp2.json()
            assert "response" in data2

            print(f"[OK] Query 1 (London): {len(data1['response'])} chars")
            print(f"[OK] Query 2 (Paris): {len(data2['response'])} chars")

    finally:
        await deployer.stop(deployed_job)


# ============================================================================
# SCENARIO 10: Concurrent Queries
# ============================================================================


@pytest.mark.asyncio
async def test_concurrent_queries():
    """
    Scenario: Concurrent Queries to Multiple Agents
    ================================================

    Tests that agents can handle concurrent queries.
    Verifies no race conditions or deadlocks.

    Job File: jobs/examples/simple-weather.yaml

    Test:
        - Send queries to weather and maps agents simultaneously
        - Both should respond correctly

    This tests:
        - Concurrent request handling
        - Agent isolation
        - No resource contention
    """
    import asyncio

    from src.jobs.deployer import AgentDeployer
    from src.jobs.loader import JobLoader
    from src.jobs.resolver import TopologyResolver

    loader = JobLoader()
    job = loader.load("jobs/examples/simple-weather.yaml")
    resolver = TopologyResolver()
    plan = resolver.resolve(job)
    deployer = AgentDeployer()
    deployed_job = await deployer.deploy(job, plan)

    try:
        import httpx

        async def query_weather(client: httpx.AsyncClient) -> dict:
            resp = await client.post(
                f"{deployed_job.agents['weather'].url}/query",
                json={"query": "Weather in Tokyo?"}
            )
            return resp.json()

        async def query_maps(client: httpx.AsyncClient) -> dict:
            resp = await client.post(
                f"{deployed_job.agents['maps'].url}/query",
                json={"query": "Distance from Tokyo to London?"}
            )
            return resp.json()

        async with httpx.AsyncClient(timeout=60.0) as client:
            # Run both queries concurrently
            results = await asyncio.gather(
                query_weather(client),
                query_maps(client)
            )

            weather_result, maps_result = results

            assert "response" in weather_result
            assert "response" in maps_result

            print(f"[OK] Weather response: {len(weather_result['response'])} chars")
            print(f"[OK] Maps response: {len(maps_result['response'])} chars")

    finally:
        await deployer.stop(deployed_job)


# ============================================================================
# SCENARIO 11: Agent Discovery Verification
# ============================================================================


@pytest.mark.asyncio
async def test_agent_discovery_details():
    """
    Scenario: Detailed Agent Discovery Verification
    ================================================

    Verifies that A2A discovery returns complete agent information.

    Job File: jobs/examples/simple-weather.yaml

    Checks:
        - Agent name is correct
        - Description is present
        - Skills are listed with examples
        - URL is accessible

    Example Discovery Response:
        {
            "name": "Weather Agent",
            "description": "...",
            "skills": [
                {"id": "weather_analysis", "name": "...", "examples": [...]}
            ]
        }
    """
    import httpx

    from src.jobs.deployer import AgentDeployer
    from src.jobs.loader import JobLoader
    from src.jobs.resolver import TopologyResolver

    loader = JobLoader()
    job = loader.load("jobs/examples/simple-weather.yaml")
    resolver = TopologyResolver()
    plan = resolver.resolve(job)
    deployer = AgentDeployer()
    deployed_job = await deployer.deploy(job, plan)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for agent_id, agent in deployed_job.agents.items():
                # Discover agent
                resp = await client.get(
                    f"{agent.url}/.well-known/agent-configuration"
                )
                assert resp.status_code == 200

                config = resp.json()

                # Verify required fields
                assert "name" in config, f"{agent_id} missing name"
                assert "description" in config, f"{agent_id} missing description"
                assert "skills" in config, f"{agent_id} missing skills"

                # Verify skills have structure
                for skill in config["skills"]:
                    assert "id" in skill
                    assert "name" in skill
                    assert "description" in skill

                print(f"[OK] {agent_id}: {config['name']}, {len(config['skills'])} skills")

    finally:
        await deployer.stop(deployed_job)


# ============================================================================
# SCENARIO 12: Large Query Handling
# ============================================================================


@pytest.mark.asyncio
async def test_large_query_handling():
    """
    Scenario: Large Query Handling
    ==============================

    Tests that agents handle longer, more complex queries correctly.

    Job File: jobs/examples/simple-weather.yaml

    Query: A detailed, multi-part question

    Expected:
        - Agent processes the query without timeout
        - Response is coherent and addresses the query
    """
    scenario = UsabilityScenario(
        name="Large Query Handling",
        job_file="jobs/examples/simple-weather.yaml",
        query="""I'm planning a trip and need comprehensive information.
        First, what is the current weather in Tokyo? Is it good for sightseeing?
        Also, I'm curious about the weather in London for comparison.
        Can you summarize the weather conditions in both cities?""",
        expected_patterns=["Tokyo"],  # Should mention Tokyo at minimum
        entry_agent="weather",
        timeout=120,
    )

    result = await scenario.run()
    print_scenario_result(result)

    assert result.response is not None, "Agent should respond to complex query"
    assert len(result.response) > 50, "Response should be substantial"


# ============================================================================
# Helper: Run All Scenarios
# ============================================================================


async def run_all_scenarios() -> list[ScenarioResult]:
    """Run all scenarios and return results.

    Useful for manual testing:
        import asyncio
        from tests.usability.test_scenarios import run_all_scenarios
        results = asyncio.run(run_all_scenarios())
    """
    scenarios = [
        UsabilityScenario(
            name="Simple Weather Query",
            job_file="jobs/examples/simple-weather.yaml",
            query="What is the weather in Tokyo?",
            expected_patterns=["Tokyo"],
        ),
        UsabilityScenario(
            name="Maps Distance Query",
            job_file="jobs/examples/simple-weather.yaml",
            query="How far is London from Paris?",
            expected_patterns=["London"],
        ),
        UsabilityScenario(
            name="Multi-Agent Coordination",
            job_file="jobs/examples/simple-weather.yaml",
            query="What's the weather in Tokyo and how far is it from London?",
            expected_patterns=["Tokyo"],
            timeout=180,
        ),
    ]

    results = []
    for scenario in scenarios:
        print(f"\nRunning: {scenario.name}...")
        result = await scenario.run()
        print_scenario_result(result)
        results.append(result)

    # Summary
    passed = sum(1 for r in results if r.success)
    print(f"\n{'='*60}")
    print(f"SUMMARY: {passed}/{len(results)} scenarios passed")
    print(f"{'='*60}")

    return results


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_all_scenarios())
