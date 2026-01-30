"""Usability test framework for deploying and verifying agent scenarios.

This framework provides:
- Automated deployment of job definitions
- Query execution against deployed agents
- Log parsing and verification
- Cleanup after tests
"""

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import httpx

from src.jobs.deployer import AgentDeployer, DeploymentError
from src.jobs.loader import JobLoader
from src.jobs.models import DeployedJob
from src.jobs.resolver import TopologyResolver


@dataclass
class ScenarioResult:
    """Result of running a usability scenario."""

    success: bool
    scenario_name: str
    job_file: str
    query: str
    response: str | None = None
    error: str | None = None
    duration_seconds: float = 0.0
    logs: dict[str, str] = field(default_factory=dict)
    matched_patterns: list[str] = field(default_factory=list)
    missing_patterns: list[str] = field(default_factory=list)


@dataclass
class UsabilityScenario:
    """A usability test scenario.

    Example:
        scenario = UsabilityScenario(
            name="Simple Weather Query",
            job_file="jobs/examples/simple-weather.yaml",
            query="What is the weather in Tokyo?",
            expected_patterns=["Tokyo", "temperature", "°C"],
            entry_agent="controller",
            timeout=60,
        )
        result = await scenario.run()
    """

    name: str
    job_file: str
    query: str
    expected_patterns: list[str]
    entry_agent: str = "controller"
    timeout: int = 60
    startup_delay: float = 3.0
    case_sensitive: bool = False

    async def run(self) -> ScenarioResult:
        """Run the scenario and return results.

        Returns:
            ScenarioResult with success/failure and details.
        """
        start_time = datetime.now()
        result = ScenarioResult(
            success=False,
            scenario_name=self.name,
            job_file=self.job_file,
            query=self.query,
        )

        deployed_job: DeployedJob | None = None
        deployer: AgentDeployer | None = None

        try:
            # 1. Load and validate job
            loader = JobLoader()
            job = loader.load(self.job_file)

            # 2. Generate deployment plan
            resolver = TopologyResolver()
            plan = resolver.resolve(job)

            # 3. Deploy agents
            deployer = AgentDeployer()
            deployed_job = await deployer.deploy(job, plan)

            # 4. Wait for agents to stabilize
            await asyncio.sleep(self.startup_delay)

            # 5. Find entry agent URL
            entry_url = self._get_entry_url(deployed_job)
            if not entry_url:
                result.error = (
                    f"Entry agent '{self.entry_agent}' not found in deployed job"
                )
                return result

            # 6. Send query
            response_text = await self._send_query(entry_url, self.query)
            result.response = response_text

            # 7. Verify expected patterns
            result.matched_patterns, result.missing_patterns = self._check_patterns(
                response_text
            )

            # 8. Collect logs
            result.logs = self._collect_logs(deployed_job)

            # 9. Determine success
            if not result.missing_patterns:
                result.success = True
            else:
                result.error = f"Missing patterns: {result.missing_patterns}"

        except DeploymentError as e:
            result.error = f"Deployment failed: {e}"
        except httpx.HTTPError as e:
            result.error = f"HTTP error: {e}"
        except Exception as e:
            result.error = f"Unexpected error: {type(e).__name__}: {e}"

        finally:
            # Cleanup
            if deployed_job and deployer:
                try:
                    await deployer.stop(deployed_job)
                except Exception:
                    pass  # Best effort cleanup

            result.duration_seconds = (datetime.now() - start_time).total_seconds()

        return result

    def _get_entry_url(self, deployed_job: DeployedJob) -> str | None:
        """Get URL of entry agent."""
        if self.entry_agent in deployed_job.agents:
            return deployed_job.agents[self.entry_agent].url
        return None

    async def _send_query(self, url: str, query: str) -> str:
        """Send query to agent and return response."""
        async with httpx.AsyncClient(timeout=float(self.timeout)) as client:
            response = await client.post(
                f"{url}/query",
                json={"query": query},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")

    def _check_patterns(self, text: str) -> tuple[list[str], list[str]]:
        """Check which patterns are present/missing in text.

        Returns:
            Tuple of (matched_patterns, missing_patterns)
        """
        matched = []
        missing = []

        check_text = text if self.case_sensitive else text.lower()

        for pattern in self.expected_patterns:
            check_pattern = pattern if self.case_sensitive else pattern.lower()
            if check_pattern in check_text:
                matched.append(pattern)
            else:
                missing.append(pattern)

        return matched, missing

    def _collect_logs(self, deployed_job: DeployedJob) -> dict[str, str]:
        """Collect logs from all deployed agents."""
        logs = {}
        log_dir = Path.cwd() / "logs" / "jobs"

        for agent_id in deployed_job.agents:
            stdout_log = log_dir / f"{agent_id}.stdout.log"
            stderr_log = log_dir / f"{agent_id}.stderr.log"

            agent_logs = []
            if stdout_log.exists():
                agent_logs.append(f"=== STDOUT ===\n{stdout_log.read_text()}")
            if stderr_log.exists():
                stderr_content = stderr_log.read_text()
                if stderr_content.strip():
                    agent_logs.append(f"=== STDERR ===\n{stderr_content}")

            if agent_logs:
                logs[agent_id] = "\n".join(agent_logs)

        return logs


class LogVerifier:
    """Utility for verifying agent logs."""

    def __init__(self, log_content: str):
        self.content = log_content
        self.lines = log_content.splitlines()

    def contains(self, pattern: str, case_sensitive: bool = False) -> bool:
        """Check if log contains pattern."""
        content = self.content if case_sensitive else self.content.lower()
        check = pattern if case_sensitive else pattern.lower()
        return check in content

    def contains_regex(self, pattern: str) -> bool:
        """Check if log matches regex pattern."""
        return bool(re.search(pattern, self.content))

    def has_error(self) -> bool:
        """Check if log contains error indicators."""
        error_patterns = [
            r"ERROR",
            r"Exception",
            r"Traceback",
            r"FAILED",
            r"error:",
        ]
        for pattern in error_patterns:
            if re.search(pattern, self.content, re.IGNORECASE):
                return True
        return False

    def get_errors(self) -> list[str]:
        """Extract error lines from log."""
        errors = []
        for line in self.lines:
            if any(
                err in line.upper()
                for err in ["ERROR", "EXCEPTION", "TRACEBACK", "FAILED"]
            ):
                errors.append(line)
        return errors

    def has_a2a_communication(self) -> bool:
        """Check if log shows A2A protocol communication."""
        a2a_patterns = [
            r"GET /\.well-known/agent-configuration",
            r"POST /query",
            r"Discovering.*agents",
            r"Connected to.*agent",
        ]
        for pattern in a2a_patterns:
            if re.search(pattern, self.content, re.IGNORECASE):
                return True
        return False


def _safe_print(text: str) -> None:
    """Print text safely, handling Unicode encoding issues on Windows."""
    try:
        print(text)
    except UnicodeEncodeError:
        # Replace problematic characters with ASCII equivalents
        safe_text = text.encode("ascii", errors="replace").decode("ascii")
        print(safe_text)


def print_scenario_result(result: ScenarioResult) -> None:
    """Pretty print a scenario result."""
    status = "[PASSED]" if result.success else "[FAILED]"

    _safe_print(f"\n{'=' * 60}")
    _safe_print(f"Scenario: {result.scenario_name}")
    _safe_print(f"Status: {status}")
    _safe_print(f"Duration: {result.duration_seconds:.2f}s")
    _safe_print(f"{'=' * 60}")
    _safe_print(f"Job: {result.job_file}")
    _safe_print(f"Query: {result.query}")

    if result.response:
        preview = (
            result.response[:200] + "..."
            if len(result.response) > 200
            else result.response
        )
        _safe_print(f"\nResponse:\n  {preview}")

    if result.matched_patterns:
        _safe_print(f"\n[OK] Matched patterns: {result.matched_patterns}")

    if result.missing_patterns:
        _safe_print(f"\n[X] Missing patterns: {result.missing_patterns}")

    if result.error:
        _safe_print(f"\nError: {result.error}")

    if result.logs:
        _safe_print("\nAgent Logs:")
        for agent_id, log in result.logs.items():
            verifier = LogVerifier(log)
            errors = verifier.get_errors()
            if errors:
                _safe_print(f"  {agent_id}: {len(errors)} errors found")
                for err in errors[:3]:  # Show first 3 errors
                    _safe_print(f"    - {err[:100]}")
            else:
                _safe_print(f"  {agent_id}: No errors")

    _safe_print(f"{'=' * 60}\n")
