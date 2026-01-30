"""Calculator MCP Tools - SDK-compatible implementation.

Provides financial calculation tools for claude-code-sdk integration.
"""

from typing import Any

from claude_agent_sdk import tool


@tool(
    "calculate_percentage_change",
    "Calculate the percentage change between two values",
    {"old_value": float, "new_value": float},
)
async def calculate_percentage_change(args: dict[str, Any]) -> dict[str, Any]:
    """Calculate percentage change between two values."""
    old_value = args.get("old_value", 0)
    new_value = args.get("new_value", 0)

    if old_value == 0:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: Cannot calculate percentage change from zero",
                }
            ]
        }

    change = ((new_value - old_value) / old_value) * 100
    direction = "increase" if change > 0 else "decrease" if change < 0 else "no change"

    result = (
        f"Percentage Change: {abs(change):.2f}% {direction}\n"
        f"From: {old_value}\n"
        f"To: {new_value}\n"
        f"Absolute Change: {new_value - old_value:.2f}"
    )

    return {"content": [{"type": "text", "text": result}]}


@tool(
    "calculate_pe_ratio",
    "Calculate the Price-to-Earnings (P/E) ratio",
    {"stock_price": float, "earnings_per_share": float},
)
async def calculate_pe_ratio(args: dict[str, Any]) -> dict[str, Any]:
    """Calculate P/E ratio."""
    price = args.get("stock_price", 0)
    eps = args.get("earnings_per_share", 0)

    if eps == 0:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: Cannot calculate P/E ratio with zero EPS",
                }
            ]
        }

    pe_ratio = price / eps

    # Provide interpretation
    if pe_ratio < 0:
        interpretation = "Negative P/E indicates the company is losing money"
    elif pe_ratio < 15:
        interpretation = "Low P/E - potentially undervalued or slow growth expected"
    elif pe_ratio < 25:
        interpretation = "Moderate P/E - reasonable valuation"
    else:
        interpretation = "High P/E - high growth expected or potentially overvalued"

    result = (
        f"P/E Ratio: {pe_ratio:.2f}\n"
        f"Stock Price: ${price:.2f}\n"
        f"EPS: ${eps:.2f}\n"
        f"Interpretation: {interpretation}"
    )

    return {"content": [{"type": "text", "text": result}]}


@tool(
    "calculate_dividend_yield",
    "Calculate the dividend yield percentage",
    {"annual_dividend": float, "stock_price": float},
)
async def calculate_dividend_yield(args: dict[str, Any]) -> dict[str, Any]:
    """Calculate dividend yield."""
    dividend = args.get("annual_dividend", 0)
    price = args.get("stock_price", 0)

    if price == 0:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: Cannot calculate yield with zero stock price",
                }
            ]
        }

    yield_pct = (dividend / price) * 100

    # Provide interpretation
    if yield_pct < 2:
        interpretation = "Low yield - typical for growth stocks"
    elif yield_pct < 4:
        interpretation = "Moderate yield - balanced income/growth"
    elif yield_pct < 6:
        interpretation = "Good yield - income-focused stock"
    else:
        interpretation = "High yield - verify sustainability"

    result = (
        f"Dividend Yield: {yield_pct:.2f}%\n"
        f"Annual Dividend: ${dividend:.2f}\n"
        f"Stock Price: ${price:.2f}\n"
        f"Interpretation: {interpretation}"
    )

    return {"content": [{"type": "text", "text": result}]}


@tool(
    "calculate_market_cap",
    "Calculate market capitalization from shares and price",
    {"shares_outstanding": float, "stock_price": float},
)
async def calculate_market_cap(args: dict[str, Any]) -> dict[str, Any]:
    """Calculate market cap."""
    shares = args.get("shares_outstanding", 0)
    price = args.get("stock_price", 0)

    market_cap = shares * price

    # Format based on size
    if market_cap >= 1_000_000_000_000:
        formatted = f"${market_cap / 1_000_000_000_000:.2f} Trillion"
        category = "Mega Cap"
    elif market_cap >= 10_000_000_000:
        formatted = f"${market_cap / 1_000_000_000:.2f} Billion"
        category = "Large Cap"
    elif market_cap >= 2_000_000_000:
        formatted = f"${market_cap / 1_000_000_000:.2f} Billion"
        category = "Mid Cap"
    elif market_cap >= 300_000_000:
        formatted = f"${market_cap / 1_000_000:.2f} Million"
        category = "Small Cap"
    else:
        formatted = f"${market_cap / 1_000_000:.2f} Million"
        category = "Micro Cap"

    result = (
        f"Market Cap: {formatted}\n"
        f"Category: {category}\n"
        f"Shares Outstanding: {shares:,.0f}\n"
        f"Stock Price: ${price:.2f}"
    )

    return {"content": [{"type": "text", "text": result}]}


@tool(
    "calculate_compound_return",
    "Calculate compound annual growth rate (CAGR)",
    {"initial_value": float, "final_value": float, "years": float},
)
async def calculate_compound_return(args: dict[str, Any]) -> dict[str, Any]:
    """Calculate CAGR."""
    initial = args.get("initial_value", 0)
    final = args.get("final_value", 0)
    years = args.get("years", 0)

    if initial <= 0 or years <= 0:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: Initial value and years must be positive",
                }
            ]
        }

    cagr = ((final / initial) ** (1 / years) - 1) * 100
    total_return = ((final - initial) / initial) * 100

    result = (
        f"CAGR: {cagr:.2f}% per year\n"
        f"Total Return: {total_return:.2f}%\n"
        f"Initial Value: ${initial:,.2f}\n"
        f"Final Value: ${final:,.2f}\n"
        f"Time Period: {years:.1f} years"
    )

    return {"content": [{"type": "text", "text": result}]}
