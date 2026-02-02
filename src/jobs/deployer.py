"""Agent deployer - Execute deployment plans."""

import asyncio
import getpass
import logging
import os
import shlex
import subprocess
import sys
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import paramiko

from ..observability.semantic import get_semantic_tracer
from .models import (
    AgentConfig,
    DeployedAgent,
    DeployedJob,
    DeploymentPlan,
    JobDefinition,
)

logger = logging.getLogger(__name__)


class DeploymentError(Exception):
    """Error during deployment."""

    pass


# ============================================================================
# Base Runner Interface
# ============================================================================


class AgentRunner(ABC):
    """Base class for agent runners."""

    @abstractmethod
    async def start(
        self,
        agent: AgentConfig,
        connected_urls: list[str],
        env: dict[str, str],
        job_id: str | None = None,
    ) -> Any:
        """Start an agent.

        Args:
            agent: Agent configuration
            connected_urls: URLs of connected agents
            env: Environment variables
            job_id: Job identifier for log organization

        Returns:
            Process/container reference
        """
        pass

    @abstractmethod
    async def stop(self, process: Any, agent_id: str) -> None:
        """Stop an agent.

        Args:
            process: Process/container reference
            agent_id: Agent identifier
        """
        pass

    @abstractmethod
    async def get_status(self, process: Any) -> str:
        """Get agent status.

        Args:
            process: Process/container reference

        Returns:
            Status string
        """
        pass

    async def stop_by_pid(
        self, pid: int, agent_id: str, host: str | None = None
    ) -> None:
        """Stop agent by process ID.

        Optional method for runners that support stopping by PID.

        Args:
            pid: Process ID
            agent_id: Agent identifier
            host: Optional host for remote runners
        """
        raise NotImplementedError(f"{type(self).__name__} doesn't support stop_by_pid")


# ============================================================================
# Local Runner (subprocess)
# ============================================================================


class LocalRunner(AgentRunner):
    """Run agents locally via subprocess."""

    def __init__(self, project_root: Path | None = None):
        """Initialize local runner.

        Args:
            project_root: Project root directory (for log files)
        """
        self.project_root = project_root or Path.cwd()
        self.log_dir = self.project_root / "logs" / "jobs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    async def start(
        self,
        agent: AgentConfig,
        connected_urls: list[str],
        env: dict[str, str],
        job_id: str | None = None,
    ) -> subprocess.Popen:
        """Start agent locally via python -m.

        Args:
            agent: Agent configuration
            connected_urls: URLs of connected agents
            env: Environment variables
            job_id: Job identifier for log organization

        Returns:
            Process handle
        """
        # Use python -m to run the agent module directly
        cmd = [sys.executable, "-m", agent.module]

        # Build environment - start with system env (critical on Windows for networking)
        process_env = os.environ.copy()
        process_env.update(env)

        # Add agent-specific config as environment variables
        for key, value in agent.config.items():
            process_env[f"AGENT_{key.upper()}"] = str(value)

        # Add connected agents (comma-separated URLs)
        if connected_urls:
            process_env["CONNECTED_AGENTS"] = ",".join(connected_urls)

        # Add agent deployment environment
        if agent.deployment.environment:
            process_env.update(agent.deployment.environment)

        # Enable semantic tracing by default for CLI deployments
        # This provides visibility into agent internals without extra configuration
        from ..config import settings

        # Always enable tracing - use parent setting or default to True
        process_env["AGENT_SEMANTIC_TRACING_ENABLED"] = "true"
        # Use job-specific trace directory for log correlation
        if job_id:
            trace_dir = str(Path(settings.semantic_trace_dir) / job_id)
            process_env["AGENT_SEMANTIC_TRACE_DIR"] = trace_dir
        else:
            process_env["AGENT_SEMANTIC_TRACE_DIR"] = settings.semantic_trace_dir

        # Setup log files - organize by job if available
        if job_id:
            job_log_dir = self.log_dir / job_id
            job_log_dir.mkdir(parents=True, exist_ok=True)
            stdout_log = job_log_dir / f"{agent.id}.stdout.log"
            stderr_log = job_log_dir / f"{agent.id}.stderr.log"
        else:
            stdout_log = self.log_dir / f"{agent.id}.stdout.log"
            stderr_log = self.log_dir / f"{agent.id}.stderr.log"

        stdout_file = open(stdout_log, "w")
        stderr_file = open(stderr_log, "w")

        # Start process
        try:
            process = subprocess.Popen(
                cmd,
                env=process_env,
                stdout=stdout_file,
                stderr=stderr_file,
                cwd=self.project_root,
            )

            # Give it a moment to start
            await asyncio.sleep(0.5)

            # Check if it crashed immediately
            if process.poll() is not None:
                stdout_file.close()
                stderr_file.close()
                with open(stderr_log) as f:
                    error = f.read()
                raise DeploymentError(f"Agent {agent.id} failed to start:\n{error}")

            return process

        except Exception as e:
            stdout_file.close()
            stderr_file.close()
            raise DeploymentError(f"Failed to start agent {agent.id}: {e}") from e

    async def stop(self, process: subprocess.Popen, agent_id: str) -> None:
        """Stop agent process.

        Args:
            process: Process handle
            agent_id: Agent identifier
        """
        try:
            process.terminate()
            try:
                await asyncio.wait_for(asyncio.to_thread(process.wait), timeout=10.0)
            except TimeoutError:
                process.kill()
                await asyncio.to_thread(process.wait)
        except Exception as e:
            logger.warning(f"Error stopping agent {agent_id}: {e}")

    async def get_status(self, process: subprocess.Popen) -> str:
        """Get process status.

        Args:
            process: Process handle

        Returns:
            Status string
        """
        if process.poll() is None:
            return "running"
        else:
            return "stopped"

    async def stop_by_pid(
        self, pid: int, agent_id: str, host: str | None = None
    ) -> None:
        """Stop agent by process ID.

        Args:
            pid: Process ID
            agent_id: Agent identifier
            host: Ignored for local runner
        """
        try:
            if sys.platform == "win32":
                # Windows: use taskkill
                result = subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid)],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0 and "not found" not in result.stderr.lower():
                    logger.warning(f"taskkill failed for {agent_id}: {result.stderr}")
            else:
                # Unix: use kill signals
                import signal as sig

                try:
                    os.kill(pid, sig.SIGTERM)
                    # Wait a bit for graceful shutdown
                    await asyncio.sleep(2)
                    # Check if still running and force kill
                    try:
                        os.kill(pid, 0)  # Check if process exists
                        os.kill(pid, sig.SIGKILL)
                    except ProcessLookupError:
                        pass  # Already dead
                except ProcessLookupError:
                    pass  # Process already gone
            logger.info(f"Stopped agent {agent_id} (PID {pid})")
        except Exception as e:
            logger.warning(f"Error stopping agent {agent_id} by PID {pid}: {e}")


