"""Usability tests for verifying tool call behavior.

These tests verify that Claude actually uses tools when responding to queries,
addressing the issue where agents respond without tool usage (Tools used: 0).

Run with: uv run pytest tests/usability/test_tool_calls.py -v -m usability
"""

import asyncio
import re
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import httpx

from src.jobs.deployer import AgentDeployer
from src.jobs.loader import JobLoader
from src.jobs.models import DeployedJob
from src.jobs.resolver import TopologyResolver

pytestmark = [pytest.mark.usability, pytest.mark.slow]


def parse_tool_usage_from_log(log_path: Path) -> dict[str, Any]:
    """Parse tool usage statistics from agent log file.

    Looks for lines like:
        "Query completed. Messages: N, Tools used: M, Response: X chars"

    Args:
        log_path: Path to agent log file

    Returns:
        Dict with tool usage info:
        - queries: list of query info dicts
        - total_queries: int
        - total_tools_used: int
        - queries_with_tools: int (queries where Tools used > 0)
    """
    result = {
        "queries": [],
        "total_queries": 0,
        "total_tools_used": 0,
        "queries_with_tools": 0,
    }

    if not log_path.exists():
        return result

    log_content = log_path.read_text()

    # Pattern: Query completed. Messages: N, Tools used: M, Response: X chars
    pattern = r"Query completed\. Messages: (\d+), Tools used: (\d+), Response: (\d+) chars"

    for match in re.finditer(pattern, log_content):
        messages = int(match.group(1))
        tools_used = int(match.group(2))
        response_chars = int(match.group(3))

        result["queries"].append({
            "messages": messages,
            "tools_used": tools_used,
            "response_chars": response_chars,
        })
        result["total_queries"] += 1
        result["total_tools_used"] += tools_used
        if tools_used > 0:
            result["queries_with_tools"] += 1

    return result


def get_agent_log_path(agent_name: str) -> Path:
    """Get path to an agent's log file.

    Args:
        agent_name: Agent name (e.g., "Weather Agent")

    Returns:
        Path to the log file
    """
    # Log file naming: name.lower().replace(" ", "_").log
    log_name = agent_name.lower().replace(" ", "_") + ".log"
    return Path(__file__).parent.parent.parent / "src" / "logs" / log_name


async def deploy_job(job_file: str) -> tuple[DeployedJob, AgentDeployer]:
    """Deploy a job and return the deployed job and deployer.

    Args:
        job_file: Path to job YAML file

    Returns:
        Tuple of (deployed_job, deployer) for cleanup
    """
    loader = JobLoader()
    job = loader.load(job_file)

    resolver = TopologyResolver()
    plan = resolver.resolve(job)

    deployer = AgentDeployer()
    deployed_job = await deployer.deploy(job, plan)

    # Wait for agents to stabilize
    await asyncio.sleep(3.0)

    return deployed_job, deployer


