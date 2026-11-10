# Proposed launch labs

Status: **draft curriculum; exactly 15 proposed launch labs; none published by this document**.

Prepared: 10 November 2026. This is an authoring and review plan, not evidence of 15 implemented labs. Content, scoring, accessibility, source approval, simulations and learner transfer still require review. Existing prototype activities do not automatically satisfy these specifications.

## Authority and publication rules

`planning/Systems Labs Product Specification.md` version 1.0 controls scope, milestone order and learning rules. The 15 labs belong to M3, after the M2 trace foundation. Each lab has 3–8 required activities below. The engine supports all seven required types; an individual lab need not use them all.

The first lab in each track is free: A01, B01, C01 and D01. All are normal, complete labs with the same progress/mastery rules. Locked paid labs expose their first activity as a preview; preview does not imply ownership of the remainder. The small free standalone algorithm-visualizer set is a separate catalogue decision and does not replace these four free labs.

All learning activities are deterministic except explicitly labelled coach dialogue. Scored answers, first-attempt evidence, completion and mastery are decided on the server. `visualize` is normally unscored but requires an acknowledgement submission; other activities below are proposed as scored. Final authoring must validate each answer rule against the reference implementation or structural rubric.

The threshold is first-attempt correct evidence on at least 70% of scored activities, with a correct first-attempt `predict` and design/defend evidence wherever present. At M3, scored `build-diagram` supplies design evidence. Hints are recorded, progressive and limited to three; the specification does not disqualify a hinted first correct submission. Full `defend`, `mock-question` and `code-step` types remain LATER; basic interview angles can be authored as content without introducing those activity types.

## Fifteen-lab catalogue

Activity sequence notation: **V** = `visualize` (unscored); **P** = `predict`; **F** = `tap-flaw`; **O** = `order-steps`; **T** = `tune`; **C** = `choose`; **D** = `build-diagram`. All listed activities are required. Design feedback assesses typed semantic structure rather than layout.

