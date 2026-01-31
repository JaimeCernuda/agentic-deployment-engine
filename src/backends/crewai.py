"""CrewAI backend implementation.

Uses CrewAI framework with Ollama as the LLM provider for local inference.
CrewAI enables role-based agent workflows with task delegation.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from ..core.exceptions import AgentBackendError, ConfigurationError
from ..observability.semantic import get_semantic_tracer
from .base import AgentBackend, BackendConfig, QueryResult

logger = logging.getLogger(__name__)


class CrewAIBackend(AgentBackend):
    """Backend using CrewAI framework with Ollama LLM.

    CrewAI is a framework for building multi-agent systems with
    role-based agents, task delegation, and collaborative workflows.
    This implementation uses Ollama for local LLM inference.

    Prerequisites:
        - Ollama installed and running (ollama serve)
        - A model pulled (e.g., ollama pull llama3)
        - crewai package installed (pip install crewai langchain-community)

    See: https://github.com/joaomdmoura/crewAI
    """

    def __init__(
        self,
        config: BackendConfig,
        ollama_model: str = "llama3",
        ollama_base_url: str = "http://localhost:11434",
    ) -> None:
        """Initialize the CrewAI backend.

        Args:
            config: Backend configuration
            ollama_model: Ollama model to use (default: llama3)
            ollama_base_url: Ollama API base URL (default: localhost:11434)
        """
        super().__init__(config)
        self.ollama_model = ollama_model
        self.ollama_base_url = ollama_base_url
        self._agent = None
        self._llm = None

    @property
    def name(self) -> str:
        """Backend name for logging/identification."""
        return "crewai"

    async def initialize(self) -> None:
        """Initialize the backend by setting up CrewAI with Ollama.

        Creates a CrewAI agent configured with the Ollama LLM.
        """
        if self._initialized:
            return

        # Import CrewAI lazily to avoid dependency issues
        try:
            from crewai import LLM, Agent

            # Suppress litellm debug logging (avoids apscheduler import errors)
            try:
                import litellm

                litellm.suppress_debug_info = True
                logging.getLogger("LiteLLM").setLevel(logging.WARNING)
            except ImportError:
                pass  # litellm not installed, no need to suppress
        except ImportError as e:
            raise ConfigurationError(
                "CrewAI dependencies not installed. Install with: pip install crewai"
            ) from e

        # Verify Ollama is running
        import httpx

        try:
            async with httpx.AsyncClient() as client:
                response = await asyncio.wait_for(
                    client.get(f"{self.ollama_base_url}/api/tags"),
                    timeout=5,
                )
                if response.status_code != 200:
                    raise ConfigurationError(
                        f"Ollama API returned {response.status_code}. "
                        "Ensure Ollama is running with: ollama serve"
                    )
                # Check if model is available
                models = response.json().get("models", [])
                model_names = [m.get("name", "").split(":")[0] for m in models]
                # Strip tag from configured model for comparison
                model_base = self.ollama_model.split(":")[0]
                if model_base not in model_names:
                    available = ", ".join(model_names) if model_names else "none"
                    raise ConfigurationError(
                        f"Model '{self.ollama_model}' not found in Ollama. "
                        f"Available models: {available}. "
                        f"Pull it with: ollama pull {self.ollama_model}"
                    )
        except httpx.ConnectError as e:
            raise ConfigurationError(
                f"Cannot connect to Ollama at {self.ollama_base_url}. "
                "Ensure Ollama is running with: ollama serve"
            ) from e
        except TimeoutError as e:
            raise ConfigurationError(
                f"Timeout connecting to Ollama at {self.ollama_base_url}"
            ) from e

        # Create Ollama LLM instance using CrewAI's native LLM class
        # Format: ollama/<model_name> with base_url parameter
        self._llm = LLM(
            model=f"ollama/{self.ollama_model}",
            base_url=self.ollama_base_url,
        )

        # Create CrewAI agent
        self._agent = Agent(
            role=self.config.name,
            goal=self.config.system_prompt or "Help the user with their requests",
            backstory=f"You are {self.config.name}, an AI assistant.",
            llm=self._llm,
            verbose=False,
            allow_delegation=False,
        )

        logger.info(
            f"CrewAI backend initialized with Ollama model: {self.ollama_model}"
        )
        self._initialized = True

    async def query(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> QueryResult:
        """Execute a query using CrewAI.

        Args:
            prompt: The query to execute
            context: Optional context (not used by CrewAI currently)

        Returns:
            QueryResult with response and metadata
        """
        await self.initialize()

        if self._agent is None:
            raise AgentBackendError(self.name, "CrewAI agent not initialized")

        tracer = get_semantic_tracer()

        try:
            from crewai import Crew, Task

            agent = self._agent  # Local var for type narrowing

            # Create a task for this query
            task = Task(
                description=prompt,
                expected_output="A helpful response to the user's query",
                agent=agent,
            )

            # Create a temporary crew with just this task
            crew = Crew(
                agents=[agent],
                tasks=[task],
                verbose=False,
            )

            # Trace the LLM query execution
            with tracer.llm_message(
                role="user",
                content=prompt,
                model=f"ollama/{self.ollama_model}",
            ) as user_span:
                tracer.add_event(
                    user_span,
                    "crewai_task_created",
                    {"task_description": prompt[:200]},
                )

            # CrewAI is synchronous, run in thread pool
            logger.debug(f"Executing CrewAI query: {prompt[:100]}...")
            result = await asyncio.to_thread(crew.kickoff)

            # Extract response text
            response_text = str(result)

            # Trace the response
            with tracer.llm_message(
                role="assistant",
                content=response_text,
                model=f"ollama/{self.ollama_model}",
            ) as response_span:
                tracer.add_event(
                    response_span,
                    "crewai_task_completed",
                    {"response_length": len(response_text)},
                )

            return QueryResult(
                response=response_text,
                messages_count=1,
                tools_used=0,
                metadata={"context": context} if context else {},
            )

        except Exception as e:
            raise AgentBackendError(self.name, str(e), cause=e) from e

    async def query_stream(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> AsyncIterator[Any]:
        """Execute a streaming query using CrewAI.

        Note: CrewAI doesn't natively support streaming, so this
        executes a regular query and yields the result.

        Args:
            prompt: The query to execute
            context: Optional context

        Yields:
            The complete response (no true streaming support)
        """
        tracer = get_semantic_tracer()

        # CrewAI doesn't support streaming natively
        # Execute as regular query and yield result
        result = await self.query(prompt, context)

        # Trace the streamed response
        with tracer.llm_message(
            role="assistant",
            content=result.response,
            model=f"ollama/{self.ollama_model}",
        ) as span:
            tracer.add_event(span, "stream_complete", {"chunks": 1})

        yield {"type": "response", "content": result.response}

    async def cleanup(self) -> None:
        """Cleanup resources."""
        self._agent = None
        self._llm = None
        self._initialized = False
        logger.info("CrewAI backend cleaned up")
