"""
Context Management A2A - Agent Runner
Reads YAML configuration and starts the context test agent.
"""
import yaml
import subprocess
import sys
import time
from pathlib import Path
import os
import requests

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class AgentRunner:
    def __init__(self, config_file="deployment.yaml"):
        # Get the directory where this script is located
        self.script_dir = Path(__file__).parent.absolute()
        self.config_file = self.script_dir / config_file
        self.processes = []
        self.config = None
        self.log_dir = self.script_dir / "logs"
        self.log_dir.mkdir(exist_ok=True)

    def load_config(self):
        """Load the YAML configuration file."""
        with open(self.config_file, 'r') as f:
            self.config = yaml.safe_load(f)
        print(f"[OK] Loaded configuration: {self.config['job']['name']}")

    def start_agent(self, agent_config):
        """Start a single agent as a subprocess."""
        agent_id = agent_config['id']
        agent_module = agent_config['module']
        port = agent_config['config']['port']
        agent_name = agent_config['config']['name']

        print(f"[START] Starting {agent_name} on port {port}...")

        # Set environment variables
        env = os.environ.copy()
        env['AGENT_PORT'] = str(port)

        # Add the script directory to PYTHONPATH so imports work correctly
        if 'PYTHONPATH' in env:
            env['PYTHONPATH'] = f"{self.script_dir}{os.pathsep}{env['PYTHONPATH']}"
        else:
            env['PYTHONPATH'] = str(self.script_dir)

        # Create log files for this agent
        stdout_log = self.log_dir / f"{agent_id}_stdout.log"
        stderr_log = self.log_dir / f"{agent_id}_stderr.log"

        # Convert module path to file path
        module_path = agent_module.replace('.', os.sep) + '.py'
        agent_file = self.script_dir / module_path

        # Start the agent as a subprocess
        cmd = [sys.executable, '-u', str(agent_file)]

        # Open log files in binary mode
        stdout_file = open(stdout_log, 'wb', buffering=0)
        stderr_file = open(stderr_log, 'wb', buffering=0)

        process = subprocess.Popen(
            cmd,
            env=env,
            cwd=self.script_dir,
            stdout=stdout_file,
            stderr=stderr_file,
            start_new_session=True
        )

        self.processes.append({
            'id': agent_id,
            'name': agent_name,
            'process': process,
            'port': port,
            'stdout_file': stdout_file,
            'stderr_file': stderr_file,
            'stdout_log': stdout_log,
            'stderr_log': stderr_log
        })

        # Wait for startup
        time.sleep(8)

        # Check if it's still running
        if process.poll() is None:
            print(f"[OK] {agent_name} started successfully on port {port}")
            print(f"   Logs: {stdout_log}")
        else:
            print(f"[ERROR] {agent_name} failed to start!")
            print(f"   Check logs at: {stderr_log}")
            with open(stderr_log, 'rb') as f:
                error_content = f.read().decode('utf-8', errors='replace')
                if error_content:
                    print(f"   Error: {error_content}")

        return process

    def start_all_agents(self):
        """Start all agents based on configuration."""
        print(f"\n{'='*60}")
        print(f"Starting Context Management Test: {self.config['job']['name']}")
        print(f"{'='*60}\n")

        agents = self.config['agents']
        strategy = self.config['deployment']['strategy']

        if strategy == 'sequential':
            for agent_config in agents:
                self.start_agent(agent_config)

        print(f"\n{'='*60}")
        print(f"[OK] All agents started!")
        print(f"{'='*60}")
        print(f"\n[INFO] Running Agents:")
        for proc_info in self.processes:
            print(f"  - {proc_info['name']} on port {proc_info['port']}")

        print(f"\n[INFO] Entry Point: Context Test Agent on port 9010")
        print(f"[INFO] Send queries to: http://localhost:9010/query")
        print(f"\n[WARN] Press Ctrl+C to stop all agents\n")

    def stop_all_agents(self):
        """Stop all running agents."""
        print(f"\n{'='*60}")
        print("[STOP] Stopping all agents...")
        print(f"{'='*60}\n")

        for proc_info in self.processes:
            process = proc_info['process']
            name = proc_info['name']

            if process.poll() is None:
                print(f"Stopping {name}...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                    print(f"[OK] {name} stopped")
                except subprocess.TimeoutExpired:
                    print(f"[WARN] Force killing {name}...")
                    process.kill()
                    print(f"[OK] {name} killed")

            # Close log files
            proc_info['stdout_file'].close()
            proc_info['stderr_file'].close()

        print(f"\n[OK] All agents stopped successfully\n")

    def check_agent_health(self):
        """Check if all agents are still running."""
        for proc_info in self.processes:
            if proc_info['process'].poll() is not None:
                print(f"\n[WARN] {proc_info['name']} has stopped unexpectedly!")
                stderr_log = proc_info['stderr_log']
                if stderr_log.exists():
                    with open(stderr_log, 'rb') as f:
                        error_content = f.read().decode('utf-8', errors='replace')
                        error_lines = error_content.splitlines()
                        if error_lines:
                            print(f"Last error lines:")
                            for line in error_lines[-10:]:
                                print(f"  {line}")
                return False
        return True

    def verify_agent_connectivity(self):
        """Verify all agents are accessible via HTTP."""
        print(f"\n{'='*60}")
        print("Verifying agent connectivity...")
        print(f"{'='*60}\n")

        print("Waiting for servers to be ready...")
        time.sleep(10)

        all_healthy = True
        for proc_info in self.processes:
            name = proc_info['name']
            port = proc_info['port']
            url = f"http://localhost:{port}"

            max_retries = 5
            retry_delay = 3
            success = False

            for attempt in range(max_retries):
                try:
                    response = requests.get(f"{url}/health", timeout=5)
                    if response.status_code == 200:
                        print(f"[OK] {name} is healthy at {url}")
                        success = True
                        break
                    else:
                        print(f"  Attempt {attempt + 1}/{max_retries}: {name} returned status {response.status_code}")
                except requests.exceptions.RequestException as e:
                    print(f"  Attempt {attempt + 1}/{max_retries}: {name} not accessible - {e}")

                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2

            if not success:
                print(f"[ERROR] {name} is not accessible after {max_retries} attempts")
                all_healthy = False

        if all_healthy:
            print(f"\n[OK] All agents are healthy and accessible!\n")
        else:
            print(f"\n[WARN] Some agents are not accessible. Check logs for details.\n")

        return all_healthy

    def run(self):
        """Main execution loop."""
        try:
            self.load_config()
            self.start_all_agents()

            all_running = all(proc['process'].poll() is None for proc in self.processes)
            if not all_running:
                print("\n[ERROR] Not all agents started successfully. Stopping...")
                self.stop_all_agents()
                return

            if not self.verify_agent_connectivity():
                print("\n[WARN] Some agents are not responding, but continuing...")

            print("Monitoring agents... (Press Ctrl+C to stop)\n")
            while True:
                time.sleep(5)
                if not self.check_agent_health():
                    print("\n[ERROR] Agent failure detected. Stopping all agents...")
                    break

        except KeyboardInterrupt:
            print("\n\n[WARN] Received interrupt signal...")
        except Exception as e:
            print(f"\n[ERROR] Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.stop_all_agents()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run context management test agent")
    parser.add_argument(
        "--config",
        type=str,
        default="deployment.yaml",
        help="YAML configuration file (default: deployment.yaml)"
    )
    args = parser.parse_args()

    runner = AgentRunner(args.config)
    runner.run()


if __name__ == "__main__":
    main()
