"""
Finance Agent Executor with A2A task lifecycle support.

Implements task-based execution for financial operations.
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
    Artifact
)
from tools.finance_tools import convert_currency, percentage_change


class FinanceAgentExecutor(AgentExecutor):
    """
    Finance Agent Executor implementing A2A task lifecycle.

    Provides currency conversion and financial calculations using Claude SDK and MCP tools.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Create SDK MCP server with finance tools
        self.mcp_server = create_sdk_mcp_server(
            name="finance_agent",
            version="1.0.0",
            tools=[convert_currency, percentage_change]
        )

        # System prompt for finance operations
        self.system_prompt = """You are the Finance Agent. You have access to MCP tools for currency conversion and financial calculations.

**IMPORTANT RULES:**
1. ALWAYS use your MCP tools to perform financial calculations - NEVER calculate manually.
2. For currency conversions, use the 'convert_currency' tool.
3. For percentage changes, use the 'percentage_change' tool.
4. If a query requires a tool you have, you MUST call that tool - do not provide answers without using tools.
5. After receiving the tool result, present it clearly to the user.

Be precise with financial data and always use the tools."""

        # Configure Claude SDK options
        self.claude_options = ClaudeAgentOptions(
            mcp_servers={"finance_agent": self.mcp_server},
            allowed_tools=[
                "mcp__finance_agent__convert_currency",
                "mcp__finance_agent__percentage_change"
            ],
            system_prompt=self.system_prompt
        )

    async def execute(
        self,
        context: RequestContext,
        task_updater: TaskUpdater
    ) -> Task:
        """
        Execute finance operation with task lifecycle management.

        Args:
            context: Request context with user query
            task_updater: Task lifecycle helper

        Returns:
            Completed task with result artifact
        """
        query = context.get_user_input()
        self.logger.info(f"Finance Agent executing: {query}")

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
                name="finance_result.txt",
                content=response_text or "No response generated",
                content_type="text/plain"
            )

            # Complete task
            task = await task_updater.complete(
                artifacts=[artifact],
                result_message="Finance operation completed"
            )

            self.logger.info(f"Finance Agent completed task: {context.task_id}")
            return task

        except Exception as e:
            self.logger.error(f"Finance Agent failed: {e}", exc_info=True)
            task = await task_updater.fail(str(e))
            return task

    async def cancel(
        self,
        context: RequestContext,
        task_updater: TaskUpdater
    ) -> Task:
        """
        Cancel ongoing finance operation.

        Args:
            context: Request context
            task_updater: Task lifecycle helper

        Returns:
            Cancelled task
        """
        self.logger.info(f"Cancelling finance task {context.task_id}")
        return await task_updater.cancel()