# ============================================================================
# SSH Runner (remote deployment)
# ============================================================================


class RemoteProcess:
    """Reference to a remote process."""

    def __init__(
        self, ssh_client: paramiko.SSHClient, pid: int, agent_id: str, host: str
    ):
        self.ssh_client = ssh_client
        self.pid = pid
        self.agent_id = agent_id
        self.host = host

    def is_running(self) -> bool:
        """Check if remote process is still running."""
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(f"ps -p {self.pid}")
            output = stdout.read().decode()
            return str(self.pid) in output
        except Exception:
            return False


class SSHRunner(AgentRunner):
    """Run agents on remote hosts via SSH."""

    def __init__(self, project_root: Path | None = None):
        """Initialize SSH runner.

        Args:
            project_root: Project root directory (for transferring code)
        """
        self.project_root = project_root or Path.cwd()
        self.connections: dict[str, paramiko.SSHClient] = {}

    def _get_ssh_client(self, agent: AgentConfig) -> paramiko.SSHClient:
        """Get or create SSH connection for agent.

        Args:
            agent: Agent configuration

        Returns:
            SSH client
        """
        host = agent.deployment.host
        if not host:
            raise DeploymentError(
                "Remote deployment requires 'host' in deployment config"
            )

        # Parse SSH config file for host aliases
        ssh_config = paramiko.SSHConfig()
        ssh_config_path = os.path.expanduser("~/.ssh/config")
        if os.path.exists(ssh_config_path):
            with open(ssh_config_path) as f:
                ssh_config.parse(f)
            logger.debug(f"Loaded SSH config from {ssh_config_path}")

        # Look up host in SSH config
        host_config = ssh_config.lookup(host)
        actual_hostname = host_config.get("hostname", host)
        config_user = host_config.get("user")
        config_port = host_config.get("port")
        config_key = host_config.get("identityfile", [None])[0]

        # Reuse connection if exists
        connection_key = (
            f"{actual_hostname}:{agent.deployment.port or config_port or 22}"
        )
        if connection_key in self.connections:
            return self.connections[connection_key]

        # Create new connection with secure host key policy
        ssh = paramiko.SSHClient()

        # Load system known hosts for host key verification
        known_hosts_path = os.path.expanduser("~/.ssh/known_hosts")
        if os.path.exists(known_hosts_path):
            ssh.load_host_keys(known_hosts_path)
            logger.debug(f"Loaded known hosts from {known_hosts_path}")

        # SECURITY: Use RejectPolicy to prevent MITM attacks
        # AutoAddPolicy would accept any host key, enabling MITM attacks
        # If you need to add a new host, use: ssh-keyscan <host> >> ~/.ssh/known_hosts
        ssh.set_missing_host_key_policy(paramiko.RejectPolicy())

        # Get SSH configuration - agent config overrides SSH config
        user = agent.deployment.user or config_user or getpass.getuser()
        ssh_port = agent.deployment.port or (int(config_port) if config_port else 22)
        ssh_key = agent.deployment.ssh_key
        password = agent.deployment.password

        # Expand ~ in ssh_key path (agent config or SSH config)
        if ssh_key:
            ssh_key = os.path.expanduser(ssh_key)
        elif config_key:
            ssh_key = os.path.expanduser(config_key)
        else:
            # Try default key
            default_key = os.path.expanduser("~/.ssh/id_rsa")
            if os.path.exists(default_key):
                ssh_key = default_key

        try:
            logger.info(f"Connecting to {user}@{actual_hostname}:{ssh_port}...")

            connect_kwargs = {
                "hostname": actual_hostname,
                "port": ssh_port,
                "username": user,
                "timeout": 10,
            }

            if ssh_key and os.path.exists(ssh_key):
                connect_kwargs["key_filename"] = ssh_key
            elif password:
                # SecretStr requires .get_secret_value() to access the actual value
                connect_kwargs["password"] = password.get_secret_value()

            ssh.connect(**connect_kwargs)
            self.connections[connection_key] = ssh
            logger.info("SSH connected successfully")

            return ssh

        except Exception as e:
            raise DeploymentError(f"SSH connection failed to {user}@{host}: {e}") from e

    def _check_remote_prerequisites(
        self, ssh: paramiko.SSHClient, host: str
    ) -> tuple[bool, bool, str]:
        """Check if Python and uv are installed on remote host.

        Args:
            ssh: SSH client
            host: Host name for error messages

        Returns:
            Tuple of (python_ok, uv_ok, uv_path)

        Raises:
            DeploymentError: If prerequisites are missing
        """
        # Check for Python 3
        stdin, stdout, stderr = ssh.exec_command("which python3 || which python")
        python_path = stdout.read().decode().strip()
        python_ok = bool(python_path)

        if not python_ok:
            raise DeploymentError(
                f"Python not found on remote host '{host}'.\n"
                f"Please install Python 3.11+ on the remote host:\n"
                f"  ssh {host} 'sudo apt install python3'  # Debian/Ubuntu\n"
                f"  ssh {host} 'sudo dnf install python3'  # Fedora/RHEL"
            )

        # Check Python version
        stdin, stdout, stderr = ssh.exec_command(
            "python3 --version 2>&1 || python --version 2>&1"
        )
        version_output = stdout.read().decode().strip()
        logger.debug(f"Remote Python version: {version_output}")

        # Check for uv - use command -v which properly short-circuits
        # Fall back to checking common installation paths
        stdin, stdout, stderr = ssh.exec_command(
            "command -v uv 2>/dev/null || "
            "(test -x ~/.local/bin/uv && echo ~/.local/bin/uv) || "
            "(test -x ~/.cargo/bin/uv && echo ~/.cargo/bin/uv)"
        )
        # Take only first line in case multiple paths are returned
        uv_path = stdout.read().decode().strip().split("\n")[0]
        uv_ok = bool(uv_path)

        if not uv_ok:
            raise DeploymentError(
                f"uv not found on remote host '{host}'.\n"
                f"Please install uv on the remote host:\n"
                f"  ssh {host} 'curl -LsSf https://astral.sh/uv/install.sh | sh'\n"
                f"Or install via pip:\n"
                f"  ssh {host} 'pip install uv'"
            )

        logger.info(
            f"Remote prerequisites OK: Python at {python_path}, uv at {uv_path}"
        )
        return python_ok, uv_ok, uv_path

    async def _install_remote_dependencies(
        self, ssh: paramiko.SSHClient, workdir: str, uv_path: str, agent_id: str
    ) -> None:
        """Install dependencies on remote host using uv.

        Args:
            ssh: SSH client
            workdir: Remote working directory
            uv_path: Path to uv binary
            agent_id: Agent ID for logging
        """
        logger.info(f"Installing dependencies on remote for {agent_id}...")

        # Expand workdir if it starts with ~
        if workdir.startswith("~"):
            stdin, stdout, stderr = ssh.exec_command("echo $HOME")
            home = stdout.read().decode().strip()
            workdir = workdir.replace("~", home, 1)

        # Run uv sync in the workdir
        cmd = f"cd {shlex.quote(workdir)} && {shlex.quote(uv_path)} sync 2>&1"
        logger.debug(f"Running: {cmd}")

        stdin, stdout, stderr = ssh.exec_command(cmd)
        exit_status = stdout.channel.recv_exit_status()
        output = stdout.read().decode()

        if exit_status != 0:
            raise DeploymentError(
                f"Failed to install dependencies on remote for {agent_id}:\n{output}"
            )

        logger.info(f"Dependencies installed successfully for {agent_id}")
        logger.debug(f"uv sync output: {output[:500]}")

    async def start(
        self,
        agent: AgentConfig,
        connected_urls: list[str],
        env: dict[str, str],
        job_id: str | None = None,
    ) -> RemoteProcess:
        """Start agent on remote host via SSH.

        Args:
            agent: Agent configuration
            connected_urls: URLs of connected agents
            env: Environment variables
            job_id: Job identifier for log organization (unused for SSH)

        Returns:
            Remote process reference
        """
        ssh = self._get_ssh_client(agent)
        host = agent.deployment.host or "unknown"

        # Check prerequisites on remote (skip for localhost SSH)
        uv_path = "uv"
        if host != "localhost":
            _, _, uv_path = self._check_remote_prerequisites(ssh, host)

        # Build environment variables
        env_vars = env.copy()
        for key, value in agent.config.items():
            env_vars[f"AGENT_{key.upper()}"] = str(value)

        if connected_urls:
            env_vars["CONNECTED_AGENTS"] = ",".join(connected_urls)

        if agent.deployment.environment:
            env_vars.update(agent.deployment.environment)

        # SECURITY: Use shlex.quote to prevent shell injection attacks
        # Double-quoting is NOT sufficient - malicious values like: value"; rm -rf / #
        # would escape the quotes. shlex.quote properly escapes for POSIX shells.
        def safe_env_value(value: str) -> str:
            """Safely escape environment variable value for shell."""
            return shlex.quote(str(value))

        env_str = " ".join([f"{k}={safe_env_value(v)}" for k, v in env_vars.items()])

        # Get remote configuration
        # Special case: if deploying to localhost, use project directory with uv
        if host == "localhost":
            import shutil

            workdir = os.getcwd()  # Use current project directory
            # Find uv in PATH
            local_uv_path = shutil.which("uv") or os.path.expanduser("~/.local/bin/uv")
            python = f"{shlex.quote(local_uv_path)} run python"  # Use uv with full path, quoted
        else:
            workdir = agent.deployment.workdir or f"~/agents/{agent.id}"
            # Use uv run python for proper virtualenv handling
            python = f"{shlex.quote(uv_path)} run python"

            # Expand ~ to absolute path on remote host (required for shlex.quote to work)
            if workdir.startswith("~"):
                stdin, stdout, stderr = ssh.exec_command("echo $HOME")
                home = stdout.read().decode().strip()
                workdir = workdir.replace("~", home, 1)
                logger.debug(f"Expanded workdir to absolute path: {workdir}")

        # Ensure working directory exists (except for localhost project dir)
        if host != "localhost":
            stdin, stdout, stderr = ssh.exec_command(f"mkdir -p {shlex.quote(workdir)}")
            stdout.channel.recv_exit_status()  # Wait for command

            # Transfer agent code to remote host
            logger.info(f"Transferring code to {workdir}...")
            await self._transfer_code(ssh, agent, workdir)

            # Install dependencies using uv
            await self._install_remote_dependencies(ssh, workdir, uv_path, agent.id)
        else:
            logger.debug(f"Using project directory: {workdir}")

        # Build command to run agent
        # We'll use nohup to keep it running after SSH disconnect
        # SECURITY: Quote workdir to prevent shell injection via path names
        safe_workdir = shlex.quote(workdir)
        log_file = f"{safe_workdir}/{shlex.quote(agent.id)}.log"
        cmd = (
            f"cd {safe_workdir} && "
            f"nohup env {env_str} {python} -m {agent.module} "
            f"> {log_file} 2>&1 & "
            f"echo $!"
        )

        logger.info("Starting remote process...")
        logger.debug(f"Command: {cmd[:100]}...")
        stdin, stdout, stderr = ssh.exec_command(cmd)

        # Get PID
        pid_str = stdout.read().decode().strip()
        try:
            pid = int(pid_str)
        except ValueError:
            error = stderr.read().decode()
            raise DeploymentError(f"Failed to start remote agent: {error}") from None

        logger.info(f"Remote process started (PID: {pid})")

        # Give it a moment to start
        await asyncio.sleep(1.0)

        # Check if still running
        stdin, stdout, stderr = ssh.exec_command(f"ps -p {pid}")
        ps_output = stdout.read().decode()
        if str(pid) not in ps_output:
            # Process died, get logs
            stdin, stdout, stderr = ssh.exec_command(f"cat {log_file} 2>&1")
            log_output = stdout.read().decode()
            if not log_output:
                log_output = "(no log output - check if log file was created)"
            raise DeploymentError(
                f"Remote agent {agent.id} failed to start:\n{log_output}"
            )

        host = agent.deployment.host
        if host is None:
            raise DeploymentError(f"No host specified for remote agent {agent.id}")
        return RemoteProcess(ssh, pid, agent.id, host)

    async def _transfer_code(
        self, ssh: paramiko.SSHClient, agent: AgentConfig, remote_dir: str
    ) -> None:
        """Transfer agent code to remote host via SFTP.

        Syncs the following directories:
        - src/ (core modules)
        - tools/ (MCP tools)
        - agents/ (agent implementations)
        - pyproject.toml (for dependency installation)

        Args:
            ssh: SSH client
            agent: Agent configuration
            remote_dir: Remote directory
        """
        # Expand ~ to actual home directory (SFTP doesn't expand ~)
        if remote_dir.startswith("~"):
            stdin, stdout, stderr = ssh.exec_command("echo $HOME")
            home = stdout.read().decode().strip()
            remote_dir = remote_dir.replace("~", home, 1)
            logger.debug(f"Expanded remote dir: {remote_dir}")

        sftp = ssh.open_sftp()

        try:
            # Directories to sync
            dirs_to_sync = ["src", "examples"]

            for dir_name in dirs_to_sync:
                local_dir = self.project_root / dir_name
                if local_dir.exists():
                    remote_path = f"{remote_dir}/{dir_name}"
                    await self._sync_directory(sftp, local_dir, remote_path)
                    logger.debug(f"Synced {dir_name}/ to {remote_path}")

            # Copy pyproject.toml and uv.lock for dependency installation
            pyproject_path = self.project_root / "pyproject.toml"
            if pyproject_path.exists():
                sftp.put(str(pyproject_path), f"{remote_dir}/pyproject.toml")
                logger.debug("Synced pyproject.toml")

            # Also sync uv.lock if it exists (ensures reproducible installs)
            uv_lock_path = self.project_root / "uv.lock"
            if uv_lock_path.exists():
                sftp.put(str(uv_lock_path), f"{remote_dir}/uv.lock")
                logger.debug("Synced uv.lock")

            logger.info(f"Code transferred to {remote_dir}")

        finally:
            sftp.close()

    def _sftp_mkdir_p(self, sftp: paramiko.SFTPClient, remote_path: str) -> None:
        """Create remote directory and all parent directories.

        Args:
            sftp: SFTP client
            remote_path: Remote directory path to create
        """
        # Normalize path and split into components
        path = remote_path.replace("\\", "/")
        parts = path.split("/")

        # Handle absolute paths (starting with /)
        if path.startswith("/"):
            current = ""
        else:
            current = ""

        for part in parts:
            if not part:
                continue
            if part == "~":
                current = "~"
                continue
            if current == "" and path.startswith("/"):
                current = f"/{part}"
            elif current:
                current = f"{current}/{part}"
            else:
                current = part
            try:
                sftp.mkdir(current)
            except OSError:
                pass  # Directory exists

    async def _sync_directory(
        self, sftp: paramiko.SFTPClient, local_dir: Path, remote_dir: str
    ) -> None:
        """Recursively sync a directory via SFTP.

        Args:
            sftp: SFTP client
            local_dir: Local directory path
            remote_dir: Remote directory path
        """
        # Create remote directory tree
        self._sftp_mkdir_p(sftp, remote_dir)

        for item in local_dir.iterdir():
            remote_path = f"{remote_dir}/{item.name}"

            # Skip __pycache__ (but NOT __init__.py) and hidden files
            if item.name == "__pycache__" or item.name.startswith("."):
                continue

            if item.is_file():
                # Only sync Python files and config files
                if item.suffix in (".py", ".toml", ".yaml", ".yml", ".json"):
                    sftp.put(str(item), remote_path)
            elif item.is_dir():
                await self._sync_directory(sftp, item, remote_path)

    async def stop(self, process: RemoteProcess, agent_id: str) -> None:
        """Stop remote agent process.

        Args:
            process: Remote process reference
            agent_id: Agent identifier
        """
        try:
            # Send SIGTERM
            stdin, stdout, stderr = process.ssh_client.exec_command(
                f"kill {process.pid}"
            )
            stdout.channel.recv_exit_status()

            # Wait for graceful shutdown
            await asyncio.sleep(2)

            # Check if still running
            if process.is_running():
                # Force kill
                stdin, stdout, stderr = process.ssh_client.exec_command(
                    f"kill -9 {process.pid}"
                )
                stdout.channel.recv_exit_status()

        except Exception as e:
            logger.warning(f"Error stopping remote agent {agent_id}: {e}")

    async def get_status(self, process: RemoteProcess) -> str:
        """Get remote process status.

        Args:
            process: Remote process reference

        Returns:
            Status string
        """
        if process.is_running():
            return "running"
        else:
            return "stopped"

    async def stop_by_pid(
        self, pid: int, agent_id: str, host: str | None = None
    ) -> None:
        """Stop remote agent by process ID.

        Args:
            pid: Process ID
            agent_id: Agent identifier
            host: SSH host (required for remote stop)
        """
        if not host:
            logger.warning(
                f"Cannot stop remote agent {agent_id} - no host info available"
            )
            return

        try:
            # Get existing connection if available, or create minimal one
            connection_key = f"{host}:22"
            if connection_key in self.connections:
                ssh = self.connections[connection_key]
            else:
                # Create minimal connection for cleanup
                ssh = paramiko.SSHClient()
                ssh.load_system_host_keys()
                ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
                ssh.connect(host, username=getpass.getuser())
                self.connections[connection_key] = ssh

            # Send SIGTERM
            stdin, stdout, stderr = ssh.exec_command(f"kill {pid}")
            stdout.channel.recv_exit_status()

            # Wait for graceful shutdown
            await asyncio.sleep(2)

            # Check if still running and force kill
            stdin, stdout, stderr = ssh.exec_command(f"kill -0 {pid} 2>/dev/null")
            if stdout.channel.recv_exit_status() == 0:
                # Still running, force kill
                stdin, stdout, stderr = ssh.exec_command(f"kill -9 {pid}")
                stdout.channel.recv_exit_status()

            logger.info(f"Stopped remote agent {agent_id} (PID {pid}) on {host}")
        except Exception as e:
            logger.warning(f"Error stopping remote agent {agent_id} by PID: {e}")

    def close_all(self):
        """Close all SSH connections."""
        for ssh in self.connections.values():
            try:
                ssh.close()
            except Exception:
                pass
        self.connections.clear()


