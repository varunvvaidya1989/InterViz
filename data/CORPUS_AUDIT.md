# EnterView corpus audit

Built 2026-11-03T06:22:12.344955+00:00. 7 unique PDFs, 579 pages, 985 text chunks, 132 contents entries, 374 question pages.

## Documents

| Document | Track | Pages | Contents entries | Question pages | Chunks |
|---|---|---:|---:|---:|---:|
| DevOps Interview Playbook | devops | 123 | 12 | 108 | 129 |
| Software Engineer to AI Engineer Interview Guide | ai-engineering | 176 | 15 | 158 | 312 |
| Backend Interview Playbook | backend | 123 | 12 | 108 | 130 |
| High-Level Design Problems | system-design | 51 | 16 | 0 | 155 |
| LLD Core Concepts | low-level-design | 24 | 21 | 0 | 51 |
| Low-Level Design Problems | low-level-design | 43 | 20 | 0 | 137 |
| System Design Core Concepts | system-design | 39 | 36 | 0 | 71 |

## Cross-document topic overlap

These are keyword-based coverage indicators, not an expert assessment of completeness.

- **caching**: Backend Interview Playbook; DevOps Interview Playbook; High-Level Design Problems; LLD Core Concepts; Low-Level Design Problems; Software Engineer to AI Engineer Interview Guide; System Design Core Concepts
- **databases**: Backend Interview Playbook; DevOps Interview Playbook; High-Level Design Problems; LLD Core Concepts; Low-Level Design Problems; Software Engineer to AI Engineer Interview Guide; System Design Core Concepts
- **design-patterns**: Backend Interview Playbook; DevOps Interview Playbook; High-Level Design Problems; LLD Core Concepts; Low-Level Design Problems; Software Engineer to AI Engineer Interview Guide; System Design Core Concepts
- **messaging**: Backend Interview Playbook; DevOps Interview Playbook; High-Level Design Problems; LLD Core Concepts; Low-Level Design Problems; Software Engineer to AI Engineer Interview Guide; System Design Core Concepts
- **networking**: Backend Interview Playbook; DevOps Interview Playbook; High-Level Design Problems; Low-Level Design Problems; Software Engineer to AI Engineer Interview Guide; System Design Core Concepts
- **operations**: Backend Interview Playbook; DevOps Interview Playbook; High-Level Design Problems; LLD Core Concepts; Low-Level Design Problems; Software Engineer to AI Engineer Interview Guide; System Design Core Concepts
- **ownership**: Backend Interview Playbook; DevOps Interview Playbook; High-Level Design Problems; LLD Core Concepts; Software Engineer to AI Engineer Interview Guide; System Design Core Concepts
- **rag**: Backend Interview Playbook; High-Level Design Problems; Software Engineer to AI Engineer Interview Guide
- **reliability**: Backend Interview Playbook; DevOps Interview Playbook; High-Level Design Problems; LLD Core Concepts; Low-Level Design Problems; Software Engineer to AI Engineer Interview Guide; System Design Core Concepts
- **security**: Backend Interview Playbook; DevOps Interview Playbook; Low-Level Design Problems; Software Engineer to AI Engineer Interview Guide; System Design Core Concepts

## Proposed learning paths

1. **Backend foundations:** system-design concepts → API and database modules → caching and messaging → reliability and incident drills.
2. **Design interviews:** coupling and SOLID → design patterns → LLD problems → HLD problems → backend blank-page design module.
3. **Ownership and behavioural:** backend project deep dives → behavioural/managerial module → DevOps ownership module → timed personal-story practice.
4. **Production engineering:** Linux/networking → containers and CI/CD → Kubernetes/IaC → observability → incident recovery.
5. **AI engineering:** LLM foundations → context engineering → retrieval architecture → retrieval failure diagnosis → evaluation → agents → AI system design.

Prerequisites and lab quality require editorial review before these become paid bundles.

## Extraction and product gaps

- Text extraction preserves block coordinates but does not interpret visual diagrams or guarantee table reading order.
- No dedicated salary-negotiation guide identified; keyword mentions are not evidence of a complete curriculum.
- Source examples and model answers must not be presented as the learner's own experience.
- Content ownership and commercial adaptation rights have not been verified.

## Source map

### DevOps Interview Playbook

Source: `docs/backend-engg/0313dad636ce7a70f40d7b261cf8426c9373a14d9dc9d3aa.pdf`

- pp. 3–12: Project and ownership deep dives
- pp. 13–22: Linux and systems troubleshooting
- pp. 23–32: Networking, DNS and traffic management
- pp. 33–42: CI/CD and release engineering
- pp. 43–52: Containers and image lifecycle
- pp. 53–62: Container orchestration and Kubernetes operations
- pp. 63–72: Infrastructure as Code, configuration management and GitOps
- pp. 73–82: AWS architecture and operations
- pp. 83–92: Observability, SRE and capacity management
- pp. 93–102: Incident response, resilience and disaster recovery
- pp. 103–112: DevSecOps and software-supply-chain security
- pp. 113–122: Platform engineering and system design

### Software Engineer to AI Engineer Interview Guide

Source: `docs/backend-engg/ac4051c9aa34c0845b804f62151cedbed83ad759672bc9fe.pdf`

- pp. 3–12: Making the switch credible
- pp. 13–22: The project you can defend
- pp. 23–35: LLM fundamentals
- pp. 36–49: Model selection and adaptation
- pp. 50–59: Prompt and context engineering
- pp. 60–75: Retrieval and RAG architecture
- pp. 76–85: RAG quality and failure diagnosis
- pp. 86–99: Evaluation and testing
- pp. 100–109: Agents and tool use
- pp. 110–120: AI product reliability and human oversight
- pp. 121–134: Voice AI
- pp. 135–144: Cost, latency and scalability
- pp. 145–154: Security, privacy and safety
- pp. 155–164: LLMOps, monitoring and deployment
- pp. 165–175: GenAI system-design exercises

