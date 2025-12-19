from claude_agent_sdk import tool


@tool(
    name="add",
    description="Add two numbers together",
    input_schema={"a": float, "b": float}
)
async def add(args):
    """Add two numbers together."""
    result = args["a"] + args["b"]
    return {"content": [{"type": "text", "text": f"Result: {result}"}]}


@tool(
    name="subtract",
    description="Subtract one number from another",
    input_schema={"a": float, "b": float}
)
async def subtract(args):
    """Subtract one number from another."""
    result = args["a"] - args["b"]
    return {"content": [{"type": "text", "text": f"Result: {result}"}]}


@tool(
    name="convert_units",
    description="Convert units between meters/kilometers or celsius/fahrenheit",
    input_schema={"value": float, "from_unit": str, "to_unit": str}
)
async def convert_units(args):
    """Convert units between meters/kilometers or celsius/fahrenheit."""
    value = args["value"]
    from_unit = args["from_unit"]
    to_unit = args["to_unit"]

    conversions = {
        ("meters", "kilometers"): lambda x: x / 1000,
        ("kilometers", "meters"): lambda x: x * 1000,
        ("celsius", "fahrenheit"): lambda x: (x * 9/5) + 32,
        ("fahrenheit", "celsius"): lambda x: (x - 32) * 5/9,
    }
    func = conversions.get((from_unit, to_unit))
    if not func:
        return {
            "content": [{"type": "text", "text": f"Error: Unsupported conversion from {from_unit} to {to_unit}"}],
            "is_error": True
        }

    result = func(value)
    return {"content": [{"type": "text", "text": f"Result: {result} {to_unit}"}]}
