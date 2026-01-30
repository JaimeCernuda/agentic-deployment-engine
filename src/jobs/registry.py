"""Job Registry for persistent job state tracking.

Provides persistent storage and retrieval of deployed job state,
enabling status/stop/logs CLI commands to work across sessions.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class AgentState(BaseModel):
    """Persistent state for a deployed agent."""

    agent_id: str
    url: str
    process_id: int | None = None
    host: str = "localhost"
    status: str = "unknown"
    log_file: str | None = None


class JobState(BaseModel):
    """Persistent state for a deployed job."""

    job_id: str
    job_file: str
    status: str  # pending, running, stopped, failed
    start_time: str
    stop_time: str | None = None
    agents: dict[str, AgentState] = {}
    topology_type: str | None = None
    entry_point: str | None = None  # Default agent for queries
    error: str | None = None


class JobRegistry:
    """Persistent registry for deployed jobs.

    Stores job state in a JSON file for persistence across
    CLI invocations and system restarts.
    """

    def __init__(self, state_dir: Path | None = None):
        """Initialize job registry.

        Args:
            state_dir: Directory for state files. Defaults to ~/.agentic-deployment/
        """
        self.state_dir = state_dir or Path.home() / ".agentic-deployment"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.jobs_file = self.state_dir / "jobs.json"
        self._jobs: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        """Load jobs from persistent storage."""
        if self.jobs_file.exists():
            try:
                data = json.loads(self.jobs_file.read_text())
                self._jobs = data.get("jobs", {})
                logger.debug(f"Loaded {len(self._jobs)} jobs from registry")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to load jobs registry: {e}")
                self._jobs = {}
        else:
            self._jobs = {}

    def _save(self) -> None:
        """Save jobs to persistent storage."""
        data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "jobs": self._jobs,
        }
        self.jobs_file.write_text(json.dumps(data, indent=2, default=str))
        logger.debug(f"Saved {len(self._jobs)} jobs to registry")

    def save_job(self, job_state: JobState) -> None:
        """Save or update a job in the registry.

        Args:
            job_state: Job state to save.
        """
        self._jobs[job_state.job_id] = job_state.model_dump()
        self._save()
        logger.info(f"Saved job {job_state.job_id} to registry")

    def get_job(self, job_id: str) -> JobState | None:
        """Get a job by ID.

        Args:
            job_id: Job identifier.

        Returns:
            JobState if found, None otherwise.
        """
        if job_id in self._jobs:
            return JobState(**self._jobs[job_id])
        return None

    def list_jobs(self, status: str | None = None, limit: int = 50) -> list[JobState]:
        """List jobs, optionally filtered by status.

        Args:
            status: Optional status filter (running, stopped, failed).
            limit: Maximum number of jobs to return.

        Returns:
            List of JobState objects.
        """
        jobs = []
        for job_data in self._jobs.values():
            job = JobState(**job_data)
            if status is None or job.status == status:
                jobs.append(job)

        # Sort by start time descending
        jobs.sort(key=lambda j: j.start_time, reverse=True)
        return jobs[:limit]

    def update_status(self, job_id: str, status: str, error: str | None = None) -> bool:
        """Update job status.

        Args:
            job_id: Job identifier.
            status: New status.
            error: Optional error message.

        Returns:
            True if job was found and updated, False otherwise.
        """
        if job_id not in self._jobs:
            return False

        self._jobs[job_id]["status"] = status
        if status == "stopped":
            self._jobs[job_id]["stop_time"] = datetime.now().isoformat()
        if error:
            self._jobs[job_id]["error"] = error

        self._save()
        logger.info(f"Updated job {job_id} status to {status}")
        return True

    def update_agent_status(self, job_id: str, agent_id: str, status: str) -> bool:
        """Update agent status within a job.

        Args:
            job_id: Job identifier.
            agent_id: Agent identifier.
            status: New agent status.

        Returns:
            True if agent was found and updated, False otherwise.
        """
        if job_id not in self._jobs:
            return False

        agents = self._jobs[job_id].get("agents", {})
        if agent_id not in agents:
            return False

        agents[agent_id]["status"] = status
        self._save()
        return True

    def delete_job(self, job_id: str) -> bool:
        """Delete a job from the registry.

        Args:
            job_id: Job identifier.

        Returns:
            True if job was found and deleted, False otherwise.
        """
        if job_id not in self._jobs:
            return False

        del self._jobs[job_id]
        self._save()
        logger.info(f"Deleted job {job_id} from registry")
        return True

    def get_running_jobs(self) -> list[JobState]:
        """Get all running jobs.

        Returns:
            List of running JobState objects.
        """
        return self.list_jobs(status="running")

    def cleanup_stale_jobs(self, max_age_hours: int = 24) -> int:
        """Remove old stopped/failed jobs from registry.

        Args:
            max_age_hours: Maximum age in hours for non-running jobs.

        Returns:
            Number of jobs removed.
        """
        cutoff = datetime.now().timestamp() - (max_age_hours * 3600)
        removed = 0

        jobs_to_remove = []
        for job_id, job_data in self._jobs.items():
            if job_data.get("status") in ("stopped", "failed"):
                try:
                    start_time = datetime.fromisoformat(job_data["start_time"])
                    if start_time.timestamp() < cutoff:
                        jobs_to_remove.append(job_id)
                except (ValueError, KeyError):
                    pass

        for job_id in jobs_to_remove:
            del self._jobs[job_id]
            removed += 1

        if removed > 0:
            self._save()
            logger.info(f"Cleaned up {removed} stale jobs")

        return removed


# Global registry instance
_registry: JobRegistry | None = None


def get_registry() -> JobRegistry:
    """Get or create the global job registry.

    Returns:
        JobRegistry instance.
    """
    global _registry
    if _registry is None:
        _registry = JobRegistry()
    return _registry