async def query_agent(url: str, query: str, timeout: float = 120.0) -> str:
    """Send a query to an agent and return the response.

    Args:
        url: Agent base URL
        query: Query string
        timeout: Request timeout

    Returns:
        Response text
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{url}/query",
            json={"query": query},
        )
        response.raise_for_status()
        return response.json().get("response", "")


# ============================================================================
# TEST: Weather Agent Tool Usage
# ============================================================================


@pytest.mark.asyncio
async def test_weather_agent_uses_tools():
    """Verify weather agent actually uses its MCP tools.

    This test:
    1. Deploys the weather agent
    2. Sends a weather query that REQUIRES tool usage
    3. Checks the agent log for "Tools used: N" where N > 0

    Expected: Weather agent should use mcp__weather_agent__get_weather tool.
    """
    deployed_job, deployer = await deploy_job("jobs/examples/simple-weather.yaml")

    try:
        # Get weather agent URL
        weather_url = deployed_job.agents["weather"].url

        # Clear any previous log entries by noting current position
        log_path = get_agent_log_path("Weather Agent")
        initial_size = log_path.stat().st_size if log_path.exists() else 0

        # Send a query that requires weather tool
        response = await query_agent(weather_url, "What is the weather in Tokyo?")

        # Give time for log to be written
        await asyncio.sleep(1.0)

        # Parse tool usage from log (only new entries)
        if log_path.exists():
            full_content = log_path.read_text()
            new_content = full_content[initial_size:]
            # Use a temp file approach or direct parsing
            usage = {"queries_with_tools": 0, "total_tools_used": 0}

            pattern = r"Query completed\. Messages: (\d+), Tools used: (\d+), Response: (\d+) chars"
            for match in re.finditer(pattern, new_content):
                tools_used = int(match.group(2))
                usage["total_tools_used"] += tools_used
                if tools_used > 0:
                    usage["queries_with_tools"] += 1
        else:
            usage = {"queries_with_tools": 0, "total_tools_used": 0}

        # Assertions
        print(f"\nWeather Agent Response: {response[:200]}...")
        print(f"Tool Usage: {usage}")

        assert usage["queries_with_tools"] > 0, (
            f"Weather agent did not use any tools! "
            f"Expected Tools used > 0 but got {usage['total_tools_used']}. "
            f"This indicates the permission_mode or tool naming issue persists."
        )
        assert "tokyo" in response.lower() or "weather" in response.lower(), (
            "Response doesn't contain expected weather information"
        )

    finally:
        await deployer.stop(deployed_job)


# ============================================================================
# TEST: Controller Agent Tool Usage
# ============================================================================


@pytest.mark.asyncio
async def test_controller_agent_uses_a2a_tools():
    """Verify controller agent uses A2A tools to query other agents.

    This test:
    1. Deploys all agents (controller, weather, maps)
    2. Sends a weather query to the controller
    3. Checks the controller log for A2A tool usage (query_agent)

    Expected: Controller should use mcp__controller_agent__query_agent
    to communicate with the weather agent.
    """
    deployed_job, deployer = await deploy_job("jobs/examples/simple-weather.yaml")

    try:
        # Get controller URL
        controller_url = deployed_job.agents["controller"].url

        # Note log position before query
        log_path = get_agent_log_path("Controller Agent")
        initial_size = log_path.stat().st_size if log_path.exists() else 0

        # Send a query that requires coordination with weather agent
        response = await query_agent(
            controller_url,
            "What is the weather in Tokyo? Please use the weather agent."
        )

        # Wait for log
        await asyncio.sleep(1.0)

        # Check tool usage in new log entries
        if log_path.exists():
            full_content = log_path.read_text()
            new_content = full_content[initial_size:]

            # Check for tool calls
            tool_pattern = r"Tool: (mcp__[a-z_]+__[a-z_]+)"
            tools_called = re.findall(tool_pattern, new_content)

            # Check for completion with tools
            pattern = r"Query completed\. Messages: (\d+), Tools used: (\d+), Response: (\d+) chars"
            tools_used = 0
            for match in re.finditer(pattern, new_content):
                tools_used += int(match.group(2))
        else:
            tools_called = []
            tools_used = 0

        print(f"\nController Agent Response: {response[:200]}...")
        print(f"Tools Called: {tools_called}")
        print(f"Total Tools Used: {tools_used}")

        # The key assertion - controller must use A2A tools
        assert tools_used > 0, (
            "Controller agent did not use any tools! "
            "Expected query_agent tool usage for A2A communication. "
            "This indicates the tool naming fix may not be working. "
            "Check that mcp__controller_agent__query_agent is in allowed_tools."
        )

        # Check that query_agent was specifically called
        a2a_tools = [t for t in tools_called if "query_agent" in t]
        assert len(a2a_tools) > 0, (
            f"Controller did not call query_agent tool. "
            f"Tools called: {tools_called}. "
            f"Expected mcp__controller_agent__query_agent."
        )

    finally:
        await deployer.stop(deployed_job)


# ============================================================================
# TEST: Maps Agent Tool Usage
# ============================================================================


@pytest.mark.asyncio
async def test_maps_agent_uses_tools():
    """Verify maps agent uses its MCP tools.

    This test:
    1. Deploys the maps agent
    2. Sends a distance query that REQUIRES tool usage
    3. Checks the agent log for tool usage

    Expected: Maps agent should use mcp__maps_agent__get_distance tool.
    """
    deployed_job, deployer = await deploy_job("jobs/examples/simple-weather.yaml")

    try:
        # Get maps agent URL
        maps_url = deployed_job.agents["maps"].url

        # Note log position
        log_path = get_agent_log_path("Maps Agent")
        initial_size = log_path.stat().st_size if log_path.exists() else 0

        # Send query requiring distance tool
        response = await query_agent(maps_url, "What is the distance from Tokyo to London?")

        await asyncio.sleep(1.0)

        # Parse tool usage
        if log_path.exists():
            full_content = log_path.read_text()
            new_content = full_content[initial_size:]

            pattern = r"Query completed\. Messages: (\d+), Tools used: (\d+), Response: (\d+) chars"
            tools_used = 0
            for match in re.finditer(pattern, new_content):
                tools_used += int(match.group(2))
        else:
            tools_used = 0

        print(f"\nMaps Agent Response: {response[:200]}...")
        print(f"Tools Used: {tools_used}")

        assert tools_used > 0, (
            "Maps agent did not use any tools! "
            "Expected Tools used > 0 for distance calculation."
        )

    finally:
        await deployer.stop(deployed_job)


# ============================================================================
# TEST: Permission Presets Affect Tool Access
# ============================================================================


@pytest.mark.asyncio
async def test_tool_naming_convention():
    """Verify tool naming follows the expected convention.

    Tool names must be: mcp__<server_key>__<tool_name>
    Where server_key = agent_name.lower().replace(" ", "_")

    This test verifies the expected tool names appear in logs.
    """
    deployed_job, deployer = await deploy_job("jobs/examples/simple-weather.yaml")

    try:
        # Query weather agent to trigger tool usage
        weather_url = deployed_job.agents["weather"].url
        await query_agent(weather_url, "What is the weather in Tokyo?")

        await asyncio.sleep(1.0)

        # Check log for correct tool naming
        log_path = get_agent_log_path("Weather Agent")
        if log_path.exists():
            content = log_path.read_text()

            # Should see the correctly named tools
            expected_tools = [
                "mcp__weather_agent__get_weather",
                "mcp__weather_agent__get_locations",
            ]

            found_tools = []
            for tool in expected_tools:
                if tool in content:
                    found_tools.append(tool)

            print(f"\nExpected tools: {expected_tools}")
            print(f"Found in logs: {found_tools}")

            # Log should show allowed_tools with correct naming
            assert "Allowed tools:" in content, "Log should show allowed tools list"
            assert "mcp__weather_agent__" in content, (
                "Tool names should use mcp__weather_agent__ prefix. "
                "Check that tool naming convention is correct."
            )

    finally:
        await deployer.stop(deployed_job)


# ============================================================================
# TEST: Comprehensive Tool Call Verification
# ============================================================================


@pytest.mark.asyncio
async def test_all_agents_use_tools():
    """Comprehensive test that ALL agents use their tools.

    This is the definitive test for the tool permission fix.
    All three agents should use their tools when queried appropriately.
    """
    deployed_job, deployer = await deploy_job("jobs/examples/simple-weather.yaml")

    results = {
        "weather": {"tools_used": 0, "response": ""},
        "maps": {"tools_used": 0, "response": ""},
        "controller": {"tools_used": 0, "response": ""},
    }

    try:
        # Test each agent
        agents_config = [
            ("weather", "What is the weather in Tokyo?", "Weather Agent"),
            ("maps", "Distance from Tokyo to London?", "Maps Agent"),
            ("controller", "What is the weather in Paris?", "Controller Agent"),
        ]

        for agent_id, query, agent_name in agents_config:
            url = deployed_job.agents[agent_id].url
            log_path = get_agent_log_path(agent_name)

            # Get initial log size
            initial_size = log_path.stat().st_size if log_path.exists() else 0

            # Send query
            response = await query_agent(url, query)
            results[agent_id]["response"] = response

            await asyncio.sleep(1.0)

            # Parse new log entries
            if log_path.exists():
                content = log_path.read_text()[initial_size:]
                pattern = r"Tools used: (\d+)"
                for match in re.finditer(pattern, content):
                    results[agent_id]["tools_used"] += int(match.group(1))

        # Print summary
        print("\n" + "=" * 60)
        print("TOOL USAGE SUMMARY")
        print("=" * 60)
        for agent_id, data in results.items():
            status = "OK" if data["tools_used"] > 0 else "FAILED"
            print(f"  {agent_id}: Tools used = {data['tools_used']} [{status}]")
        print("=" * 60)

        # Assertions - all agents MUST use tools
        for agent_id, data in results.items():
            assert data["tools_used"] > 0, (
                f"{agent_id} agent did not use any tools! "
                f"This test verifies the permission fix. "
                f"Response was: {data['response'][:100]}..."
            )

        print("\nAll agents successfully used their tools!")

    finally:
        await deployer.stop(deployed_job)


# ============================================================================
# Helper: Run Tool Verification Tests
# ============================================================================


async def run_tool_verification() -> dict[str, bool]:
    """Run all tool verification tests and return results.

    Useful for manual testing:
        import asyncio
        from tests.usability.test_tool_calls import run_tool_verification
        results = asyncio.run(run_tool_verification())
    """
    print("\n" + "=" * 60)
    print("TOOL CALL VERIFICATION")
    print("=" * 60)

    results = {}

    tests = [
        ("weather_uses_tools", test_weather_agent_uses_tools),
        ("controller_uses_tools", test_controller_agent_uses_a2a_tools),
        ("maps_uses_tools", test_maps_agent_uses_tools),
    ]

    for name, test_func in tests:
        print(f"\nRunning: {name}...")
        try:
            await test_func()
            results[name] = True
            print("  [PASSED]")
        except AssertionError as e:
            results[name] = False
            print(f"  [FAILED] {e}")
        except Exception as e:
            results[name] = False
            print(f"  [ERROR] {type(e).__name__}: {e}")

    # Summary
    passed = sum(1 for v in results.values() if v)
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed}/{len(results)} tests passed")
    print("=" * 60)

    return results


if __name__ == "__main__":
    asyncio.run(run_tool_verification())
