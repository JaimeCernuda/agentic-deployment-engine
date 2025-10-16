# Multi-Agent Architecture Patterns - Visual Comparison

Complete visual reference of all major multi-agent architecture patterns.

---

## All Patterns Side-by-Side

```mermaid
graph TB
    subgraph Pattern1 [1. Hub-and-Spoke / Star]
        U1[User] --> C1[Coordinator]
        C1 --> A1[Agent 1]
        C1 --> A2[Agent 2]
        C1 --> A3[Agent 3]
        A1 --> C1
        A2 --> C1
        A3 --> C1
        C1 --> U1
    end

    subgraph Pattern2 [2. Pipeline / Sequential]
        U2[User] --> P1[Agent 1]
        P1 --> P2[Agent 2]
        P2 --> P3[Agent 3]
        P3 --> P4[Agent 4]
        P4 --> U2
    end

    subgraph Pattern3 [3. Peer-to-Peer / Mesh]
        U3[User] --> M1[Agent 1]
        M1 <--> M2[Agent 2]
        M1 <--> M3[Agent 3]
        M1 <--> M4[Agent 4]
        M2 <--> M3
        M2 <--> M4
        M3 <--> M4
        M1 -.-> U3
        M2 -.-> U3
        M3 -.-> U3
        M4 -.-> U3
    end

    subgraph Pattern4 [4. Hierarchical / Tree]
        U4[User] --> Root[Root]
        Root --> C4a[Coord A]
        Root --> C4b[Coord B]
        C4a --> L1[Agent 1]
        C4a --> L2[Agent 2]
        C4b --> L3[Agent 3]
        C4b --> L4[Agent 4]
        L1 --> C4a
        L2 --> C4a
        L3 --> C4b
        L4 --> C4b
        C4a --> Root
        C4b --> Root
        Root --> U4
    end

    subgraph Pattern5 [5. Blackboard / Shared Memory]
        U5[User] --> BB[(Blackboard)]
        BB --> B1[Agent 1]
        BB --> B2[Agent 2]
        BB --> B3[Agent 3]
        BB --> B4[Agent 4]
        B1 --> BB
        B2 --> BB
        B3 --> BB
        B4 --> BB
        BB --> Coord5[Coordinator]
        Coord5 --> U5
    end

    subgraph Pattern6 [6. Marketplace / Broker]
        U6[User] --> Broker[Broker]
        Broker <--> Pool6[Agent Pool]
        Pool6 --> MK1[Agent 1]
        Pool6 --> MK2[Agent 2]
        Pool6 --> MK3[Agent 3]
        Pool6 --> MK4[Agent 4]
        MK1 --> Pool6
        MK2 --> Pool6
        MK3 --> Pool6
        MK4 --> Pool6
        Pool6 --> Broker
        Broker --> U6
    end

    subgraph Pattern7 [7. Event-Driven / Pub-Sub]
        U7[User] --> Bus[(Event Bus)]
        Bus --> E1[Agent 1]
        Bus --> E2[Agent 2]
        Bus --> E3[Agent 3]
        Bus --> E4[Agent 4]
        E1 --> Bus
        E2 --> Bus
        E3 --> Bus
        E4 --> Bus
        Bus --> Coord7[Coordinator]
        Coord7 --> U7
    end

    style C1 fill:#e74c3c,stroke:#a93226,color:#fff
    style Root fill:#e74c3c,stroke:#a93226,color:#fff
    style Broker fill:#e74c3c,stroke:#a93226,color:#fff
    style Coord5 fill:#e74c3c,stroke:#a93226,color:#fff
    style Coord7 fill:#e74c3c,stroke:#a93226,color:#fff
    style BB fill:#34495e,stroke:#1c2833,color:#fff
    style Bus fill:#34495e,stroke:#1c2833,color:#fff
    style Pool6 fill:#95a5a6,stroke:#7f8c8d,color:#fff
```

---

## Pattern Characteristics Summary

| Pattern | Communication | Coordination | Coupling | Scalability |
|---------|--------------|--------------|----------|-------------|
| **1. Hub-and-Spoke** | Centralized | Single coordinator | Tight | Medium |
| **2. Pipeline** | Sequential | Implicit ordering | Tight | Medium |
| **3. Peer-to-Peer** | Distributed | Negotiated | Loose | High |
| **4. Hierarchical** | Tree-based | Multi-level | Medium | High |
| **5. Blackboard** | Shared state | Opportunistic | Loose | Medium |
| **6. Marketplace** | Brokered | Dynamic selection | Loose | High |
| **7. Event-Driven** | Pub/Sub | Event triggers | Very Loose | Very High |

