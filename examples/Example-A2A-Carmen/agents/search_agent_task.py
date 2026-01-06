"""
Search Agent with A2A Task Lifecycle Support.

Uses BaseA2ATaskAgent and SearchAgentExecutor for full A2A protocol compliance.
"""
import sys
from pathlib import Path

# Add project root and example directory to path for imports
project_root = Path(__file__).parent.parent.parent.parent
example_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(example_dir))

from base_a2a_task_agent import BaseA2ATaskAgent
from executors.search_executor import SearchAgentExecutor


class SearchAgentTask(BaseA2ATaskAgent):
    """
    Search Agent with A2A task lifecycle.

    Provides:
    - Web search capabilities
    - Information retrieval
    - Task state management (SUBMITTED → WORKING → COMPLETED)
    - Context management for multi-turn conversations
    """

    def __init__(self, port=9004):
        # Create agent executor
        agent_executor = SearchAgentExecutor()

        super().__init__(
            name="Search Agent (Task-based)",
            description="Searches the web for information with A2A task lifecycle support",
            port=port,
            agent_executor=agent_executor
        )

    def _get_skills(self):
        """Define search agent skills for A2A discovery"""
        return [
            {
                "id": "web_search",
                "name": "Web Search",
                "description": "Search the web for current information and news",
                "tags": ["search", "web", "information", "research"],
                "examples": [
                    "Search for information about Python programming",
                    "Find the latest news about artificial intelligence",
                    "Search for current temperature in Madrid"
                ]
            }
        ]


def main():
    """Run the Search Agent with task support."""
    import os
    port = int(os.getenv("AGENT_PORT", "9004"))

    agent = SearchAgentTask(port=port)
    print(f"Starting Search Agent (Task-based) on port {port}...")
    agent.run()


if __name__ == "__main__":
    main()
