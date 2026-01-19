from claude_agent_sdk import tool


@tool(
    name="convert_currency",
    description="Convert between USD, EUR, and GBP currencies",
    input_schema={"amount": float, "from_currency": str, "to_currency": str}
)
async def convert_currency(args):
    """Convert between USD, EUR, and GBP currencies."""
    amount = args["amount"]
    from_currency = args["from_currency"].upper()
    to_currency = args["to_currency"].upper()

    # Exchange rates (simplified, in real scenario would use API)
    rates = {
        ("USD", "EUR"): 0.85,
        ("EUR", "USD"): 1.18,
        ("USD", "GBP"): 0.73,
        ("GBP", "USD"): 1.37,
        ("EUR", "GBP"): 0.86,
        ("GBP", "EUR"): 1.16,
        ("USD", "USD"): 1.0,
        ("EUR", "EUR"): 1.0,
        ("GBP", "GBP"): 1.0,
    }

    rate = rates.get((from_currency, to_currency))
    if not rate:
        return {
            "content": [{"type": "text", "text": f"Error: Unsupported currency conversion from {from_currency} to {to_currency}"}],
            "is_error": True
        }

    result = amount * rate
    return {"content": [{"type": "text", "text": f"Result: {result:.2f} {to_currency}"}]}


@tool(
    name="calculate_interest",
    description="Calculate simple interest (I = P * r * t)",
    input_schema={"principal": float, "rate": float, "time": float}
)
async def calculate_interest(args):
    """Calculate simple interest: I = P * r * t"""
    principal = args["principal"]
    rate = args["rate"]
    time = args["time"]

    interest = principal * rate * time
    total = principal + interest

    return {
        "content": [{
            "type": "text",
            "text": f"Interest: {interest:.2f}, Total Amount: {total:.2f}"
        }]
    }


@tool(
    name="percentage_change",
    description="Calculate percentage change between two values",
    input_schema={"old_value": float, "new_value": float}
)
async def percentage_change(args):
    """Calculate percentage change between two values."""
    old_value = args["old_value"]
    new_value = args["new_value"]

    if old_value == 0:
        return {
            "content": [{"type": "text", "text": "Error: Cannot calculate percentage change from zero"}],
            "is_error": True
        }

    change = ((new_value - old_value) / old_value) * 100
    return {"content": [{"type": "text", "text": f"Result: {change:.2f}%"}]}