---

## Detailed Individual Patterns

### 1. Hub-and-Spoke (Star)

```mermaid
graph TB
    User[User Request] --> Coordinator[Central Coordinator]

    Coordinator -->|Task 1| Agent1[Specialized Agent 1]
    Coordinator -->|Task 2| Agent2[Specialized Agent 2]
    Coordinator -->|Task 3| Agent3[Specialized Agent 3]
    Coordinator -->|Task 4| Agent4[Specialized Agent 4]

    Agent1 -->|Result 1| Coordinator
    Agent2 -->|Result 2| Coordinator
    Agent3 -->|Result 3| Coordinator
    Agent4 -->|Result 4| Coordinator

    Coordinator -->|Aggregated Response| User

    style Coordinator fill:#e74c3c,stroke:#a93226,color:#fff,stroke-width:3px
    style Agent1 fill:#3498db,stroke:#2874a6,color:#fff
    style Agent2 fill:#2ecc71,stroke:#27ae60,color:#fff
    style Agent3 fill:#f39c12,stroke:#d68910,color:#fff
    style Agent4 fill:#9b59b6,stroke:#7d3c98,color:#fff
    style User fill:#95a5a6,stroke:#7f8c8d,color:#fff
```

**Flow:** User → Coordinator → Agents (parallel) → Coordinator → User

---

### 2. Pipeline / Sequential

```mermaid
graph LR
    User[User Input] --> Stage1[Agent 1<br/>Intake/Parse]
    Stage1 --> Stage2[Agent 2<br/>Validate]
    Stage2 --> Stage3[Agent 3<br/>Process]
    Stage3 --> Stage4[Agent 4<br/>Transform]
    Stage4 --> Stage5[Agent 5<br/>Format]
    Stage5 --> User2[User Output]

    style Stage1 fill:#3498db,stroke:#2874a6,color:#fff
    style Stage2 fill:#2ecc71,stroke:#27ae60,color:#fff
    style Stage3 fill:#f39c12,stroke:#d68910,color:#fff
    style Stage4 fill:#9b59b6,stroke:#7d3c98,color:#fff
    style Stage5 fill:#e74c3c,stroke:#c0392b,color:#fff
    style User fill:#95a5a6,stroke:#7f8c8d,color:#fff
    style User2 fill:#95a5a6,stroke:#7f8c8d,color:#fff
```

**Flow:** User → Agent 1 → Agent 2 → Agent 3 → Agent 4 → Agent 5 → User

---

### 3. Peer-to-Peer / Mesh

```mermaid
graph TB
    User[User] -->|Initial Request| Agent1[Agent 1]

    Agent1 <-->|Direct Communication| Agent2[Agent 2]
    Agent1 <-->|Direct Communication| Agent3[Agent 3]
    Agent1 <-->|Direct Communication| Agent4[Agent 4]
    Agent2 <-->|Direct Communication| Agent3
    Agent2 <-->|Direct Communication| Agent4
    Agent3 <-->|Direct Communication| Agent4

    Agent1 -.->|Can Respond| User
    Agent2 -.->|Can Respond| User
    Agent3 -.->|Can Respond| User
    Agent4 -.->|Can Respond| User

    style Agent1 fill:#3498db,stroke:#2874a6,color:#fff,stroke-width:3px
    style Agent2 fill:#2ecc71,stroke:#27ae60,color:#fff
    style Agent3 fill:#f39c12,stroke:#d68910,color:#fff
    style Agent4 fill:#9b59b6,stroke:#7d3c98,color:#fff
    style User fill:#95a5a6,stroke:#7f8c8d,color:#fff
```

**Flow:** User → Any Agent → Agents collaborate directly → Response from any Agent

---

### 4. Hierarchical / Tree

