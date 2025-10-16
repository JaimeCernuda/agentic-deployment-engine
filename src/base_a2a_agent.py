"""
Base A2A Agent using claude-code-sdk properly.

Provides A2A capabilities with clean inheritance and dynamic agent connections.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
from pathlib import Path
from .agent_registry import AgentRegistry


class QueryRequest(BaseModel):
    query: str
    context: Dict[str, Any] = {}


class QueryResponse(BaseModel):
    response: str


class BaseA2AAgent(ABC):
    """
    Base A2A Agent providing clean A2A inheritance.

    Uses claude-code-sdk properly with MCP server configuration.
    """

    def __init__(
        self,
        name: str,
        description: str,
        port: int,
        sdk_mcp_server=None,
        system_prompt: str = None,
        connected_agents: Optional[List[str]] = None
    ):
        self.name = name
        self.description = description
        self.port = port
        self.connected_agents = connected_agents or []
        self.agent_registry = AgentRegistry() if connected_agents else None

        # System prompt will be set after agent discovery if needed
        self._base_system_prompt = system_prompt or self._get_default_system_prompt()
        self.system_prompt = self._base_system_prompt

        # Setup logging in local logs directory
        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"{name.lower().replace(' ', '_')}.log"

        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # Clear existing handlers to avoid duplicates
        self.logger.handlers.clear()

        # File handler with detailed formatting
        fh = logging.FileHandler(log_file, mode='a')
        fh.setLevel(logging.DEBUG)

        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        # Detailed formatter for file logs
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
        )
        # Simple formatter for console
        console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        fh.setFormatter(file_formatter)
        ch.setFormatter(console_formatter)

        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

        self.logger.info(f"Initializing {name} on port {port}")
        self.logger.info(f"Log file: {log_file}")

        # Configure claude-code-sdk with SDK MCP server
        mcp_servers = {}
        if sdk_mcp_server:
            server_key = self.name.lower().replace(" ", "_")
            mcp_servers[server_key] = sdk_mcp_server
            self.logger.debug(f"SDK MCP server configured with key: {server_key}")
            self.logger.debug(f"SDK server type: {sdk_mcp_server.get('type') if isinstance(sdk_mcp_server, dict) else type(sdk_mcp_server)}")

            # Log SDK server tools if available
            if isinstance(sdk_mcp_server, dict) and 'instance' in sdk_mcp_server:
                server_instance = sdk_mcp_server['instance']
                if hasattr(server_instance, 'list_tools'):
                    self.logger.debug(f"SDK MCP server has list_tools method")

        allowed_tools = self._get_allowed_tools()
        self.logger.debug(f"Allowed tools: {allowed_tools}")
        self.logger.debug(f"System prompt length: {len(self.system_prompt)} chars")
        self.logger.debug(f"System prompt preview: {self.system_prompt[:200]}...")

        self.claude_options = ClaudeAgentOptions(
            mcp_servers=mcp_servers,
            allowed_tools=allowed_tools,
            system_prompt=self.system_prompt
        )
        self.claude_client = None

        # Create A2A endpoints
        self.app = FastAPI(title=name, description=description)
        self._setup_routes()

    def _setup_routes(self):
        """Setup A2A discovery and query endpoints."""

        @self.app.get("/.well-known/agent-configuration")
        async def agent_card():
            return {
                "name": self.name,
                "description": self.description,
                "url": f"http://localhost:{self.port}",
                "version": "1.0.0",
                "capabilities": {
                    "streaming": True,
                    "push_notifications": False
                },
                "default_input_modes": ["text"],
                "default_output_modes": ["text"],
                "skills": self._get_skills()
            }

        @self.app.get("/health")
        async def health():
            return {"status": "healthy", "agent": self.name}

        @self.app.post("/query", response_model=QueryResponse)
        async def query(request: QueryRequest):
            response = await self._handle_query(request.query)
            return QueryResponse(response=response)

    async def _get_claude_client(self) -> ClaudeSDKClient:
        """Get claude-code-sdk client."""
        if self.claude_client is None:
            self.logger.info("Creating ClaudeSDKClient...")
            try:
                self.claude_client = ClaudeSDKClient(self.claude_options)
                self.logger.info("Connecting to Claude CLI...")
                await self.claude_client.connect()
                self.logger.info("Successfully connected to Claude CLI")
            except Exception as e:
                self.logger.error(f"Failed to create/connect ClaudeSDKClient: {e}", exc_info=True)
                raise
        return self.claude_client

    async def _handle_query(self, query: str) -> str:
        """Handle query using claude-code-sdk."""
        self.logger.info(f"Handling query: {query}")
        self.logger.debug(f"Query length: {len(query)} chars")

        try:
            # Create a FRESH client for each query to avoid state issues
            self.logger.info("Creating fresh ClaudeSDKClient for this query...")
            client = ClaudeSDKClient(self.claude_options)
            await client.connect()
            self.logger.info("Successfully connected to Claude CLI")

            self.logger.debug("Sending query to Claude...")
            await client.query(query)

            response = ""
            message_count = 0
            tool_use_count = 0

            self.logger.debug("Receiving response...")
            async for message in client.receive_response():
                message_count += 1
                message_type = type(message).__name__
                self.logger.debug(f"Message {message_count}: {message_type}")

                # Log message details based on type
                if hasattr(message, 'role'):
                    self.logger.debug(f"  Role: {message.role}")

                if hasattr(message, 'content'):
                    for i, block in enumerate(message.content):
                        block_type = type(block).__name__
                        self.logger.debug(f"  Content block {i}: {block_type}")

                        if hasattr(block, 'text'):
                            text_preview = block.text[:200] if len(block.text) > 200 else block.text
                            self.logger.debug(f"    Text: {text_preview}...")
                            response += block.text

                        if hasattr(block, 'name'):
                            tool_use_count += 1
                            self.logger.debug(f"    Tool: {block.name}")
                            if hasattr(block, 'input'):
                                self.logger.debug(f"    Input: {block.input}")

                        # Log tool results (success or error)
                        if hasattr(block, 'tool_use_id'):
                            self.logger.debug(f"    Tool Result for: {block.tool_use_id}")
                            if hasattr(block, 'content'):
                                self.logger.debug(f"    Result content: {block.content}")
                            if hasattr(block, 'is_error'):
                                self.logger.debug(f"    Is error: {block.is_error}")

                if hasattr(message, 'stop_reason'):
                    self.logger.debug(f"  Stop reason: {message.stop_reason}")

            # Disconnect after query
            await client.disconnect()

            self.logger.info(f"Query completed. Messages: {message_count}, Tools used: {tool_use_count}, Response: {len(response)} chars")
            return response or "No response generated"

        except Exception as e:
            self.logger.error(f"Error handling query: {e}", exc_info=True)
            return f"Error: {str(e)}"

    @abstractmethod
    def _get_skills(self) -> List[Dict[str, Any]]:
        """Define agent skills for A2A discovery."""
        pass

    @abstractmethod
    def _get_allowed_tools(self) -> List[str]:
        """Define allowed tools for claude-code-sdk."""
        pass

    def _get_default_system_prompt(self) -> str:
        """Get default system prompt for this agent."""
        return f"""You are {self.name}, {self.description}.

