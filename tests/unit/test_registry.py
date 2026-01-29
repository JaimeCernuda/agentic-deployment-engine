"""Comprehensive tests for the job registry module (src/jobs/registry.py).

Tests all registry components:
- AgentState model
- JobState model
- JobRegistry class (persistence, CRUD operations)
- Global registry instance
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.jobs.registry import (
    AgentState,
    JobRegistry,
    JobState,
    get_registry,
)


# ============================================================================
# AgentState Model Tests
# ============================================================================


class TestAgentState:
    """Tests for AgentState model."""

    def test_minimal_agent_state(self) -> None:
        """AgentState with only required fields."""
        state = AgentState(agent_id="agent1", url="http://localhost:9001")

        assert state.agent_id == "agent1"
        assert state.url == "http://localhost:9001"
        assert state.process_id is None
        assert state.host == "localhost"
        assert state.status == "unknown"
        assert state.log_file is None

    def test_full_agent_state(self) -> None:
        """AgentState with all fields."""
        state = AgentState(
            agent_id="agent1",
            url="http://192.168.1.100:9001",
            process_id=12345,
            host="192.168.1.100",
            status="running",
            log_file="/var/log/agent1.log",
        )

        assert state.agent_id == "agent1"
        assert state.url == "http://192.168.1.100:9001"
        assert state.process_id == 12345
        assert state.host == "192.168.1.100"
        assert state.status == "running"
        assert state.log_file == "/var/log/agent1.log"

    def test_agent_state_model_dump(self) -> None:
        """AgentState should serialize correctly."""
        state = AgentState(
            agent_id="agent1",
            url="http://localhost:9001",
            process_id=123,
        )

        data = state.model_dump()

        assert data["agent_id"] == "agent1"
        assert data["url"] == "http://localhost:9001"
        assert data["process_id"] == 123


# ============================================================================
# JobState Model Tests
# ============================================================================


class TestJobState:
    """Tests for JobState model."""

    def test_minimal_job_state(self) -> None:
        """JobState with only required fields."""
        state = JobState(
            job_id="test-job",
            job_file="/path/to/job.yaml",
            status="running",
            start_time=datetime.now().isoformat(),
        )

        assert state.job_id == "test-job"
        assert state.job_file == "/path/to/job.yaml"
        assert state.status == "running"
        assert state.stop_time is None
        assert state.agents == {}
        assert state.topology_type is None
        assert state.error is None

    def test_full_job_state(self) -> None:
        """JobState with all fields."""
        start = datetime.now()
        stop = start + timedelta(hours=1)

        state = JobState(
            job_id="test-job",
            job_file="/path/to/job.yaml",
            status="stopped",
            start_time=start.isoformat(),
            stop_time=stop.isoformat(),
            agents={
                "agent1": AgentState(
                    agent_id="agent1", url="http://localhost:9001"
                ).model_dump()
            },
            topology_type="hub-spoke",
            error="Test error",
        )

        assert state.job_id == "test-job"
        assert state.status == "stopped"
        assert state.stop_time == stop.isoformat()
        assert "agent1" in state.agents
        assert state.topology_type == "hub-spoke"
        assert state.error == "Test error"

    def test_job_state_status_values(self) -> None:
        """JobState should accept various status values."""
        statuses = ["pending", "running", "stopped", "failed"]

        for status in statuses:
            state = JobState(
                job_id="test",
                job_file="test.yaml",
                status=status,
                start_time=datetime.now().isoformat(),
            )
            assert state.status == status


# ============================================================================
# JobRegistry Tests
# ============================================================================


class TestJobRegistry:
    """Tests for JobRegistry class."""

    @pytest.fixture
    def temp_registry(self, tmp_path: Path) -> JobRegistry:
        """Create a registry with temp directory."""
        return JobRegistry(state_dir=tmp_path)

    @pytest.fixture
    def sample_job_state(self) -> JobState:
        """Create a sample job state for testing."""
        return JobState(
            job_id="test-job",
            job_file="/path/to/job.yaml",
            status="running",
            start_time=datetime.now().isoformat(),
            topology_type="hub-spoke",
            agents={
                "agent1": AgentState(
                    agent_id="agent1",
                    url="http://localhost:9001",
                    process_id=12345,
                    status="running",
                ).model_dump()
            },
        )

    def test_initialization_creates_directory(self, tmp_path: Path) -> None:
        """Registry should create state directory on init."""
        state_dir = tmp_path / "new_dir"
        assert not state_dir.exists()

        JobRegistry(state_dir=state_dir)

        assert state_dir.exists()

    def test_initialization_loads_existing_jobs(self, tmp_path: Path) -> None:
        """Registry should load existing jobs from file."""
        # Create a jobs file
        jobs_file = tmp_path / "jobs.json"
        jobs_file.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "jobs": {
                        "existing-job": {
                            "job_id": "existing-job",
                            "job_file": "test.yaml",
                            "status": "stopped",
                            "start_time": datetime.now().isoformat(),
                            "agents": {},
                        }
                    },
                }
            )
        )

        registry = JobRegistry(state_dir=tmp_path)
        job = registry.get_job("existing-job")

        assert job is not None
        assert job.job_id == "existing-job"
        assert job.status == "stopped"

    def test_initialization_handles_corrupted_file(self, tmp_path: Path) -> None:
        """Registry should handle corrupted jobs file gracefully."""
        jobs_file = tmp_path / "jobs.json"
        jobs_file.write_text("invalid json content {{{")

        registry = JobRegistry(state_dir=tmp_path)

        # Should start with empty jobs
        assert registry.list_jobs() == []

    def test_save_job(
        self, temp_registry: JobRegistry, sample_job_state: JobState
    ) -> None:
        """save_job() should persist job state."""
        temp_registry.save_job(sample_job_state)

        # Verify in memory
        job = temp_registry.get_job("test-job")
        assert job is not None
        assert job.job_id == "test-job"

        # Verify on disk
        jobs_file = temp_registry.jobs_file
        assert jobs_file.exists()
        data = json.loads(jobs_file.read_text())
        assert "test-job" in data["jobs"]

    def test_save_job_updates_existing(
        self, temp_registry: JobRegistry, sample_job_state: JobState
    ) -> None:
        """save_job() should update existing job."""
        temp_registry.save_job(sample_job_state)

        # Update the job
        sample_job_state.status = "stopped"
        temp_registry.save_job(sample_job_state)

        job = temp_registry.get_job("test-job")
        assert job.status == "stopped"

    def test_get_job_returns_none_for_nonexistent(
        self, temp_registry: JobRegistry
    ) -> None:
        """get_job() should return None for nonexistent job."""
        job = temp_registry.get_job("nonexistent")

        assert job is None

    def test_get_job_returns_job_state(
        self, temp_registry: JobRegistry, sample_job_state: JobState
    ) -> None:
        """get_job() should return JobState for existing job."""
        temp_registry.save_job(sample_job_state)

        job = temp_registry.get_job("test-job")

        assert isinstance(job, JobState)
        assert job.job_id == "test-job"

    def test_list_jobs_empty(self, temp_registry: JobRegistry) -> None:
        """list_jobs() should return empty list when no jobs."""
        jobs = temp_registry.list_jobs()

        assert jobs == []

    def test_list_jobs_returns_all(self, temp_registry: JobRegistry) -> None:
        """list_jobs() should return all jobs."""
        for i in range(3):
            job = JobState(
                job_id=f"job-{i}",
                job_file=f"job-{i}.yaml",
                status="running",
                start_time=datetime.now().isoformat(),
            )
            temp_registry.save_job(job)

        jobs = temp_registry.list_jobs()

        assert len(jobs) == 3

    def test_list_jobs_filters_by_status(self, temp_registry: JobRegistry) -> None:
        """list_jobs() should filter by status."""
        # Create jobs with different statuses - use index for unique IDs
        statuses = ["running", "stopped", "running", "failed"]
        for i, status in enumerate(statuses):
            job = JobState(
                job_id=f"job-{i}-{status}",
                job_file="test.yaml",
                status=status,
                start_time=datetime.now().isoformat(),
            )
            temp_registry.save_job(job)

        running_jobs = temp_registry.list_jobs(status="running")
        stopped_jobs = temp_registry.list_jobs(status="stopped")

        assert len(running_jobs) == 2
        assert len(stopped_jobs) == 1

    def test_list_jobs_respects_limit(self, temp_registry: JobRegistry) -> None:
        """list_jobs() should respect limit parameter."""
        for i in range(10):
            job = JobState(
                job_id=f"job-{i}",
                job_file="test.yaml",
                status="running",
                start_time=datetime.now().isoformat(),
            )
            temp_registry.save_job(job)

        jobs = temp_registry.list_jobs(limit=5)

        assert len(jobs) == 5

    def test_list_jobs_sorted_by_start_time(self, temp_registry: JobRegistry) -> None:
        """list_jobs() should sort by start time descending."""
        times = [
            datetime(2024, 1, 1, 10, 0),
            datetime(2024, 1, 1, 12, 0),
            datetime(2024, 1, 1, 8, 0),
        ]

        for i, t in enumerate(times):
            job = JobState(
                job_id=f"job-{i}",
                job_file="test.yaml",
                status="running",
                start_time=t.isoformat(),
            )
            temp_registry.save_job(job)

        jobs = temp_registry.list_jobs()

        # Should be sorted newest first
        assert jobs[0].job_id == "job-1"  # 12:00
        assert jobs[1].job_id == "job-0"  # 10:00
        assert jobs[2].job_id == "job-2"  # 08:00

    def test_update_status(
        self, temp_registry: JobRegistry, sample_job_state: JobState
    ) -> None:
        """update_status() should update job status."""
        temp_registry.save_job(sample_job_state)

        result = temp_registry.update_status("test-job", "stopped")

        assert result is True
        job = temp_registry.get_job("test-job")
        assert job.status == "stopped"

    def test_update_status_sets_stop_time(
        self, temp_registry: JobRegistry, sample_job_state: JobState
    ) -> None:
        """update_status() should set stop_time when stopping."""
        temp_registry.save_job(sample_job_state)

        temp_registry.update_status("test-job", "stopped")

        job = temp_registry.get_job("test-job")
        assert job.stop_time is not None

    def test_update_status_sets_error(
        self, temp_registry: JobRegistry, sample_job_state: JobState
    ) -> None:
        """update_status() should set error message."""
        temp_registry.save_job(sample_job_state)

        temp_registry.update_status("test-job", "failed", error="Connection refused")

        job = temp_registry.get_job("test-job")
        assert job.error == "Connection refused"

    def test_update_status_returns_false_for_nonexistent(
        self, temp_registry: JobRegistry
    ) -> None:
        """update_status() should return False for nonexistent job."""
        result = temp_registry.update_status("nonexistent", "stopped")

        assert result is False

    def test_update_agent_status(
        self, temp_registry: JobRegistry, sample_job_state: JobState
    ) -> None:
        """update_agent_status() should update agent status."""
        temp_registry.save_job(sample_job_state)

        result = temp_registry.update_agent_status("test-job", "agent1", "stopped")

        assert result is True
        job = temp_registry.get_job("test-job")
        # agents can be dict or AgentState depending on pydantic validation
        agent = job.agents["agent1"]
        if isinstance(agent, dict):
            assert agent["status"] == "stopped"
        else:
            assert agent.status == "stopped"

    def test_update_agent_status_nonexistent_job(
        self, temp_registry: JobRegistry
    ) -> None:
        """update_agent_status() should return False for nonexistent job."""
        result = temp_registry.update_agent_status("nonexistent", "agent1", "stopped")

        assert result is False

    def test_update_agent_status_nonexistent_agent(
        self, temp_registry: JobRegistry, sample_job_state: JobState
    ) -> None:
        """update_agent_status() should return False for nonexistent agent."""
        temp_registry.save_job(sample_job_state)

        result = temp_registry.update_agent_status("test-job", "nonexistent", "stopped")

        assert result is False

    def test_delete_job(
        self, temp_registry: JobRegistry, sample_job_state: JobState
    ) -> None:
        """delete_job() should remove job from registry."""
        temp_registry.save_job(sample_job_state)

        result = temp_registry.delete_job("test-job")

        assert result is True
        assert temp_registry.get_job("test-job") is None

    def test_delete_job_nonexistent(self, temp_registry: JobRegistry) -> None:
        """delete_job() should return False for nonexistent job."""
        result = temp_registry.delete_job("nonexistent")

        assert result is False

    def test_get_running_jobs(self, temp_registry: JobRegistry) -> None:
        """get_running_jobs() should return only running jobs."""
        statuses = ["running", "stopped", "running", "failed"]
        for i, status in enumerate(statuses):
            job = JobState(
                job_id=f"job-{i}-{status}",
                job_file="test.yaml",
                status=status,
                start_time=datetime.now().isoformat(),
            )
            temp_registry.save_job(job)

        running = temp_registry.get_running_jobs()

        assert len(running) == 2
        for job in running:
            assert job.status == "running"

    def test_cleanup_stale_jobs(self, temp_registry: JobRegistry) -> None:
        """cleanup_stale_jobs() should remove old stopped/failed jobs."""
        # Old stopped job (should be removed)
        old_time = datetime.now() - timedelta(hours=48)
        old_job = JobState(
            job_id="old-job",
            job_file="test.yaml",
            status="stopped",
            start_time=old_time.isoformat(),
        )
        temp_registry.save_job(old_job)

        # Recent stopped job (should be kept)
        recent_job = JobState(
            job_id="recent-job",
            job_file="test.yaml",
            status="stopped",
            start_time=datetime.now().isoformat(),
        )
        temp_registry.save_job(recent_job)

        # Running job (should be kept regardless of age)
        running_job = JobState(
            job_id="running-job",
            job_file="test.yaml",
            status="running",
            start_time=old_time.isoformat(),
        )
        temp_registry.save_job(running_job)

        removed = temp_registry.cleanup_stale_jobs(max_age_hours=24)

        assert removed == 1
        assert temp_registry.get_job("old-job") is None
        assert temp_registry.get_job("recent-job") is not None
        assert temp_registry.get_job("running-job") is not None

    def test_cleanup_stale_jobs_none_to_remove(
        self, temp_registry: JobRegistry
    ) -> None:
        """cleanup_stale_jobs() should handle case with nothing to remove."""
        job = JobState(
            job_id="test",
            job_file="test.yaml",
            status="running",
            start_time=datetime.now().isoformat(),
        )
        temp_registry.save_job(job)

        removed = temp_registry.cleanup_stale_jobs()

        assert removed == 0

    def test_persistence_across_instances(self, tmp_path: Path) -> None:
        """Registry data should persist across instances."""
        # Create and save with first instance
        registry1 = JobRegistry(state_dir=tmp_path)
        job = JobState(
            job_id="persistent-job",
            job_file="test.yaml",
            status="running",
            start_time=datetime.now().isoformat(),
        )
        registry1.save_job(job)

        # Create new instance and verify data
        registry2 = JobRegistry(state_dir=tmp_path)
        loaded_job = registry2.get_job("persistent-job")

        assert loaded_job is not None
        assert loaded_job.job_id == "persistent-job"


# ============================================================================
# Global Registry Tests
# ============================================================================


class TestGetRegistry:
    """Tests for get_registry() function."""

    def test_get_registry_returns_singleton(self) -> None:
        """get_registry() should return same instance."""
        # Reset global registry
        import src.jobs.registry as registry_module

        registry_module._registry = None

        reg1 = get_registry()
        reg2 = get_registry()

        assert reg1 is reg2

    def test_get_registry_creates_instance(self) -> None:
        """get_registry() should create instance if None."""
        import src.jobs.registry as registry_module

        registry_module._registry = None

        registry = get_registry()

        assert registry is not None
        assert isinstance(registry, JobRegistry)
