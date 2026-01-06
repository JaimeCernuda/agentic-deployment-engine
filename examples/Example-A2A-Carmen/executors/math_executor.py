"""
Math Agent Executor with A2A task lifecycle support.

Implements task-based execution for mathematical operations and conversions.
"""
import sys
from pathlib import Path
import logging

# Add project root and example directory to path
project_root = Path(__file__).parent.parent.parent.parent
example_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(example_dir))

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, create_sdk_mcp_server
from base_a2a_task_agent import (
    AgentExecutor,
    RequestContext,
    TaskUpdater,
    Task,
    TaskState,
    Artifact
)
from tools.math_tools import add, subtract, convert_units


class MathAgentExecutor(AgentExecutor):
    """
    Math Agent Executor implementing A2A task lifecycle.

    Provides mathematical operations and unit conversions using Claude SDK and MCP tools.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Create SDK MCP server with math tools
        self.mcp_server = create_sdk_mcp_server(
            name="math_agent",
            version="1.0.0",
            tools=[add, subtract, convert_units]
        )

        # System prompt for math operations
        self.system_prompt = """You are the Math Agent. You have access to MCP tools for mathematical operations and unit conversions.

**IMPORTANT RULES:**
1. ALWAYS use your MCP tools to answer queries - NEVER calculate or convert manually.
2. For addition operations, use the 'add' tool.
3. For subtraction operations, use the 'subtract' tool.
4. For unit conversions (meters/kilometers, celsius/fahrenheit), use the 'convert_units' tool.
5. If a query requires a tool you have, you MUST call that tool - do not provide answers without using tools.
6. After receiving the tool result, present it clearly to the user in a concise manner.

Be precise and always use the tools for calculations."""

        # Configure Claude SDK options
        self.claude_options = ClaudeAgentOptions(
            mcp_servers={"math_agent": self.mcp_server},
            allowed_tools=[
                "mcp__math_agent__add",
                "mcp__math_agent__subtract",
                "mcp__math_agent__convert_units"
            ],
            system_prompt=self.system_prompt
        )

    async def execute(
        self,
        context: RequestContext,
        task_updater: TaskUpdater
    ) -> Task:
        """
        Execute math operation with task lifecycle management.

        Args:
            context: Request context with user query
            task_updater: Task lifecycle helper

        Returns:
            Completed task with result artifact
        """
        query = context.get_user_input()
        self.logger.info(f"Math Agent executing: {query}")

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
                name="math_result.txt",
                content=response_text or "No response generated",
                content_type="text/plain"
            )

            # Complete task
            task = await task_updater.complete(
                artifacts=[artifact],
                result_message="Math operation completed"
            )

            self.logger.info(f"Math Agent completed task: {context.task_id}")
            return task

        except Exception as e:
            self.logger.error(f"Math Agent failed: {e}", exc_info=True)
            task = await task_updater.fail(str(e))
            return task

    async def cancel(
        self,
        context: RequestContext,
        task_updater: TaskUpdater
    ) -> Task:
        """
        Cancel ongoing math operation.

        Args:
            context: Request context
            task_updater: Task lifecycle helper

        Returns:
            Cancelled task
        """
        self.logger.info(f"Cancelling math task {context.task_id}")
        return await task_updater.cancel()
