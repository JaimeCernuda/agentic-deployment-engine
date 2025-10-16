"""
Agent Registry for dynamic A2A agent discovery and configuration.

Provides runtime agent discovery and system prompt generation.
"""
import httpx
from typing import Dict, Any, List, Optional
import logging


logger = logging.getLogger(__name__)


class AgentInfo:
    """Information about a discovered agent."""

    def __init__(self, url: str, config: Dict[str, Any]):
        self.url = url
        self.name = config.get("name", "Unknown")
        self.description = config.get("description", "")
        self.skills = config.get("skills", [])
        self.capabilities = config.get("capabilities", {})

    def to_prompt_section(self) -> str:
        """Generate system prompt section for this agent.

        Returns:
            Formatted string describing agent for system prompt
        """
        section = f"- {self.name}: {self.url}\n"
        section += f"  Description: {self.description}\n"

        if self.skills:
            section += "  Skills:\n"
            for skill in self.skills:
                skill_name = skill.get("name", "Unknown")
                skill_desc = skill.get("description", "")
                section += f"    * {skill_name}: {skill_desc}\n"

                # Add examples if available
                examples = skill.get("examples", [])
                if examples:
                    section += "      Examples:\n"
                    for example in examples[:2]:  # Limit to 2 examples per skill
                        section += f"        - {example}\n"

        return section


class AgentRegistry:
    """Registry for managing and discovering A2A agents."""

    def __init__(self):
        self.agents: Dict[str, AgentInfo] = {}
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._client = httpx.AsyncClient(timeout=10.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    async def discover_agent(self, url: str) -> Optional[AgentInfo]:
        """Discover an agent at the given URL.

        Args:
            url: Base URL of the agent (e.g., "http://localhost:9001")

        Returns:
            AgentInfo if successful, None otherwise
        """
        try:
            if not self._client:
                self._client = httpx.AsyncClient(timeout=10.0)

            response = await self._client.get(
                f"{url}/.well-known/agent-configuration"
            )
            response.raise_for_status()
            config = response.json()

            agent_info = AgentInfo(url, config)
            self.agents[url] = agent_info

            logger.info(f"Discovered agent: {agent_info.name} at {url}")
            return agent_info

        except Exception as e:
            logger.error(f"Failed to discover agent at {url}: {e}")
            return None

    async def discover_multiple(self, urls: List[str]) -> List[AgentInfo]:
        """Discover multiple agents concurrently.

        Args:
            urls: List of agent URLs to discover

        Returns:
            List of successfully discovered AgentInfo objects
        """
        discovered = []
        for url in urls:
            agent_info = await self.discover_agent(url)
            if agent_info:
                discovered.append(agent_info)
        return discovered

    def get_agent(self, url: str) -> Optional[AgentInfo]:
        """Get cached agent info by URL.

        Args:
            url: Agent URL

        Returns:
            AgentInfo if cached, None otherwise
        """
        return self.agents.get(url)

    def generate_system_prompt(
        self,
        base_prompt: str,
        agent_urls: Optional[List[str]] = None
    ) -> str:
        """Generate system prompt with discovered agent information.

        Args:
            base_prompt: Base system prompt text
            agent_urls: Optional list of agent URLs to include (defaults to all)

        Returns:
            Complete system prompt with agent information
        """
        if not self.agents:
            return base_prompt

        # Determine which agents to include
        if agent_urls:
            agents_to_include = [
                self.agents[url] for url in agent_urls if url in self.agents
            ]
        else:
            agents_to_include = list(self.agents.values())

        if not agents_to_include:
            return base_prompt

        # Build prompt with agent information
        prompt = base_prompt + "\n\n**Available Agents:**\n\n"
        prompt += "You can query these agents using the mcp__a2a_transport__query_agent tool:\n\n"

        for agent in agents_to_include:
            prompt += agent.to_prompt_section() + "\n"

        prompt += "\n**Usage:**\n"
        prompt += "Use mcp__a2a_transport__query_agent with:\n"
        prompt += '- agent_url: The agent\'s URL (e.g., "http://localhost:9001")\n'
        prompt += '- query: Your question for the agent\n'

        return prompt

    def list_agents(self) -> List[AgentInfo]:
        """Get list of all discovered agents.

        Returns:
            List of AgentInfo objects
        """
        return list(self.agents.values())

    async def cleanup(self):
        """Cleanup resources."""
        if self._client:
            await self._client.aclose()
            self._client = None
