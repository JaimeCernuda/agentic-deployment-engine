"""CLI for A2A job deployment."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .deployer import AgentDeployer, DeploymentError
from .loader import JobLoadError, JobLoader
from .resolver import TopologyResolver

app = typer.Typer(
    name="deploy",
    help="A2A Job Deployment System - Deploy multi-agent workflows",
    add_completion=False,
)
console = Console()


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

        console.print("[green]✓ Job definition is valid[/green]")

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
        console.print(f"[red]✗ Validation failed:[/red]\n{e}")
        raise typer.Exit(code=1)


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
        console.print("[green]✓ Job valid[/green]")

        # Generate plan
        deployment_plan = resolver.resolve(job)
        console.print(f"[green]✓ Plan generated: {len(deployment_plan.stages)} stages[/green]")

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
                stage_table.add_row(
                    str(idx + 1), ", ".join(stage), str(len(stage))
                )

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
                    conn_table.add_row(
                        agent_id, "\n".join(urls), str(len(urls))
                    )
                else:
                    conn_table.add_row(agent_id, "[dim]none[/dim]", "0")

            console.print(conn_table)

    except JobLoadError as e:
        console.print(f"[red]✗ Validation failed:[/red]\n{e}")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]✗ Planning failed:[/red]\n{e}")
        raise typer.Exit(code=1)


# ============================================================================
# Start Command
# ============================================================================


@app.command()
def start(
    job_file: Path = typer.Argument(..., help="Path to job YAML file"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Job name override"),
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
            console.print(f"[green]✓ Loaded {job.job.name}[/green]")

            # 2. Generate plan
            console.print("[dim]Generating deployment plan...[/dim]")
            deployment_plan = resolver.resolve(job)
            console.print(
                f"[green]✓ Plan generated: {len(deployment_plan.stages)} stages[/green]"
            )

            # 3. Deploy
            console.print("[dim]Deploying agents...[/dim]")
            deployed_job = await deployer.deploy(job, deployment_plan)

            console.print(
                Panel(
                    f"[green]✓ Job deployed successfully[/green]\n\n"
                    f"Job ID: {deployed_job.job_id}\n"
                    f"Agents: {len(deployed_job.agents)}\n"
                    f"Status: {deployed_job.status}\n\n"
                    f"Use [cyan]uv run deploy status {deployed_job.job_id}[/cyan] to monitor",
                    title="Deployment Complete",
                )
            )

            # Keep running
            console.print(
                "\n[yellow]Press Ctrl+C to stop the job and exit[/yellow]"
            )

            try:
                # Wait indefinitely
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                console.print("\n[yellow]Stopping job...[/yellow]")
                await deployer.stop(deployed_job)
                console.print("[green]✓ Job stopped[/green]")

        except JobLoadError as e:
            console.print(f"[red]✗ Validation failed:[/red]\n{e}")
            raise typer.Exit(code=1)
        except DeploymentError as e:
            console.print(f"[red]✗ Deployment failed:[/red]\n{e}")
            raise typer.Exit(code=1)
        except Exception as e:
            console.print(f"[red]✗ Error:[/red]\n{e}")
            raise typer.Exit(code=1)

    asyncio.run(_deploy())


# ============================================================================
# Status Command (placeholder)
# ============================================================================


@app.command()
def status(
    job_name: str = typer.Argument(..., help="Job name"),
):
    """Show job status."""
    console.print(f"[yellow]Status command not yet implemented for: {job_name}[/yellow]")
    console.print(
        "[dim]This will show health status of all agents in the job[/dim]"
    )


# ============================================================================
# Stop Command (placeholder)
# ============================================================================


@app.command()
def stop(
    job_name: str = typer.Argument(..., help="Job name"),
):
    """Stop a running job."""
    console.print(f"[yellow]Stop command not yet implemented for: {job_name}[/yellow]")
    console.print("[dim]This will gracefully stop all agents in the job[/dim]")


# ============================================================================
# List Command (placeholder)
# ============================================================================


@app.command()
def list():
    """List all deployed jobs."""
    console.print("[yellow]List command not yet implemented[/yellow]")
    console.print("[dim]This will show all running jobs[/dim]")


# ============================================================================
# Logs Command (placeholder)
# ============================================================================


@app.command()
def logs(
    job_name: str = typer.Argument(..., help="Job name"),
    agent: Optional[str] = typer.Option(None, "--agent", "-a", help="Agent ID"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow logs"),
):
    """View job logs."""
    console.print(f"[yellow]Logs command not yet implemented for: {job_name}[/yellow]")
    console.print("[dim]This will show logs from job agents[/dim]")


# ============================================================================
# Main
# ============================================================================


def main():
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