```mermaid
graph TB
    User[User] --> Root[Root Coordinator]

    Root --> Domain1[Domain Coordinator A]
    Root --> Domain2[Domain Coordinator B]
    Root --> Domain3[Domain Coordinator C]

    Domain1 --> Agent1[Agent 1a]
    Domain1 --> Agent2[Agent 1b]
    Domain1 --> Agent3[Agent 1c]

    Domain2 --> Agent4[Agent 2a]
    Domain2 --> Agent5[Agent 2b]

    Domain3 --> Agent6[Agent 3a]
    Domain3 --> Agent7[Agent 3b]
    Domain3 --> Agent8[Agent 3c]

    Agent1 --> Domain1
    Agent2 --> Domain1
    Agent3 --> Domain1
    Agent4 --> Domain2
    Agent5 --> Domain2
    Agent6 --> Domain3
    Agent7 --> Domain3
    Agent8 --> Domain3

    Domain1 --> Root
    Domain2 --> Root
    Domain3 --> Root

    Root --> User

    style Root fill:#e74c3c,stroke:#c0392b,color:#fff,stroke-width:3px
    style Domain1 fill:#3498db,stroke:#2874a6,color:#fff,stroke-width:2px
    style Domain2 fill:#2ecc71,stroke:#27ae60,color:#fff,stroke-width:2px
    style Domain3 fill:#f39c12,stroke:#d68910,color:#fff,stroke-width:2px
    style User fill:#95a5a6,stroke:#7f8c8d,color:#fff
```

**Flow:** User → Root → Domain Coordinators → Leaf Agents → Domain Coordinators → Root → User

---

### 5. Blackboard / Shared Memory

```mermaid
graph TB
    User[User] -->|Write Query| Blackboard

    subgraph Blackboard [Shared Blackboard Space]
        Knowledge[(Knowledge Base<br/>- Query<br/>- Partial Results<br/>- Final Solution)]
    end

    Agent1[Agent 1] <-->|Read/Write| Knowledge
    Agent2[Agent 2] <-->|Read/Write| Knowledge
    Agent3[Agent 3] <-->|Read/Write| Knowledge
    Agent4[Agent 4] <-->|Read/Write| Knowledge
    Agent5[Agent 5] <-->|Read/Write| Knowledge

    Knowledge -->|Monitor Completion| Coordinator[Solution Coordinator]
    Coordinator -->|Final Response| User

    Agent1 -.->|Subscribe to Events| Knowledge
    Agent2 -.->|Subscribe to Events| Knowledge
    Agent3 -.->|Subscribe to Events| Knowledge
    Agent4 -.->|Subscribe to Events| Knowledge
    Agent5 -.->|Subscribe to Events| Knowledge

    style Knowledge fill:#34495e,stroke:#1c2833,color:#fff,stroke-width:3px
    style Coordinator fill:#e74c3c,stroke:#c0392b,color:#fff
    style Agent1 fill:#3498db,stroke:#2874a6,color:#fff
    style Agent2 fill:#2ecc71,stroke:#27ae60,color:#fff
    style Agent3 fill:#f39c12,stroke:#d68910,color:#fff
    style Agent4 fill:#9b59b6,stroke:#7d3c98,color:#fff
    style Agent5 fill:#16a085,stroke:#138d75,color:#fff
    style User fill:#95a5a6,stroke:#7f8c8d,color:#fff
```

**Flow:** User → Blackboard ← Agents (async read/write) → Coordinator monitors → User

---

### 6. Marketplace / Broker

```mermaid
graph TB
    User[User Request] --> Broker[Broker / Auctioneer]

    Broker -->|Broadcast RFP| Pool[Agent Marketplace]

    subgraph Pool [Agent Pool with Capabilities]
        Agent1[Agent 1<br/>Fast, $$$]
        Agent2[Agent 2<br/>Accurate, $$]
        Agent3[Agent 3<br/>Cheap, $]
        Agent4[Agent 4<br/>Premium, $$$$]
        Agent5[Agent 5<br/>Balanced, $$]
    end

    Pool -->|Submit Bids| Broker

    Broker -->|Select & Assign| Selected[Selected Agents<br/>Based on Constraints]

    Selected -->|Execute Tasks| Results[Task Results]
    Results --> Broker
    Broker --> User

    style Broker fill:#e74c3c,stroke:#c0392b,color:#fff,stroke-width:3px
    style Pool fill:#95a5a6,stroke:#7f8c8d,color:#fff,stroke-width:2px
    style Selected fill:#27ae60,stroke:#229954,color:#fff,stroke-width:2px
    style Agent1 fill:#3498db,stroke:#2874a6,color:#fff
    style Agent2 fill:#2ecc71,stroke:#27ae60,color:#fff
    style Agent3 fill:#f39c12,stroke:#d68910,color:#fff
    style Agent4 fill:#9b59b6,stroke:#7d3c98,color:#fff
    style Agent5 fill:#16a085,stroke:#138d75,color:#fff
    style User fill:#95a5a6,stroke:#7f8c8d,color:#fff
```

