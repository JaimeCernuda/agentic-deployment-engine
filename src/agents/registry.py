"""
Agent Registry for dynamic A2A agent discovery and configuration.

Provides runtime agent discovery and system prompt generation.
"""

import logging
import re
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# Cache entry type: (AgentInfo, timestamp)
CacheEntry = tuple["AgentInfo", float]


def sanitize_prompt_text(text: str, max_length: int = 200) -> str:
    """Sanitize text for safe inclusion in system prompts.

    Prevents prompt injection attacks by:
    - Removing control characters
    - Removing newlines that could manipulate prompt structure
    - Filtering common injection patterns
    - Truncating to max length

    Args:
        text: Text to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized text safe for prompt inclusion
    """
    if not text:
        return ""

    # Convert to string if not already
    text = str(text)

    # Remove control characters (except space)
    text = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)

    # Remove newlines and carriage returns (prevent prompt structure manipulation)
    text = text.replace("\n", " ").replace("\r", " ")

    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)

    # Filter common prompt injection patterns
    injection_patterns = [
        r"(?i)ignore\s+(all\s+)?(previous|prior|above|earlier)",
        r"(?i)disregard\s+(all\s+)?(previous|prior|above|earlier)",
        r"(?i)forget\s+(all\s+)?(previous|prior|above|earlier)",
        r"(?i)override\s+(all\s+)?(previous|prior|above|earlier)",
        r"(?i)new\s+instructions?\s*:",
        r"(?i)system\s*:",
        r"(?i)assistant\s*:",
        r"(?i)user\s*:",
        r"(?i)human\s*:",
        r"(?i)<\s*system\s*>",
        r"(?i)<\s*/\s*system\s*>",
        r"(?i)\[\s*INST\s*\]",
        r"(?i)\[\s*/\s*INST\s*\]",
    ]

    for pattern in injection_patterns:
        text = re.sub(pattern, "[FILTERED]", text)

    # Truncate if too long
    if len(text) > max_length:
        text = text[: max_length - 3] + "..."

    return text.strip()


class AgentInfo:
    """Information about a discovered agent."""

    def __init__(self, url: str, config: dict[str, Any]):
        self.url = url
        self.name = config.get("name", "Unknown")
        self.description = config.get("description", "")
        self.skills = config.get("skills", [])
        self.capabilities = config.get("capabilities", {})

    def to_prompt_section(self) -> str:
        """Generate system prompt section for this agent.

        All text is sanitized to prevent prompt injection attacks.

        Returns:
            Formatted string describing agent for system prompt
        """
        # Sanitize all text from external sources
        safe_name = sanitize_prompt_text(self.name, max_length=50)
        safe_desc = sanitize_prompt_text(self.description, max_length=200)

        section = f"- {safe_name}: {self.url}\n"
        section += f"  Description: {safe_desc}\n"

        if self.skills:
            section += "  Skills:\n"
            # Limit number of skills to prevent prompt bloat
            for skill in self.skills[:5]:
                skill_name = sanitize_prompt_text(
                    skill.get("name", "Unknown"), max_length=30
                )
                skill_desc = sanitize_prompt_text(
                    skill.get("description", ""), max_length=100
                )
                section += f"    * {skill_name}: {skill_desc}\n"

                # Add examples if available (sanitized and limited)
                examples = skill.get("examples", [])
                if examples:
                    section += "      Examples:\n"
                    for example in examples[:2]:  # Limit to 2 examples per skill
                        safe_example = sanitize_prompt_text(example, max_length=80)
                        section += f"        - {safe_example}\n"

        return section


class AgentRegistry:
    """Registry for managing and discovering A2A agents.

    Features:
    - TTL-based cache expiration (default 300 seconds)
    - Max cache size with LRU-style eviction (default 100 entries)
    - Automatic cleanup of stale entries
    """

    def __init__(self, max_cache_size: int = 100, ttl_seconds: float = 300.0) -> None:
        """Initialize the agent registry.

        Args:
            max_cache_size: Maximum number of agents to cache (default 100).
            ttl_seconds: Time-to-live for cache entries in seconds (default 300).
        """
        self._cache: dict[str, CacheEntry] = {}
        self._max_size = max_cache_size
        self._ttl = ttl_seconds
        self._client: httpx.AsyncClient | None = None

    @property
    def agents(self) -> dict[str, AgentInfo]:
        """Get non-expired agents (for backwards compatibility).

        Returns:
            Dictionary mapping URLs to AgentInfo objects.
        """
        self._evict_expired()
        return {url: entry[0] for url, entry in self._cache.items()}

    def _evict_expired(self) -> None:
        """Remove expired entries from cache."""
        now = time.monotonic()
        expired_keys = [
            url
            for url, (_, timestamp) in self._cache.items()
            if now - timestamp > self._ttl
        ]
        for key in expired_keys:
            del self._cache[key]
            logger.debug(f"Evicted expired cache entry: {key}")

    def _evict_oldest(self) -> None:
        """Remove oldest entry if cache exceeds max size."""
        if len(self._cache) >= self._max_size:
            # Find oldest entry
            oldest_url = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_url]
            logger.debug(f"Evicted oldest cache entry: {oldest_url}")

    async def __aenter__(self) -> "AgentRegistry":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(timeout=10.0)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    async def discover_agent(self, url: str) -> AgentInfo | None:
        """Discover an agent at the given URL.

        Args:
            url: Base URL of the agent (e.g., "http://localhost:9001")

        Returns:
            AgentInfo if successful, None otherwise
        """
        # Check cache first (if not expired)
        if url in self._cache:
            agent_info, timestamp = self._cache[url]
            if time.monotonic() - timestamp <= self._ttl:
                logger.debug(f"Cache hit for agent at {url}")
                return agent_info

        try:
            if not self._client:
                self._client = httpx.AsyncClient(timeout=10.0)

            response = await self._client.get(f"{url}/.well-known/agent-configuration")
            response.raise_for_status()
            config = response.json()

            agent_info = AgentInfo(url, config)

            # Evict oldest if needed before adding new entry
            self._evict_oldest()
            self._cache[url] = (agent_info, time.monotonic())

            logger.info(f"Discovered agent: {agent_info.name} at {url}")
            return agent_info

        except Exception as e:
            logger.error(f"Failed to discover agent at {url}: {e}")
            return None

    async def discover_multiple(self, urls: list[str]) -> list[AgentInfo]:
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

    def get_agent(self, url: str) -> AgentInfo | None:
        """Get cached agent info by URL.

        Returns None if the entry has expired or doesn't exist.

        Args:
            url: Agent URL

        Returns:
            AgentInfo if cached and not expired, None otherwise
        """
        if url not in self._cache:
            return None

        agent_info, timestamp = self._cache[url]
        if time.monotonic() - timestamp > self._ttl:
            # Entry expired
            del self._cache[url]
            return None

        return agent_info

    def generate_system_prompt(
        self, base_prompt: str, agent_urls: list[str] | None = None
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
        prompt += "- query: Your question for the agent\n"

        return prompt

    def list_agents(self) -> list[AgentInfo]:
        """Get list of all discovered agents.

        Excludes expired entries.

        Returns:
            List of AgentInfo objects
        """
        return list(self.agents.values())

    def clear_cache(self) -> None:
        """Clear all cached agents."""
        self._cache.clear()
        logger.debug("Agent cache cleared")

    def cache_size(self) -> int:
        """Get current number of cached entries.

        Returns:
            Number of entries in cache (including potentially expired).
        """
        return len(self._cache)

    async def cleanup(self) -> None:
        """Cleanup resources."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._cache.clear()