# ============================================================================
# Agent Deployer
# ============================================================================


class AgentDeployer:
    """Deploy agents according to deployment plan."""

    def __init__(self, project_root: Path | None = None):
        """Initialize deployer.

        Args:
            project_root: Project root directory
        """
        self.project_root = project_root or Path.cwd()
        self.runners: dict[str, AgentRunner] = {
            "localhost": LocalRunner(self.project_root),
            "remote": SSHRunner(self.project_root),
            # TODO: Add DockerRunner, KubernetesRunner
        }

    async def deploy(self, job: JobDefinition, plan: DeploymentPlan) -> DeployedJob:
        """Execute deployment plan.

        Args:
            job: Job definition
            plan: Deployment plan

        Returns:
            Deployed job with running agents

        Raises:
            DeploymentError: If deployment fails
        """
        # Generate unique run ID with timestamp for log separation
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        run_id = f"{job.job.name}-{timestamp}"

        # Generate job-level trace_id for live cross-agent tracing
        # All agents will write to the same trace file using this ID
        import uuid

        job_trace_id = str(uuid.uuid4())

        # Get semantic tracer and start job deployment trace with job-level trace_id
        tracer = get_semantic_tracer()
        tracer.start_trace(f"deploy-{job.job.name}", parent_trace_id=None)
        # Override with job trace_id for consistency
        tracer._trace_id = job_trace_id
        if tracer.exporter:
            tracer.exporter.start_trace(job_trace_id, f"job-{job.job.name}")

        agent_ids = [a.id for a in job.agents]
        topology_type = job.topology.type if job.topology else None

        logger.info(f"Deploying job: {job.job.name} (run: {run_id})")
        logger.info(f"Job trace ID: {job_trace_id}")
        logger.info(f"Deployment strategy: {job.deployment.strategy}")
        logger.info(f"Stages: {len(plan.stages)}")

        deployed_agents: dict[str, DeployedAgent] = {}
        processes: dict[str, Any] = {}

        # Wrap entire deployment in semantic trace
        with tracer.job_deployment(
            job_id=run_id,
            job_name=job.job.name,
            agents=agent_ids,
            topology=topology_type,
        ) as job_span:
            try:
                # Build global environment
                global_env = dict(job.environment) if job.environment else {}

                # Pass job trace_id to all agents for live cross-agent tracing
                # All agents will write to the same NDJSON trace file
                global_env["AGENT_JOB_TRACE_ID"] = job_trace_id

                # Auto-configure AGENT_ALLOWED_HOSTS for cross-node communication
                # Extract all unique hosts from agent URLs to enable A2A communication
                allowed_hosts = self._build_allowed_hosts(plan)
                if allowed_hosts:
                    existing = global_env.get("AGENT_ALLOWED_HOSTS", "")
                    if existing:
                        # Merge with any user-provided hosts
                        all_hosts = set(existing.split(",")) | allowed_hosts
                    else:
                        all_hosts = allowed_hosts
                    global_env["AGENT_ALLOWED_HOSTS"] = ",".join(sorted(all_hosts))
                    logger.info(
                        f"Cross-node allowed hosts: {global_env['AGENT_ALLOWED_HOSTS']}"
                    )

                # Deploy stage by stage
                for stage_idx, stage in enumerate(plan.stages):
                    if not stage:
                        continue

                    logger.info(f"Stage {stage_idx + 1}/{len(plan.stages)}: {stage}")
                    tracer.add_event(
                        job_span,
                        "stage_started",
                        {"stage_index": stage_idx + 1, "agents": stage},
                    )

                    # Deploy all agents in this stage (in parallel if strategy allows)
                    if job.deployment.strategy == "parallel" or (
                        job.deployment.strategy == "staged"
                    ):
                        # Parallel deployment within stage
                        tasks = []
                        for agent_id in stage:
                            task = self._deploy_agent(
                                job, agent_id, plan, global_env, run_id, tracer
                            )
                            tasks.append((agent_id, task))

                        # Wait for all in parallel
                        for agent_id, task in tasks:
                            try:
                                agent, process = await task
                                deployed_agents[agent_id] = agent
                                processes[agent_id] = process
                            except Exception as e:
                                raise DeploymentError(
                                    f"Failed to deploy agent {agent_id}: {e}"
                                ) from e

                    else:
                        # Sequential deployment
                        for agent_id in stage:
                            try:
                                agent, process = await self._deploy_agent(
                                    job, agent_id, plan, global_env, run_id, tracer
                                )
                                deployed_agents[agent_id] = agent
                                processes[agent_id] = process
                            except Exception as e:
                                raise DeploymentError(
                                    f"Failed to deploy agent {agent_id}: {e}"
                                ) from e

                    tracer.add_event(
                        job_span,
                        "stage_completed",
                        {"stage_index": stage_idx + 1, "deployed_count": len(stage)},
                    )

                logger.info(f"Deployed {len(deployed_agents)} agents successfully")

                return DeployedJob(
                    job_id=run_id,
                    definition=job,
                    plan=plan,
                    agents=deployed_agents,
                    start_time=datetime.now().isoformat(),
                    status="running",
                )

            except Exception as e:
                # Cleanup on failure
                logger.error(f"Deployment failed: {e}")
                logger.info("Cleaning up deployed agents...")
                await self._cleanup_agents(job, processes)
                raise

    def _build_allowed_hosts(self, plan: DeploymentPlan) -> set[str]:
        """Extract unique hosts from agent URLs for SSRF allowlist.

        This enables cross-node A2A communication by automatically adding
        all agent hosts to the AGENT_ALLOWED_HOSTS environment variable.

        Args:
            plan: Deployment plan with agent URLs

        Returns:
            Set of unique hostnames/IPs from agent URLs
        """
        from urllib.parse import urlparse

        allowed = {"localhost", "127.0.0.1"}  # Always include localhost

        for url in plan.agent_urls.values():
            try:
                parsed = urlparse(url)
                if parsed.hostname:
                    allowed.add(parsed.hostname)
            except Exception:
                pass

        return allowed

    async def _deploy_agent(
        self,
        job: JobDefinition,
        agent_id: str,
        plan: DeploymentPlan,
        global_env: dict[str, str],
        run_id: str,
        tracer: Any = None,
    ) -> tuple[DeployedAgent, Any]:
        """Deploy a single agent.

        Args:
            job: Job definition
            agent_id: Agent identifier
            plan: Deployment plan
            global_env: Global environment variables
            run_id: Unique run identifier for log organization
            tracer: Semantic tracer for observability

        Returns:
            Tuple of (DeployedAgent, process handle)
        """
        agent_config = job.get_agent(agent_id)
        if not agent_config:
            raise DeploymentError(f"Agent {agent_id} not found in job definition")

        # Use provided tracer or get global one
        if tracer is None:
            tracer = get_semantic_tracer()

        logger.info(f"Deploying {agent_id}...")

        # Get runner for deployment target
        runner = self.runners.get(agent_config.deployment.target)
        if not runner:
            raise DeploymentError(
                f"No runner available for target: {agent_config.deployment.target}"
            )

        # Get connected agent URLs
        connected_urls = plan.connections.get(agent_id, [])

        # Add job context to environment for logging correlation
        agent_env = dict(global_env)
        agent_env["JOB_ID"] = run_id
        agent_env["AGENT_ID"] = agent_id

        # Get agent URL and port
        agent_url = plan.agent_urls.get(agent_id, "")
        port = agent_config.config.get("port")

        # Wrap agent startup in lifecycle trace
        with tracer.agent_lifecycle(
            agent_id=agent_id,
            agent_name=agent_config.config.get("name", agent_id),
            action="start",
            port=port,
            host=agent_config.deployment.host or "localhost",
        ) as agent_span:
            # Start agent with run_id for log organization
            process = await runner.start(
                agent_config, connected_urls, agent_env, job_id=run_id
            )

            tracer.add_event(
                agent_span,
                "process_started",
                {
                    "pid": getattr(process, "pid", None),
                    "target": agent_config.deployment.target,
                },
            )

            # Wait for health check
            await self._wait_for_health(
                agent_url,
                agent_id,
                timeout=job.deployment.timeout,
                retries=job.deployment.health_check.retries,
                tracer=tracer,
                agent_span=agent_span,
            )

            tracer.add_event(agent_span, "health_check_passed", {"url": agent_url})

        logger.info(f"Agent {agent_id} deployed at {agent_url}")

        # Get host for SSH deployments
        host = None
        if agent_config.deployment.target == "remote" and agent_config.deployment.host:
            host = agent_config.deployment.host

        # Create deployed agent record
        deployed_agent = DeployedAgent(
            agent_id=agent_id,
            url=agent_url,
            process_id=getattr(process, "pid", None),
            host=host,
            status="healthy",
        )

        return deployed_agent, process

    async def _wait_for_health(
        self,
        url: str,
        agent_id: str,
        timeout: int,
        retries: int,
        tracer: Any = None,
        agent_span: Any = None,
    ) -> None:
        """Wait for agent to become healthy.

        Args:
            url: Agent URL
            agent_id: Agent identifier
            timeout: Total timeout in seconds
            retries: Number of retries
            tracer: Semantic tracer for observability
            agent_span: Parent span to add events to

        Raises:
            DeploymentError: If agent doesn't become healthy
        """
        if not url:
            return

        health_url = f"{url}/.well-known/agent-configuration"
        interval = timeout / max(retries, 1)

        async with httpx.AsyncClient() as client:
            for attempt in range(retries):
                try:
                    response = await client.get(
                        health_url, timeout=5.0, follow_redirects=True
                    )

                    if response.status_code == 200:
                        return  # Healthy!

                    # Add event for non-200 response
                    if tracer and agent_span:
                        tracer.add_event(
                            agent_span,
                            "health_check_attempt",
                            {
                                "attempt": attempt + 1,
                                "status_code": response.status_code,
                                "success": False,
                            },
                        )

                except Exception as e:
                    # Add event for failed attempt
                    if tracer and agent_span:
                        tracer.add_event(
                            agent_span,
                            "health_check_attempt",
                            {
                                "attempt": attempt + 1,
                                "error": str(e)[:100],
                                "success": False,
                            },
                        )

                if attempt < retries - 1:
                    await asyncio.sleep(interval)

        raise DeploymentError(f"Agent {agent_id} failed to become healthy at {url}")

    async def stop(self, deployed_job: DeployedJob) -> None:
        """Stop all agents in a deployed job.

        Args:
            deployed_job: Deployed job to stop
        """
        logger.info(f"Stopping job: {deployed_job.job_id}")

        # Stop in reverse order
        stages = list(reversed(deployed_job.plan.stages))

        for stage_idx, stage in enumerate(stages):
            logger.info(f"Stage {stage_idx + 1}/{len(stages)}: Stopping {stage}")

            for agent_id in stage:
                if agent_id in deployed_job.agents:
                    agent = deployed_job.agents[agent_id]
                    logger.info(f"Stopping {agent_id}...")

                    # Get agent config to determine runner
                    agent_config = deployed_job.definition.get_agent(agent_id)
                    if agent_config and agent.process_id:
                        runner = self.runners.get(agent_config.deployment.target)
                        if runner:
                            # Stop by PID since we don't have process handles
                            if hasattr(runner, "stop_by_pid"):
                                # For SSH runner, pass host info
                                if agent.host:
                                    await runner.stop_by_pid(
                                        agent.process_id, agent_id, host=agent.host
                                    )
                                else:
                                    await runner.stop_by_pid(agent.process_id, agent_id)
                            else:
                                logger.warning(
                                    f"Runner {type(runner).__name__} doesn't support stop_by_pid"
                                )

        logger.info("Job stopped successfully")

    async def _cleanup_agents(
        self, job: JobDefinition, processes: dict[str, Any]
    ) -> None:
        """Cleanup agents after deployment failure.

        Args:
            job: Job definition
            processes: Process handles
        """
        for agent_id, process in processes.items():
            agent_config = job.get_agent(agent_id)
            if agent_config:
                runner = self.runners.get(agent_config.deployment.target)
                if runner:
                    try:
                        await runner.stop(process, agent_id)
                    except Exception as e:
                        logger.warning(f"Failed to stop {agent_id}: {e}")
