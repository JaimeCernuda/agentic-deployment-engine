#!/usr/bin/env python3
"""Start all agents for the Clean MCP + A2A System."""

import signal
import subprocess
import sys
import time

from .observability import get_logger, setup_logging

logger = get_logger(__name__)


def start_agents() -> None:
    """Start all agents with SDK integration."""
    setup_logging(level="INFO")

    logger.info("Starting Clean MCP + A2A System with SDK Integration")

    processes: list[tuple[str, subprocess.Popen[bytes]]] = []

    try:
        # Start Weather Agent
        # Note: stdout/stderr left as default (inherited) so logs are visible
        logger.info("Starting Weather Agent (port 9001)...")
        weather = subprocess.Popen(["uv", "run", "weather-agent"])
        processes.append(("Weather Agent", weather))
        time.sleep(3)

        # Start Maps Agent
        logger.info("Starting Maps Agent (port 9002)...")
        maps = subprocess.Popen(["uv", "run", "maps-agent"])
        processes.append(("Maps Agent", maps))
        time.sleep(3)

        # Start Controller Agent
        logger.info("Starting Controller Agent (port 9000)...")
        controller = subprocess.Popen(["uv", "run", "controller-agent"])
        processes.append(("Controller Agent", controller))
        time.sleep(2)

        logger.info("All agents started successfully")
        logger.info("Architecture:")
        logger.info("  Weather Agent (port 9001): SDK MCP server with weather tools")
        logger.info("  Maps Agent (port 9002): SDK MCP server with maps tools")
        logger.info("  Controller Agent (port 9000): Coordinates via A2A using curl")
        logger.info("Test with: uv run test-system")
        logger.info("Stop with: Ctrl+C or pkill -f 'uv run'")
        logger.info("Press Ctrl+C to stop all agents...")

        # Wait for interrupt
        while True:
            time.sleep(1)
            # Check if any process has terminated
            for name, proc in processes:
                if proc.poll() is not None:
                    logger.warning("%s has stopped unexpectedly", name)
                    raise KeyboardInterrupt

    except KeyboardInterrupt:
        logger.info("Shutting down agents...")
        for name, proc in processes:
            if proc.poll() is None:  # Process is still running
                logger.info("Stopping %s...", name)
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
        logger.info("All agents stopped")
        sys.exit(0)


def main():
    """Entry point for start-all command."""
    # Handle signal for clean shutdown
    signal.signal(signal.SIGINT, lambda s, f: None)
    start_agents()


if __name__ == "__main__":
    main()
