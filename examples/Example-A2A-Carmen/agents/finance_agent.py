import sys
from pathlib import Path

# Add project root and example directory to path for imports
project_root = Path(__file__).parent.parent.parent.parent
example_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(example_dir))

from claude_agent_sdk import create_sdk_mcp_server
from src.base_a2a_agent import BaseA2AAgent
from tools.finance_tools import convert_currency, calculate_interest, percentage_change


class FinanceAgent(BaseA2AAgent):
    """
    Finance Agent using MCP server.
    Provides financial calculation and currency conversion tools to other agents.
    """

    def __init__(self, port=9003):
        # Create SDK MCP server with finance tools
        finance_sdk_server = create_sdk_mcp_server(
            name="finance_agent",
            version="1.0.0",
            tools=[convert_currency, calculate_interest, percentage_change]
        )

        system_prompt = (
            "You are the Finance Agent. You have access to MCP tools for financial operations and currency conversions.\n\n"
            "**IMPORTANT RULES:**\n"
            "1. ALWAYS use your MCP tools to answer queries - NEVER calculate or convert manually.\n"
            "2. For currency conversions (USD, EUR, GBP), use the 'convert_currency' tool.\n"
            "3. For simple interest calculations, use the 'calculate_interest' tool.\n"
            "4. For percentage change calculations, use the 'percentage_change' tool.\n"
            "5. If a query requires a tool you have, you MUST call that tool - do not provide answers without using tools.\n"
            "6. After receiving the tool result, present it clearly to the user.\n"
        )

        super().__init__(
            name="Finance Agent",
            description="Performs financial calculations and currency conversions using MCP tools.",
            port=port,
            sdk_mcp_server=finance_sdk_server,
            system_prompt=system_prompt
        )

    def _get_skills(self):
        """Define finance agent skills for A2A discovery."""
        return [
            {
                "id": "currency_conversion",
                "name": "Currency Conversion",
                "description": "Convert between USD, EUR, and GBP currencies",
                "tags": ["finance", "currency", "conversion", "money"],
                "examples": [
                    "Convert 100 USD to EUR",
                    "How much is 50 GBP in USD?",
                    "Convert 200 EUR to GBP"
                ]
            },
            {
                "id": "financial_calculations",
                "name": "Financial Calculations",
                "description": "Calculate interest and percentage changes",
                "tags": ["finance", "interest", "percentage", "calculations"],
                "examples": [
                    "Calculate simple interest for 1000 at 5% for 2 years",
                    "What's the percentage change from 100 to 150?",
                    "Calculate interest on 5000 principal at 3% rate for 5 years"
                ]
            }
        ]

    def _get_allowed_tools(self):
        """Allow access to registered MCP finance tools."""
        return [
            "mcp__finance_agent__convert_currency",
            "mcp__finance_agent__calculate_interest",
            "mcp__finance_agent__percentage_change"
        ]


def main():
    """Run the Finance Agent."""
    agent = FinanceAgent(port=9003)
    print("Starting Finance Agent on port 9003...")
    agent.run()


if __name__ == "__main__":
    main()
