"""
Search Agent Executor with A2A task lifecycle support.

Implements task-based execution for web search operations.
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


class SearchAgentExecutor(AgentExecutor):
    """
    Search Agent Executor implementing A2A task lifecycle.

    Provides web search capabilities using Claude SDK built-in tools.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # System prompt for search operations
        self.system_prompt = """You are the Search Agent. You can search the web for information.

**IMPORTANT RULES:**
1. For any web search queries, use your built-in web search capabilities.
2. Provide concise, accurate information from your search results.
3. Always cite or mention that the information comes from web search.
4. If you cannot find relevant information, say so clearly."""

        # Configure Claude SDK options (no MCP server, uses built-in tools)
        self.claude_options = ClaudeAgentOptions(
            mcp_servers={},
            allowed_tools=[],  # Uses Claude's built-in capabilities
            system_prompt=self.system_prompt
        )

    async def execute(
        self,
        context: RequestContext,
        task_updater: TaskUpdater
    ) -> Task:
        """
        Execute search operation with task lifecycle management.

        Args:
            context: Request context with user query
            task_updater: Task lifecycle helper

        Returns:
            Completed task with result artifact
        """
        query = context.get_user_input()
        self.logger.info(f"Search Agent executing: {query}")

        try:
            # Create task and mark as working
            await task_updater.submit()
            await task_updater.start_work()

            # Use context manager pattern (like test_weather_simple.py)
            async with ClaudeSDKClient(options=self.claude_options) as client:
                # Send query
                await client.query(query)

                # Collect response
                response_text = ""
                async for message in client.receive_response():
                    if hasattr(message, 'content'):
                        for block in message.content:
                            if hasattr(block, 'text'):
                                response_text += block.text

            # Create result artifact
            artifact = Artifact(
                name="search_result.txt",
                content=response_text or "No search results found",
                content_type="text/plain"
            )

            # Complete task
            task = await task_updater.complete(
                artifacts=[artifact],
                result_message="Search completed"
            )

            self.logger.info(f"Search Agent completed task: {context.task_id}")
            return task

        except Exception as e:
            self.logger.error(f"Search Agent failed: {e}", exc_info=True)
            task = await task_updater.fail(str(e))
            return task

    async def cancel(
        self,
        context: RequestContext,
        task_updater: TaskUpdater
    ) -> Task:
        """
        Cancel ongoing search operation.

        Args:
            context: Request context
            task_updater: Task lifecycle helper

        Returns:
            Cancelled task
        """
        self.logger.info(f"Cancelling search task {context.task_id}")
        return await task_updater.cancel()
