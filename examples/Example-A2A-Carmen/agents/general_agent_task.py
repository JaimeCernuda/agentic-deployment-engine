"""
General Agent with A2A Task Lifecycle Support.

Uses BaseA2ATaskAgent and GeneralAgentExecutor for full A2A protocol compliance.
Orchestrates tasks across specialized agents using dynamic discovery.
"""
import sys
from pathlib import Path

# Add project root and example directory to path for imports
project_root = Path(__file__).parent.parent.parent.parent
example_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(example_dir))

from base_a2a_task_agent import BaseA2ATaskAgent
from executors.general_executor import GeneralAgentExecutor


class GeneralAgentTask(BaseA2ATaskAgent):
    """
    General Agent with A2A task lifecycle.

    Provides:
    - Orchestration across specialized agents
    - Dynamic agent discovery
    - Multi-turn conversation support
    - Task state management (SUBMITTED → WORKING → COMPLETED)
    - Context management for conversation continuity
    """

    def __init__(self, port=9001, agent_urls_to_discover=None):
        # URLs of agents to discover
        agent_urls_to_discover = agent_urls_to_discover or [
            "http://localhost:9002",  # Math Agent
            "http://localhost:9003",  # Finance Agent
            "http://localhost:9004",  # Search Agent
        ]

        # Create agent executor with discovery
        agent_executor = GeneralAgentExecutor(agent_urls_to_discover)

        super().__init__(
            name="General Agent (Task-based)",
            description="Orchestrates tasks across specialized agents with A2A task lifecycle support",
            port=port,
            agent_executor=agent_executor
        )

    def _get_skills(self):
        """Define general agent skills for A2A discovery"""
        return [
            {
                "id": "general_knowledge",
                "name": "General Knowledge",
                "description": "Answer general knowledge questions on various topics",
                "tags": ["general", "knowledge", "questions"],
                "examples": [
                    "Who discovered gravity?",
                    "What is the capital of France?",
                    "Explain photosynthesis"
                ]
            },
            {
                "id": "agent_orchestration",
                "name": "Agent Orchestration",
                "description": "Delegate tasks to specialized agents (math, finance, search)",
                "tags": ["orchestration", "delegation", "coordination"],
                "examples": [
                    "Calculate 25 + 17 for me",
                    "Convert 100 USD to EUR",
                    "Search for latest AI news"
                ]
            },
            {
                "id": "multi_agent_workflows",
                "name": "Multi-Agent Workflows",
                "description": "Coordinate complex tasks requiring multiple specialized agents",
                "tags": ["workflow", "multi-agent", "complex"],
                "examples": [
                    "Convert 100 USD to EUR and add 50",
                    "Search temperature in Madrid and convert to fahrenheit"
                ]
            }
        ]


def main():
    """Run the General Agent with task support."""
    import os
    port = int(os.getenv("AGENT_PORT", "9001"))

    # URLs of agents to discover
    agent_urls_to_discover = [
        "http://localhost:9002",  # Math Agent
        "http://localhost:9003",  # Finance Agent
        "http://localhost:9004",  # Search Agent
    ]

    agent = GeneralAgentTask(port=port, agent_urls_to_discover=agent_urls_to_discover)
    print(f"Starting General Agent (Task-based) on port {port}...")
    agent.run()


if __name__ == "__main__":
    main()
