"""
Math Agent with A2A Task Lifecycle Support.

Uses BaseA2ATaskAgent and MathAgentExecutor for full A2A protocol compliance.
"""
import sys
from pathlib import Path

# Add project root and example directory to path for imports
project_root = Path(__file__).parent.parent.parent.parent
example_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(example_dir))

from base_a2a_task_agent import BaseA2ATaskAgent
from executors.math_executor import MathAgentExecutor


class MathAgentTask(BaseA2ATaskAgent):
    """
    Math Agent with A2A task lifecycle.

    Provides:
    - Mathematical operations (add, subtract)
    - Unit conversions (meters/km, celsius/fahrenheit)
    - Task state management (SUBMITTED → WORKING → COMPLETED)
    - Context management for multi-turn conversations
    """

    def __init__(self, port=9002):
        # Create agent executor
        agent_executor = MathAgentExecutor()

        super().__init__(
            name="Math Agent (Task-based)",
            description="Performs calculations and conversions with A2A task lifecycle support",
            port=port,
            agent_executor=agent_executor
        )

    def _get_skills(self):
        """Define math agent skills for A2A discovery"""
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


def main():
    """Run the Math Agent with task support."""
    import os
    port = int(os.getenv("AGENT_PORT", "9002"))

    agent = MathAgentTask(port=port)
    print(f"Starting Math Agent (Task-based) on port {port}...")
    agent.run()


if __name__ == "__main__":
    main()