**Flow:** User → Broker → RFP Broadcast → Agents Bid → Broker Selects → Task Execution → User

---

### 7. Event-Driven / Pub-Sub

```mermaid
graph TB
    User[User] -->|Publish Event| EventBus

    subgraph EventBus [Event Bus / Message Broker]
        Topic1[Topic: Requests]
        Topic2[Topic: Processing]
        Topic3[Topic: Results]
        Topic4[Topic: Notifications]
    end

    Topic1 -->|Subscribe| Agent1[Agent 1]
    Topic1 -->|Subscribe| Agent2[Agent 2]

    Agent1 -->|Publish| Topic2
    Agent2 -->|Publish| Topic2

    Topic2 -->|Subscribe| Agent3[Agent 3]
    Topic2 -->|Subscribe| Agent4[Agent 4]

    Agent3 -->|Publish| Topic3
    Agent4 -->|Publish| Topic3

    Topic3 -->|Subscribe| Agent5[Agent 5]
    Agent5 -->|Publish| Topic4

    Topic4 -->|Subscribe| Coordinator[Response Coordinator]
    Coordinator --> User

    style EventBus fill:#34495e,stroke:#1c2833,color:#fff,stroke-width:3px
    style Coordinator fill:#e74c3c,stroke:#c0392b,color:#fff
    style Agent1 fill:#3498db,stroke:#2874a6,color:#fff
    style Agent2 fill:#2ecc71,stroke:#27ae60,color:#fff
    style Agent3 fill:#f39c12,stroke:#d68910,color:#fff
    style Agent4 fill:#9b59b6,stroke:#7d3c98,color:#fff
    style Agent5 fill:#16a085,stroke:#138d75,color:#fff
    style User fill:#95a5a6,stroke:#7f8c8d,color:#fff
```

**Flow:** User → Event Bus → Agents subscribe to topics → Publish new events → Cascading reactions → Coordinator → User

---

## Selection Decision Tree

```mermaid
graph TD
    Start([Choose Architecture]) --> Q1{System Size?}

    Q1 -->|Small<br/>2-5 agents| Simple
    Q1 -->|Medium<br/>6-15 agents| Medium
    Q1 -->|Large<br/>16+ agents| Large

    Simple --> Q2{Need<br/>Workflows?}
    Q2 -->|No| HubSpoke[Hub-and-Spoke<br/>⭐ Simple & Effective]
    Q2 -->|Yes| Pipeline[Pipeline<br/>⭐ Clear Flow]

    Medium --> Q3{Clear<br/>Domains?}
    Q3 -->|Yes| Hierarchical[Hierarchical<br/>⭐ Organized]
    Q3 -->|No| Q4{Complex<br/>Problem?}
    Q4 -->|Yes| Blackboard[Blackboard<br/>⭐ Collaborative]
    Q4 -->|No| HubSpoke

    Large --> Q5{Real-time<br/>Required?}
    Q5 -->|Yes| EventDriven[Event-Driven<br/>⭐ Scalable]
    Q5 -->|No| Q6{High<br/>Availability?}
    Q6 -->|Yes| P2P[Peer-to-Peer<br/>⭐ Resilient]
    Q6 -->|No| Q7{Resource<br/>Optimization?}
    Q7 -->|Yes| Marketplace[Marketplace<br/>⭐ Optimized]
    Q7 -->|No| Hierarchical

    style HubSpoke fill:#27ae60,stroke:#229954,color:#fff
    style Pipeline fill:#27ae60,stroke:#229954,color:#fff
    style Hierarchical fill:#27ae60,stroke:#229954,color:#fff
    style Blackboard fill:#27ae60,stroke:#229954,color:#fff
    style EventDriven fill:#27ae60,stroke:#229954,color:#fff
    style P2P fill:#27ae60,stroke:#229954,color:#fff
    style Marketplace fill:#27ae60,stroke:#229954,color:#fff
    style Start fill:#e74c3c,stroke:#c0392b,color:#fff
```

