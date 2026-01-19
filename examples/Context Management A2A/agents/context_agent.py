"""
Context Test Agent - A2A agent for context management experiments.

This agent implements the A2A protocol correctly with:
- context_id: Groups messages from the same conversation
- task_id: Identifies each individual task
- In-memory task/context store for message history

It does NOT add any custom context management logic beyond what A2A specifies.
"""

import sys
import uuid
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

# Add project root and example directory to path for imports
project_root = Path(__file__).parent.parent.parent.parent
example_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(example_dir))

from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions


# ============================================================================
# A2A Protocol Models
# ============================================================================

class TextPart(BaseModel):
    """A2A Text Part"""
    kind: str = "text"
    text: str


class FilePart(BaseModel):
    """A2A File Part for attachments"""
    kind: str = "file"
    file_name: str
    file_content: str  # Base64 encoded or plain text for txt files
    mime_type: Optional[str] = "text/plain"


class MessagePart(BaseModel):
    """A2A Message Part - can be text or file"""
    kind: str = "text"
    text: Optional[str] = None
    # File fields (when kind="file")
    file_name: Optional[str] = None
    file_content: Optional[str] = None
    mime_type: Optional[str] = None


class Message(BaseModel):
    """A2A Message following the protocol spec"""
    role: str  # "user" or "agent"
    parts: List[MessagePart]
    message_id: str
    task_id: Optional[str] = None
    context_id: Optional[str] = None
    timestamp: Optional[str] = None


class TaskStatus(BaseModel):
    """A2A Task Status"""
    state: str  # submitted, working, completed, failed, etc.
    message: Optional[str] = None
    timestamp: Optional[str] = None


class Task(BaseModel):
    """A2A Task following the protocol spec"""
    task_id: str
    context_id: str
    status: TaskStatus
    history: List[Message] = []
    artifacts: List[Any] = []
    metadata: Dict[str, Any] = {}


# ============================================================================
# Request/Response Models
# ============================================================================

class MessageSendRequest(BaseModel):
    """Request to send a message (A2A style)"""
    message: Message
    context_id: Optional[str] = None
    task_id: Optional[str] = None


class FileAttachment(BaseModel):
    """File attachment for query"""
    file_name: str
    file_content: str  # Plain text content or base64 encoded
    mime_type: Optional[str] = "text/plain"


class QueryRequest(BaseModel):
    """Simple query request with A2A context support and file attachments"""
    query: str
    context_id: Optional[str] = None
    task_id: Optional[str] = None
    files: Optional[List[FileAttachment]] = None  # Optional file attachments


class QueryResponse(BaseModel):
    """Response with A2A context info"""
    response: str
    context_id: str
    task_id: str
    task: Optional[Task] = None


# ============================================================================
# In-Memory Task Store (A2A Standard)
# ============================================================================

class InMemoryTaskStore:
    """
    In-memory storage for tasks with context tracking.

    Following A2A specification for context management.
    """

    def __init__(self):
        # task_id -> Task
        self.tasks: Dict[str, Task] = {}
        # context_id -> [task_ids]
        self.contexts: Dict[str, List[str]] = {}
        self.logger = logging.getLogger("TaskStore")

    def create_task(self, task: Task) -> Task:
        """Create and store a new task."""
        self.tasks[task.task_id] = task

        if task.context_id not in self.contexts:
            self.contexts[task.context_id] = []
        self.contexts[task.context_id].append(task.task_id)

        self.logger.debug(f"Created task {task.task_id} in context {task.context_id}")
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        return self.tasks.get(task_id)

    def update_task(self, task_id: str, status: TaskStatus) -> Optional[Task]:
        """Update task status."""
        if task_id not in self.tasks:
            return None

        task = self.tasks[task_id]

        # Check terminal states (cannot be updated)
        terminal_states = ["completed", "failed", "canceled", "rejected"]
        if task.status.state in terminal_states:
            self.logger.warning(f"Cannot update terminal task {task_id}")
            return None

        task.status = status
        return task

    def add_message_to_task(self, task_id: str, message: Message) -> Optional[Task]:
        """Add a message to task history."""
        if task_id not in self.tasks:
            return None

        task = self.tasks[task_id]
        task.history.append(message)
        return task

    def get_context_tasks(self, context_id: str) -> List[Task]:
        """Get all tasks in a context."""
        task_ids = self.contexts.get(context_id, [])
        return [self.tasks[tid] for tid in task_ids if tid in self.tasks]

    def get_context_history(self, context_id: str) -> List[Message]:
        """Get all messages from all tasks in a context."""
        tasks = self.get_context_tasks(context_id)
        all_messages = []
        for task in tasks:
            all_messages.extend(task.history)
        return all_messages


# ============================================================================
# Context Test Agent
# ============================================================================

