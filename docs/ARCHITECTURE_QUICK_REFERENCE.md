# Multi-Agent Architecture Quick Reference

Visual guide to multi-agent system patterns with mermaid diagrams.

---

## 1. Hub-and-Spoke (Current System)

**Pattern:** Central coordinator dispatches to specialized agents

```mermaid
graph TB
    U[User] --> C[Controller<br/>Coordinator]
    C --> A1[Agent 1]
    C --> A2[Agent 2]
    C --> A3[Agent 3]
    A1 --> C
    A2 --> C
    A3 --> C
    C --> U

    style C fill:#e74c3c,stroke:#a93226,color:#fff
    style A1 fill:#50c878,stroke:#2d7a4a,color:#fff
    style A2 fill:#f39c12,stroke:#c87f0a,color:#fff
    style A3 fill:#3498db,stroke:#2874a6,color:#fff
```

**Pros:** Simple, clear coordination | **Cons:** Single point of failure, bottleneck

---

## 2. Pipeline / Sequential

**Pattern:** Agents process in sequence, each adding value

```mermaid
graph LR
    U[User] --> A1[Agent 1<br/>Parse]
    A1 --> A2[Agent 2<br/>Enrich]
    A2 --> A3[Agent 3<br/>Transform]
    A3 --> A4[Agent 4<br/>Format]
    A4 --> U

    style A1 fill:#50c878,stroke:#2d7a4a,color:#fff
    style A2 fill:#f39c12,stroke:#c87f0a,color:#fff
    style A3 fill:#3498db,stroke:#2874a6,color:#fff
    style A4 fill:#9b59b6,stroke:#6c3483,color:#fff
```

**Pros:** Clear flow, easy debugging | **Cons:** Serial latency, rigid ordering

---

## 3. Peer-to-Peer / Mesh

**Pattern:** Agents communicate directly with each other

```mermaid
graph TB
    U[User] --> A1[Agent 1]

    A1 <--> A2[Agent 2]
    A1 <--> A3[Agent 3]
    A1 <--> A4[Agent 4]
    A2 <--> A3
    A2 <--> A4
    A3 <--> A4

    A1 -.-> U
    A2 -.-> U
    A3 -.-> U
    A4 -.-> U

    style A1 fill:#50c878,stroke:#2d7a4a,color:#fff
    style A2 fill:#f39c12,stroke:#c87f0a,color:#fff
    style A3 fill:#3498db,stroke:#2874a6,color:#fff
    style A4 fill:#9b59b6,stroke:#6c3483,color:#fff
```

**Pros:** Resilient, flexible | **Cons:** Complex, hard to debug

---

## 4. Hierarchical / Tree

**Pattern:** Multi-level coordination with domain coordinators

```mermaid
graph TB
    Root[Root<br/>Coordinator]

    Root --> C1[Domain 1<br/>Coordinator]
    Root --> C2[Domain 2<br/>Coordinator]
    Root --> C3[Domain 3<br/>Coordinator]

    C1 --> A1[Agent 1a]
    C1 --> A2[Agent 1b]
    C1 --> A3[Agent 1c]

    C2 --> A4[Agent 2a]
    C2 --> A5[Agent 2b]

    C3 --> A6[Agent 3a]
    C3 --> A7[Agent 3b]
    C3 --> A8[Agent 3c]

    style Root fill:#e74c3c,stroke:#a93226,color:#fff
    style C1 fill:#50c878,stroke:#2d7a4a,color:#fff
    style C2 fill:#f39c12,stroke:#c87f0a,color:#fff
    style C3 fill:#3498db,stroke:#2874a6,color:#fff
```

**Pros:** Scales well, clear domains | **Cons:** Higher latency, complex setup

---

## 5. Blackboard / Shared Memory

**Pattern:** Agents collaborate via shared knowledge space

```mermaid
graph TB
    U[User] --> BB[(Blackboard<br/>Shared State)]

    A1[Agent 1] --> BB
    A2[Agent 2] --> BB
    A3[Agent 3] --> BB
    A4[Agent 4] --> BB

    BB --> A1
    BB --> A2
    BB --> A3
    BB --> A4

    BB --> C[Coordinator]
    C --> U

    style BB fill:#34495e,stroke:#1c2833,color:#fff
    style A1 fill:#50c878,stroke:#2d7a4a,color:#fff
    style A2 fill:#f39c12,stroke:#c87f0a,color:#fff
    style A3 fill:#3498db,stroke:#2874a6,color:#fff
    style A4 fill:#9b59b6,stroke:#6c3483,color:#fff
    style C fill:#e74c3c,stroke:#a93226,color:#fff
```

