"""
General Agent Executor with A2A task lifecycle support.

Implements task-based execution for orchestration and delegation to specialized agents.
"""
import sys
from pathlib import Path
import logging

# Add project root and example directory to path
project_root = Path(__file__).parent.parent.parent.parent
example_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(example_dir))

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from base_a2a_task_agent import (
    AgentExecutor,
    RequestContext,
    TaskUpdater,
    Task,
    Artifact
)
from src.a2a_transport import create_a2a_transport_server
from src.agent_registry import AgentRegistry


class GeneralAgentExecutor(AgentExecutor):
    """
    General Agent Executor implementing A2A task lifecycle.

    Orchestrates queries across specialized agents using dynamic discovery.
    Maintains conversation history per context_id.
    """

    def __init__(self, agent_urls_to_discover: list = None):
        self.logger = logging.getLogger(__name__)

        # Agent registry for dynamic discovery
        self.agent_registry = AgentRegistry()

        # Conversation history per context_id
        self.conversation_history = {}

        # Discover agents
        agent_urls_to_discover = agent_urls_to_discover or [
            "http://localhost:9002",  # Math Agent
            "http://localhost:9003",  # Finance Agent
            "http://localhost:9004",  # Search Agent
        ]

        # Synchronous discovery during initialization
        import asyncio
        async def discover_all():
            for url in agent_urls_to_discover:
                await self.agent_registry.discover_agent(url)

        asyncio.run(discover_all())

        # Generate system prompt with discovered agents
        base_prompt = """You are a General Agent responsible for answering any kind of user question clearly and helpfully.

You can delegate tasks to specialized agents that have been discovered in the system.

**Your delegation strategy:**
1. Analyze the user's question to understand what type of capability is needed
2. Match the question to the appropriate specialized agent based on their skills
3. Use the mcp__a2a_transport__query_agent tool with the agent's URL to delegate
4. If a task requires multiple agents (e.g., search for data, then calculate):
   - Call each agent in the appropriate order
   - Integrate all results in your final answer
5. For general knowledge questions that don't require specialized tools → answer directly yourself
6. Never perform calculations or conversions manually; always delegate to specialized agents

**Example delegation patterns:**
- Math operations or unit conversions → delegate to agents with math/conversion skills
- Currency or financial calculations → delegate to agents with finance skills
- Web searches or current information → delegate to agents with search skills
- General knowledge (e.g., "Who discovered gravity?") → answer directly

**Important:**
- Always use the exact agent URL when calling mcp__a2a_transport__query_agent
- The query_agent tool requires: agent_url (string) and query (string)
- Integrate responses from agents naturally into your final answer to the user
- You can call multiple agents sequentially if needed for complex tasks"""

        self.system_prompt = self.agent_registry.generate_system_prompt(base_prompt)

        # Create A2A transport MCP server
        a2a_server = create_a2a_transport_server()

        # Configure Claude SDK options
        self.claude_options = ClaudeAgentOptions(
            mcp_servers={"general_agent": a2a_server},
            allowed_tools=[
                "mcp__general_agent__query_agent",
                "mcp__general_agent__discover_agent"
            ],
            system_prompt=self.system_prompt
        )

        discovered = self.agent_registry.list_agents()
        self.logger.info(f"General Agent initialized with {len(discovered)} discovered agents")

    async def execute(
        self,
        context: RequestContext,
        task_updater: TaskUpdater
    ) -> Task:
        """
        Execute orchestration with task lifecycle management.

        Maintains conversation history and delegates to specialized agents as needed.

        Args:
            context: Request context with user query
            task_updater: Task lifecycle helper

        Returns:
            Completed task with result artifact
        """
        query = context.get_user_input()
        context_id = context.context_id

        self.logger.info(f"General Agent executing in context {context_id}: {query}")

        # Initialize conversation history for new context
        if context_id not in self.conversation_history:
            self.conversation_history[context_id] = []

        # Add user message to history
        self.conversation_history[context_id].append({
            'role': 'user',
            'content': query,
            'task_id': context.task_id
        })

        try:
            # Create task and mark as working
            await task_updater.submit()
            await task_updater.start_work()

            # Use context manager pattern (like test_weather_simple.py)
            async with ClaudeSDKClient(options=self.claude_options) as client:
                # Send query (Claude will decide whether to delegate or answer directly)
                await client.query(query)

                # Collect response
                response_text = ""
                tool_calls = []

                async for message in client.receive_response():
                    if hasattr(message, 'content'):
                        for block in message.content:
                            if hasattr(block, 'text'):
                                response_text += block.text
                            if hasattr(block, 'name'):
                                # Track tool usage for logging
                                tool_calls.append(block.name)

            # Add assistant response to history
            self.conversation_history[context_id].append({
                'role': 'assistant',
                'content': response_text,
                'task_id': context.task_id,
                'tools_used': tool_calls
            })

            self.logger.info(f"General Agent used {len(tool_calls)} tools: {tool_calls}")

            # Create result artifact
            artifact = Artifact(
                name="general_response.txt",
                content=response_text or "No response generated",
                content_type="text/plain"
            )

            # Complete task
            task = await task_updater.complete(
                artifacts=[artifact],
                result_message="Query processed successfully"
            )

            self.logger.info(f"General Agent completed task: {context.task_id}")
            return task

        except Exception as e:
            self.logger.error(f"General Agent failed: {e}", exc_info=True)
            task = await task_updater.fail(str(e))
            return task

    async def cancel(
        self,
        context: RequestContext,
        task_updater: TaskUpdater
    ) -> Task:
        """
        Cancel ongoing orchestration.

        Args:
            context: Request context
            task_updater: Task lifecycle helper

        Returns:
            Cancelled task
        """
        self.logger.info(f"Cancelling general task {context.task_id}")
        return await task_updater.cancel()