You have access to specialized tools for your domain. Use them to provide accurate and helpful responses.
Always be concise and professional in your responses."""

    async def _discover_agents(self):
        """Discover connected agents and update system prompt."""
        if not self.agent_registry or not self.connected_agents:
            return

        self.logger.info(f"Discovering {len(self.connected_agents)} connected agents...")
        discovered = await self.agent_registry.discover_multiple(self.connected_agents)
        self.logger.info(f"Successfully discovered {len(discovered)} agents")

        # Update system prompt with discovered agent info
        self.system_prompt = self.agent_registry.generate_system_prompt(
            self._base_system_prompt,
            self.connected_agents
        )

        # Recreate claude options with updated system prompt
        self.claude_options = ClaudeAgentOptions(
            mcp_servers=self.claude_options.mcp_servers,
            allowed_tools=self.claude_options.allowed_tools,
            system_prompt=self.system_prompt
        )

        self.logger.debug(f"Updated system prompt ({len(self.system_prompt)} chars)")

    def run(self):
        """Run the A2A agent."""
        # Discover agents before starting server if configured
        if self.connected_agents:
            self.logger.info("Discovering agents before startup...")
            asyncio.run(self._discover_agents())

        uvicorn.run(self.app, host="0.0.0.0", port=self.port)

    async def cleanup(self):
        """Cleanup resources."""
        if self.claude_client:
            await self.claude_client.disconnect()
        if self.agent_registry:
            await self.agent_registry.cleanup()