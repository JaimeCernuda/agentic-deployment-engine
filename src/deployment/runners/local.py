"""Local runner - start agents via subprocess."""

import subprocess
import os
from typing import List
from ..models import AgentConfig


class LocalRunner:
    """Run agents locally via subprocess."""

    def start(self, agent: AgentConfig, connected_urls: List[str]) -> subprocess.Popen:
        """Start agent locally.

        Args:
            agent: Agent configuration
            connected_urls: List of URLs this agent should connect to

        Returns:
            subprocess.Popen object
        """
        # Build command to start agent
        # Assumes agents are registered as CLI entry points in pyproject.toml
        # E.g., "weather-agent" for agents.weather_agent:main

        # Convert module to CLI command
        # agents.weather_agent → weather-agent
        module_parts = agent.module.split(".")
        if len(module_parts) >= 2:
            # agents.weather_agent → weather-agent
            cli_command = f"{module_parts[-1].replace('_', '-')}"
        else:
            cli_command = agent.module

        cmd = ["uv", "run", cli_command]

        # Setup environment
        env = os.environ.copy()

        # Add agent-specific environment
        if agent.environment:
            env.update(agent.environment)

        # Pass connected URLs via environment variable
        if connected_urls:
            env["CONNECTED_AGENTS"] = ",".join(connected_urls)

        # Start process
        print(f"  Running: {' '.join(cmd)}")
        print(f"  Environment: CONNECTED_AGENTS={env.get('CONNECTED_AGENTS', 'none')}")

        process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        return process