**Pros:** Loose coupling, incremental solving | **Cons:** State management complexity

---

## 6. Marketplace / Broker

**Pattern:** Dynamic agent selection via bidding/negotiation

```mermaid
graph TB
    U[User] --> B[Broker<br/>Task Analyzer]

    B --> Pool[Agent Pool]

    subgraph Pool
        A1[Agent 1<br/>Bid: Fast]
        A2[Agent 2<br/>Bid: Cheap]
        A3[Agent 3<br/>Bid: Accurate]
        A4[Agent 4<br/>Bid: Premium]
    end

    Pool --> B
    B --> Selected[Selected Agents]
    Selected --> B
    B --> U

    style B fill:#e74c3c,stroke:#a93226,color:#fff
    style Selected fill:#50c878,stroke:#2d7a4a,color:#fff
```

**Pros:** Resource optimization, fault tolerance | **Cons:** Bidding overhead

---

## 7. Event-Driven / Pub-Sub

**Pattern:** Agents react to events via message bus

```mermaid
graph TB
    U[User] --> EB[Event Bus]

    subgraph EB [Event Bus]
        T1[Topic: queries]
        T2[Topic: weather]
        T3[Topic: location]
        T4[Topic: results]
    end

    T1 --> A1[Agent 1<br/>Subscribe]
    T1 --> A2[Agent 2<br/>Subscribe]

    A1 --> T2
    T2 --> A3[Agent 3]

    A2 --> T3
    T3 --> A3

    A3 --> T4
    T4 --> C[Coordinator]
    C --> U

    style EB fill:#34495e,stroke:#1c2833,color:#fff
    style A1 fill:#50c878,stroke:#2d7a4a,color:#fff
    style A2 fill:#f39c12,stroke:#c87f0a,color:#fff
    style A3 fill:#3498db,stroke:#2874a6,color:#fff
```

**Pros:** Highly scalable, decoupled | **Cons:** Requires infrastructure, complex flow

---

## 8. Hybrid: Hub + Pipeline

**Pattern:** Coordinator dispatches to specialized pipelines

```mermaid
graph TB
    U[User] --> C[Controller]

    C --> P1[Pipeline 1]
    C --> P2[Pipeline 2]

    subgraph P1
        direction LR
        A1[Step 1] --> A2[Step 2] --> A3[Step 3]
    end

    subgraph P2
        direction LR
        B1[Step 1] --> B2[Step 2]
    end

    P1 --> C
    P2 --> C
    C --> U

    style C fill:#e74c3c,stroke:#a93226,color:#fff
```

**Pros:** Combines coordination + workflows | **Cons:** More complex

---

## 9. Hybrid: Hierarchical + Marketplace

**Pattern:** Domain coordinators use marketplaces for agent selection

```mermaid
graph TB
    Root[Root<br/>Coordinator]

    Root --> B1[Weather<br/>Broker]
    Root --> B2[Maps<br/>Broker]

    B1 --> WP[Weather Pool<br/>3 providers]
    B2 --> MP[Maps Pool<br/>4 providers]

    WP --> B1
    MP --> B2

    B1 --> Root
    B2 --> Root

    style Root fill:#e74c3c,stroke:#a93226,color:#fff
    style B1 fill:#50c878,stroke:#2d7a4a,color:#fff
    style B2 fill:#f39c12,stroke:#c87f0a,color:#fff
```

**Pros:** Scalable + optimized | **Cons:** Very complex

---

## Architecture Selection Guide

