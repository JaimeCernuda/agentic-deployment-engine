"""Calculator Agent using claude-code-sdk with SDK MCP server.

Provides financial calculations through A2A protocol.
"""

import os
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server

from examples.tools.calculator_tools import (
    calculate_compound_return,
    calculate_dividend_yield,
    calculate_market_cap,
    calculate_pe_ratio,
    calculate_percentage_change,
)
from src import BaseA2AAgent
from src.security import PermissionPreset


class CalculatorAgent(BaseA2AAgent):
    """Calculator Agent for financial calculations.

    Provides tools for percentage changes, P/E ratios, dividend yields,
    market cap calculations, and compound returns.
    """

    def __init__(
        self,
        port: int = 9004,
        permission_preset: PermissionPreset = PermissionPreset.FULL_ACCESS,
    ):
        # Create SDK MCP server with calculator tools
        calculator_sdk_server = create_sdk_mcp_server(
            name="calculator_agent",
            version="1.0.0",
            tools=[
                calculate_percentage_change,
                calculate_pe_ratio,
                calculate_dividend_yield,
                calculate_market_cap,
                calculate_compound_return,
            ],
        )

        # Custom system prompt for calculator agent
        system_prompt = """You are a Calculator Agent specialized in financial calculations and analysis.

**IMPORTANT: You MUST use the SDK MCP tools available to you:**
- `mcp__calculator_agent__calculate_percentage_change`: Calculate % change between two values
- `mcp__calculator_agent__calculate_pe_ratio`: Calculate Price-to-Earnings ratio
- `mcp__calculator_agent__calculate_dividend_yield`: Calculate dividend yield percentage
- `mcp__calculator_agent__calculate_market_cap`: Calculate market capitalization
- `mcp__calculator_agent__calculate_compound_return`: Calculate CAGR over a period

**How to respond to queries:**
1. Identify what calculation is needed
2. Use the appropriate tool with the correct parameters
3. Provide the result with context and interpretation

**DO NOT:**
- Perform calculations manually - always use the tools
- Guess or estimate values - ask for specific numbers if not provided
- Provide investment advice - focus on calculations only"""

        super().__init__(
            name="Calculator Agent",
            description="Financial calculation tools using SDK MCP",
            port=port,
            sdk_mcp_server=calculator_sdk_server,
            system_prompt=system_prompt,
            permission_preset=permission_preset,
        )

    def _get_skills(self) -> list[dict[str, Any]]:
        """Define calculator agent skills for A2A discovery."""
        return [
            {
                "id": "percentage_change",
                "name": "Percentage Change Calculator",
                "description": "Calculate percentage change between two values",
                "tags": ["calculator", "percentage", "change"],
                "examples": [
                    "What's the % change from 100 to 150?",
                    "Calculate the percentage increase from 50 to 75",
                ],
            },
            {
                "id": "pe_ratio",
                "name": "P/E Ratio Calculator",
                "description": "Calculate Price-to-Earnings ratio with interpretation",
                "tags": ["calculator", "pe", "valuation"],
                "examples": [
                    "Calculate P/E ratio for a $150 stock with $5 EPS",
                    "What's the P/E if price is 200 and earnings are 8?",
                ],
            },
            {
                "id": "dividend_yield",
                "name": "Dividend Yield Calculator",
                "description": "Calculate dividend yield percentage",
                "tags": ["calculator", "dividend", "yield"],
                "examples": [
                    "Calculate yield for $3 dividend on $100 stock",
                    "What's the dividend yield?",
                ],
            },
            {
                "id": "market_cap",
                "name": "Market Cap Calculator",
                "description": "Calculate market capitalization from shares and price",
                "tags": ["calculator", "market-cap", "valuation"],
                "examples": [
                    "Calculate market cap for 1 billion shares at $150",
                    "What's the market cap?",
                ],
            },
            {
                "id": "compound_return",
                "name": "CAGR Calculator",
                "description": "Calculate compound annual growth rate",
                "tags": ["calculator", "cagr", "returns"],
                "examples": [
                    "Calculate CAGR from $1000 to $2000 over 5 years",
                    "What's the annual return?",
                ],
            },
        ]

    def _get_allowed_tools(self) -> list[str]:
        """Allow Calculator SDK MCP tools."""
        return [
            "mcp__calculator_agent__calculate_percentage_change",
            "mcp__calculator_agent__calculate_pe_ratio",
            "mcp__calculator_agent__calculate_dividend_yield",
            "mcp__calculator_agent__calculate_market_cap",
            "mcp__calculator_agent__calculate_compound_return",
        ]


def main():
    """Run the Calculator Agent."""
    port = int(os.getenv("AGENT_PORT", "9004"))

    # Read permission preset from environment
    preset_name = os.getenv("AGENT_PERMISSION_PRESET", "full_access").lower()
    preset_map = {
        "full_access": PermissionPreset.FULL_ACCESS,
        "read_only": PermissionPreset.READ_ONLY,
        "communication_only": PermissionPreset.COMMUNICATION_ONLY,
    }
    permission_preset = preset_map.get(preset_name, PermissionPreset.FULL_ACCESS)

    agent = CalculatorAgent(port=port, permission_preset=permission_preset)
    print(f"Starting Calculator Agent on port {port}...")
    print(f"Permission preset: {permission_preset.value}")
    print("Using SDK MCP server with financial calculation tools")
    agent.run()


if __name__ == "__main__":
    main()
