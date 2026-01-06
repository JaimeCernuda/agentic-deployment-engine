"""
Base A2A Task Agent with full A2A Protocol task lifecycle support.

This is an extension of base_a2a_agent.py that implements:
- JSON-RPC 2.0 protocol
- Task lifecycle management (SUBMITTED → WORKING → COMPLETED/FAILED)
- Context management for multi-turn conversations
- Task refinement support via referenceTaskIds
- Artifact management

Original License: Based on base_a2a_agent.py
Extension: Implements A2A Protocol v1.0 task lifecycle specification
Reference: https://a2a-protocol.org/latest/topics/life-of-a-task/
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from enum import Enum
from datetime import datetime
from uuid import uuid4
from fastapi import FastAPI, Request as FastAPIRequest
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict
import uvicorn
from pathlib import Path


# JSON-RPC 2.0 Models
class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Dict[str, Any] = {}
    id: Optional[int | str] = None


class JSONRPCResponse(BaseModel):
    model_config = ConfigDict(
        # Exclude None values in JSON serialization per JSON-RPC 2.0 spec
        # (response must have EITHER result OR error, not both)
        json_schema_extra={},
        use_enum_values=True
    )
    jsonrpc: str = "2.0"
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[int | str] = None

    def model_dump(self, **kwargs):
        """Override model_dump to exclude None fields"""
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(**kwargs)

    def to_json_response(self) -> JSONResponse:
        """Convert to FastAPI JSONResponse with None fields excluded"""
        return JSONResponse(
            content=self.model_dump(exclude_none=True),
            media_type="application/json"
        )


class JSONRPCError(BaseModel):
    code: int
    message: str
    data: Optional[Any] = None


# A2A Task Models
class TaskState(str, Enum):
    """A2A Task States according to protocol specification"""
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input_required"
    AUTH_REQUIRED = "auth_required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class TaskStatus(BaseModel):
    state: TaskState
    message: Optional[str] = None
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class Artifact(BaseModel):
    """Task artifact - output of a completed task"""
    artifact_id: str = Field(default_factory=lambda: f"artifact-{uuid4().hex[:8]}")
    name: str
    content: str
    content_type: str = "text/plain"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class Task(BaseModel):
    """A2A Task object with full lifecycle support"""
    task_id: str
    context_id: str
    status: TaskStatus
    artifacts: List[Artifact] = []
    reference_task_ids: List[str] = []
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class Message(BaseModel):
    """A2A Message object"""
    message_id: str
    context_id: str
    role: str  # "user" or "assistant"
    content: str
    reference_task_ids: List[str] = []


# Task Store
class InMemoryTaskStore:
    """In-memory storage for tasks (does not persist across restarts)"""

    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.contexts: Dict[str, List[str]] = {}  # context_id -> [task_ids]
        self.logger = logging.getLogger(__name__)

    async def create_task(self, task: Task) -> Task:
        """Create a new task"""
        self.tasks[task.task_id] = task

        # Track task in context
        if task.context_id not in self.contexts:
            self.contexts[task.context_id] = []
        self.contexts[task.context_id].append(task.task_id)

        self.logger.debug(f"Created task {task.task_id} in context {task.context_id}")
        return task

    async def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        return self.tasks.get(task_id)

    async def update_task(self, task_id: str, status: TaskStatus) -> Optional[Task]:
        """Update task status"""
        if task_id in self.tasks:
            task = self.tasks[task_id]

            # Validate immutability: cannot update terminal states
            if task.status.state in [TaskState.COMPLETED, TaskState.FAILED,
                                     TaskState.CANCELLED, TaskState.REJECTED]:
                self.logger.warning(f"Cannot update terminal task {task_id}")
                return None

            task.status = status
            task.updated_at = datetime.utcnow().isoformat()
            self.logger.debug(f"Updated task {task_id} to state {status.state}")
            return task
        return None

    async def add_artifacts(self, task_id: str, artifacts: List[Artifact]) -> Optional[Task]:
        """Add artifacts to completed task"""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.artifacts.extend(artifacts)
            task.updated_at = datetime.utcnow().isoformat()
            return task
        return None

    async def get_context_tasks(self, context_id: str) -> List[Task]:
        """Get all tasks in a context"""
        task_ids = self.contexts.get(context_id, [])
        return [self.tasks[tid] for tid in task_ids if tid in self.tasks]


# Request Context
class RequestContext:
    """Provides information about the incoming request"""

    def __init__(
        self,
        task_id: str,
        context_id: str,
        message: Message,
        current_task: Optional[Task] = None
    ):
        self.task_id = task_id
        self.context_id = context_id
        self.message = message
        self.current_task = current_task

    def get_user_input(self) -> str:
        """Extract text from user's message"""
        return self.message.content