| ID | Track / launch position | Lab and observable outcome | Proposed skills / prerequisites | Required activity sequence | Scored count / threshold and coverage |
|---|---|---|---|---|---|
| **A01** | DSA / first, **free** | **Bubble Sort: Comparisons, Swaps and Invariants.** Trace adjacent comparisons and explain why the sorted suffix grows. | `complexity.basic`, `arrays.indexing`, `sorting.bubble`, `sorting.invariants`; entry-level input literacy. | V: trace a small array; P: next comparison; O: compare/swap/pass order; F: incorrect boundary; C: work-growth explanation. **5 activities.** | 4 scored; at least 3 first-correct, including P. No design activity. |
| **A02** | DSA / second | **Binary Search: Boundaries and Termination.** Maintain a search interval and avoid off-by-one or nontermination errors. | `arrays.indexing`, `search.binary`, `search.invariants`, `complexity.logarithmic`; A01's array/indexing skill. | V: interval trace; P: next midpoint; T: target and boundary case; F: nonshrinking interval; C: precondition/termination rule. **5 activities.** | 4 scored; at least 3 first-correct, including P. No design activity. |
| **A03** | DSA / third | **Graph Traversal: BFS and DFS.** Predict discovery order and explain the frontier structure. | `graphs.representation`, `graphs.bfs`, `graphs.dfs`, `queues.frontier`, `stacks.frontier`; A01's sequence/indexing skill. | V: inspect BFS trace; P: next enqueued node; O: DFS stack operations; D: build a small typed graph satisfying a reachability constraint; C: traversal choice for a stated need. **5 activities.** | 4 scored; at least 3 first-correct, including P and D. Side-by-side compare mode stays M8. |
| **A04** | DSA / fourth | **BST Inorder: Recursion and the Call Stack.** Connect recursive calls, traversal order and sorted output for a valid BST. | `trees.bst`, `trees.inorder`, `recursion.call-stack`; A03's node/edge representation skill. | V: tree/call-stack trace; P: next visited node; O: left/visit/right operations; F: a violated BST ordering condition; C: traversal consequence. **5 activities.** | 4 scored; at least 3 first-correct, including P. No design activity. |
| **B01** | System design / first, **free** | **Request Journey: DNS, CDN and Origin.** Trace resolution and delivery while separating client, edge and origin responsibilities. | `networking.request-lifecycle`, `networking.dns`, `delivery.cdn`; entry-level client/server vocabulary. | V: a request trace; O: resolve/connect/request sequence; P: cache-hit route; D: construct the client/edge/origin path; C: cache freshness choice. **5 activities.** | 4 scored; at least 3 first-correct, including P and D. |
| **B02** | System design / second | **Load Balancing: Capacity and Failed Backends.** Route a workload while accounting for unequal capacity and delayed health detection. | `scaling.load-balancing`, `scaling.capacity`, `reliability.health-checks`; B01. | V: routing trace; P: next eligible destination; T: weights/capacity for a fixed workload; F: unsafe health assumption; D: remove a single-backend dependency. **5 activities.** | 4 scored; at least 3 first-correct, including P and D. |
| **B03** | System design / third | **Caching: Freshness and Stampedes.** Distinguish hit/miss/stale paths and single-flight from TTL jitter. | `caching.cache-aside`, `caching.invalidation`, `caching.stampede`; B01 and B02's capacity skill. | V: cache-aside trace; P: returned value after a source update; T: refresh policy under explicit freshness/load limits; F: duplicate refill assumption; D: protect the source from a hot-key burst; C: jitter versus coalescing. **6 activities.** | 5 scored; at least 4 first-correct, including P and D. |
| **B04** | System design / fourth | **Queues: Throughput and Backpressure.** Predict backlog growth and choose an explicit overload response. | `messaging.queues`, `messaging.delivery`, `reliability.backpressure`; B02's capacity skill. | V: producer/consumer trace; P: queue length after a time interval; T: admission/consumer capacity; O: acknowledgement and retry sequence; D: bounded worker pipeline; C: overload trade-off. **6 activities.** | 5 scored; at least 4 first-correct, including P and D. |
| **B05** | System design / fifth | **Database Indexes: Reads, Writes and Query Cost.** Explain when an index helps a query and what it adds to writes. | `databases.indexes`, `databases.query-plans`, `databases.write-cost`; A01's complexity skill and B01. | V: scan versus indexed lookup states; P: rows examined under a stated model; T: index choice for a bounded workload; F: unsupported selectivity assumption; C: read/write trade-off. **5 activities.** | 4 scored; at least 3 first-correct, including P. No design activity. |
| **C01** | Software engineering / first, **free** | **Testing and CI: Protect a Change.** Select useful checks and diagnose a pipeline that permits an unsafe change. | `testing.behaviour`, `testing.regression`, `delivery.ci`; entry-level change/test vocabulary. | V: a change moving through checks; P: outcome of an explicit test/change pair; O: pipeline stages; F: a missing behavioural check; C: meaningful regression coverage. **5 activities.** | 4 scored; at least 3 first-correct, including P. No design activity. |
| **C02** | Software engineering / second | **SOLID and Strategy: Change a Requirement Safely.** Use a changing rule to justify an abstraction and its cost. | `design.coupling`, `design.solid`, `patterns.strategy`; C01. | V: dependency/change walkthrough; P: affected components; F: concrete reach-through; D: a dependency graph for interchangeable rules; C: abstraction trade-off. **5 activities.** | 4 scored; at least 3 first-correct, including P and D. |
| **C03** | Software engineering / third | **API Evolution: Compatibility and Authorization.** Evolve a contract without confusing compatibility with access control. | `api.versioning`, `api.compatibility`, `security.object-authorization`; C01 and B01. | V: old/new client request flow; P: compatibility outcome; F: object-access vulnerability; O: safe migration sequence; D: place the authorization responsibility; C: versioning trade-off. **6 activities.** | 5 scored; at least 4 first-correct, including P and D. |
| **D01** | Product architectures / first, **free** | **URL Shortener: Create, Resolve and Scale.** Design distinct create/resolve paths and account for uniqueness, caching and failures. | `product.url-shortener`, `capacity.estimation`, `storage.uniqueness`; B01, B02 and B03. | V: requirements and request paths; P: cached resolve result; T: capacity arithmetic; D: create/resolve architecture; F: alias race; C: redirect/caching trade-off. **6 activities.** | 5 scored; at least 4 first-correct, including P and D. |
| **D02** | Product architectures / second | **Chat: Delivery, Ordering and Reconnection.** Separate transport, durable delivery and client reconciliation. | `product.chat`, `messaging.ordering`, `messaging.deduplication`, `reliability.reconnection`; B04 and C03. | V: message lifecycle; P: duplicate/out-of-order outcome; O: reconnect/replay sequence; D: durable delivery path; F: unsafe acknowledgement; C: delivery guarantee trade-off. **6 activities.** | 5 scored; at least 4 first-correct, including P and D. |
| **D03** | Product architectures / third | **Payments: Retries, Idempotency and Recovery.** Prevent duplicate effects under retry and distinguish known failure from unknown outcome. | `product.payments`, `api.idempotency`, `transactions.recovery`, `reliability.unknown-outcome`; B04 and C03, with transaction fundamentals introduced in the lab. | V: payment attempt/event trace; P: retry outcome; O: durable claim/effect/result operations; D: idempotent processing path; F: read-then-write race; C: recovery/consistency trade-off. **6 activities.** | 5 scored; at least 4 first-correct, including P and D. |

