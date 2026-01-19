# Context Management in A2A Protocol

## Overview

This document describes how **Context Management** works in the A2A (Agent-to-Agent) Protocol, following the [official A2A Python SDK](https://github.com/a2aproject/a2a-python) and the [A2A Protocol Specification](https://a2a-protocol.org/latest/specification/).

Context Management is essential for:
- **Multi-turn conversations**: Maintaining conversation continuity across multiple interactions
- **Task grouping**: Logically grouping related tasks within the same conversation
- **Message history**: Preserving and accessing previous messages in a conversation
- **State management**: Tracking conversation state across agent interactions

---

## Core Concepts

### What is a Context?

A **Context** (`context_id`) is an identifier that logically groups multiple related `Task` and `Message` objects, providing continuity across a series of interactions.

> *"All tasks and messages with the same `context_id` SHOULD be treated as part of the same conversational session."* — A2A Specification

### Context ID Generation Rules

Per the A2A specification:

1. **Server-generated**: Agents must create new identifiers when processing messages lacking one
2. **Client-preserved**: Client-provided values are preserved if validation succeeds
3. **Opaque identifiers**: Values function as opaque identifiers for client implementations

```
┌─────────────────────────────────────────────────────────────────┐
│                    Context Lifecycle                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Client Request (no context_id)                                 │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────────┐                                          │
│  │ Server generates │──► context_id = "ctx-abc123"             │
│  │ new context_id   │                                          │
│  └──────────────────┘                                          │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────────┐     ┌──────────────────┐                 │
│  │    Task 1        │────►│    Task 2        │──► ...          │
│  │ context_id=abc123│     │ context_id=abc123│                 │
│  └──────────────────┘     └──────────────────┘                 │
│                                                                 │
│  All tasks share the same context = Same conversation          │
└─────────────────────────────────────────────────────────────────┘
```

---

## A2A SDK Components for Context Management

### 1. Task Model

The `Task` class from `a2a.types` includes context information:

```python
from a2a.types import Task, TaskStatus, TaskState

# Task model fields:
# - id: str                    # Unique task identifier (accessed via task.task_id)
# - context_id: str            # Context this task belongs to
# - status: TaskStatus         # Current task status
# - history: List[Message]     # Message history in this task
# - artifacts: List[Artifact]  # Task output artifacts
# - metadata: Dict[str, Any]   # Additional metadata
```

### 2. TaskState Lifecycle

Tasks transition through these states:

```python
from a2a.types import TaskState

# Available states:
TaskState.submitted      # Initial state when task is created
TaskState.working        # Agent is processing the task
TaskState.input_required # Agent needs more input from user
TaskState.completed      # Task completed successfully
TaskState.canceled       # Task was canceled
TaskState.failed         # Task failed with error
TaskState.rejected       # Task was rejected by agent
TaskState.auth_required  # Authentication required
TaskState.unknown        # Unknown state
```

**State Transition Diagram:**

```
                    ┌─────────────┐
                    │  SUBMITTED  │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
              ┌────►│   WORKING   │◄────┐
              │     └──────┬──────┘     │
              │            │            │
              │     ┌──────┴──────┐     │
              │     ▼             ▼     │
        ┌───────────────┐  ┌───────────────┐
        │INPUT_REQUIRED │  │ AUTH_REQUIRED │
        └───────┬───────┘  └───────┬───────┘
                │                  │
                └────────┬─────────┘
                         │
           ┌─────────────┼─────────────┐
           ▼             ▼             ▼
    ┌───────────┐ ┌───────────┐ ┌───────────┐
    │ COMPLETED │ │  FAILED   │ │ CANCELED  │
    └───────────┘ └───────────┘ └───────────┘
         │             │             │
         └─────────────┴─────────────┘
                       │
               [Terminal States]
               Cannot be modified
```

### 3. RequestContext (SDK Official)

The `RequestContext` class provides request information:

```python
from a2a.server.agent_execution import RequestContext
from a2a.types import MessageSendParams, Message

# Constructor signature:
RequestContext(
    request: MessageSendParams | None = None,  # The incoming request
    task_id: str | None = None,                # Task identifier
    context_id: str | None = None,             # Context identifier
    task: Task | None = None,                  # Current task (if exists)
    related_tasks: list[Task] | None = None,   # Referenced tasks
    call_context: ServerCallContext | None = None,
    task_id_generator: IDGenerator | None = None,
    context_id_generator: IDGenerator | None = None
)

# Key attributes:
context.context_id      # Current context identifier
context.task_id         # Current task identifier
context.message         # The incoming message
context.current_task    # The current Task object (if any)
context.related_tasks   # List of related tasks
context.get_user_input() # Extract text from user message
```

### 4. EventQueue

Event-driven communication channel:

```python
from a2a.server.events import EventQueue

# Methods:
event_queue = EventQueue()
await event_queue.enqueue_event(event)  # Add event to queue
event = await event_queue.dequeue_event()  # Get next event
await event_queue.close()  # Signal no more events

# Supported event types:
# - Message
# - Task
# - TaskStatusUpdateEvent
# - TaskArtifactUpdateEvent
```

### 5. TaskUpdater

Helper for updating task state:

```python
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState

# Constructor:
updater = TaskUpdater(
    event_queue=event_queue,     # EventQueue instance
    task_id="task-123",          # Task to update
    context_id="ctx-456"         # Context of the task
)

# Methods:
await updater.submit()                    # Set state to SUBMITTED
await updater.start_work()                # Set state to WORKING
await updater.update_status(state, msg)   # Update with message
await updater.add_artifact(parts, name)   # Add output artifact
await updater.complete(message)           # Set state to COMPLETED
await updater.failed(error_message)       # Set state to FAILED
await updater.cancel()                    # Set state to CANCELED
await updater.requires_input(message)     # Set state to INPUT_REQUIRED
await updater.requires_auth(message)      # Set state to AUTH_REQUIRED
await updater.reject(reason)              # Set state to REJECTED
```

### 6. TaskStore (SDK Interface)

Abstract interface for task persistence:

```python
from a2a.server.tasks import TaskStore, InMemoryTaskStore

# TaskStore interface methods:
async def get(task_id: str, context: ServerCallContext | None) -> Task | None
async def save(task: Task, context: ServerCallContext | None) -> None
async def delete(task_id: str, context: ServerCallContext | None) -> None

# Built-in implementation:
store = InMemoryTaskStore()  # Simple in-memory storage
```

---

## In-Memory Context Storage Implementation

### Custom TaskStore with Context Tracking

Here's how to implement a custom in-memory store that tracks both tasks and contexts:

```python
from typing import Dict, List, Optional
from datetime import datetime
import logging

from a2a.types import Task, TaskStatus, TaskState, Artifact


class InMemoryTaskStore:
    """
    In-memory storage for tasks with context tracking.

    Features:
    - Task CRUD operations
    - Context-to-task mapping
    - Terminal state immutability
    - Message history per task
    """

    def __init__(self):
        # Primary storage: task_id -> Task
        self.tasks: Dict[str, Task] = {}

        # Context index: context_id -> [task_ids]
        self.contexts: Dict[str, List[str]] = {}

        self.logger = logging.getLogger(__name__)

    async def create_task(self, task: Task) -> Task:
        """
        Create and store a new task.

        Args:
            task: Task object with task_id and context_id

        Returns:
            The stored task
        """
        # Store task by ID
        self.tasks[task.task_id] = task

        # Index task by context
        if task.context_id not in self.contexts:
            self.contexts[task.context_id] = []
        self.contexts[task.context_id].append(task.task_id)

        self.logger.debug(
            f"Created task {task.task_id} in context {task.context_id}"
        )
        return task

    async def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        return self.tasks.get(task_id)

    async def update_task(
        self,
        task_id: str,
        status: TaskStatus
    ) -> Optional[Task]:
        """
        Update task status.

        Note: Terminal states (COMPLETED, FAILED, CANCELED, REJECTED)
        cannot be updated per A2A specification.
        """
        if task_id not in self.tasks:
            return None

        task = self.tasks[task_id]

        # Validate immutability: cannot update terminal states
        terminal_states = [
            TaskState.completed,
            TaskState.failed,
            TaskState.canceled,
            TaskState.rejected
        ]

        if task.status.state in terminal_states:
            self.logger.warning(
                f"Cannot update terminal task {task_id} "
                f"(state: {task.status.state})"
            )
            return None

        task.status = status
        self.logger.debug(
            f"Updated task {task_id} to state {status.state}"
        )
        return task

    async def add_artifacts(
        self,
        task_id: str,
        artifacts: List[Artifact]
    ) -> Optional[Task]:
        """Add artifacts to task"""
        if task_id not in self.tasks:
            return None

        task = self.tasks[task_id]
        if task.artifacts is None:
            task.artifacts = []
        task.artifacts.extend(artifacts)
        return task

    async def get_context_tasks(self, context_id: str) -> List[Task]:
        """
        Get all tasks in a context.

        This enables multi-turn conversation support by retrieving
        all related tasks in chronological order.
        """
        task_ids = self.contexts.get(context_id, [])
        return [
            self.tasks[tid]
            for tid in task_ids
            if tid in self.tasks
        ]

    async def delete_task(self, task_id: str) -> bool:
        """Delete task and remove from context index"""
        if task_id not in self.tasks:
            return False

        task = self.tasks.pop(task_id)

        # Remove from context index
        if task.context_id in self.contexts:
            self.contexts[task.context_id] = [
                tid for tid in self.contexts[task.context_id]
                if tid != task_id
            ]

        return True

    async def get_context_history(
        self,
        context_id: str,
        max_messages: Optional[int] = None
    ) -> List[Message]:
        """
        Get message history for a context.

        Args:
            context_id: Context to retrieve history for
            max_messages: Maximum messages to return (None = all)

        Returns:
            List of messages in chronological order
        """
        tasks = await self.get_context_tasks(context_id)

        all_messages = []
        for task in tasks:
            if task.history:
                all_messages.extend(task.history)

        if max_messages is not None:
            return all_messages[-max_messages:]
        return all_messages
```

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                     InMemoryTaskStore                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    tasks: Dict[str, Task]                    │   │
│  │                                                              │   │
│  │  "task-001" ──► Task(id="task-001", context_id="ctx-A")     │   │
│  │  "task-002" ──► Task(id="task-002", context_id="ctx-A")     │   │
│  │  "task-003" ──► Task(id="task-003", context_id="ctx-B")     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              contexts: Dict[str, List[str]]                  │   │
│  │                                                              │   │
│  │  "ctx-A" ──► ["task-001", "task-002"]  (Conversation A)     │   │
│  │  "ctx-B" ──► ["task-003"]               (Conversation B)     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Methods:                                                           │
│  ├── create_task(task) ──► Store + Index by context                │
│  ├── get_task(task_id) ──► Retrieve single task                    │
│  ├── update_task(task_id, status) ──► Update (respects terminal)   │
│  ├── get_context_tasks(context_id) ──► All tasks in conversation   │
│  └── get_context_history(context_id) ──► Message history           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Implementing an AgentExecutor with Context Support

### Complete Example

```python
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    Task, TaskState, Part, TextPart, Message, Role
)
from a2a.utils import new_task, new_agent_text_message


class MyAgentExecutor(AgentExecutor):
    """
    Agent executor with full context management support.

    Implements:
    - Task lifecycle (SUBMITTED -> WORKING -> COMPLETED)
    - Context-aware responses
    - Message history access
    - Artifact generation
    """

    def __init__(self, task_store: InMemoryTaskStore):
        self.task_store = task_store

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue
    ) -> None:
        """
        Execute agent logic with context awareness.

        Args:
            context: RequestContext from A2A SDK
            event_queue: EventQueue for sending events
        """
        # 1. Extract user input
        user_input = context.get_user_input()

        # 2. Create or retrieve task
        task = context.current_task
        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)
            await self.task_store.create_task(task)

        # 3. Create TaskUpdater for state management
        updater = TaskUpdater(
            event_queue=event_queue,
            task_id=task.task_id,
            context_id=task.context_id
        )

        # 4. Transition to WORKING state
        await updater.update_status(
            TaskState.working,
            new_agent_text_message(
                "Processing your request...",
                context_id=context.context_id
            )
        )

        # 5. Access conversation history for context
        history = await self.task_store.get_context_history(
            context.context_id
        )

        # 6. Process with context awareness
        response = await self._process_with_context(
            user_input=user_input,
            history=history,
            related_tasks=context.related_tasks or []
        )

        # 7. Add result as artifact
        await updater.add_artifact(
            parts=[Part(root=TextPart(text=response))],
            name="response"
        )

        # 8. Complete task
        await updater.complete()

    async def _process_with_context(
        self,
        user_input: str,
        history: List[Message],
        related_tasks: List[Task]
    ) -> str:
        """
        Process request using conversation context.

        This is where you implement your agent's logic,
        leveraging the conversation history for context-aware responses.
        """
        # Build context from history
        context_messages = []
        for msg in history[-10:]:  # Last 10 messages
            role = "User" if msg.role == Role.user else "Agent"
            text = self._extract_text(msg)
            context_messages.append(f"{role}: {text}")

        # Your agent logic here...
        return f"Processed: {user_input}"

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue
    ) -> None:
        """Cancel an ongoing task"""
        if context.current_task:
            updater = TaskUpdater(
                event_queue=event_queue,
                task_id=context.current_task.task_id,
                context_id=context.context_id
            )
            await updater.cancel()
```

---

## Multi-Turn Conversation Flow

### Sequence Diagram

```
┌──────────┐          ┌──────────┐          ┌───────────┐
│  Client  │          │   Agent  │          │ TaskStore │
└────┬─────┘          └────┬─────┘          └─────┬─────┘
     │                     │                      │
     │ 1. Send message     │                      │
     │ (no context_id)     │                      │
     │────────────────────►│                      │
     │                     │                      │
     │                     │ 2. Generate IDs      │
     │                     │ context_id="ctx-001" │
     │                     │ task_id="task-001"   │
     │                     │                      │
     │                     │ 3. Create task       │
     │                     │─────────────────────►│
     │                     │                      │
     │                     │ 4. Process & respond │
     │◄────────────────────│                      │
     │ Task completed      │                      │
     │ context_id="ctx-001"│                      │
     │                     │                      │
     │ 5. Follow-up        │                      │
     │ context_id="ctx-001"│                      │
     │────────────────────►│                      │
     │                     │                      │
     │                     │ 6. Get context tasks │
     │                     │─────────────────────►│
     │                     │◄─────────────────────│
     │                     │ [task-001]           │
     │                     │                      │
     │                     │ 7. Process with      │
     │                     │    history context   │
     │                     │                      │
     │◄────────────────────│                      │
     │ Contextual response │                      │
     │                     │                      │
```

### Code Example: Client-Side

```python
import httpx

async def multi_turn_conversation():
    """Example of multi-turn conversation with context"""

    async with httpx.AsyncClient() as client:
        # First message - no context_id
        response1 = await client.post(
            "http://localhost:9001/",
            json={
                "jsonrpc": "2.0",
                "method": "message/send",
                "params": {
                    "message": {
                        "role": "user",
                        "parts": [{"text": "What is 2+2?"}]
                    }
                },
                "id": 1
            }
        )
        result1 = response1.json()

        # Extract context_id from response
        context_id = result1["result"]["context_id"]
        print(f"Context established: {context_id}")

        # Follow-up message - same context_id
        response2 = await client.post(
            "http://localhost:9001/",
            json={
                "jsonrpc": "2.0",
                "method": "message/send",
                "params": {
                    "context_id": context_id,  # Continue conversation
                    "message": {
                        "role": "user",
                        "parts": [{"text": "Now multiply that by 3"}]
                    }
                },
                "id": 2
            }
        )
        result2 = response2.json()

        # Agent understands "that" = 4 from context
        print(f"Response: {result2['result']}")
```

---

## History Length Parameter

The `historyLength` parameter controls how many messages to return:

| Value | Behavior |
|-------|----------|
| Not set | Server returns implementation-defined default |
| `0` | No history included |
| `N` (positive) | Return maximum N recent messages |

```python
# In your agent implementation:
async def get_task_with_history(
    self,
    task_id: str,
    history_length: Optional[int] = None
) -> Task:
    """Get task with optional history trimming"""
    task = await self.task_store.get_task(task_id)

    if task and history_length is not None:
        if history_length == 0:
            task.history = None
        elif task.history:
            task.history = task.history[-history_length:]

    return task
```

---

## Best Practices

### 1. Context Isolation

```python
# Each conversation should have its own context
# Never share context_id between unrelated conversations

context_id = f"ctx-{uuid4().hex[:8]}"  # Unique per conversation
```

### 2. Terminal State Immutability

```python
# Once a task reaches a terminal state, it cannot be modified
TERMINAL_STATES = [
    TaskState.completed,
    TaskState.failed,
    TaskState.canceled,
    TaskState.rejected
]

if task.status.state in TERMINAL_STATES:
    # Create new task instead of modifying
    pass
```

### 3. Context Expiration

```python
class InMemoryTaskStoreWithExpiration(InMemoryTaskStore):
    """Task store with automatic context cleanup"""

    def __init__(self, expiration_hours: int = 24):
        super().__init__()
        self.expiration = timedelta(hours=expiration_hours)
        self.context_timestamps: Dict[str, datetime] = {}

    async def cleanup_expired_contexts(self):
        """Remove contexts older than expiration time"""
        now = datetime.utcnow()
        expired = [
            ctx_id for ctx_id, timestamp in self.context_timestamps.items()
            if now - timestamp > self.expiration
        ]

        for ctx_id in expired:
            await self._delete_context(ctx_id)
```

### 4. Reference Task Support

```python
# Use reference_task_ids to link related tasks
params = {
    "context_id": context_id,
    "reference_task_ids": ["task-001", "task-002"],  # Related tasks
    "message": {...}
}

# In executor, access via:
related_tasks = context.related_tasks  # List[Task]
```

---

## References

- [A2A Protocol Specification](https://a2a-protocol.org/latest/specification/)
- [A2A Python SDK (GitHub)](https://github.com/a2aproject/a2a-python)
- [A2A Samples Repository](https://github.com/a2aproject/a2a-samples)
- [PyPI: a2a-sdk](https://pypi.org/project/a2a-sdk/)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01-17 | Initial documentation |