```mermaid
graph TD
    Start[Start] --> NumAgents{Number of<br/>Agents?}

    NumAgents -->|2-5| Simple{Need<br/>workflows?}
    NumAgents -->|6-15| Medium{Clear<br/>domains?}
    NumAgents -->|16+| Large{Real-time<br/>needs?}

    Simple -->|No| HubSpoke[Hub-and-Spoke<br/>⭐ Current]
    Simple -->|Yes| Pipeline[Pipeline]

    Medium -->|Yes| Hierarchical[Hierarchical]
    Medium -->|No| HubSpoke

    Large -->|Yes| EventDriven[Event-Driven]
    Large -->|No| P2P[Peer-to-Peer]

    style HubSpoke fill:#50c878,stroke:#2d7a4a,color:#fff
    style Pipeline fill:#3498db,stroke:#2874a6,color:#fff
    style Hierarchical fill:#f39c12,stroke:#c87f0a,color:#fff
    style EventDriven fill:#9b59b6,stroke:#6c3483,color:#fff
    style P2P fill:#e67e22,stroke:#ba4a00,color:#fff
```

---

## Current System (clean_mcp_a2a)

**Architecture:** Hub-and-Spoke ✅

```mermaid
graph TB
    User[User Query<br/>curl POST] -->|HTTP| Controller[Controller Agent<br/>Port 9000<br/>A2A Transport]

    Controller -->|query_agent<br/>Weather?| Weather[Weather Agent<br/>Port 9001<br/>Weather Tools]
    Controller -->|query_agent<br/>Distance?| Maps[Maps Agent<br/>Port 9002<br/>Maps Tools]

    Weather -->|Temperature<br/>Conditions| Controller
    Maps -->|Distance<br/>Routes| Controller

    Controller -->|Synthesized<br/>Response| User

    Weather -.->|Discovery<br/>/.well-known/| Controller
    Maps -.->|Discovery<br/>/.well-known/| Controller

    style Controller fill:#4a90e2,stroke:#2e5c8a,color:#fff
    style Weather fill:#50c878,stroke:#2d7a4a,color:#fff
    style Maps fill:#f39c12,stroke:#c87f0a,color:#fff
    style User fill:#e74c3c,stroke:#a93226,color:#fff
```

**Key Components:**
- `BaseA2AAgent` - Base class for all agents
- `A2ATransport` - SDK MCP tools for agent communication
- `AgentRegistry` - Dynamic agent discovery
- HTTP endpoints - A2A protocol (query, discovery)

**Tools:**
- Controller: `mcp__a2a_transport__query_agent`, `mcp__a2a_transport__discover_agent`
- Weather: `mcp__weather_agent__get_weather`, `mcp__weather_agent__get_forecast`
- Maps: `mcp__maps_agent__get_distance`, `mcp__maps_agent__get_route`

---

## Migration Paths

### From Hub-and-Spoke to Pipeline

```mermaid
graph LR
    subgraph Before [Current: Hub-and-Spoke]
        C1[Controller] --> W1[Weather]
        C1 --> M1[Maps]
        W1 --> C1
        M1 --> C1
    end

    subgraph After [Pipeline]
        W2[Weather] --> M2[Maps]
        M2 --> R2[Recommend]
        R2 --> F2[Format]
    end

    Before -.->|Evolve| After
```

### From Hub-and-Spoke to Event-Driven

```mermaid
graph TB
    subgraph Before [Current: Hub-and-Spoke]
        C1[Controller] --> A1[Agent 1]
        C1 --> A2[Agent 2]
    end

    subgraph After [Event-Driven]
        Bus[(Event Bus)]
        Bus --> E1[Agent 1]
        Bus --> E2[Agent 2]
        E1 --> Bus
        E2 --> Bus
    end

    Before -.->|Add Event Bus| After
```

---

## Quick Comparison

| Architecture | Agents | Complexity | Use When |
|-------------|--------|-----------|----------|
| Hub-and-Spoke | 2-10 | ⭐⭐ | **Current** - Simple coordination |
| Pipeline | 3-8 | ⭐⭐ | Sequential workflows needed |
| Peer-to-Peer | 5+ | ⭐⭐⭐⭐⭐ | Distributed, high availability |
| Hierarchical | 10+ | ⭐⭐⭐⭐ | Clear domain boundaries |
| Blackboard | Any | ⭐⭐⭐⭐ | Complex problem-solving |
| Marketplace | Any | ⭐⭐⭐⭐⭐ | Resource optimization, SLAs |
| Event-Driven | 5+ | ⭐⭐⭐⭐ | Real-time, high throughput |

**Current Recommendation:** ✅ Hub-and-Spoke is perfect for your current scale (2-5 agents)