# Task Updater Helper
class TaskUpdater:
    """Helper class for managing task lifecycle"""

    def __init__(
        self,
        task_store: InMemoryTaskStore,
        task_id: str,
        context_id: str
    ):
        self.task_store = task_store
        self.task_id = task_id
        self.context_id = context_id
        self.logger = logging.getLogger(__name__)

    async def submit(self) -> Task:
        """Mark task as SUBMITTED"""
        task = Task(
            task_id=self.task_id,
            context_id=self.context_id,
            status=TaskStatus(state=TaskState.SUBMITTED)
        )
        return await self.task_store.create_task(task)

    async def start_work(self) -> Optional[Task]:
        """Mark task as WORKING"""
        status = TaskStatus(state=TaskState.WORKING)
        return await self.task_store.update_task(self.task_id, status)

    async def update_status(
        self,
        state: TaskState,
        message: Optional[str] = None
    ) -> Optional[Task]:
        """Update task status"""
        status = TaskStatus(state=state, message=message)
        return await self.task_store.update_task(self.task_id, status)

    async def complete(
        self,
        artifacts: List[Artifact],
        result_message: Optional[str] = None
    ) -> Optional[Task]:
        """Mark task as COMPLETED with artifacts"""
        # Update status to completed
        status = TaskStatus(
            state=TaskState.COMPLETED,
            message=result_message or "Task completed successfully"
        )
        task = await self.task_store.update_task(self.task_id, status)

        # Add artifacts
        if task:
            task = await self.task_store.add_artifacts(self.task_id, artifacts)

        return task

    async def fail(self, error_message: str) -> Optional[Task]:
        """Mark task as FAILED"""
        status = TaskStatus(state=TaskState.FAILED, message=error_message)
        return await self.task_store.update_task(self.task_id, status)

    async def cancel(self) -> Optional[Task]:
        """Mark task as CANCELLED"""
        status = TaskStatus(state=TaskState.CANCELLED, message="Task cancelled by user")
        return await self.task_store.update_task(self.task_id, status)


# Agent Executor Interface
class AgentExecutor(ABC):
    """
    Agent executor interface.
    Contains core logic for executing tasks and managing lifecycle.
    """

    @abstractmethod
    async def execute(
        self,
        context: RequestContext,
        task_updater: TaskUpdater
    ) -> Task:
        """
        Execute the agent's logic based on the request.
        Update task status using TaskUpdater.

        Args:
            context: Request context (message, task_id, context_id, etc.)
            task_updater: Helper for task lifecycle management

        Returns:
            Completed Task object
        """
        pass

    @abstractmethod
    async def cancel(
        self,
        context: RequestContext,
        task_updater: TaskUpdater
    ) -> Task:
        """
        Request the agent to cancel an ongoing task.

        Args:
            context: Request context with task ID to cancel
            task_updater: Helper for task lifecycle management

        Returns:
            Cancelled Task object
        """
        pass


