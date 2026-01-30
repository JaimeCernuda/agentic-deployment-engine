"""Stock Agent using claude-code-sdk with SDK MCP server.

Provides stock market information and analysis through A2A protocol.
"""

import os
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server

from examples.tools.stock_tools import (
    compare_stocks,
    get_stock_history,
    get_stock_price,
    list_stocks,
)
from src import BaseA2AAgent
from src.security import PermissionPreset


class StockAgent(BaseA2AAgent):
    """Stock Agent that uses SDK MCP server via claude-code-sdk.

    Inherits A2A capabilities and uses claude-code-sdk with in-process
    MCP server for stock market functionality.
    """

    def __init__(
        self,
        port: int = 9003,
        permission_preset: PermissionPreset = PermissionPreset.FULL_ACCESS,
    ):
        # Create SDK MCP server with stock tools
        stock_sdk_server = create_sdk_mcp_server(
            name="stock_agent",
            version="1.0.0",
            tools=[get_stock_price, get_stock_history, compare_stocks, list_stocks],
        )

        # Custom system prompt for stock agent
        system_prompt = """You are a Stock Agent specialized in providing stock market information and analysis.

**IMPORTANT: You MUST use the SDK MCP tools available to you:**
- `mcp__stock_agent__get_stock_price`: Get current price and info for a stock symbol
- `mcp__stock_agent__get_stock_history`: Get historical price data for a stock
- `mcp__stock_agent__compare_stocks`: Compare two stocks by key metrics
- `mcp__stock_agent__list_stocks`: List all available stock symbols

**How to respond to queries:**
1. When asked about a specific stock, use get_stock_price with the ticker symbol
2. For historical data, use get_stock_history with the symbol and number of days
3. For comparisons, use compare_stocks with both ticker symbols
4. When asked what's available, use list_stocks

**Supported Symbols:** AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA

**DO NOT:**
- Guess stock prices - always use the tools
- Provide financial advice or recommendations
- Make predictions about future prices"""

        super().__init__(
            name="Stock Agent",
            description="Stock market data and analysis using SDK MCP tools",
            port=port,
            sdk_mcp_server=stock_sdk_server,
            system_prompt=system_prompt,
            permission_preset=permission_preset,
        )

    def _get_skills(self) -> list[dict[str, Any]]:
        """Define stock agent skills for A2A discovery."""
        return [
            {
                "id": "stock_price",
                "name": "Stock Price Lookup",
                "description": "Get current stock prices and company information",
                "tags": ["stocks", "finance", "price"],
                "examples": [
                    "What's the price of AAPL?",
                    "Get me NVDA stock info",
                    "How is Microsoft doing?",
                ],
            },
            {
                "id": "stock_history",
                "name": "Stock History",
                "description": "Get historical stock price data",
                "tags": ["stocks", "history", "trends"],
                "examples": [
                    "Show me TSLA history for the last 7 days",
                    "What was GOOGL's price trend this week?",
                ],
            },
            {
                "id": "stock_comparison",
                "name": "Stock Comparison",
                "description": "Compare two stocks by key metrics",
                "tags": ["stocks", "comparison", "analysis"],
                "examples": [
                    "Compare AAPL and MSFT",
                    "How does NVDA compare to TSLA?",
                ],
            },
            {
                "id": "stock_list",
                "name": "Available Stocks",
                "description": "List all available stock symbols",
                "tags": ["stocks", "list"],
                "examples": [
                    "What stocks can you look up?",
                    "List available symbols",
                ],
            },
        ]

    def _get_allowed_tools(self) -> list[str]:
        """Allow Stock SDK MCP tools."""
        return [
            "mcp__stock_agent__get_stock_price",
            "mcp__stock_agent__get_stock_history",
            "mcp__stock_agent__compare_stocks",
            "mcp__stock_agent__list_stocks",
        ]


def main():
    """Run the Stock Agent."""
    port = int(os.getenv("AGENT_PORT", "9003"))

    # Read permission preset from environment
    preset_name = os.getenv("AGENT_PERMISSION_PRESET", "full_access").lower()
    preset_map = {
        "full_access": PermissionPreset.FULL_ACCESS,
        "read_only": PermissionPreset.READ_ONLY,
        "communication_only": PermissionPreset.COMMUNICATION_ONLY,
    }
    permission_preset = preset_map.get(preset_name, PermissionPreset.FULL_ACCESS)

    agent = StockAgent(port=port, permission_preset=permission_preset)
    print(f"Starting Stock Agent on port {port}...")
    print(f"Permission preset: {permission_preset.value}")
    print("Using SDK MCP server with stock tools")
    agent.run()


if __name__ == "__main__":
    main()
