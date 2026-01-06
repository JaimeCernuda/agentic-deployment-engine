# A2A Protocol - Life of a Task Implementation Guide

**Complete Reference for Implementing Task Lifecycle in A2A Python SDK**

---

## Table of Contents

1. [Core Concepts](#core-concepts)
2. [Task States and Lifecycle](#task-states-and-lifecycle)
3. [SDK Components](#sdk-components)
4. [Implementation Examples](#implementation-examples)
5. [Advanced Patterns](#advanced-patterns)
6. [Complete Server Examples](#complete-server-examples)
7. [References](#references)

---

## Core Concepts

### What is a Task?

According to the official A2A documentation:

> When a client sends a message to an agent, the agent might determine that fulfilling the request requires a stateful task to be completed (e.g., "generate a report," "book a flight," "answer a question"). Each task has a unique ID defined by the agent and progresses through a defined lifecycle (e.g., submitted, working, input-required, completed, failed).

### Message vs Task Response

Agents can respond in two fundamental ways:

1. **Stateless Message Response**
   - For immediate, self-contained interactions
   - No state management required
   - Example: Simple Q&A, quick lookups

2. **Stateful Task Response**
   - For long-running processes
   - Requires state tracking and lifecycle management
   - Has unique `taskId` and progresses through states
   - Example: "Book a flight", "Generate a report"

### Context ID

**Purpose**: Groups multiple Task objects and Message objects, providing continuity across interactions.

**How it works**:
1. Client sends first message → Agent creates new `contextId`
2. Client sends follow-up → Uses same `contextId`
3. Agent maintains conversational context across tasks

```python
# Example: All tasks share the same context
contextId = "ctx-trip-planning-123"
├─ Task 1: "Book flight to Paris"
├─ Task 2: "Book hotel in Paris"  
└─ Task 3: "Find restaurants nearby"
```

---

## Task States and Lifecycle

### Task States (Official Enum)

```python
from a2a.types import TaskState

# Initial state
TaskState.SUBMITTED      # Task created, not yet started

# Processing state
TaskState.WORKING        # Actively processing

# Interrupted states (require external action)
TaskState.INPUT_REQUIRED # Needs user input
TaskState.AUTH_REQUIRED  # Needs authentication

# Terminal states (cannot transition further)
TaskState.COMPLETED      # Successfully completed
TaskState.FAILED         # Failed with error
TaskState.CANCELLED      # Cancelled by user/system
TaskState.REJECTED       # Rejected (cannot be processed)
```

### Valid State Transitions

```
SUBMITTED → WORKING, REJECTED, CANCELLED
WORKING → INPUT_REQUIRED, AUTH_REQUIRED, COMPLETED, FAILED, CANCELLED
INPUT_REQUIRED → WORKING, CANCELLED, FAILED
AUTH_REQUIRED → WORKING, CANCELLED, FAILED
COMPLETED → [No transitions - terminal]
FAILED → [No transitions - terminal]
CANCELLED → [No transitions - terminal]
REJECTED → [No transitions - terminal]
```

### Task Immutability

**Critical Rule**: Once a task reaches a terminal state, it **cannot restart**.

**Benefits**:
- Clear input/output mapping per task
- Complete audit trail
- Idempotency guarantees
- Simplified error handling

**Refinements**: New requests create NEW tasks with same `contextId`

```python
# Example: Image refinement
Task 1: "Generate sailboat image" → COMPLETED → artifact_v1.png
Task 2: "Make boat red" (references Task 1) → COMPLETED → artifact_v2.png
# Task 1 remains unchanged (immutable)
# Task 2 is a new, separate task
```

---

## SDK Components

### 1. AgentExecutor (Abstract Base Class)

**Location**: `a2a.server.agent_execution.AgentExecutor`

**Required Methods**:

```python
from abc import ABC, abstractmethod
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue

class AgentExecutor(ABC):
    """
    Agent executor interface.
    Contains core logic for executing tasks and publishing updates.
    """
    
    @abstractmethod
    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue
    ) -> None:
        """
        Execute the agent's logic based on the request.
        Publish updates to the event queue.
        
        Args:
            context: Request context (message, task_id, context_id, etc.)
            event_queue: Queue for publishing events
        """
        pass
    
    @abstractmethod
    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue
    ) -> None:
        """
        Request the agent to cancel an ongoing task.
        
        Args:
            context: Request context with task ID to cancel
            event_queue: Queue for publishing cancellation status
        """
        pass
```

### 2. RequestContext

**Location**: `a2a.server.agent_execution.RequestContext`

**Available Properties**:

```python
class RequestContext:
    """Provides information about the incoming request"""
    
    # Core identifiers
    task_id: str           # Unique task ID
    context_id: str        # Context ID for grouping
    
    # Request data
    message: Message       # Full message object
    current_task: Task     # Current task object (if exists)
    
    # Helper methods
    def get_user_input(self) -> str:
        """Extract text from user's message parts"""
        pass
```

**Usage Example**:

```python
async def execute(self, context: RequestContext, event_queue: EventQueue):
    # Get user input
    user_input = context.get_user_input()
    
    # Access IDs
    task_id = context.task_id
    context_id = context.context_id
    
    # Full message
    message = context.message
    
    # Current task (may be None)
    current_task = context.current_task
```

### 3. EventQueue

**Location**: `a2a.server.events.EventQueue`

**Purpose**: Buffer for sending events back to the client

**Supported Event Types**:
- `Message` - Simple message response
- `Task` - Task object with status and artifacts
- `TaskStatusUpdateEvent` - Status update for existing task
- `TaskArtifactUpdateEvent` - Artifact update for existing task
- `A2AError` / `JSONRPCError` - Error responses

**Usage**:

```python
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message, new_task

async def execute(self, context: RequestContext, event_queue: EventQueue):
    # Send a simple message
    await event_queue.enqueue_event(
        new_agent_text_message("Hello World")
    )
    
    # Send a task
    task = new_task(
        task_id=context.task_id,
        context_id=context.context_id,
        state=TaskState.COMPLETED,
        artifacts=[artifact]
    )
    await event_queue.enqueue_event(task)
```

### 4. TaskUpdater (Helper Class)

**Location**: `a2a.server.agent_execution.TaskUpdater`

**Purpose**: Simplifies task lifecycle management

**Methods**:

```python
from a2a.server.agent_execution import TaskUpdater
from a2a.types import TaskState

class TaskUpdater:
    """Helper for publishing task lifecycle events"""
    
    def __init__(
        self,
        event_queue: EventQueue,
        task_id: str,
        context_id: str
    ):
        pass
    
    def submit(self) -> None:
        """Mark task as SUBMITTED"""
        pass
    
    def start_work(self) -> None:
        """Mark task as WORKING"""
        pass
    
    async def update_status(
        self,
        state: TaskState,
        message: Optional[str] = None
    ) -> None:
        """Update task status"""
        pass
    
    async def complete(
        self,
        artifacts: List[Artifact],
        messages: List[Message]
    ) -> None:
        """Mark task as COMPLETED with artifacts"""
        pass
    
    async def fail(self, error_message: str) -> None:
        """Mark task as FAILED"""
        pass
```

**Usage Example**:

```python
async def execute(self, context: RequestContext, event_queue: EventQueue):
    # Create updater
    updater = TaskUpdater(
        event_queue,
        context.task_id,
        context.context_id
    )
    
    # Lifecycle progression
    updater.submit()
    updater.start_work()
    
    # During processing
    await updater.update_status(
        TaskState.WORKING,
        "Processing your request..."
    )
    
    # When complete
    await updater.complete(
        artifacts=[artifact],
        messages=[context.message]
    )
```

### 5. InMemoryTaskStore

**Location**: `a2a.server.tasks.InMemoryTaskStore`

**Purpose**: Store and manage tasks (in-memory implementation)

**Usage**:

```python
from a2a.server.tasks import InMemoryTaskStore

# Create task store
task_store = InMemoryTaskStore()

# Used by DefaultRequestHandler to track task state
```

**Note**: Tasks are stored in memory and don't persist across restarts.

### 6. DefaultRequestHandler

**Location**: `a2a.server.request_handlers.DefaultRequestHandler`

**Purpose**: Orchestrates A2A protocol request handling

```python
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore

request_handler = DefaultRequestHandler(
    agent_executor=MyAgentExecutor(),
    task_store=InMemoryTaskStore(),
    # Optional: for push notifications
    push_config_store=None,
    push_sender=None
)
```

**What it does**:
1. Receives JSON-RPC requests
2. Creates/updates tasks in TaskStore
3. Calls `execute()` or `cancel()` on AgentExecutor
4. Processes EventQueue
5. Returns JSON-RPC responses

### 7. A2AStarletteApplication

**Location**: `a2a.server.apps.A2AStarletteApplication`

**Purpose**: HTTP server for A2A agents

```python
from a2a.server.apps import A2AStarletteApplication

server = A2AStarletteApplication(
    agent_card=agent_card,
    http_handler=request_handler
)

# Build and run
import uvicorn
uvicorn.run(server.build(), host='localhost', port=9999)
```

**Features**:
- Exposes agent card at `/.well-known/agent.json`
- Handles HTTP POST requests to `/`
- Supports streaming via Server-Sent Events (SSE)

---

## Implementation Examples

### Example 1: Simple Message Response (Hello World)

**Source**: Official A2A Python Tutorial

```python
from typing_extensions import override
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

class HelloWorldAgent:
    """Hello World Agent."""
    async def invoke(self) -> str:
        return 'Hello World'

class HelloWorldAgentExecutor(AgentExecutor):
    """Simple message response - no task lifecycle"""
    
    def __init__(self):
        self.agent = HelloWorldAgent()
    
    @override
    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        # Get result from agent
        result = await self.agent.invoke()
        
        # Send as simple message (not a task)
        event_queue.enqueue_event(new_agent_text_message(result))
    
    @override
    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue
    ) -> None:
        raise Exception('cancel not supported')
```

### Example 2: Task with Completed State

**Source**: Google Codelabs - BurgerSellerAgent

```python
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import completed_task, new_artifact
from a2a.types import Part, TextPart
import logging

logger = logging.getLogger(__name__)

class BurgerSellerAgentExecutor(AgentExecutor):
    """Returns a completed task with artifact"""
    
    def __init__(self):
        self.agent = BurgerSellerAgent()
    
    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        # Get user input
        query = context.get_user_input()
        
        try:
            # Process request
            result = self.agent.invoke(query, context.context_id)
            logger.info(f"Final Result ===> {result}")
            
            # Create artifact with result
            parts = [Part(root=TextPart(text=str(result)))]
            
            # Send completed task
            await event_queue.enqueue_event(
                completed_task(
                    context.task_id,
                    context.context_id,
                    [new_artifact(parts, f"burger_{context.task_id}")],
                    [context.message]
                )
            )
            
        except Exception as e:
            logger.error(f"Error processing task: {e}")
            # Here you would send a FAILED task status
```

### Example 3: Task with Lifecycle Updates (Streaming)

**Source**: CurrencyAgent Tutorial with LangGraph

```python
from a2a.server.agent_execution import AgentExecutor, RequestContext, TaskUpdater
from a2a.server.events import EventQueue
from a2a.types import TaskState
from a2a.utils import new_text_artifact
import logging

logger = logging.getLogger(__name__)

class CurrencyAgentExecutor(AgentExecutor):
    """Demonstrates task lifecycle with status updates"""
    
    def __init__(self):
        self.agent = CurrencyAgent()
    
    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        query = context.get_user_input()
        task = context.current_task
        
        # Create TaskUpdater for lifecycle management
        updater = TaskUpdater(event_queue, task.id, task.context_id)
        
        try:
            # Stream results from LLM
            async for item in self.agent.stream(query, task.context_id):
                
                is_task_complete = item.get('is_task_complete', False)
                require_user_input = item.get('require_user_input', False)
                content = item.get('content', '')
                
                if not is_task_complete and not require_user_input:
                    # Send progress update
                    await updater.update_status(
                        TaskState.WORKING,
                        message=content
                    )
                    logger.info(f"Status update: {content}")
                    
                elif require_user_input:
                    # Need user input
                    await updater.update_status(
                        TaskState.INPUT_REQUIRED,
                        message=content
                    )
                    logger.info("Waiting for user input")
                    
                elif is_task_complete:
                    # Task completed
                    artifact = new_text_artifact(content)
                    await updater.complete(
                        artifacts=[artifact],
                        messages=[context.message]
                    )
                    logger.info("Task completed")
                    
        except Exception as e:
            # Task failed
            logger.error(f"Task failed: {e}")
            await updater.fail(str(e))
    
    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue
    ) -> None:
        logger.info(f"Cancelling task {context.task_id}")
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.update_status(TaskState.CANCELLED)
```

### Example 4: Multi-turn Conversation with Context

**Source**: Towards Data Science Multi-Agent Article

```python
from a2a.server.agent_execution import AgentExecutor, RequestContext, TaskUpdater
from a2a.server.events import EventQueue
from a2a.types import TaskState

class ConversationalAgentExecutor(AgentExecutor):
    """Maintains conversation history via context_id"""
    
    def __init__(self):
        self.agent = ConversationalAgent()
        # Store conversation history per context_id
        self.conversation_history = {}
    
    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        query = context.get_user_input()
        context_id = context.context_id
        
        # Get or create conversation history for this context
        if context_id not in self.conversation_history:
            self.conversation_history[context_id] = []
        
        # Add user message to history
        self.conversation_history[context_id].append({
            'role': 'user',
            'content': query
        })
        
        # Create TaskUpdater
        updater = TaskUpdater(event_queue, context.task_id, context_id)
        updater.submit()
        updater.start_work()
        
        # Process with full conversation history
        result = await self.agent.invoke(
            query,
            history=self.conversation_history[context_id]
        )
        
        # Add assistant response to history
        self.conversation_history[context_id].append({
            'role': 'assistant',
            'content': result
        })
        
        # Complete task
        artifact = new_text_artifact(result)
        await updater.complete(
            artifacts=[artifact],
            messages=[context.message]
        )
```

---

## Advanced Patterns

### Pattern 1: Task Refinement

**Concept**: Creating new tasks that reference previous tasks

```python
# Client sends refinement request
{
    "jsonrpc": "2.0",
    "id": "req-002",
    "method": "message/send",
    "params": {
        "message": {
            "role": "user",
            "messageId": "msg-002",
            "contextId": "ctx-abc123",      # Same context
            "referenceTaskIds": ["task-001"], # Reference to original task
            "parts": [{"text": "Make the boat red"}]
        }
    }
}
```

**Executor Implementation**:

```python
async def execute(self, context: RequestContext, event_queue: EventQueue):
    query = context.get_user_input()
    
    # Check if this is a refinement (has reference tasks)
    reference_task_ids = context.message.reference_task_ids
    
    if reference_task_ids:
        # This is a refinement - fetch original task artifacts
        original_artifacts = await self.fetch_artifacts(reference_task_ids)
        
        # Process refinement with original context
        result = await self.agent.refine(query, original_artifacts)
    else:
        # New task
        result = await self.agent.invoke(query)
    
    # Create new task (immutable - don't modify original)
    updater = TaskUpdater(event_queue, context.task_id, context.context_id)
    artifact = new_artifact(result, "refined_output.png")
    await updater.complete(artifacts=[artifact], messages=[context.message])
```

### Pattern 2: Parallel Task Execution

**Concept**: Multiple tasks in same context, processed concurrently

```python
# Example scenario: Trip planning
# Task 1: Book flight → COMPLETED
# ├─ Task 2: Book hotel (parallel)
# ├─ Task 3: Book activity (parallel)  
# └─ Task 4: Currency conversion (parallel)

async def execute_parallel_workflow(self, base_task_id: str, context_id: str):
    """
    Execute multiple dependent tasks in parallel
    """
    # Wait for base task to complete
    base_result = await self.wait_for_task(base_task_id)
    
    # Create parallel tasks
    parallel_tasks = [
        self.book_hotel(base_result, context_id),
        self.book_activity(base_result, context_id),
        self.convert_currency(base_result, context_id)
    ]
    
    # Execute in parallel
    results = await asyncio.gather(*parallel_tasks)
    
    return results
```

### Pattern 3: Push Notifications (Long-running Tasks)

**Setup**:

```python
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.push_notifications import (
    InMemoryPushNotificationConfigStore,
    BasePushNotificationSender
)
import httpx

# Create HTTP client
httpx_client = httpx.AsyncClient()

# Push notification config store
push_config_store = InMemoryPushNotificationConfigStore()

# Push notification sender
push_sender = BasePushNotificationSender(
    httpx_client=httpx_client,
    config_store=push_config_store
)

# Request handler with push support
request_handler = DefaultRequestHandler(
    agent_executor=MyAgentExecutor(),
    task_store=InMemoryTaskStore(),
    push_config_store=push_config_store,
    push_sender=push_sender
)
```

**Usage in Executor**:

```python
async def execute(self, context: RequestContext, event_queue: EventQueue):
    """
    Long-running task with push notifications
    """
    updater = TaskUpdater(event_queue, context.task_id, context.context_id)
    updater.submit()
    updater.start_work()
    
    # Start long-running process
    for i in range(100):
        await asyncio.sleep(1)  # Simulate work
        
        # Send periodic updates (pushed to client webhook)
        await updater.update_status(
            TaskState.WORKING,
            f"Processing: {i+1}/100 complete"
        )
    
    # Final completion
    await updater.complete(
        artifacts=[final_artifact],
        messages=[context.message]
    )
```

---

## Complete Server Examples

### Minimal Server (Hello World)

```python
# __main__.py
import logging
import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from agent_executor import HelloWorldAgentExecutor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    # 1. Define agent skill
    skill = AgentSkill(
        id='hello_world',
        name='Hello World',
        description='Returns a greeting',
        tags=['greeting']
    )
    
    # 2. Create agent card
    agent_card = AgentCard(
        name='Hello World Agent',
        description='A simple agent that says hello',
        url='http://localhost:9999/',
        version='1.0.0',
        default_input_modes=['text/plain'],
        default_output_modes=['text/plain'],
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill]
    )
    
    # 3. Create agent executor
    agent_executor = HelloWorldAgentExecutor()
    
    # 4. Create request handler
    request_handler = DefaultRequestHandler(
        agent_executor=agent_executor,
        task_store=InMemoryTaskStore()
    )
    
    # 5. Create server
    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler
    )
    
    # 6. Run server
    logger.info("Starting Hello World Agent on http://localhost:9999")
    uvicorn.run(server.build(), host='localhost', port=9999)

if __name__ == '__main__':
    main()
```

### Production Server (with Streaming and Push Notifications)

```python
# __main__.py
import logging
import os
import click
import uvicorn
import httpx
from dotenv import load_dotenv

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.push_notifications import (
    InMemoryPushNotificationConfigStore,
    BasePushNotificationSender
)
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from agent import CurrencyAgent
from agent_executor import CurrencyAgentExecutor

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.command()
@click.option('--host', default='localhost')
@click.option('--port', default=10000)
def main(host, port):
    try:
        # Verify API key
        if not os.getenv('GEMINI_API_KEY'):
            raise ValueError('GEMINI_API_KEY environment variable not set')
        
        # Create HTTP client
        httpx_client = httpx.AsyncClient()
        
        # Push notification setup
        push_config_store = InMemoryPushNotificationConfigStore()
        push_sender = BasePushNotificationSender(
            httpx_client=httpx_client,
            config_store=push_config_store
        )
        
        # Agent capabilities
        capabilities = AgentCapabilities(
            streaming=True,
            push_notifications=True
        )
        
        # Agent skill
        skill = AgentSkill(
            id='currency_conversion',
            name='Currency Conversion',
            description='Convert between different currencies',
            tags=['currency', 'finance'],
            examples=['Convert 100 USD to EUR']
        )
        
        # Agent card
        agent_card = AgentCard(
            name='Currency Agent',
            description='Converts currencies using live exchange rates',
            url=f'http://{host}:{port}/',
            version='1.0.0',
            default_input_modes=['text/plain'],
            default_output_modes=['text/plain'],
            capabilities=capabilities,
            skills=[skill]
        )
        
        # Agent executor
        agent_executor = CurrencyAgentExecutor()
        
        # Request handler
        request_handler = DefaultRequestHandler(
            agent_executor=agent_executor,
            task_store=InMemoryTaskStore(),
            push_config_store=push_config_store,
            push_sender=push_sender
        )
        
        # Server
        server = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler
        )
        
        # Run
        logger.info(f"Starting Currency Agent on http://{host}:{port}")
        uvicorn.run(server.build(), host=host, port=port)
        
    except Exception as e:
        logger.error(f'Error starting server: {e}')
        exit(1)

if __name__ == '__main__':
    main()
```

---

## Key Implementation Guidelines

### 1. Always Use TaskUpdater for Stateful Tasks

```python
# ✅ GOOD: Using TaskUpdater
async def execute(self, context: RequestContext, event_queue: EventQueue):
    updater = TaskUpdater(event_queue, context.task_id, context.context_id)
    updater.submit()
    updater.start_work()
    await updater.complete(artifacts=[artifact], messages=[context.message])

# ❌ BAD: Manual task creation (error-prone)
async def execute(self, context: RequestContext, event_queue: EventQueue):
    task = Task(id=context.task_id, status=TaskStatus(state=TaskState.WORKING))
    await event_queue.enqueue_event(task)
```

### 2. Maintain Conversation History via context_id

```python
# Store history per context_id
self.conversations = {}  # context_id -> [messages]

async def execute(self, context: RequestContext, event_queue: EventQueue):
    context_id = context.context_id
    
    # Initialize if new context
    if context_id not in self.conversations:
        self.conversations[context_id] = []
    
    # Add user message
    self.conversations[context_id].append(context.message)
    
    # Process with full history
    result = await self.agent.invoke(
        context.get_user_input(),
        history=self.conversations[context_id]
    )
```

### 3. Handle Refinements via referenceTaskIds

```python
async def execute(self, context: RequestContext, event_queue: EventQueue):
    # Check for referenced tasks
    if context.message.reference_task_ids:
        # This is a refinement
        original_task_id = context.message.reference_task_ids[0]
        original_task = await self.task_store.get_task(original_task_id)
        
        # Use original task's artifacts as input
        result = await self.refine(
            context.get_user_input(),
            original_task.artifacts
        )
    else:
        # New task
        result = await self.process(context.get_user_input())
```

### 4. Error Handling

```python
async def execute(self, context: RequestContext, event_queue: EventQueue):
    updater = TaskUpdater(event_queue, context.task_id, context.context_id)
    updater.submit()
    updater.start_work()
    
    try:
        result = await self.agent.invoke(context.get_user_input())
        await updater.complete(artifacts=[artifact], messages=[context.message])
        
    except ValueError as e:
        # User error - recoverable
        await updater.update_status(
            TaskState.INPUT_REQUIRED,
            f"Invalid input: {e}"
        )
        
    except Exception as e:
        # System error - task failed
        logger.error(f"Task failed: {e}", exc_info=True)
        await updater.fail(str(e))
```

### 5. Artifact Naming for Refinements

```python
# Use consistent artifact names across refinements
async def execute(self, context: RequestContext, event_queue: EventQueue):
    # Generate artifact with consistent name
    artifact = new_artifact(
        parts=[Part(root=FilePart(...))],
        name="output_image.png"  # ← Same name for all versions
    )
    
    # New artifact_id but same name
    # Allows client to track lineage
```

---

## Utility Functions Reference

### From a2a.utils

```python
from a2a.utils import (
    new_agent_text_message,
    new_task,
    new_text_artifact,
    new_artifact,
    completed_task
)

# Create a simple text message
message = new_agent_text_message("Hello World")

# Create a task
task = new_task(
    task_id="task-123",
    context_id="ctx-456",
    state=TaskState.COMPLETED,
    artifacts=[artifact]
)

# Create a text artifact
artifact = new_text_artifact("This is the output text")

# Create an artifact with custom parts
artifact = new_artifact(
    parts=[Part(root=TextPart(text="content"))],
    name="output.txt"
)

# Create a completed task (shortcut)
task = completed_task(
    task_id="task-123",
    context_id="ctx-456",
    artifacts=[artifact],
    messages=[message]
)
```

---

## Common Pitfalls and Solutions

### Pitfall 1: Mutating Terminal Tasks

**Problem**:
```python
# ❌ WRONG: Trying to update a completed task
task = await task_store.get_task("task-123")
if task.state == TaskState.COMPLETED:
    task.state = TaskState.WORKING  # Will fail!
```

**Solution**:
```python
# ✅ CORRECT: Create new task for refinement
if task.state == TaskState.COMPLETED:
    # Create new task that references the original
    new_task_id = generate_task_id()
    # Process as new task with referenceTaskIds
```

### Pitfall 2: Not Maintaining Context

**Problem**:
```python
# ❌ WRONG: Losing conversation history
async def execute(self, context: RequestContext, event_queue: EventQueue):
    # Each execution has no memory of previous turns
    result = await self.agent.invoke(context.get_user_input())
```

**Solution**:
```python
# ✅ CORRECT: Store history per context_id
async def execute(self, context: RequestContext, event_queue: EventQueue):
    history = self.get_history(context.context_id)
    result = await self.agent.invoke(
        context.get_user_input(),
        history=history
    )
    self.save_to_history(context.context_id, result)
```

### Pitfall 3: Blocking in execute()

**Problem**:
```python
# ❌ WRONG: Synchronous blocking call
async def execute(self, context: RequestContext, event_queue: EventQueue):
    result = self.agent.blocking_call()  # Blocks event loop!
```

**Solution**:
```python
# ✅ CORRECT: Use async/await
async def execute(self, context: RequestContext, event_queue: EventQueue):
    result = await self.agent.async_call()
    
# Or run sync code in executor
import asyncio
async def execute(self, context: RequestContext, event_queue: EventQueue):
    result = await asyncio.to_thread(self.agent.blocking_call)
```

---

## Testing Your Implementation

### Test Client Example

```python
# test_client.py
import asyncio
import httpx
from uuid import uuid4
from a2a.client import A2AClient
from a2a.types import SendMessageRequest, MessageSendParams

async def main():
    async with httpx.AsyncClient() as httpx_client:
        # Get agent card
        client = await A2AClient.get_client_from_agent_card_url(
            httpx_client,
            'http://localhost:9999'
        )
        
        # Test 1: Simple message
        message_payload = {
            'message': {
                'role': 'user',
                'parts': [{'type': 'text', 'text': 'Hello!'}],
                'messageId': uuid4().hex,
            }
        }
        
        request = SendMessageRequest(
            params=MessageSendParams(**message_payload)
        )
        
        response = await client.send_message(request)
        print("Response:", response.model_dump(mode='json', exclude_none=True))
        
        # Test 2: Refinement (if response included taskId)
        if hasattr(response, 'id'):
            task_id = response.id
            context_id = response.context_id
            
            refinement_payload = {
                'message': {
                    'role': 'user',
                    'contextId': context_id,
                    'referenceTaskIds': [task_id],
                    'parts': [{'type': 'text', 'text': 'Make it better'}],
                    'messageId': uuid4().hex,
                }
            }
            
            refinement_request = SendMessageRequest(
                params=MessageSendParams(**refinement_payload)
            )
            
            refinement_response = await client.send_message(refinement_request)
            print("Refinement:", refinement_response.model_dump(mode='json'))

if __name__ == '__main__':
    asyncio.run(main())
```

---

## References

### Official Documentation

1. **A2A Protocol Specification**
   - Life of a Task: https://a2a-protocol.org/latest/topics/life-of-a-task/
   - Overview: https://a2a-protocol.org/latest/specification/
   - Core Concepts: https://a2a-protocol.org/latest/topics/key-concepts/

2. **Python SDK Tutorial**
   - Getting Started: https://a2aprotocol.ai/docs/guide/google-a2a-python-sdk-tutorial
   - Agent Executor: https://a2a-protocol.org/latest/tutorials/python/4-agent-executor/
   - Currency Agent Example: https://a2aprotocol.ai/blog/a2a-sdk-currency-agent-tutorial

3. **SDK Repository**
   - GitHub: https://github.com/a2aproject/a2a-python
   - Examples: https://github.com/a2aproject/a2a-samples

### Community Resources

4. **Tutorials**
   - Google Codelabs: https://codelabs.developers.google.com/intro-a2a-purchasing-concierge
   - Towards Data Science: https://towardsdatascience.com/multi-agent-communication-with-the-a2a-python-sdk/
   - LangGraph Integration: https://gyliu513.github.io/jekyll/update/2025/07/29/langgraph-a2a.html
   - HuggingFace Blog: https://huggingface.co/blog/1bo/a2a-protocol-explained

---

## Version Information

**Document Version**: 1.0  
**A2A SDK Version**: 0.2.3+  
**Last Updated**: January 2026  
**Protocol Version**: A2A v1.0

---

## Quick Reference Card

### Essential Imports

```python
# Core execution
from a2a.server.agent_execution import AgentExecutor, RequestContext, TaskUpdater
from a2a.server.events import EventQueue

# Server components
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore

# Types
from a2a.types import (
    AgentCard, AgentCapabilities, AgentSkill,
    Task, TaskState, TaskStatus,
    Message, Part, TextPart, FilePart, DataPart
)

# Utilities
from a2a.utils import (
    new_agent_text_message,
    new_task,
    new_text_artifact,
    completed_task
)
```

### Minimal Implementation Checklist

- [ ] Create AgentExecutor subclass
- [ ] Implement `execute()` method
- [ ] Implement `cancel()` method
- [ ] Define AgentSkill
- [ ] Create AgentCard
- [ ] Initialize DefaultRequestHandler with TaskStore
- [ ] Create A2AStarletteApplication
- [ ] Run server with uvicorn

### Task Lifecycle Checklist

- [ ] Use TaskUpdater for stateful tasks
- [ ] Call `submit()` and `start_work()`
- [ ] Send status updates during processing
- [ ] Handle INPUT_REQUIRED state for user input
- [ ] Call `complete()` with artifacts
- [ ] Handle errors with `fail()`
- [ ] Implement `cancel()` for cancellation

---

**End of Implementation Guide**
