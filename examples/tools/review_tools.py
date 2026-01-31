"""Code Review MCP Tools.

Provides tools for code review analysis:
- Linting (style/formatting)
- Security scanning
- Complexity metrics
"""

from typing import Any

from claude_agent_sdk import tool

# Mock data for demonstration
LINT_ISSUES = {
    "src/main.py": [
        {"line": 12, "type": "style", "message": "Line too long (95 > 88 characters)"},
        {"line": 45, "type": "style", "message": "Missing docstring"},
    ],
    "src/utils.py": [
        {"line": 3, "type": "import", "message": "Unused import 'os'"},
    ],
}

SECURITY_ISSUES = {
    "src/auth.py": [
        {
            "line": 23,
            "severity": "high",
            "type": "hardcoded_secret",
            "message": "Potential hardcoded API key detected",
        },
    ],
    "src/db.py": [
        {
            "line": 67,
            "severity": "medium",
            "type": "sql_injection",
            "message": "Possible SQL injection vulnerability",
        },
    ],
}

COMPLEXITY_DATA = {
    "src/main.py": {
        "cyclomatic_complexity": 12,
        "cognitive_complexity": 8,
        "lines_of_code": 145,
        "functions": 6,
        "max_nesting": 3,
    },
    "src/utils.py": {
        "cyclomatic_complexity": 5,
        "cognitive_complexity": 3,
        "lines_of_code": 78,
        "functions": 4,
        "max_nesting": 2,
    },
}


@tool(
    "run_linter",
    "Run code linter (ruff/eslint) on specified files",
    {"file_path": str},
)
async def run_linter(args: dict[str, Any]) -> dict[str, Any]:
    """Run linter on a file and return issues."""
    file_path = args.get("file_path", "")

    if file_path in LINT_ISSUES:
        issues = LINT_ISSUES[file_path]
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Found {len(issues)} linting issues in {file_path}:\n"
                    + "\n".join(
                        f"- Line {i['line']}: [{i['type']}] {i['message']}"
                        for i in issues
                    ),
                }
            ]
        }

    return {
        "content": [{"type": "text", "text": f"No linting issues found in {file_path}"}]
    }


@tool(
    "list_files_to_review",
    "Get list of files that should be reviewed",
    {},
)
async def list_files_to_review(args: dict[str, Any]) -> dict[str, Any]:
    """List files available for review."""
    files = list(
        set(LINT_ISSUES.keys())
        | set(SECURITY_ISSUES.keys())
        | set(COMPLEXITY_DATA.keys())
    )
    return {
        "content": [
            {
                "type": "text",
                "text": "Files to review:\n" + "\n".join(f"- {f}" for f in files),
            }
        ]
    }


@tool(
    "security_scan",
    "Run security scan (bandit/detect-secrets) on specified files",
    {"file_path": str},
)
async def security_scan(args: dict[str, Any]) -> dict[str, Any]:
    """Run security scan on a file."""
    file_path = args.get("file_path", "")

    if file_path in SECURITY_ISSUES:
        issues = SECURITY_ISSUES[file_path]
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Found {len(issues)} security issues in {file_path}:\n"
                    + "\n".join(
                        f"- Line {i['line']}: [{i['severity'].upper()}] {i['type']}: {i['message']}"
                        for i in issues
                    ),
                }
            ]
        }

    return {
        "content": [
            {"type": "text", "text": f"No security issues found in {file_path}"}
        ]
    }


@tool(
    "analyze_complexity",
    "Analyze code complexity metrics for a file",
    {"file_path": str},
)
async def analyze_complexity(args: dict[str, Any]) -> dict[str, Any]:
    """Analyze complexity metrics for a file."""
    file_path = args.get("file_path", "")

    if file_path in COMPLEXITY_DATA:
        data = COMPLEXITY_DATA[file_path]
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Complexity analysis for {file_path}:\n"
                    f"- Cyclomatic Complexity: {data['cyclomatic_complexity']}\n"
                    f"- Cognitive Complexity: {data['cognitive_complexity']}\n"
                    f"- Lines of Code: {data['lines_of_code']}\n"
                    f"- Functions: {data['functions']}\n"
                    f"- Max Nesting: {data['max_nesting']}",
                }
            ]
        }

    return {
        "content": [{"type": "text", "text": f"No complexity data for {file_path}"}]
    }


# Export tools for SDK MCP server
LINTER_TOOLS = [run_linter, list_files_to_review]
SECURITY_TOOLS = [security_scan, list_files_to_review]
COMPLEXITY_TOOLS = [analyze_complexity, list_files_to_review]
