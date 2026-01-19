import sys
from pathlib import Path

# Add project root and example directory to path for imports
project_root = Path(__file__).parent.parent.parent.parent
example_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(example_dir))

from claude_agent_sdk import create_sdk_mcp_server
from src.base_a2a_agent import BaseA2AAgent
from tools.math_tools import add, subtract, convert_units


class MathAgent(BaseA2AAgent):
    """
    Math Agent using MCP server.
    Provides calculation and conversion tools to other agents.
    """

    def __init__(self, port=9002):
        # Create SDK MCP server with tools
        tools_sdk_server = create_sdk_mcp_server(
            name="math_agent",
            version="1.0.0",
            tools=[add, subtract, convert_units]
        )

        system_prompt = (
            "You are the Math Agent. You have access to MCP tools for mathematical operations and unit conversions.\n\n"
            "**IMPORTANT RULES:**\n"
            "1. ALWAYS use your MCP tools to answer queries - NEVER calculate or convert manually.\n"
            "2. For addition operations, use the 'add' tool.\n"
            "3. For subtraction operations, use the 'subtract' tool.\n"
            "4. For unit conversions (meters/kilometers, celsius/fahrenheit), use the 'convert_units' tool.\n"
            "5. If a query requires a tool you have, you MUST call that tool - do not provide answers without using tools.\n"
            "6. After receiving the tool result, present it clearly to the user.\n"
        )

        super().__init__(
            name="Math Agent",
            description="Performs calculations and conversions using MCP tools.",
            port=port,
            sdk_mcp_server=tools_sdk_server,
            system_prompt=system_prompt
        )

    def _get_skills(self):
        """Define tools agent skills for A2A discovery."""
        return [
            {
                "id": "math_operations",
                "name": "Math Operations",
                "description": "Perform mathematical operations like addition and subtraction",
                "tags": ["math", "calculation", "numbers"],
                "examples": [
                    "What is 5 + 3?",
                    "Calculate 100 - 45",
                    "Add 25 and 17"
                ]
            },
            {
                "id": "unit_conversions",
                "name": "Unit Conversions",
                "description": "Convert between meters/kilometers and celsius/fahrenheit",
                "tags": ["conversion", "units", "distance", "temperature"],
                "examples": [
                    "Convert 100 celsius to fahrenheit",
                    "Convert 5000 meters to kilometers",
                    "How many kilometers is 2500 meters?"
                ]
            }
        ]

    def _get_allowed_tools(self):
        """Allow access to registered MCP tools."""
        return [
            "mcp__math_agent__add",
            "mcp__math_agent__subtract",
            "mcp__math_agent__convert_units"
        ]


def main():
    """Run the Math Agent."""
    agent = MathAgent(port=9002)
    print("Starting Math Agent on port 9002...")
    agent.run()


if __name__ == "__main__":
    main()