### Backend Interview Playbook

Source: `docs/backend-engg/backend-interview-guide-2026-18-09-10-54-51.pdf`

- pp. 3–12: Project and ownership deep dives
- pp. 13–22: API design and integration
- pp. 23–32: Databases and transactions
- pp. 33–42: Kafka, queues and asynchronous processing
- pp. 43–52: Redis and caching
- pp. 53–62: Distributed systems and microservices
- pp. 63–72: Reliability and resilience
- pp. 73–82: Production incidents and debugging
- pp. 83–92: Observability and deployment
- pp. 93–102: Security and data protection
- pp. 103–112: System design (the blank-page round)
- pp. 113–122: Behavioural and managerial rounds

### High-Level Design Problems

Source: `docs/backend-engg/hld-interview-problems-2026-12-09-06-25-0.pdf`

- pp. 3–5: Design a URL Shortener
- pp. 6–8: Design a News Feed
- pp. 9–11: Design a Chat App
- pp. 12–14: Design Ride-Hailing & Delivery Matching
- pp. 15–17: Design a Rate Limiter
- pp. 18–20: Design a Notification Service
- pp. 21–23: Design a Video Streaming Service
- pp. 24–26: Design a Ticket Booking System
- pp. 27–29: Design a Typeahead Service
- pp. 30–32: Design a Web Crawler
- pp. 33–35: Design a File Sync Service
- pp. 36–38: Design a Payment System
- pp. 39–41: Design an Ad Click Aggregator
- pp. 42–44: Design a Job Scheduler
- pp. 45–47: Design a Search System
- pp. 48–50: Design a Trading System

### LLD Core Concepts

Source: `docs/backend-engg/lld-core-concepts-2026-12-09-06-25-0.pdf`

- pp. 3–3: Coupling & Cohesion
- pp. 4–4: SOLID Principles
- pp. 5–5: DRY
- pp. 6–6: YAGNI
- pp. 7–7: KISS
- pp. 8–8: Composition vs Inheritance
- pp. 9–9: Interface vs Abstract Class
- pp. 10–10: Association, Aggregation, Composition
- pp. 11–11: How to Approach Any LLD Problem
- pp. 12–12: Factory Method
- pp. 13–13: Builder
- pp. 14–14: Singleton
- pp. 15–15: Adapter
- pp. 16–16: Decorator
- pp. 17–17: Composite
- pp. 18–18: Strategy
- pp. 19–19: Observer
- pp. 20–20: State
- pp. 21–21: Command
- pp. 22–22: Chain of Responsibility
- pp. 23–23: Template Method

### Low-Level Design Problems

Source: `docs/backend-engg/lld-design-problems-2026-12-09-06-25-0.pdf`

- pp. 3–4: Parking Lot
- pp. 5–6: Vending Machine
- pp. 7–8: Elevator System
- pp. 9–10: ATM
- pp. 11–12: Coffee Machine
- pp. 13–14: Chess
- pp. 15–16: Tic-Tac-Toe
- pp. 17–18: Snake and Ladder
- pp. 19–20: Movie Ticket Booking
- pp. 21–22: Hotel Management
- pp. 23–24: Car Rental
- pp. 25–26: Library Management
- pp. 27–28: Splitwise
- pp. 29–30: Digital Wallet
- pp. 31–32: LRU Cache
- pp. 33–34: In-Memory File System
- pp. 35–36: Text Editor
- pp. 37–38: Logging
- pp. 39–40: Notification Service
- pp. 41–42: Pub-Sub

### System Design Core Concepts

Source: `docs/backend-engg/system-design-core-concepts-2026-12-09-06-25-0.pdf`

- pp. 3–3: Vertical Scaling
- pp. 4–4: Horizontal Scaling
- pp. 5–5: Load Balancing
- pp. 6–6: Sharding / Partitioning
- pp. 7–7: Replication
- pp. 8–8: Stateless vs Stateful Services
- pp. 9–9: Monolith vs N-Tier vs Microservices
- pp. 10–10: SQL vs NoSQL
- pp. 11–11: Caching
- pp. 12–12: Indexing
- pp. 13–13: Consistent Hashing
- pp. 14–14: ACID Transactions & Isolation
- pp. 15–15: Write-Ahead Log
- pp. 16–16: Object vs Block vs File Storage
- pp. 17–17: Database Connection Pooling
- pp. 18–18: DNS Resolution
- pp. 19–19: CDN & Edge Caching
- pp. 20–20: HTTP/1.1 vs HTTP/2 vs HTTP/3
- pp. 21–21: Service Discovery
- pp. 22–22: Real-Time Communication
- pp. 23–23: API Gateway / Reverse Proxy
- pp. 24–24: CAP Theorem
- pp. 25–25: Consistency Models
- pp. 26–26: Consensus (Paxos, Raft)
- pp. 27–27: Distributed Locks
- pp. 28–28: Message Queues
- pp. 29–29: Idempotency
- pp. 30–30: Event-Driven Architecture
- pp. 31–31: Backpressure
- pp. 32–32: Rate Limiting
- pp. 33–33: Bloom Filters
- pp. 34–34: Circuit Breaker + Retry
- pp. 35–35: Back-of-Envelope Estimation
- pp. 36–36: Monitoring & Observability
- pp. 37–37: Batch vs Stream Processing
- pp. 38–38: AuthN vs AuthZ
