#!/usr/bin/env python3
"""Start all agents for the Clean MCP + A2A System."""

import subprocess
import time
import sys
import signal


def start_agents():
    """Start all agents with SDK integration."""
    print("🚀 Starting Clean MCP + A2A System with SDK Integration")
    print("=" * 55)

    processes = []

    try:
        # Start Weather Agent
        print("\nStarting Weather Agent (port 9001)...")
        weather = subprocess.Popen(
            ["uv", "run", "weather-agent"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        processes.append(("Weather Agent", weather))
        time.sleep(3)

        # Start Maps Agent
        print("Starting Maps Agent (port 9002)...")
        maps = subprocess.Popen(
            ["uv", "run", "maps-agent"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        processes.append(("Maps Agent", maps))
        time.sleep(3)

        # Start Controller Agent
        print("Starting Controller Agent (port 9000)...")
        controller = subprocess.Popen(
            ["uv", "run", "controller-agent"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        processes.append(("Controller Agent", controller))
        time.sleep(2)

        print("\n🎉 All agents started!")
        print("\nArchitecture:")
        print("  Weather Agent (port 9001): SDK MCP server with weather tools")
        print("  Maps Agent (port 9002): SDK MCP server with maps tools")
        print("  Controller Agent (port 9000): Coordinates via A2A using curl")
        print("\nTest with: uv run test-system")
        print("Stop with: Ctrl+C or pkill -f 'uv run'")
        print("\nPress Ctrl+C to stop all agents...")

        # Wait for interrupt
        while True:
            time.sleep(1)
            # Check if any process has terminated
            for name, proc in processes:
                if proc.poll() is not None:
                    print(f"\n⚠️ {name} has stopped unexpectedly")
                    raise KeyboardInterrupt

    except KeyboardInterrupt:
        print("\n\nShutting down agents...")
        for name, proc in processes:
            if proc.poll() is None:  # Process is still running
                print(f"  Stopping {name}...")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
        print("✅ All agents stopped")
        sys.exit(0)


def main():
    """Entry point for start-all command."""
    # Handle signal for clean shutdown
    signal.signal(signal.SIGINT, lambda s, f: None)
    start_agents()


if __name__ == "__main__":
    main()