Distribution: **4 DSA + 5 system-design + 3 software-engineering + 3 product-architecture labs = 15**. All seven required activity types appear. The five M2 algorithms are exercised by A01–A04; A03 includes BFS and DFS as sequential reference traces until compare mode ships in M8.

These 15 labs are the M3 seed, not a claim of complete §4 curriculum coverage. Maintain a coverage backlog for the remaining foundations/core/advanced topics and product case studies through M8's 60+ lab expansion. All §5.1 renderer families belong to M2; linked-node/table renderers use synthetic state fixtures before later labs introduce their reference algorithms.

The prerequisite entries are a proposed acyclic skill graph, not automatic learner lockouts. Recommendations explain prerequisites. A first-track free lab remains accessible even if the interface recommends prerequisite practice elsewhere.

## Source support and original-authoring gaps

The seven local PDFs provide candidate source material, not automatically approved commercial content:

- `docs/backend-engg/system-design-core-concepts-2026-12-09-06-25-0.pdf`
- `docs/backend-engg/hld-interview-problems-2026-12-09-06-25-0.pdf`
- `docs/backend-engg/lld-core-concepts-2026-12-09-06-25-0.pdf`
- `docs/backend-engg/lld-design-problems-2026-12-09-06-25-0.pdf`
- `docs/backend-engg/backend-interview-guide-2026-18-09-10-54-51.pdf`
- `docs/backend-engg/0313dad636ce7a70f40d7b261cf8426c9373a14d9dc9d3aa.pdf` — DevOps Interview Playbook.
- `docs/backend-engg/ac4051c9aa34c0845b804f62151cedbed83ad759672bc9fe.pdf` — Software Engineer to AI Engineer Interview Guide.

| Labs | Candidate grounding | Required original work and approval gap |
|---|---|---|
| A01–A04 | Existing corpus is primarily backend/design/interview material; it does not establish complete DSA lesson coverage. | Author original explanations, reference implementations, four-language code, traces, assessments and diagrams. Verify algorithm claims through reference tests and approved references. Do not copy a third-party visualizer's content or assets. |
| B01–B05 | System-design concepts; backend/DevOps networking, database, caching and messaging modules. | Confirm exact page/section claims; author original trace models, inputs, games, wording and misconception feedback. State simplifications; validate calculations and deterministic outcomes. |
| C01–C03 | DevOps CI/CD material; LLD coupling/SOLID/Strategy; backend API/security modules. | Author original code/change scenarios and structural rubrics. Review security and compatibility claims against approved sources; avoid presenting one pattern as universally correct. |
| D01–D03 | HLD URL shortener/chat/payment problems; backend API/messaging/transaction material. | Author original worked requirements, estimates, graphs, failure traces and assessment variants. Preserve realistic alternatives and conditional assumptions; source narratives are examples, not learner experience. |

The specification §14 OPEN licensing/attribution decision remains unresolved in this draft. The owner must establish what third-party source material may be commercially adapted and admitted to the coach's approved source corpus. Until then, referenced PDF passages are candidate research inputs; no content is marked approved or published here. Company-name usage is separately OPEN; the proposed lab titles use generic product categories.

Each lab's final authoring package must name its author/reviewer, source IDs with exact section/page anchors, attribution requirements, content version, source approval status and original assets. Original authoring does not by itself clear rights in copied illustrations, code or text. Approved lesson sections become the coach's grounding units at M6.

## Per-lab authoring and publication checklist

1. Freeze the objective, learner level, misconception and skill graph entries.
2. Write the 3–8 activity definitions, each with translation keys, prompt, reference data, correct-answer logic, up to three hints and an explanation.
3. Classify scored/unscored activities and eligible design evidence. Verify threshold and required predict/design coverage.
4. Produce deterministic reference traces/models and test all answer keys, including boundary and deliberately wrong cases.
5. Provide keyboard/screen-reader alternatives, reduced-motion states, phone layouts and light/dark diagrams.
6. Author the interview angle and model answer outline as source-supported lesson content. Timed mocks and advanced dialogue remain at their assigned milestones.
7. Review original source claims, simplifications, examples and attribution/approval status. Do not fabricate a learner's career achievements.
8. Validate schema, explanations, skills and prerequisite reachability in CI. Preview locally with hot reload.
9. Complete independent learning/content review plus staging phone/desktop evidence against the exact content version and commit.
10. Publish only after the required source decisions and milestone acceptance gates pass. Generated drafts, schema validity and source-index existence are insufficient evidence.

## Evidence status

No launch-lab package in this document has yet supplied the required reference tests, answer-key review, translation catalogue, accessibility audit, staging recordings, learner transfer study or source-rights approval. These remain explicit backlog deliverables. The existing caching prototype is a reusable experiment candidate for B03, but its earlier participation/self-review completion behaviour must be replaced by the specification's server-scored attempt and mastery rules.
