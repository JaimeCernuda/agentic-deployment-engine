"""CrewAI backend implementation.

Uses CrewAI framework with Ollama as the LLM provider for local inference.
CrewAI enables role-based agent workflows with task delegation.
Uses CrewAI callbacks for internal observability of execution steps.

Bridges SDK MCP tools to CrewAI-compatible tools for tool calling support.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from ..core.exceptions import AgentBackendError, ConfigurationError
from ..observability.semantic import get_semantic_tracer
from .base import AgentBackend, BackendConfig, QueryResult

logger = logging.getLogger(__name__)


def _create_crewai_tool_from_mcp(
    tool_name: str,
    tool_description: str,
    server_instance: Any,
    original_tool_name: str,
) -> Any:
    """Create a CrewAI-compatible tool wrapper for an MCP tool.

    Args:
        tool_name: Full tool name (mcp__server__tool).
        tool_description: Description of what the tool does.
        server_instance: The MCP Server instance.
        original_tool_name: Original tool name for MCP call.

    Returns:
        A CrewAI Tool object that bridges to the MCP tool.
    """
    try:
        from crewai.tools import BaseTool
    except ImportError:
        logger.warning("CrewAI tools module not available, skipping tool bridging")
        return None

    # Import MCP types for calling tools
    try:
        from mcp.types import CallToolRequest, CallToolRequestParams
    except ImportError:
        logger.warning("MCP types not available, skipping tool bridging")
        return None

    class MCPToolWrapper(BaseTool):
        """Wrapper that bridges an MCP tool to CrewAI."""

        name: str = tool_name
        description: str = tool_description

        def _run(self, **kwargs: Any) -> str:
            """Execute the MCP tool synchronously."""
            try:
                # Get the CallToolRequest handler from the server
                handler = server_instance.request_handlers.get(CallToolRequest)
                if not handler:
                    return f"Error: No handler for tool {original_tool_name}"

                # Create the MCP call request
                params = CallToolRequestParams(
                    name=original_tool_name,
                    arguments=kwargs,
                )
                req = CallToolRequest(params=params)

                # Run the async handler in a new event loop
                loop = asyncio.new_event_loop()
                try:
                    result = loop.run_until_complete(handler(req))
                finally:
                    loop.close()

                # Extract text content from MCP result
                if hasattr(result, "root") and hasattr(result.root, "content"):
                    contents = result.root.content
                    if isinstance(contents, list):
                        texts = []
                        for c in contents:
                            if hasattr(c, "text"):
                                texts.append(c.text)
                            else:
                                texts.append(str(c))
                        return "\n".join(texts)
                return str(result)
            except Exception as e:
                logger.error(f"MCP tool {tool_name} failed: {e}")
                return f"Error calling {tool_name}: {e}"

    return MCPToolWrapper()


async def _extract_sdk_tools_async(mcp_servers: dict[str, Any]) -> list[Any]:
    """Extract SDK MCP tools and create CrewAI wrappers.

    Uses the MCP ListToolsRequest handler to enumerate tools and creates
    wrappers that call tools via the CallToolRequest handler.

    Args:
        mcp_servers: MCP server configurations from BackendConfig.

    Returns:
        List of CrewAI-compatible tool wrappers.
    """
    crewai_tools = []

    # Import MCP types for listing tools
    try:
        from mcp.types import ListToolsRequest
    except ImportError:
        logger.warning("MCP types not available, cannot extract SDK tools")
        return []

    for server_key, server_config in mcp_servers.items():
        if not isinstance(server_config, dict):
            continue

        server_type = server_config.get("type")
        if server_type != "sdk":
            continue

        instance = server_config.get("instance")
        if not instance:
            continue

        # Check if this instance has request handlers (MCP Server)
        if not hasattr(instance, "request_handlers"):
            continue

        # Get the ListToolsRequest handler
        list_handler = instance.request_handlers.get(ListToolsRequest)
        if not list_handler:
            logger.debug(f"No ListToolsRequest handler in SDK server '{server_key}'")
            continue

        try:
            # Call the list tools handler (async)
            req = ListToolsRequest()
            result = await list_handler(req)

            # Extract tools from the result
            if hasattr(result, "root") and hasattr(result.root, "tools"):
                tools = result.root.tools
                logger.debug(f"Found {len(tools)} tools in SDK server '{server_key}'")

                for tool in tools:
                    tool_name = getattr(tool, "name", None)
                    tool_desc = getattr(tool, "description", "") or f"Call {tool_name}"

                    if not tool_name:
                        continue

                    # Create CrewAI wrapper that calls via MCP handlers
                    wrapper = _create_crewai_tool_from_mcp(
                        tool_name=f"mcp__{server_key}__{tool_name}",
                        tool_description=tool_desc,
                        server_instance=instance,
                        original_tool_name=tool_name,
                    )

                    if wrapper:
                        crewai_tools.append(wrapper)
                        logger.info(f"Bridged MCP tool: {tool_name} -> CrewAI")

        except Exception as e:
            logger.error(f"Failed to extract tools from SDK server '{server_key}': {e}")

    return crewai_tools


def _create_step_callback(model_name: str) -> Any:
    """Create a step callback for tracing internal CrewAI execution.

    This callback fires INSIDE the CrewAI execution loop, giving us
    visibility into each step the agent takes.

    Args:
        model_name: The model name for tracing.

    Returns:
        Callback function for CrewAI's step_callback parameter.
    """

    def step_callback(step_output: Any) -> None:
        """Called on each step inside the CrewAI execution loop."""
        tracer = get_semantic_tracer()

        # Extract step information
        step_text = str(step_output)[:500] if step_output else ""

        # Check if this is a tool use step
        is_tool_use = hasattr(step_output, "tool") or "tool" in step_text.lower()

        if is_tool_use:
            # Try to extract tool info
            tool_name = getattr(step_output, "tool", "unknown_tool")
            tool_input = getattr(step_output, "tool_input", {})

            with tracer.tool_call(str(tool_name), tool_input) as span:
                tracer.add_event(
                    span,
                    "crewai_tool_step",
                    {"step_output": step_text[:200]},
                )
            logger.debug(f"[CALLBACK] CrewAI tool step: {tool_name}")
        else:
            # This is an LLM reasoning step
            with tracer.llm_message(
                role="assistant",
                content=step_text,
                model=model_name,
            ) as span:
                tracer.add_event(
                    span,
                    "crewai_reasoning_step",
                    {"step_length": len(step_text)},
                )
            logger.debug(f"[CALLBACK] CrewAI reasoning step: {step_text[:50]}...")

    return step_callback


def _create_task_callback(model_name: str) -> Any:
    """Create a task callback for tracing CrewAI task completion.

    Args:
        model_name: The model name for tracing.

    Returns:
        Callback function for CrewAI's task_callback parameter.
    """

    def task_callback(task_output: Any) -> None:
        """Called when a task completes inside CrewAI."""
        tracer = get_semantic_tracer()

        task_result = str(task_output)[:500] if task_output else ""
        description = getattr(task_output, "description", "")[:200]

        with tracer.llm_message(
            role="assistant",
            content=task_result,
            model=model_name,
        ) as span:
            tracer.add_event(
                span,
                "crewai_task_completed",
                {
                    "task_description": description,
                    "result_length": len(task_result),
                },
            )

        logger.debug(f"[CALLBACK] CrewAI task completed: {description[:50]}...")

    return task_callback


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

        # Bridge SDK MCP tools to CrewAI tools (async)
        crewai_tools = await _extract_sdk_tools_async(self.config.mcp_servers)
        if crewai_tools:
            logger.info(f"Bridged {len(crewai_tools)} SDK tools to CrewAI")
        else:
            logger.debug("No SDK tools found to bridge")

        # Create CrewAI agent with bridged tools
        self._agent = Agent(
            role=self.config.name,
            goal=self.config.system_prompt or "Help the user with their requests",
            backstory=f"You are {self.config.name}, an AI assistant.",
            llm=self._llm,
            verbose=False,
            allow_delegation=False,
            tools=crewai_tools if crewai_tools else None,
        )

        logger.info(
            f"CrewAI backend initialized with Ollama model: {self.ollama_model}"
            + (f" ({len(crewai_tools)} tools)" if crewai_tools else "")
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

            # Create callbacks for internal tracing
            # These fire INSIDE the CrewAI loop for true internal visibility
            model_name = f"ollama/{self.ollama_model}"
            step_cb = _create_step_callback(model_name)
            task_cb = _create_task_callback(model_name)

            # Create a temporary crew with callbacks for internal tracing
            crew = Crew(
                agents=[agent],
                tasks=[task],
                verbose=False,
                step_callback=step_cb,  # Fires on each internal step
                task_callback=task_cb,  # Fires on task completion
            )

            # Framework-level: trace the incoming query
            with tracer.llm_message(
                role="user",
                content=prompt,
                model=model_name,
            ) as user_span:
                tracer.add_event(
                    user_span,
                    "crewai_query_received",
                    {"query_length": len(prompt)},
                )

            # CrewAI is synchronous, run in thread pool
            logger.debug(f"Executing CrewAI query: {prompt[:100]}...")
            result = await asyncio.to_thread(crew.kickoff)

            # Extract response text
            response_text = str(result)

            # Framework-level: trace the final response
            # (internal steps already traced via callbacks)
            with tracer.llm_message(
                role="assistant",
                content=response_text,
                model=model_name,
            ) as response_span:
                tracer.add_event(
                    response_span,
                    "crewai_query_completed",
                    {"response_length": len(response_text)},
                )

            # Count tool uses from the result if available
            tools_used = 0
            if hasattr(result, "tools_used"):
                tools_used = len(result.tools_used)

            return QueryResult(
                response=response_text,
                messages_count=1,
                tools_used=tools_used,
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
        # CrewAI doesn't support streaming natively
        # Execute as regular query and yield result
        # (internal tracing handled by callbacks in query())
        result = await self.query(prompt, context)
        yield {"type": "response", "content": result.response}

    async def cleanup(self) -> None:
        """Cleanup resources."""
        self._agent = None
        self._llm = None
        self._initialized = False
        logger.info("CrewAI backend cleaned up")
