"""
Finance Agent with A2A Task Lifecycle Support.

Uses BaseA2ATaskAgent and FinanceAgentExecutor for full A2A protocol compliance.
"""
import sys
from pathlib import Path

# Add project root and example directory to path for imports
project_root = Path(__file__).parent.parent.parent.parent
example_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(example_dir))

from base_a2a_task_agent import BaseA2ATaskAgent
from executors.finance_executor import FinanceAgentExecutor


class FinanceAgentTask(BaseA2ATaskAgent):
    """
    Finance Agent with A2A task lifecycle.

    Provides:
    - Currency conversion
    - Percentage change calculations
    - Task state management (SUBMITTED → WORKING → COMPLETED)
    - Context management for multi-turn conversations
    """

    def __init__(self, port=9003):
        # Create agent executor
        agent_executor = FinanceAgentExecutor()

        super().__init__(
            name="Finance Agent (Task-based)",
            description="Handles financial operations with A2A task lifecycle support",
            port=port,
            agent_executor=agent_executor
        )

    def _get_skills(self):
        """Define finance agent skills for A2A discovery"""
        return [
            {
                "id": "currency_conversion",
                "name": "Currency Conversion",
                "description": "Convert between different currencies (USD, EUR, GBP, JPY)",
                "tags": ["finance", "currency", "exchange", "money"],
                "examples": [
                    "Convert 100 USD to EUR",
                    "How much is 50 EUR in GBP?",
                    "Convert 1000 JPY to USD"
                ]
            },
            {
                "id": "percentage_calculations",
                "name": "Percentage Change",
                "description": "Calculate percentage changes between values",
                "tags": ["finance", "percentage", "change", "growth"],
                "examples": [
                    "What is the percentage change from 50 to 75?",
                    "Calculate percentage increase from 100 to 150",
                    "Percentage change from 200 to 180"
                ]
            }
        ]


def main():
    """Run the Finance Agent with task support."""
    import os
    port = int(os.getenv("AGENT_PORT", "9003"))

    agent = FinanceAgentTask(port=port)
    print(f"Starting Finance Agent (Task-based) on port {port}...")
    agent.run()


if __name__ == "__main__":
    main()
