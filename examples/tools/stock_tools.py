"""Stock MCP Tools - SDK-compatible implementation.

Provides stock price tools for claude-code-sdk integration.
Uses mock data for demonstration purposes.
"""

import random
from datetime import datetime, timedelta
from typing import Any

from claude_agent_sdk import tool

# Mock stock data with realistic prices
STOCK_DATA: dict[str, dict[str, Any]] = {
    "AAPL": {
        "name": "Apple Inc.",
        "price": 178.50,
        "currency": "USD",
        "change_percent": 1.23,
        "market_cap": "2.8T",
        "sector": "Technology",
    },
    "GOOGL": {
        "name": "Alphabet Inc.",
        "price": 141.25,
        "currency": "USD",
        "change_percent": -0.45,
        "market_cap": "1.8T",
        "sector": "Technology",
    },
    "MSFT": {
        "name": "Microsoft Corporation",
        "price": 378.90,
        "currency": "USD",
        "change_percent": 0.87,
        "market_cap": "2.9T",
        "sector": "Technology",
    },
    "AMZN": {
        "name": "Amazon.com Inc.",
        "price": 178.15,
        "currency": "USD",
        "change_percent": 2.15,
        "market_cap": "1.9T",
        "sector": "Consumer Cyclical",
    },
    "TSLA": {
        "name": "Tesla Inc.",
        "price": 248.30,
        "currency": "USD",
        "change_percent": -1.82,
        "market_cap": "790B",
        "sector": "Automotive",
    },
    "NVDA": {
        "name": "NVIDIA Corporation",
        "price": 495.80,
        "currency": "USD",
        "change_percent": 3.45,
        "market_cap": "1.2T",
        "sector": "Technology",
    },
}


def _add_price_jitter(price: float) -> float:
    """Add small random jitter to simulate real-time prices."""
    jitter = random.uniform(-0.5, 0.5)
    return round(price + jitter, 2)


@tool(
    "get_stock_price",
    "Get current stock price and information for a ticker symbol",
    {"symbol": str},
)
async def get_stock_price(args: dict[str, Any]) -> dict[str, Any]:
    """Get stock price data for a ticker symbol."""
    symbol = args.get("symbol", "").upper().strip()

    if symbol not in STOCK_DATA:
        available = ", ".join(sorted(STOCK_DATA.keys()))
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Stock data not found for '{symbol}'. Available symbols: {available}",
                }
            ]
        }

    data = STOCK_DATA[symbol].copy()
    # Simulate real-time price changes
    current_price = _add_price_jitter(data["price"])
    change_sign = "+" if data["change_percent"] >= 0 else ""

    result = (
        f"📈 {data['name']} ({symbol})\n"
        f"Price: ${current_price:.2f} {data['currency']}\n"
        f"Change: {change_sign}{data['change_percent']:.2f}%\n"
        f"Market Cap: {data['market_cap']}\n"
        f"Sector: {data['sector']}\n"
        f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    return {"content": [{"type": "text", "text": result}]}


@tool(
    "get_stock_history",
    "Get historical price data for a stock over a specified period",
    {"symbol": str, "days": int},
)
async def get_stock_history(args: dict[str, Any]) -> dict[str, Any]:
    """Get historical stock price data."""
    symbol = args.get("symbol", "").upper().strip()
    days = min(args.get("days", 7), 30)  # Cap at 30 days

    if symbol not in STOCK_DATA:
        return {
            "content": [
                {"type": "text", "text": f"Stock data not found for '{symbol}'"}
            ]
        }

    base_price = STOCK_DATA[symbol]["price"]

    # Generate mock historical data
    history = []
    for i in range(days, 0, -1):
        date = datetime.now() - timedelta(days=i)
        # Simulate price fluctuation
        variation = random.uniform(-5, 5)
        price = round(base_price + variation, 2)
        history.append(f"{date.strftime('%Y-%m-%d')}: ${price:.2f}")

    result = f"📊 {STOCK_DATA[symbol]['name']} ({symbol}) - {days} Day History\n"
    result += "\n".join(history)

    return {"content": [{"type": "text", "text": result}]}


@tool(
    "compare_stocks",
    "Compare two stocks by their key metrics",
    {"symbol1": str, "symbol2": str},
)
async def compare_stocks(args: dict[str, Any]) -> dict[str, Any]:
    """Compare two stocks."""
    symbol1 = args.get("symbol1", "").upper().strip()
    symbol2 = args.get("symbol2", "").upper().strip()

    errors = []
    if symbol1 not in STOCK_DATA:
        errors.append(f"'{symbol1}' not found")
    if symbol2 not in STOCK_DATA:
        errors.append(f"'{symbol2}' not found")

    if errors:
        available = ", ".join(sorted(STOCK_DATA.keys()))
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error: {', '.join(errors)}. Available: {available}",
                }
            ]
        }

    stock1 = STOCK_DATA[symbol1]
    stock2 = STOCK_DATA[symbol2]

    result = f"📊 Stock Comparison: {symbol1} vs {symbol2}\n\n"
    result += f"{'Metric':<15} {symbol1:<12} {symbol2:<12}\n"
    result += "-" * 40 + "\n"
    result += f"{'Price':<15} ${stock1['price']:<11.2f} ${stock2['price']:<11.2f}\n"
    result += f"{'Change %':<15} {stock1['change_percent']:+.2f}%{'':<7} {stock2['change_percent']:+.2f}%\n"
    result += (
        f"{'Market Cap':<15} {stock1['market_cap']:<12} {stock2['market_cap']:<12}\n"
    )
    result += f"{'Sector':<15} {stock1['sector']:<12} {stock2['sector']:<12}\n"

    return {"content": [{"type": "text", "text": result}]}


@tool("list_stocks", "List all available stock symbols with brief info", {})
async def list_stocks(args: dict[str, Any]) -> dict[str, Any]:
    """List all available stocks."""
    result = "📈 Available Stocks:\n\n"

    for symbol, data in sorted(STOCK_DATA.items()):
        change_sign = "+" if data["change_percent"] >= 0 else ""
        result += f"• {symbol}: {data['name']} - ${data['price']:.2f} ({change_sign}{data['change_percent']:.2f}%)\n"

    return {"content": [{"type": "text", "text": result}]}
