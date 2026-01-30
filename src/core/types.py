"""TypedDict definitions for A2A protocol and internal types.

Provides type safety and documentation for structured data used throughout
the agentic deployment engine.
"""

from typing import Any, Literal, NotRequired, TypedDict


class QueryContext(TypedDict):
    """Context for agent queries.

    Carries metadata through query processing for tracing and attribution.
    """

    request_id: str
    trace_id: NotRequired[str]
    span_id: NotRequired[str]
    user_id: NotRequired[str]


class AgentCapabilities(TypedDict):
    """Agent capability flags for A2A discovery.

    Describes what features an agent supports.
    """

    streaming: bool
    push_notifications: bool


class SkillDefinition(TypedDict):
    """Skill definition for A2A discovery.

    Describes a capability the agent can perform.
    """

    id: str
    name: str
    description: str
    examples: NotRequired[list[str]]


class AgentCard(TypedDict):
    """Agent A2A discovery response.

    Standard format for the /.well-known/agent-configuration endpoint.
    """

    name: str
    description: str
    url: str
    version: str
    capabilities: AgentCapabilities
    skills: list[SkillDefinition]
    default_input_modes: list[Literal["text", "image", "audio"]]
    default_output_modes: list[Literal["text", "image", "audio"]]


class ToolResultContent(TypedDict):
    """Content block within a tool result."""

    type: str
    text: NotRequired[str]


class ToolResult(TypedDict):
    """MCP tool result format.

    Standard format for tool responses.
    """

    content: list[ToolResultContent]
    is_error: NotRequired[bool]


class TraceContext(TypedDict):
    """W3C Trace Context for distributed tracing.

    Used to propagate trace information across A2A calls.
    See: https://www.w3.org/TR/trace-context/
    """

    traceparent: str
    tracestate: NotRequired[str]


class QueryRequest(TypedDict):
    """A2A query request format."""

    query: str
    context: NotRequired[dict[str, Any]]


class QueryResponse(TypedDict):
    """A2A query response format."""

    response: str


class HealthResponse(TypedDict):
    """Health check response format."""

    status: Literal["healthy", "unhealthy"]
    agent: str


class BackendQueryResult(TypedDict):
    """Result from a backend query operation."""

    response: str
    messages_count: int
    tools_used: int
    metadata: NotRequired[dict[str, Any]]


class DeploymentTarget(TypedDict):
    """Deployment target specification."""

    type: Literal["localhost", "ssh", "docker", "kubernetes"]
    host: NotRequired[str]
    port: NotRequired[int]
    user: NotRequired[str]
    key_file: NotRequired[str]


class AgentDeploymentConfig(TypedDict):
    """Configuration for deploying a single agent."""

    name: str
    entry_point: str
    port: int
    target: DeploymentTarget
    environment: NotRequired[dict[str, str]]
    dependencies: NotRequired[list[str]]