# Base A2A Task Agent
class BaseA2ATaskAgent(ABC):
    """
    Base A2A Agent with full task lifecycle support.

    Extension of BaseA2AAgent implementing A2A Protocol v1.0:
    - JSON-RPC 2.0 protocol
    - Task states: SUBMITTED → WORKING → COMPLETED/FAILED
    - Context management for conversations
    - Task refinement support
    """

    def __init__(
        self,
        name: str,
        description: str,
        port: int,
        agent_executor: AgentExecutor,
        system_prompt: str = None
    ):
        self.name = name
        self.description = description
        self.port = port
        self.agent_executor = agent_executor
        self.system_prompt = system_prompt or self._get_default_system_prompt()

        # Task store
        self.task_store = InMemoryTaskStore()

        # Conversation history per context
        self.conversation_history: Dict[str, List[Message]] = {}

        # Setup logging
        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"{name.lower().replace(' ', '_')}_task.log"

        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()

        fh = logging.FileHandler(log_file, mode='a')
        fh.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
        )
        console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        fh.setFormatter(file_formatter)
        ch.setFormatter(console_formatter)

        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

        self.logger.info(f"Initializing {name} with A2A Task support on port {port}")
        self.logger.info(f"Log file: {log_file}")

        # Create FastAPI app with A2A endpoints
        self.app = FastAPI(title=name, description=description)
        self._setup_routes()

    def _setup_routes(self):
        """Setup A2A protocol endpoints"""

        @self.app.get("/.well-known/agent-configuration")
        async def agent_card():
            """A2A discovery endpoint"""
            return {
                "name": self.name,
                "description": self.description,
                "url": f"http://localhost:{self.port}",
                "version": "1.0.0",
                "capabilities": {
                    "streaming": False,
                    "push_notifications": False,
                },
                "default_input_modes": ["text"],
                "default_output_modes": ["text"],
                "skills": self._get_skills()
            }

        @self.app.get("/health")
        async def health():
            """Health check endpoint"""
            return {"status": "healthy", "agent": self.name}

        @self.app.post("/query")
        async def query_endpoint(request: FastAPIRequest):
            """
            Dual-format endpoint supporting both JSON-RPC 2.0 and basic A2A format.

            Supported formats:
            1. JSON-RPC 2.0: {"jsonrpc": "2.0", "method": "query", "params": {...}, "id": ...}
            2. Basic A2A: {"query": "..."}

            JSON-RPC methods:
            - query: Send a query (creates/updates task)
            - task/get: Get task status
            - task/cancel: Cancel a task
            """
            body = {}
            is_jsonrpc = False

            try:
                body = await request.json()

                # Detect format: JSON-RPC 2.0 or basic A2A
                is_jsonrpc = body.get("jsonrpc") == "2.0"

                if is_jsonrpc:
                    # JSON-RPC 2.0 format
                    self.logger.info(f"Received JSON-RPC 2.0 request: method={body.get('method')}, id={body.get('id')}")

                    rpc_request = JSONRPCRequest(**body)

                    if rpc_request.method == "query":
                        result = await self._handle_query(rpc_request.params)
                        return JSONRPCResponse(jsonrpc="2.0", result=result, id=rpc_request.id).to_json_response()

                    elif rpc_request.method == "task/get":
                        result = await self._handle_task_get(rpc_request.params)
                        return JSONRPCResponse(jsonrpc="2.0", result=result, id=rpc_request.id).to_json_response()

                    elif rpc_request.method == "task/cancel":
                        result = await self._handle_task_cancel(rpc_request.params)
                        return JSONRPCResponse(jsonrpc="2.0", result=result, id=rpc_request.id).to_json_response()

                    else:
                        error = JSONRPCError(
                            code=-32601,
                            message=f"Method not found: {rpc_request.method}"
                        )
                        return JSONRPCResponse(jsonrpc="2.0", error=error.model_dump(), id=rpc_request.id).to_json_response()

                else:
                    # Basic A2A format: {"query": "..."}
                    query = body.get("query", "")
                    self.logger.info(f"Received basic A2A request: query={query[:50]}...")

                    if not query:
                        return {
                            "error": "query parameter is required",
                            "response": None
                        }

                    # Convert to params format expected by _handle_query
                    params = {
                        "query": query,
                        "context_id": body.get("context_id", f"ctx-{uuid4().hex[:8]}"),
                        "task_id": body.get("task_id", f"task-{uuid4().hex[:8]}"),
                        "reference_task_ids": body.get("reference_task_ids", [])
                    }

                    result = await self._handle_query(params)

                    # Return basic A2A response format
                    return {
                        "response": result.get("response", "No response")
                    }

            except Exception as e:
                self.logger.error(f"Error processing request: {e}", exc_info=True)

                # Return error in appropriate format
                if is_jsonrpc:
                    error = JSONRPCError(
                        code=-32603,
                        message="Internal error",
                        data=str(e)
                    )
                    return JSONRPCResponse(jsonrpc="2.0", error=error.model_dump(), id=body.get("id")).to_json_response()
                else:
                    return {
                        "error": str(e),
                        "response": None
                    }

    async def _handle_query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle query request with task lifecycle"""
        query = params.get("query", "")
        context_id = params.get("context_id", f"ctx-{uuid4().hex[:8]}")
        task_id = params.get("task_id", f"task-{uuid4().hex[:8]}")
        reference_task_ids = params.get("reference_task_ids", [])

        self.logger.info(f"Handling query in context {context_id}, task {task_id}")

        # Create message
        message = Message(
            message_id=f"msg-{uuid4().hex[:8]}",
            context_id=context_id,
            role="user",
            content=query,
            reference_task_ids=reference_task_ids
        )

        # Add to conversation history
        if context_id not in self.conversation_history:
            self.conversation_history[context_id] = []
        self.conversation_history[context_id].append(message)

        # Create request context
        current_task = await self.task_store.get_task(task_id)
        context = RequestContext(
            task_id=task_id,
            context_id=context_id,
            message=message,
            current_task=current_task
        )

        # Create task updater
        task_updater = TaskUpdater(self.task_store, task_id, context_id)

        # Execute agent
        task = await self.agent_executor.execute(context, task_updater)

        # Add assistant message to history
        assistant_message = Message(
            message_id=f"msg-{uuid4().hex[:8]}",
            context_id=context_id,
            role="assistant",
            content=task.artifacts[0].content if task.artifacts else "No response"
        )
        self.conversation_history[context_id].append(assistant_message)

        return {
            "task": task.model_dump(),
            "response": task.artifacts[0].content if task.artifacts else "No response"
        }

    async def _handle_task_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get task status"""
        task_id = params.get("task_id")

        if not task_id:
            raise ValueError("task_id is required")

        task = await self.task_store.get_task(task_id)

        if not task:
            raise ValueError(f"Task not found: {task_id}")

        return {"task": task.model_dump()}

    async def _handle_task_cancel(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Cancel a task"""
        task_id = params.get("task_id")
        context_id = params.get("context_id", "")

        if not task_id:
            raise ValueError("task_id is required")

        # Create context for cancellation
        message = Message(
            message_id=f"msg-{uuid4().hex[:8]}",
            context_id=context_id,
            role="user",
            content="[CANCEL]"
        )

        context = RequestContext(
            task_id=task_id,
            context_id=context_id,
            message=message
        )

        task_updater = TaskUpdater(self.task_store, task_id, context_id)

        # Execute cancellation
        task = await self.agent_executor.cancel(context, task_updater)

        return {"task": task.model_dump()}

    @abstractmethod
    def _get_skills(self) -> List[Dict[str, Any]]:
        """Define agent skills for A2A discovery"""
        pass

    def _get_default_system_prompt(self) -> str:
        """Get default system prompt for this agent"""
        return f"""You are {self.name}, {self.description}.

You have access to specialized tools for your domain. Use them to provide accurate and helpful responses.
Always be concise and professional in your responses."""

    def run(self):
        """Run the A2A agent"""
        self.logger.info(f"Starting {self.name} on port {self.port}")
        uvicorn.run(self.app, host="0.0.0.0", port=self.port)

    async def cleanup(self):
        """Cleanup resources"""
        self.logger.info("Cleaning up agent resources")