class ContextTestAgent:
    """
    Context Test Agent for A2A context management experiments.

    Implements A2A protocol with:
    - context_id for conversation grouping
    - task_id for individual task tracking
    - In-memory message history per context

    NO custom context management logic - pure A2A native behavior.
    NO system prompt - to avoid influencing model behavior.
    """

    def __init__(self, port: int = 9010):
        self.name = "Context Test Agent"
        self.description = "Agent for testing A2A native context management."
        self.port = port

        # A2A Task Store
        self.task_store = InMemoryTaskStore()

        # Setup logging
        log_dir = Path(__file__).parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / "context_test_agent.log"

        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()

        fh = logging.FileHandler(log_file, mode='a')
        fh.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

        # Claude SDK options - Add file reading tools for context test
        # Working directory for file operations
        self.work_dir = Path(__file__).parent.parent

        # Minimal system prompt to guide file reading behavior
        minimal_system_prompt = """When you read a file, respond only with "Done" or "I've noted that". Never describe, summarize, or repeat file contents unless explicitly asked "what does it say" or "what's in the file"."""

        self.claude_options = ClaudeAgentOptions(
            mcp_servers={},
            tools=["Read"],  # Enable Read tool for file operations
            allowed_tools=["Read"],
            system_prompt=minimal_system_prompt,
            cwd=str(self.work_dir),  # Set working directory for file operations
            permission_mode="acceptEdits"  # Auto-accept file reads
        )

        # FastAPI app
        self.app = FastAPI(title=self.name, description=self.description)
        self._setup_routes()

        self.logger.info(f"Initialized {self.name} on port {port}")

    def _setup_routes(self):
        """Setup A2A endpoints."""

        @self.app.get("/.well-known/agent-configuration")
        async def agent_card():
            """A2A Agent Card for discovery."""
            return {
                "name": self.name,
                "description": self.description,
                "url": f"http://localhost:{self.port}",
                "version": "1.0.0",
                "capabilities": {
                    "streaming": False,
                    "push_notifications": False,
                    "context_management": True
                },
                "default_input_modes": ["text"],
                "default_output_modes": ["text"],
                "skills": [
                    {
                        "id": "context_test",
                        "name": "Context Testing",
                        "description": "Test A2A native context management"
                    }
                ]
            }

        @self.app.get("/health")
        async def health():
            return {"status": "healthy", "agent": self.name}

        @self.app.post("/query", response_model=QueryResponse)
        async def query(request: QueryRequest):
            """
            Handle query with A2A context management.

            - If context_id is provided, continues that conversation
            - If not, creates a new context
            - Always creates a new task within the context
            - Includes full context history when calling the model
            - Supports file attachments
            """
            return await self._handle_query(
                query=request.query,
                context_id=request.context_id,
                task_id=request.task_id,
                files=request.files
            )

        @self.app.post("/message/send")
        async def message_send(request: MessageSendRequest):
            """A2A message/send endpoint."""
            # Extract text from message parts
            text_parts = [p.text for p in request.message.parts if p.kind == "text"]
            query = " ".join(text_parts)

            return await self._handle_query(
                query=query,
                context_id=request.context_id or request.message.context_id,
                task_id=request.task_id or request.message.task_id
            )

        @self.app.get("/context/{context_id}")
        async def get_context(context_id: str):
            """Get all tasks and messages in a context."""
            tasks = self.task_store.get_context_tasks(context_id)
            history = self.task_store.get_context_history(context_id)
            return {
                "context_id": context_id,
                "task_count": len(tasks),
                "message_count": len(history),
                "tasks": [t.model_dump() for t in tasks],
                "history": [m.model_dump() for m in history]
            }

    async def _handle_query(
        self,
        query: str,
        context_id: Optional[str] = None,
        task_id: Optional[str] = None,
        files: Optional[List['FileAttachment']] = None
    ) -> QueryResponse:
        """
        Handle query with A2A context management.

        1. Generate or use provided context_id
        2. Create new task within context
        3. Build conversation history from context
        4. Send to Claude with full history (including file contents)
        5. Store response in task history
        """
        # Generate IDs if not provided (A2A spec: server generates if missing)
        if not context_id:
            context_id = f"ctx-{uuid.uuid4().hex[:12]}"
            self.logger.info(f"Generated new context_id: {context_id}")
        else:
            self.logger.info(f"Using existing context_id: {context_id}")

        if not task_id:
            task_id = f"task-{uuid.uuid4().hex[:12]}"

        timestamp = datetime.utcnow().isoformat()

        # Build message parts (text + files)
        message_parts = []

        # Add text part if there's a query
        if query:
            message_parts.append(MessagePart(kind="text", text=query))

        # Add file parts if there are attachments
        if files:
            for file in files:
                self.logger.info(f"Processing file attachment: {file.file_name}")
                message_parts.append(MessagePart(
                    kind="file",
                    file_name=file.file_name,
                    file_content=file.file_content,
                    mime_type=file.mime_type
                ))

        # Create user message
        user_message = Message(
            role="user",
            parts=message_parts,
            message_id=f"msg-{uuid.uuid4().hex[:8]}",
            task_id=task_id,
            context_id=context_id,
            timestamp=timestamp
        )

        # Create task in SUBMITTED state
        task = Task(
            task_id=task_id,
            context_id=context_id,
            status=TaskStatus(state="submitted", timestamp=timestamp),
            history=[user_message]
        )
        self.task_store.create_task(task)

        # Update to WORKING state
        self.task_store.update_task(
            task_id,
            TaskStatus(state="working", timestamp=datetime.utcnow().isoformat())
        )

        # Get conversation history from this context
        context_history = self.task_store.get_context_history(context_id)

        self.logger.info(
            f"Processing query in context {context_id}, "
            f"task {task_id}, history: {len(context_history)} messages"
        )

        # Build prompt with full conversation history
        conversation_prompt = self._build_conversation_prompt(context_history)

        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"CONTEXT PASSED TO CLAUDE - Task: {task_id}")
        self.logger.info(f"Context ID: {context_id}")
        self.logger.info(f"History messages: {len(context_history)}")
        self.logger.info(f"Prompt length: {len(conversation_prompt)} chars")
        self.logger.info(f"{'='*70}")
        self.logger.info(f"FULL PROMPT:\n{conversation_prompt}")
        self.logger.info(f"{'='*70}\n")

        # Call Claude
        try:
            response_text = await self._call_claude(conversation_prompt)
        except Exception as e:
            self.logger.error(f"Claude call failed: {e}")
            self.task_store.update_task(
                task_id,
                TaskStatus(state="failed", message=str(e), timestamp=datetime.utcnow().isoformat())
            )
            return QueryResponse(
                response=f"Error: {str(e)}",
                context_id=context_id,
                task_id=task_id,
                task=self.task_store.get_task(task_id)
            )

        # Create agent response message
        agent_message = Message(
            role="agent",
            parts=[MessagePart(text=response_text)],
            message_id=f"msg-{uuid.uuid4().hex[:8]}",
            task_id=task_id,
            context_id=context_id,
            timestamp=datetime.utcnow().isoformat()
        )

        # Add to task history
        self.task_store.add_message_to_task(task_id, agent_message)

        # Update to COMPLETED state
        self.task_store.update_task(
            task_id,
            TaskStatus(state="completed", timestamp=datetime.utcnow().isoformat())
        )

        final_task = self.task_store.get_task(task_id)

        self.logger.info(f"Query completed. Response: {len(response_text)} chars")

        return QueryResponse(
            response=response_text,
            context_id=context_id,
            task_id=task_id,
            task=final_task
        )

    def _build_conversation_prompt(self, history: List[Message]) -> str:
        """
        Build a conversation prompt from message history.

        This includes ALL messages from the context - no filtering,
        no summarization, no relevance logic. Pure A2A native behavior.

        File attachments are included as their content with file name label.
        """
        if not history:
            return ""

        # Simply concatenate all messages with role labels
        prompt_parts = []
        for msg in history:
            role_label = "User" if msg.role == "user" else "Assistant"

            # Build content from all parts (text and files)
            content_parts = []
            for part in msg.parts:
                if part.kind == "text" and part.text:
                    content_parts.append(part.text)
                elif part.kind == "file" and part.file_content:
                    # Include ONLY file name reference, NOT content (native behavior test)
                    file_label = f"[File: {part.file_name}]"
                    content_parts.append(file_label)

            if content_parts:
                content = "\n".join(content_parts)
                prompt_parts.append(f"{role_label}: {content}")

        return "\n\n".join(prompt_parts)

    async def _call_claude(self, prompt: str) -> str:
        """Call Claude with the given prompt."""
        self.logger.debug("Creating Claude client...")

        client = ClaudeSDKClient(self.claude_options)
        await client.connect()

        self.logger.debug("Sending query to Claude...")
        await client.query(prompt)

        response = ""
        async for message in client.receive_response():
            if hasattr(message, 'content'):
                for block in message.content:
                    if hasattr(block, 'text'):
                        response += block.text

        await client.disconnect()

        return response or "No response generated"

    def run(self):
        """Run the agent."""
        self.logger.info(f"Starting {self.name} on port {self.port}...")
        uvicorn.run(self.app, host="0.0.0.0", port=self.port)


def main():
    """Run the Context Test Agent."""
    import os
    port = int(os.getenv("AGENT_PORT", "9010"))

    agent = ContextTestAgent(port=port)
    print(f"Starting Context Test Agent on port {port}...")
    print("This agent tests A2A native context management.")
    print("  - Uses context_id to group conversations")
    print("  - Uses task_id to track individual tasks")
    print("  - Maintains in-memory message history per context")
    print("  - NO system prompt (pure native behavior)")
    agent.run()


if __name__ == "__main__":
    main()
