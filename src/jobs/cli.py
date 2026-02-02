"""CLI for A2A job deployment."""

import asyncio
import json
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..observability.semantic import read_ndjson_trace, write_unified_trace
from .deployer import AgentDeployer, DeploymentError
from .loader import JobLoader, JobLoadError
from .registry import AgentState, JobState, get_registry
from .resolver import TopologyResolver

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    import codecs

    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "replace")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "replace")

app = typer.Typer(
    name="deploy",
    help="A2A Job Deployment System - Deploy multi-agent workflows",
    add_completion=False,
)
console = Console(force_terminal=True)


# ============================================================================
# Validate Command
# ============================================================================


@app.command()
def validate(
    job_file: Path = typer.Argument(..., help="Path to job YAML file"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Validate a job definition file."""
    console.print(f"[bold]Validating job:[/bold] {job_file}")

    loader = JobLoader()

    try:
        job = loader.load(job_file)

        console.print("[green][OK] Job definition is valid[/green]")

        if verbose:
            console.print(f"\n[bold]Job:[/bold] {job.job.name} v{job.job.version}")
            console.print(f"[bold]Description:[/bold] {job.job.description}")
            console.print(f"[bold]Agents:[/bold] {len(job.agents)}")
            console.print(f"[bold]Topology:[/bold] {job.topology.type}")

            # Agent table
            table = Table(title="Agents")
            table.add_column("ID", style="cyan")
            table.add_column("Type", style="green")
            table.add_column("Port", style="yellow")
            table.add_column("Target", style="magenta")

            for agent in job.agents:
                table.add_row(
                    agent.id,
                    agent.type,
                    str(agent.config.get("port", "N/A")),
                    agent.deployment.target,
                )

            console.print(table)

    except JobLoadError as e:
        console.print(f"[red][FAIL] Validation failed:[/red]\n{e}")
        raise typer.Exit(code=1) from None


# ============================================================================
# Plan Command
# ============================================================================


@app.command()
def plan(
    job_file: Path = typer.Argument(..., help="Path to job YAML file"),
    output_format: str = typer.Option(
        "table", "--format", "-f", help="Output format: table, json"
    ),
):
    """Generate deployment plan (dry run)."""
    console.print(f"[bold]Planning deployment:[/bold] {job_file}")

    loader = JobLoader()
    resolver = TopologyResolver()

    try:
        # Load and validate
        job = loader.load(job_file)
        console.print("[green][OK] Job valid[/green]")

        # Generate plan
        deployment_plan = resolver.resolve(job)
        console.print(
            f"[green][OK] Plan generated: {len(deployment_plan.stages)} stages[/green]"
        )

        if output_format == "json":
            # JSON output
            plan_dict = {
                "job": job.job.name,
                "stages": deployment_plan.stages,
                "agent_urls": deployment_plan.agent_urls,
                "connections": deployment_plan.connections,
            }
            console.print_json(json.dumps(plan_dict, indent=2))

        else:
            # Table output
            console.print(f"\n[bold]Deployment Plan for {job.job.name}[/bold]")

            # Stages
            stage_table = Table(title="Deployment Stages")
            stage_table.add_column("Stage", style="cyan")
            stage_table.add_column("Agents", style="green")
            stage_table.add_column("Count", style="yellow")

            for idx, stage in enumerate(deployment_plan.stages):
                stage_table.add_row(str(idx + 1), ", ".join(stage), str(len(stage)))

            console.print(stage_table)

            # Agent URLs
            url_table = Table(title="Agent URLs")
            url_table.add_column("Agent", style="cyan")
            url_table.add_column("URL", style="green")

            for agent_id, url in deployment_plan.agent_urls.items():
                url_table.add_row(agent_id, url)

            console.print(url_table)

            # Connections
            conn_table = Table(title="Connections")
            conn_table.add_column("Agent", style="cyan")
            conn_table.add_column("Connects To", style="green")
            conn_table.add_column("Count", style="yellow")

            for agent_id, urls in deployment_plan.connections.items():
                if urls:
                    conn_table.add_row(agent_id, "\n".join(urls), str(len(urls)))
                else:
                    conn_table.add_row(agent_id, "[dim]none[/dim]", "0")

            console.print(conn_table)

    except JobLoadError as e:
        console.print(f"[red][FAIL] Validation failed:[/red]\n{e}")
        raise typer.Exit(code=1) from None
    except Exception as e:
        console.print(f"[red][FAIL] Planning failed:[/red]\n{e}")
        raise typer.Exit(code=1) from None


# ============================================================================
# Start Command
# ============================================================================


@app.command()
def start(
    job_file: Path = typer.Argument(..., help="Path to job YAML file"),
    name: str | None = typer.Option(None, "--name", "-n", help="Job name override"),
):
    """Deploy and start a job."""
    console.print(f"[bold]Deploying job:[/bold] {job_file}")

    async def _deploy():
        loader = JobLoader()
        resolver = TopologyResolver()
        deployer = AgentDeployer()

        try:
            # 1. Load and validate
            console.print("[dim]Loading job definition...[/dim]")
            job = loader.load(job_file)
            console.print(f"[green][OK] Loaded {job.job.name}[/green]")

            # 2. Generate plan
            console.print("[dim]Generating deployment plan...[/dim]")
            deployment_plan = resolver.resolve(job)
            console.print(
                f"[green][OK] Plan generated: {len(deployment_plan.stages)} stages[/green]"
            )

            # 3. Deploy
            console.print("[dim]Deploying agents...[/dim]")
            deployed_job = await deployer.deploy(job, deployment_plan)

            # 4. Save to registry
            registry = get_registry()
            # Determine entry point (from execution config or topology hub)
            entry_point = None
            if job.execution and job.execution.entry_point:
                entry_point = job.execution.entry_point
            elif job.topology.type == "hub-spoke" and job.topology.hub:
                entry_point = job.topology.hub

            job_state = JobState(
                job_id=deployed_job.job_id,
                job_file=str(job_file.absolute()),
                status="running",
                start_time=deployed_job.start_time,
                topology_type=job.topology.type,
                entry_point=entry_point,
                agents={
                    agent_id: AgentState(
                        agent_id=agent_id,
                        url=agent.url,
                        process_id=agent.process_id,
                        status=agent.status,
                    )
                    for agent_id, agent in deployed_job.agents.items()
                },
            )
            registry.save_job(job_state)

            console.print(
                Panel(
                    f"[green][OK] Job deployed successfully[/green]\n\n"
                    f"Job ID: {deployed_job.job_id}\n"
                    f"Agents: {len(deployed_job.agents)}\n"
                    f"Status: {deployed_job.status}\n\n"
                    f"Use [cyan]uv run deploy status {deployed_job.job_id}[/cyan] to monitor",
                    title="Deployment Complete",
                )
            )

            # Start health monitoring
            from .monitor import HealthMonitor, MonitorConfig

            monitor_config = MonitorConfig(
                check_interval=job.deployment.health_check.interval
                if job.deployment.health_check
                else 10.0,
                max_consecutive_failures=3,
                max_restarts=5,
            )

            async def on_status_change(agent_id: str, status):
                from .monitor import AgentHealthStatus

                if status == AgentHealthStatus.UNREACHABLE:
                    console.print(f"[yellow]⚠ Agent {agent_id} is unreachable[/yellow]")
                elif status == AgentHealthStatus.RESTARTING:
                    console.print(f"[cyan]↻ Restarting agent {agent_id}...[/cyan]")
                elif status == AgentHealthStatus.HEALTHY:
                    console.print(f"[green]✓ Agent {agent_id} is healthy[/green]")
                elif status == AgentHealthStatus.FAILED:
                    console.print(
                        f"[red]✗ Agent {agent_id} failed (max restarts exceeded)[/red]"
                    )

            monitor = HealthMonitor(
                config=monitor_config,
                status_callback=on_status_change,
            )

            # Add all deployed agents to monitoring
            for agent_id, agent in deployed_job.agents.items():
                monitor.add_agent(agent_id, agent.url)

            await monitor.start()

            # Keep running
            console.print("\n[yellow]Press Ctrl+C to stop the job and exit[/yellow]")

            try:
                # Wait indefinitely
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                console.print("\n[yellow]Stopping job...[/yellow]")
                await monitor.stop()
                await deployer.stop(deployed_job)
                registry.update_status(deployed_job.job_id, "stopped")
                console.print("[green][OK] Job stopped[/green]")

        except JobLoadError as e:
            console.print(f"[red][FAIL] Validation failed:[/red]\n{e}")
            raise typer.Exit(code=1) from None
        except DeploymentError as e:
            console.print(f"[red][FAIL] Deployment failed:[/red]\n{e}")
            raise typer.Exit(code=1) from None
        except Exception as e:
            console.print(f"[red][FAIL] Error:[/red]\n{e}")
            raise typer.Exit(code=1) from None

    asyncio.run(_deploy())


# ============================================================================
# Status Command
# ============================================================================


@app.command()
def status(
    job_name: str = typer.Argument(..., help="Job name or ID"),
):
    """Show job status and agent health."""
    registry = get_registry()
    job_state = registry.get_job(job_name)

    if not job_state:
        console.print(f"[red][FAIL] Job not found: {job_name}[/red]")
        console.print("[dim]Use 'uv run deploy list' to see all jobs[/dim]")
        raise typer.Exit(code=1) from None

    # Job info panel
    status_color = {
        "running": "green",
        "stopped": "yellow",
        "failed": "red",
    }.get(job_state.status, "white")

    console.print(
        Panel(
            f"[bold]Job:[/bold] {job_state.job_id}\n"
            f"[bold]Status:[/bold] [{status_color}]{job_state.status}[/{status_color}]\n"
            f"[bold]Started:[/bold] {job_state.start_time}\n"
            f"[bold]Topology:[/bold] {job_state.topology_type or 'unknown'}\n"
            f"[bold]Job File:[/bold] {job_state.job_file}",
            title="Job Status",
        )
    )

    # Agent status table
    table = Table(title="Agent Status")
    table.add_column("Agent ID", style="cyan")
    table.add_column("URL", style="blue")
    table.add_column("PID", style="yellow")
    table.add_column("Health", style="magenta")
    table.add_column("Host", style="dim")

    async def check_health(url: str) -> tuple[str, str]:
        """Check agent health via HTTP.

        Returns:
            Tuple of (display_string, raw_status) for display and logic.
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{url}/health")
                if resp.status_code == 200:
                    return "[green]healthy[/green]", "healthy"
                return f"[yellow]unhealthy ({resp.status_code})[/yellow]", "unhealthy"
        except Exception:
            return "[red]unreachable[/red]", "unreachable"

    async def get_all_health():
        """Get health for all agents."""
        results = {}
        for agent_id, agent in job_state.agents.items():
            results[agent_id] = await check_health(agent.url)
        return results

    health_results = asyncio.run(get_all_health())

    # Count unhealthy agents for job status assessment
    unhealthy_count = sum(
        1 for _, (_, status) in health_results.items() if status != "healthy"
    )
    total_count = len(health_results)

    for agent_id, agent in job_state.agents.items():
        health_display, _ = health_results.get(agent_id, ("unknown", "unknown"))
        table.add_row(
            agent_id,
            agent.url,
            str(agent.process_id) if agent.process_id else "N/A",
            health_display,
            agent.host or "localhost",
        )

    console.print(table)

    # Display health summary
    if unhealthy_count == 0:
        console.print(f"\n[green]All {total_count} agents healthy[/green]")
    else:
        console.print(
            f"\n[yellow]Health: {total_count - unhealthy_count}/{total_count} agents healthy, "
            f"{unhealthy_count} unhealthy[/yellow]"
        )


# ============================================================================
# Stop Command
# ============================================================================


@app.command()
def stop(
    job_name: str = typer.Argument(..., help="Job name or ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Force kill processes"),
):
    """Stop a running job."""
    import signal

    registry = get_registry()
    job_state = registry.get_job(job_name)

    if not job_state:
        console.print(f"[red][FAIL] Job not found: {job_name}[/red]")
        raise typer.Exit(code=1) from None

    if job_state.status != "running":
        console.print(
            f"[yellow]Job is not running (status: {job_state.status})[/yellow]"
        )
        raise typer.Exit(code=0)

    console.print(f"[bold]Stopping job:[/bold] {job_name}")

    stopped = 0
    failed = 0

    for agent_id, agent in job_state.agents.items():
        if agent.process_id:
            try:
                import os
                import sys

                if sys.platform == "win32":
                    # Windows: use taskkill
                    os.system(f"taskkill /PID {agent.process_id} /F")
                else:
                    # Unix: use signals
                    sig = signal.SIGKILL if force else signal.SIGTERM
                    os.kill(agent.process_id, sig)
                console.print(
                    f"  [green][OK][/green] Stopped {agent_id} (PID: {agent.process_id})"
                )
                stopped += 1
            except ProcessLookupError:
                console.print(f"  [yellow]![/yellow] {agent_id} already stopped")
            except PermissionError:
                console.print(f"  [red][FAIL][/red] Permission denied for {agent_id}")
                failed += 1
            except Exception as e:
                console.print(f"  [red][FAIL][/red] Failed to stop {agent_id}: {e}")
                failed += 1
        else:
            console.print(f"  [dim]-[/dim] {agent_id} has no PID recorded")

    registry.update_status(job_name, "stopped")

    if failed == 0:
        console.print(f"\n[green][OK] Job stopped ({stopped} agents)[/green]")
    else:
        console.print(
            f"\n[yellow]Partially stopped ({stopped} ok, {failed} failed)[/yellow]"
        )


# ============================================================================
# Query Command
# ============================================================================


@app.command()
def query(
    job_name: str = typer.Argument(..., help="Job name or ID"),
    message: str = typer.Argument(..., help="Query message to send"),
    agent: str | None = typer.Option(
        None, "--agent", "-a", help="Specific agent to query (default: entry point)"
    ),
    session: str | None = typer.Option(
        None,
        "--session",
        "-s",
        help="Session ID for multi-turn conversation (reuse to maintain context)",
    ),
    timeout: int = typer.Option(60, "--timeout", "-t", help="Timeout in seconds"),
    raw: bool = typer.Option(False, "--raw", "-r", help="Output raw JSON response"),
):
    """Send a query to a running job.

    Use --session to maintain conversation context across multiple queries:

        uv run deploy query my-job "Hello" --session my-session
        uv run deploy query my-job "What did I just say?" --session my-session
    """
    registry = get_registry()
    job_state = registry.get_job(job_name)

    if not job_state:
        console.print(f"[red][FAIL] Job not found: {job_name}[/red]")
        raise typer.Exit(code=1) from None

    if job_state.status != "running":
        console.print(
            f"[red][FAIL] Job is not running (status: {job_state.status})[/red]"
        )
        raise typer.Exit(code=1) from None

    # Determine which agent to query
    if agent:
        if agent not in job_state.agents:
            console.print(f"[red][FAIL] Agent not found: {agent}[/red]")
            console.print(
                f"[dim]Available agents: {', '.join(job_state.agents.keys())}[/dim]"
            )
            raise typer.Exit(code=1) from None
        target_agent = job_state.agents[agent]
    else:
        # Use entry point or first agent
        entry_point = job_state.entry_point
        if entry_point and entry_point in job_state.agents:
            target_agent = job_state.agents[entry_point]
            agent = entry_point
        else:
            # Fall back to first agent
            agent = next(iter(job_state.agents.keys()))
            target_agent = job_state.agents[agent]

    if not target_agent.url:
        console.print(f"[red][FAIL] Agent {agent} has no URL[/red]")
        raise typer.Exit(code=1) from None

    # Send query
    if not raw:
        session_info = f" (session: {session})" if session else ""
        console.print(
            f"[dim]Querying {agent} at {target_agent.url}{session_info}...[/dim]"
        )

    async def send_query():
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Include session_id in request body for multi-turn context
            request_body = {"query": message}
            if session:
                request_body["session_id"] = session

            response = await client.post(
                f"{target_agent.url}/query",
                json=request_body,
            )
            response.raise_for_status()
            return response.json()

    try:
        result = asyncio.run(send_query())

        if raw:
            console.print(json.dumps(result, indent=2))
        else:
            response_text = result.get("response", str(result))
            # Show session ID if returned (for continuing conversation)
            session_id = result.get("session_id")
            title = f"[bold]{agent}[/bold]"
            if session_id and not session:
                # New session created, show ID for reuse
                title += f" [dim](session: {session_id})[/dim]"
            console.print(Panel(response_text, title=title, expand=False))

        # Check for trace files after query completes
        # With SharedNDJSONExporter, traces are already unified during execution
        try:
            from ..config import settings

            trace_dir = Path(settings.semantic_trace_dir) / job_state.job_id
            if trace_dir.exists():
                # Check for new NDJSON format (already unified)
                ndjson_files = list(trace_dir.glob("*.ndjson"))
                if ndjson_files and not raw:
                    console.print(f"[dim]Trace file: {ndjson_files[0].name}[/dim]")
                else:
                    # Legacy JSON format - merge into unified file
                    unified_path = write_unified_trace(trace_dir)
                    if unified_path and not raw:
                        console.print(f"[dim]Traces merged: {unified_path.name}[/dim]")
        except Exception:
            pass  # Don't fail query if trace handling fails

    except httpx.TimeoutException:
        console.print(f"[red][FAIL] Request timed out after {timeout}s[/red]")
        raise typer.Exit(code=1) from None
    except httpx.HTTPStatusError as e:
        console.print(f"[red][FAIL] HTTP error: {e.response.status_code}[/red]")
        raise typer.Exit(code=1) from None
    except Exception as e:
        console.print(f"[red][FAIL] Query failed: {e}[/red]")
        raise typer.Exit(code=1) from None


# ============================================================================
# List Command
# ============================================================================


@app.command(name="list")
def list_jobs(
    all_jobs: bool = typer.Option(
        False, "--all", "-a", help="Show all jobs, not just running"
    ),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum jobs to show"),
):
    """List deployed jobs."""
    registry = get_registry()

    status_filter = None if all_jobs else "running"
    jobs = registry.list_jobs(status=status_filter, limit=limit)

    if not jobs:
        if all_jobs:
            console.print("[dim]No jobs found in registry[/dim]")
        else:
            console.print("[dim]No running jobs. Use --all to see all jobs.[/dim]")
        return

    table = Table(title="Deployed Jobs")
    table.add_column("Job ID", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Agents", style="yellow")
    table.add_column("Topology", style="magenta")
    table.add_column("Started", style="blue")

    for job in jobs:
        status_color = {
            "running": "green",
            "stopped": "yellow",
            "failed": "red",
        }.get(job.status, "white")

        # Parse and format start time
        try:
            start_dt = datetime.fromisoformat(job.start_time)
            start_str = start_dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            start_str = job.start_time[:16]

        table.add_row(
            job.job_id,
            f"[{status_color}]{job.status}[/{status_color}]",
            str(len(job.agents)),
            job.topology_type or "unknown",
            start_str,
        )

    console.print(table)
    console.print(f"\n[dim]Showing {len(jobs)} jobs[/dim]")


# ============================================================================
# Logs Command
# ============================================================================


@app.command()
def logs(
    job_name: str = typer.Argument(..., help="Job name or ID"),
    agent: str | None = typer.Option(None, "--agent", "-a", help="Agent ID"),
    tail: int = typer.Option(50, "--tail", "-n", help="Number of lines to show"),
    follow: bool = typer.Option(
        False, "--follow", "-f", help="Follow logs (not yet implemented)"
    ),
):
    """View job logs."""
    registry = get_registry()
    job_state = registry.get_job(job_name)

    if not job_state:
        console.print(f"[red][FAIL] Job not found: {job_name}[/red]")
        raise typer.Exit(code=1) from None

    # Determine log directory - use job_id for job-specific logs
    log_dir = Path.cwd() / "logs" / "jobs" / job_state.job_id

    if agent:
        # Show logs for specific agent
        agents_to_show = [agent]
    else:
        # Show logs for all agents
        agents_to_show = list(job_state.agents.keys())

    for agent_id in agents_to_show:
        if agent_id not in job_state.agents:
            console.print(f"[yellow]Agent not found: {agent_id}[/yellow]")
            continue

        stdout_log = log_dir / f"{agent_id}.stdout.log"
        stderr_log = log_dir / f"{agent_id}.stderr.log"

        console.print(f"\n[bold cyan]===  {agent_id} ===[/bold cyan]")

        # Show stdout
        if stdout_log.exists():
            lines = stdout_log.read_text().splitlines()
            if lines:
                console.print("[dim]--- stdout ---[/dim]")
                for line in lines[-tail:]:
                    console.print(line)
        else:
            console.print(f"[dim]No stdout log: {stdout_log}[/dim]")

        # Show stderr
        if stderr_log.exists():
            lines = stderr_log.read_text().splitlines()
            if lines:
                console.print("[dim]--- stderr ---[/dim]")
                for line in lines[-tail:]:
                    console.print(f"[red]{line}[/red]")

    if follow:
        console.print(
            "\n[yellow]Follow mode not yet implemented. Use 'tail -f' on log files.[/yellow]"
        )


# ============================================================================
# Cleanup Command
# ============================================================================


@app.command()
def cleanup(
    older_than: str = typer.Option(
        "7d",
        "--older-than",
        "-o",
        help="Remove jobs older than duration (e.g., 24h, 7d, 30d)",
    ),
    status: str | None = typer.Option(
        "stopped",
        "--status",
        "-s",
        help="Only remove jobs with this status (running, stopped, failed, or 'all')",
    ),
    job_id: str | None = typer.Argument(
        None, help="Specific job ID to remove (ignores --older-than and --status)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n", help="Show what would be deleted without deleting"
    ),
    include_logs: bool = typer.Option(
        True, "--logs/--no-logs", help="Also delete log files"
    ),
):
    """Clean up old jobs and their logs.

    Examples:
        uv run deploy cleanup                    # Remove stopped jobs older than 7 days
        uv run deploy cleanup --older-than 24h   # Remove stopped jobs older than 24 hours
        uv run deploy cleanup --status all       # Remove all non-running jobs older than 7 days
        uv run deploy cleanup my-job-id          # Remove specific job
        uv run deploy cleanup --dry-run          # Preview what would be deleted
    """
    registry = get_registry()
    logs_dir = Path.cwd() / "logs" / "jobs"

    # Parse duration
    def parse_duration(duration_str: str) -> timedelta:
        """Parse duration string like '24h', '7d', '30d' to timedelta."""
        duration_str = duration_str.strip().lower()
        if duration_str.endswith("h"):
            return timedelta(hours=int(duration_str[:-1]))
        elif duration_str.endswith("d"):
            return timedelta(days=int(duration_str[:-1]))
        elif duration_str.endswith("w"):
            return timedelta(weeks=int(duration_str[:-1]))
        else:
            # Default to days
            return timedelta(days=int(duration_str))

    jobs_to_delete: list[JobState] = []
    log_dirs_to_delete: list[Path] = []

    if job_id:
        # Delete specific job
        job = registry.get_job(job_id)
        if not job:
            console.print(f"[red][FAIL] Job not found: {job_id}[/red]")
            raise typer.Exit(code=1) from None

        if job.status == "running":
            console.print(
                f"[red][FAIL] Cannot delete running job. Stop it first with: "
                f"uv run deploy stop {job_id}[/red]"
            )
            raise typer.Exit(code=1) from None

        jobs_to_delete.append(job)

        # Find matching log directories
        for log_dir in logs_dir.glob(f"{job_id}*"):
            if log_dir.is_dir():
                log_dirs_to_delete.append(log_dir)

    else:
        # Delete jobs matching criteria
        cutoff = datetime.now() - parse_duration(older_than)
        all_jobs = registry.list_jobs(status=None, limit=1000)

        for job in all_jobs:
            # Skip running jobs unless explicitly requested
            if job.status == "running":
                continue

            # Check status filter
            if status and status != "all" and job.status != status:
                continue

            # Check age
            try:
                job_time = datetime.fromisoformat(job.start_time)
                if job_time > cutoff:
                    continue
            except ValueError:
                continue

            jobs_to_delete.append(job)

            # Find matching log directories
            for log_dir in logs_dir.glob(f"{job.job_id}*"):
                if log_dir.is_dir():
                    log_dirs_to_delete.append(log_dir)

    if not jobs_to_delete:
        console.print("[dim]No jobs match the cleanup criteria[/dim]")
        return

    # Show what will be deleted
    action = "Would delete" if dry_run else "Deleting"
    console.print(f"\n[bold]{action} {len(jobs_to_delete)} job(s):[/bold]")

    table = Table()
    table.add_column("Job ID", style="cyan")
    table.add_column("Status", style="yellow")
    table.add_column("Started", style="dim")

    for job in jobs_to_delete:
        table.add_row(job.job_id, job.status, job.start_time[:19])

    console.print(table)

    if include_logs and log_dirs_to_delete:
        console.print(
            f"\n[bold]{action} {len(log_dirs_to_delete)} log directories[/bold]"
        )

    if dry_run:
        console.print("\n[yellow]Dry run - no changes made[/yellow]")
        return

    # Perform deletion
    deleted_jobs = 0
    deleted_logs = 0

    for job in jobs_to_delete:
        if registry.delete_job(job.job_id):
            deleted_jobs += 1

    if include_logs:
        for log_dir in log_dirs_to_delete:
            try:
                shutil.rmtree(log_dir)
                deleted_logs += 1
            except Exception as e:
                console.print(
                    f"[yellow]Warning: Could not delete {log_dir}: {e}[/yellow]"
                )

    console.print(
        f"\n[green][OK] Cleaned up {deleted_jobs} jobs"
        + (f" and {deleted_logs} log directories" if include_logs else "")
        + "[/green]"
    )


# ============================================================================
# Traces Command
# ============================================================================


@app.command()
def traces(
    job_id: str | None = typer.Argument(
        None, help="Job ID to view traces for (optional)"
    ),
    merge: bool = typer.Option(
        False, "--merge", "-m", help="Merge legacy trace files into unified trace"
    ),
    show: bool = typer.Option(
        False, "--show", "-s", help="Show trace summary (span count, agents, etc.)"
    ),
):
    """View and merge job traces.

    New traces use NDJSON format (already unified during execution).
    Legacy JSON traces can be merged with --merge flag.

    Examples:
        uv run deploy traces                          # List all trace directories
        uv run deploy traces my-job-id --show         # Show trace summary
        uv run deploy traces my-job-id --merge        # Merge legacy JSON traces
    """
    from ..config import settings
    from ..observability.semantic import merge_job_traces

    traces_dir = Path(settings.semantic_trace_dir)

    if not traces_dir.exists():
        console.print(f"[dim]No traces directory found at {traces_dir}[/dim]")
        return

    if job_id:
        # Handle specific job
        job_trace_dir = traces_dir / job_id
        if not job_trace_dir.exists():
            # Try to find job by prefix
            matches = list(traces_dir.glob(f"{job_id}*"))
            if len(matches) == 1:
                job_trace_dir = matches[0]
            elif len(matches) > 1:
                console.print(f"[yellow]Multiple matches for '{job_id}':[/yellow]")
                for match in matches:
                    console.print(f"  {match.name}")
                return
            else:
                console.print(f"[red]No traces found for job: {job_id}[/red]")
                return

        # Check for new NDJSON format first (already unified)
        ndjson_files = list(job_trace_dir.glob("*.ndjson"))
        trace_files = list(job_trace_dir.glob("trace_*.json"))
        unified_file = job_trace_dir / "unified_trace.json"

        if show or not merge:
            # Show trace summary
            if ndjson_files:
                # New NDJSON format - already unified
                ndjson_file = ndjson_files[0]
                trace_data = read_ndjson_trace(ndjson_file)
                if trace_data:
                    console.print(f"\n[bold]Trace: {job_trace_dir.name}[/bold]")
                    console.print("  Format: NDJSON (live unified)")
                    console.print(f"  Spans: {trace_data.get('span_count', 0)}")
                    console.print(
                        f"  Agents: {', '.join(trace_data.get('agents', []))}"
                    )
                    console.print(f"  File: {ndjson_file}")
            elif unified_file.exists():
                # Legacy unified JSON
                with open(unified_file) as f:
                    unified = json.load(f)
                console.print(f"\n[bold]Unified Trace: {job_trace_dir.name}[/bold]")
                console.print("  Format: JSON (merged)")
                console.print(f"  Spans: {unified.get('span_count', 0)}")
                console.print(f"  Agents: {', '.join(unified.get('agents', []))}")
                console.print(f"  Source files: {unified.get('source_files', 0)}")
                console.print(f"  File: {unified_file}")
            elif trace_files:
                # Legacy individual JSON files
                console.print(f"\n[bold]Traces: {job_trace_dir.name}[/bold]")
                console.print("  Format: JSON (not merged)")
                console.print(f"  Files: {len(trace_files)}")
                for tf in trace_files:
                    console.print(f"    - {tf.name}")
                console.print("\n[dim]Run with --merge to create unified trace[/dim]")
            else:
                console.print(f"\n[dim]No trace files in {job_trace_dir.name}[/dim]")

        if merge:
            if ndjson_files:
                console.print(
                    "[yellow]Traces are already unified (NDJSON format). "
                    "--merge is for legacy JSON traces.[/yellow]"
                )
            else:
                # Merge legacy JSON traces
                unified_path = write_unified_trace(job_trace_dir)
                if unified_path:
                    console.print(
                        f"[green][OK] Unified trace created: {unified_path}[/green]"
                    )

                    # Show summary
                    unified = merge_job_traces(job_trace_dir)
                    if unified:
                        console.print(f"  Spans: {unified.get('span_count', 0)}")
                        console.print(
                            f"  Agents: {', '.join(unified.get('agents', []))}"
                        )
                else:
                    console.print("[red]Failed to merge traces[/red]")

    else:
        # List all trace directories
        trace_dirs = [d for d in traces_dir.iterdir() if d.is_dir()]

        if not trace_dirs:
            console.print("[dim]No trace directories found[/dim]")
            return

        table = Table(title="Job Traces")
        table.add_column("Job ID", style="cyan")
        table.add_column("Files", justify="right")
        table.add_column("Unified", justify="center")

        for trace_dir in sorted(trace_dirs, key=lambda d: d.name, reverse=True):
            trace_files = list(trace_dir.glob("trace_*.json"))
            unified = (trace_dir / "unified_trace.json").exists()
            table.add_row(
                trace_dir.name,
                str(len(trace_files)),
                "[green]✓[/green]" if unified else "[dim]-[/dim]",
            )

        console.print(table)
        console.print(
            "\n[dim]Use 'uv run deploy traces <job-id> --show' to view details[/dim]"
        )


# ============================================================================
# Sessions Subcommand Group
# ============================================================================

sessions_app = typer.Typer(
    name="sessions",
    help="Manage conversation sessions",
)
app.add_typer(sessions_app, name="sessions")


@sessions_app.command(name="list")
def sessions_list(
    job_name: str | None = typer.Argument(None, help="Job name (optional filter)"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum sessions to show"),
):
    """List active conversation sessions."""
    console.print("[bold]Active Sessions[/bold]\n")

    # Sessions are stored per-agent in memory, so we need to query agents
    # For now, show sessions from the file-based session store
    sessions_dir = Path.cwd() / ".sessions"

    if not sessions_dir.exists():
        console.print("[dim]No sessions found. Start a chat to create one.[/dim]")
        return

    session_files = list(sessions_dir.glob("*.json"))
    if not session_files:
        console.print("[dim]No sessions found.[/dim]")
        return

    table = Table()
    table.add_column("Session ID", style="cyan")
    table.add_column("Agent", style="green")
    table.add_column("Messages", justify="right")
    table.add_column("Last Active", style="dim")

    count = 0
    for sf in sorted(session_files, key=lambda f: f.stat().st_mtime, reverse=True):
        if count >= limit:
            break
        try:
            with open(sf) as f:
                session_data = json.load(f)
            # Filter by job if specified
            if job_name and session_data.get("job_id") != job_name:
                continue

            session_id = session_data.get("session_id", sf.stem)
            agent = session_data.get("agent_id", "unknown")
            messages = len(session_data.get("messages", []))
            last_active = datetime.fromtimestamp(
                session_data.get("last_accessed", sf.stat().st_mtime)
            ).strftime("%Y-%m-%d %H:%M")

            table.add_row(session_id[:36], agent, str(messages), last_active)
            count += 1
        except (json.JSONDecodeError, KeyError):
            continue

    if count == 0:
        console.print("[dim]No sessions found.[/dim]")
    else:
        console.print(table)
        console.print(f"\n[dim]Showing {count} session(s)[/dim]")


@sessions_app.command(name="show")
def sessions_show(
    session_id: str = typer.Argument(..., help="Session ID to show"),
    messages: int = typer.Option(10, "--messages", "-n", help="Number of messages"),
):
    """Show session details and conversation history."""
    sessions_dir = Path.cwd() / ".sessions"
    session_file = sessions_dir / f"{session_id}.json"

    if not session_file.exists():
        # Try partial match
        matches = list(sessions_dir.glob(f"{session_id}*.json"))
        if len(matches) == 1:
            session_file = matches[0]
        elif len(matches) > 1:
            console.print(f"[yellow]Multiple matches for '{session_id}':[/yellow]")
            for m in matches:
                console.print(f"  {m.stem}")
            return
        else:
            console.print(f"[red]Session not found: {session_id}[/red]")
            return

    try:
        with open(session_file) as f:
            session_data = json.load(f)
    except json.JSONDecodeError:
        console.print(f"[red]Invalid session file: {session_file}[/red]")
        return

    # Session info
    console.print(
        Panel(
            f"[bold]Session:[/bold] {session_data.get('session_id', 'unknown')}\n"
            f"[bold]Agent:[/bold] {session_data.get('agent_id', 'unknown')}\n"
            f"[bold]Job:[/bold] {session_data.get('job_id', 'unknown')}\n"
            f"[bold]Messages:[/bold] {len(session_data.get('messages', []))}\n"
            f"[bold]Created:[/bold] {datetime.fromtimestamp(session_data.get('created_at', 0)).strftime('%Y-%m-%d %H:%M:%S')}",
            title="Session Info",
        )
    )

    # Conversation history
    msgs = session_data.get("messages", [])
    if msgs:
        console.print("\n[bold]Conversation History[/bold]")
        for msg in msgs[-messages:]:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if role == "user":
                console.print(f"\n[cyan]You:[/cyan] {content}")
            else:
                console.print(
                    f"\n[green]Agent:[/green] {content[:500]}{'...' if len(content) > 500 else ''}"
                )


@sessions_app.command(name="delete")
def sessions_delete(
    session_id: str = typer.Argument(..., help="Session ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a conversation session."""
    sessions_dir = Path.cwd() / ".sessions"
    session_file = sessions_dir / f"{session_id}.json"

    if not session_file.exists():
        # Try partial match
        matches = list(sessions_dir.glob(f"{session_id}*.json"))
        if len(matches) == 1:
            session_file = matches[0]
            session_id = session_file.stem
        elif len(matches) > 1:
            console.print(f"[yellow]Multiple matches for '{session_id}':[/yellow]")
            for m in matches:
                console.print(f"  {m.stem}")
            return
        else:
            console.print(f"[red]Session not found: {session_id}[/red]")
            return

    if not force:
        confirm = typer.confirm(f"Delete session {session_id}?")
        if not confirm:
            console.print("[dim]Cancelled[/dim]")
            return

    session_file.unlink()
    console.print(f"[green][OK] Deleted session: {session_id}[/green]")


@sessions_app.command(name="clear")
def sessions_clear(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    older_than: str | None = typer.Option(
        None,
        "--older-than",
        "-o",
        help="Only clear sessions older than (e.g., 24h, 7d)",
    ),
):
    """Clear all conversation sessions."""
    sessions_dir = Path.cwd() / ".sessions"

    if not sessions_dir.exists():
        console.print("[dim]No sessions to clear[/dim]")
        return

    session_files = list(sessions_dir.glob("*.json"))
    if not session_files:
        console.print("[dim]No sessions to clear[/dim]")
        return

    # Filter by age if specified
    if older_than:
        cutoff = datetime.now()
        if older_than.endswith("h"):
            cutoff -= timedelta(hours=int(older_than[:-1]))
        elif older_than.endswith("d"):
            cutoff -= timedelta(days=int(older_than[:-1]))
        else:
            cutoff -= timedelta(days=int(older_than))

        session_files = [
            f
            for f in session_files
            if datetime.fromtimestamp(f.stat().st_mtime) < cutoff
        ]

    if not session_files:
        console.print("[dim]No sessions match the criteria[/dim]")
        return

    if not force:
        confirm = typer.confirm(f"Delete {len(session_files)} session(s)?")
        if not confirm:
            console.print("[dim]Cancelled[/dim]")
            return

    for sf in session_files:
        sf.unlink()

    console.print(f"[green][OK] Cleared {len(session_files)} session(s)[/green]")


# ============================================================================
# Chat Command (Interactive REPL)
# ============================================================================


@app.command()
def chat(
    job_name: str = typer.Argument(..., help="Job name or ID to chat with"),
    agent: str | None = typer.Option(
        None, "--agent", "-a", help="Specific agent to chat with (default: entry point)"
    ),
    session: str | None = typer.Option(
        None, "--session", "-s", help="Resume existing session by ID"
    ),
    timeout: int = typer.Option(
        120, "--timeout", "-t", help="Query timeout in seconds"
    ),
):
    """Start an interactive chat session with a running job.

    Enter queries at the prompt and receive responses. The session maintains
    conversation context across multiple exchanges.

    Special commands:
        /help     - Show available commands
        /agents   - List available agents in the job
        /session  - Show current session info
        /clear    - Clear conversation history (new session)
        /quit     - Exit chat (also: /exit, Ctrl+C, Ctrl+D)

    Examples:
        uv run deploy chat my-job                    # Chat with job entry point
        uv run deploy chat my-job --agent weather   # Chat with specific agent
        uv run deploy chat my-job --session abc123  # Resume session
    """
    import uuid

    # Import readline for history support (optional on Windows)
    try:
        import readline  # noqa: F401 - imported for side effects
    except ImportError:
        readline = None  # type: ignore[assignment]

    registry = get_registry()
    job_state = registry.get_job(job_name)

    if not job_state:
        console.print(f"[red][FAIL] Job not found: {job_name}[/red]")
        console.print("[dim]Use 'uv run deploy list' to see running jobs[/dim]")
        raise typer.Exit(code=1) from None

    if job_state.status != "running":
        console.print(
            f"[red][FAIL] Job is not running (status: {job_state.status})[/red]"
        )
        raise typer.Exit(code=1) from None

    # Determine target agent
    if agent:
        if agent not in job_state.agents:
            console.print(f"[red][FAIL] Agent not found: {agent}[/red]")
            console.print(f"[dim]Available: {', '.join(job_state.agents.keys())}[/dim]")
            raise typer.Exit(code=1) from None
        target_agent = job_state.agents[agent]
        agent_id = agent
    else:
        # Use entry point or first agent
        entry_point = job_state.entry_point
        if entry_point and entry_point in job_state.agents:
            target_agent = job_state.agents[entry_point]
            agent_id = entry_point
        else:
            agent_id = next(iter(job_state.agents.keys()))
            target_agent = job_state.agents[agent_id]

    if not target_agent.url:
        console.print(f"[red][FAIL] Agent {agent_id} has no URL[/red]")
        raise typer.Exit(code=1) from None

    # Session management
    session_id = session or str(uuid.uuid4())
    sessions_dir = Path.cwd() / ".sessions"
    sessions_dir.mkdir(exist_ok=True)
    session_file = sessions_dir / f"{session_id}.json"

    # Load or create session data
    if session_file.exists():
        with open(session_file) as f:
            session_data = json.load(f)
        console.print(f"[dim]Resuming session: {session_id[:8]}...[/dim]")
    else:
        session_data = {
            "session_id": session_id,
            "job_id": job_name,
            "agent_id": agent_id,
            "messages": [],
            "created_at": datetime.now().timestamp(),
            "last_accessed": datetime.now().timestamp(),
        }

    # Setup readline history (if available)
    history_file = sessions_dir / ".chat_history"
    if readline:
        try:
            readline.read_history_file(history_file)
        except FileNotFoundError:
            pass
        readline.set_history_length(1000)

    # Welcome message
    console.print(
        Panel(
            f"[bold]Chat Session[/bold]\n\n"
            f"Job: {job_name}\n"
            f"Agent: {agent_id} ({target_agent.url})\n"
            f"Session: {session_id[:8]}...\n\n"
            f"[dim]Type /help for commands, /quit to exit[/dim]",
            title="Interactive Chat",
            border_style="cyan",
        )
    )

    async def send_query(message: str) -> dict:
        """Send query to agent."""
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{target_agent.url}/query",
                json={"query": message, "session_id": session_id},
            )
            response.raise_for_status()
            return response.json()

    def save_session():
        """Save session to file."""
        session_data["last_accessed"] = datetime.now().timestamp()
        with open(session_file, "w") as f:
            json.dump(session_data, f, indent=2)

    def handle_command(cmd: str) -> bool:
        """Handle slash commands. Returns True if should continue, False to exit."""
        nonlocal session_id, session_data, session_file

        cmd = cmd.lower().strip()

        if cmd in ("/quit", "/exit", "/q"):
            save_session()
            console.print("\n[dim]Goodbye![/dim]")
            return False

        elif cmd == "/help":
            console.print(
                Panel(
                    "[bold]Available Commands[/bold]\n\n"
                    "/help     - Show this help message\n"
                    "/agents   - List available agents in the job\n"
                    "/session  - Show current session info\n"
                    "/clear    - Start new session (clear history)\n"
                    "/quit     - Exit chat (also: /exit, /q, Ctrl+C)",
                    title="Help",
                    border_style="blue",
                )
            )

        elif cmd == "/agents":
            table = Table(title="Available Agents")
            table.add_column("Agent", style="cyan")
            table.add_column("URL", style="dim")
            table.add_column("Current", justify="center")
            for aid, ag in job_state.agents.items():
                current = "[green]✓[/green]" if aid == agent_id else ""
                table.add_row(aid, ag.url, current)
            console.print(table)

        elif cmd == "/session":
            console.print(
                Panel(
                    f"[bold]Session ID:[/bold] {session_id}\n"
                    f"[bold]Job:[/bold] {job_name}\n"
                    f"[bold]Agent:[/bold] {agent_id}\n"
                    f"[bold]Messages:[/bold] {len(session_data['messages'])}\n"
                    f"[bold]Created:[/bold] {datetime.fromtimestamp(session_data['created_at']).strftime('%Y-%m-%d %H:%M:%S')}",
                    title="Session Info",
                    border_style="yellow",
                )
            )

        elif cmd == "/clear":
            # Create new session
            session_id = str(uuid.uuid4())
            session_file = sessions_dir / f"{session_id}.json"
            session_data = {
                "session_id": session_id,
                "job_id": job_name,
                "agent_id": agent_id,
                "messages": [],
                "created_at": datetime.now().timestamp(),
                "last_accessed": datetime.now().timestamp(),
            }
            console.print(f"[green]New session started: {session_id[:8]}...[/green]")

        else:
            console.print(f"[yellow]Unknown command: {cmd}[/yellow]")
            console.print("[dim]Type /help for available commands[/dim]")

        return True

    # Main REPL loop
    try:
        while True:
            try:
                # Get user input
                user_input = input("\n[You] > ").strip()

                if not user_input:
                    continue

                # Handle commands
                if user_input.startswith("/"):
                    if not handle_command(user_input):
                        break
                    continue

                # Send query to agent
                console.print("[dim]Thinking...[/dim]", end="\r")

                try:
                    result = asyncio.run(send_query(user_input))
                    response_text = result.get("response", str(result))

                    # Clear "Thinking..." and show response
                    console.print(" " * 20, end="\r")  # Clear line
                    console.print(f"\n[bold green][{agent_id}][/bold green]")
                    console.print(response_text)

                    # Update session history
                    session_data["messages"].append(
                        {
                            "role": "user",
                            "content": user_input,
                            "timestamp": datetime.now().timestamp(),
                        }
                    )
                    session_data["messages"].append(
                        {
                            "role": "assistant",
                            "content": response_text,
                            "timestamp": datetime.now().timestamp(),
                        }
                    )
                    save_session()

                except httpx.TimeoutException:
                    console.print(f"[red]Request timed out after {timeout}s[/red]")
                except httpx.HTTPStatusError as e:
                    console.print(f"[red]HTTP error: {e.response.status_code}[/red]")
                except Exception as e:
                    console.print(f"[red]Error: {e}[/red]")

            except EOFError:
                # Ctrl+D
                save_session()
                console.print("\n[dim]Goodbye![/dim]")
                break

    except KeyboardInterrupt:
        # Ctrl+C
        save_session()
        console.print("\n[dim]Session saved. Goodbye![/dim]")

    # Save readline history (if available)
    if readline:
        try:
            readline.write_history_file(history_file)
        except Exception:
            pass


# ============================================================================
# Main
# ============================================================================


def main():
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