---

## Pattern Complexity vs Scalability

```mermaid
graph LR
    subgraph Complexity [Implementation Complexity →]
        Low[Low]
        MedLow[Med-Low]
        Med[Medium]
        MedHigh[Med-High]
        High[Very High]
    end

    subgraph Patterns [Architecture Patterns]
        P1[Hub-and-Spoke]
        P2[Pipeline]
        P3[Hierarchical]
        P4[Blackboard]
        P5[Event-Driven]
        P6[Peer-to-Peer]
        P7[Marketplace]
    end

    Low -.-> P1
    Low -.-> P2
    MedHigh -.-> P3
    MedHigh -.-> P4
    MedHigh -.-> P5
    High -.-> P6
    High -.-> P7

    style P1 fill:#27ae60,stroke:#229954,color:#fff
    style P2 fill:#27ae60,stroke:#229954,color:#fff
    style P3 fill:#f39c12,stroke:#d68910,color:#fff
    style P4 fill:#f39c12,stroke:#d68910,color:#fff
    style P5 fill:#f39c12,stroke:#d68910,color:#fff
    style P6 fill:#e74c3c,stroke:#c0392b,color:#fff
    style P7 fill:#e74c3c,stroke:#c0392b,color:#fff
```

**Legend:**
- 🟢 Green: Low complexity, good starting point
- 🟠 Orange: Medium complexity, scales well
- 🔴 Red: High complexity, maximum scalability

---

## Communication Patterns

```mermaid
graph TB
    subgraph Centralized [Centralized Communication]
        C1[Hub-and-Spoke]
        C2[Hierarchical]
        C3[Marketplace]
    end

    subgraph Distributed [Distributed Communication]
        D1[Peer-to-Peer]
        D2[Event-Driven]
        D3[Blackboard]
    end

    subgraph Sequential [Sequential Communication]
        S1[Pipeline]
    end

    Centralized -.->|Good for<br/>Control| Control[Controlled<br/>Coordination]
    Distributed -.->|Good for<br/>Scale| Scale[Horizontal<br/>Scaling]
    Sequential -.->|Good for<br/>Workflows| Workflow[Clear<br/>Workflows]

    style Centralized fill:#3498db,stroke:#2874a6,color:#fff
    style Distributed fill:#2ecc71,stroke:#27ae60,color:#fff
    style Sequential fill:#f39c12,stroke:#d68910,color:#fff
```

---

## Use Case Mapping

| Use Case | Recommended Pattern | Why |
|----------|-------------------|-----|
| **Small team coordination** | Hub-and-Spoke | Simple, clear control |
| **Document processing** | Pipeline | Sequential transformation |
| **Enterprise multi-domain** | Hierarchical | Domain separation |
| **Research/AI planning** | Blackboard | Opportunistic collaboration |
| **IoT/Real-time monitoring** | Event-Driven | Asynchronous, scalable |
| **Distributed services** | Peer-to-Peer | High availability |
| **Cloud agent platform** | Marketplace | Resource optimization |

---

## Quick Reference Card

### When to Use Each Pattern

**Hub-and-Spoke:**
- ✅ 2-10 agents
- ✅ Clear coordination needed
- ✅ Simple to implement
- ❌ Single point of failure

**Pipeline:**
- ✅ Sequential dependencies
- ✅ Data transformation
- ✅ Easy to debug
- ❌ Serial latency

**Peer-to-Peer:**
- ✅ High availability critical
- ✅ Large scale (10+ agents)
- ✅ Dynamic collaboration
- ❌ Complex debugging

**Hierarchical:**
- ✅ Clear domains
- ✅ 10+ agents
- ✅ Scalable structure
- ❌ Multi-hop latency

**Blackboard:**
- ✅ Complex problems
- ✅ Incremental solving
- ✅ Opportunistic agents
- ❌ State management

**Marketplace:**
- ✅ Resource optimization
- ✅ SLA requirements
- ✅ Heterogeneous agents
- ❌ Bidding overhead

**Event-Driven:**
- ✅ Real-time needs
- ✅ High throughput
- ✅ Loose coupling
- ❌ Infrastructure needed
