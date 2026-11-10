# Learning experience contract

Status: **draft planning artifact; not published product content**.

Prepared: 10 November 2026. Implementation, user testing, accessibility audit, screenshots and performance measurements for this contract are **not yet available**. Earlier prototype tests do not establish conformance to this contract.

## Authority and working boundaries

`planning/Systems Labs Product Specification.md` version 1.0 is the product source of truth. MUST requirements take precedence over this contract and the older `planning/AGENT_HARNESS_PLAN.md`. Use the specification's M1–M8 sequence. Requirements below do not authorise implementing later milestones early.

The lead owns product scope, learning outcomes, task boundaries and recorded technical choices. UI/UX owns interaction and visual specifications and implementation review. Learning design owns misconceptions, skill/prerequisite mapping, assessment specifications and source support. Coding implements these contracts; independent QA verifies them against the exact submitted revision. A coding agent must not create a new mastery rule or silently simplify a learning objective.

Only the OPEN decisions in specification §14 are questions for the product owner. Routine ambiguities are resolved through the simplest compliant technical choice, recorded by the lead in `docs/decisions.md`. This document proposes choices; it does not replace that decision log.

## Learner journey and persistent concepts

**Choose a skill → understand the mechanism → predict an outcome → experiment → sketch a design → defend a decision → review → revisit weaknesses.**

Ownership, completion and mastery must have distinct labels and state presentations:

| Concept | Interface meaning | Evidence source |
|---|---|---|
| Ownership | The learner currently has access | Server-derived entitlement |
| Completion | Every required activity has at least one submission | Server attempts and lab progress |
| Mastery | First-attempt evidence meets the specification's threshold and coverage rules | Server scoring and skill state |
| Due for review | Previously demonstrated skills require another review | Server review schedule |

An overlapping bundle purchase must not create a second lab identity or reset progress. A refund or access revocation must preserve progress. The UI must explain access loss without describing previously completed work as erased.

Every view has one clear next action, designed empty/loading/error states, and a route back to the learner's current task. Continuing saved work must be reachable within two taps from the normal signed-in entry flow.

## Agent deliverables and handoff

Before coding a feature, the UI/UX and learning-design assignment supplies:

1. Learning objective and target learner; prerequisite skills and likely misconceptions.
2. An interaction storyboard with learner actions, system reactions and feedback.
3. Desktop, tablet and phone layouts, including keyboard and reduced-motion behaviour.
4. Component and state contracts, including loading, empty, validation, network failure and recovery states.
5. Translation keys for visible copy, narration, hints, errors and accessibility names.
6. Scored/unscored classification, answer logic, source references and progressive hints.
7. Acceptance criteria mapped to required tests and staging evidence.

The reviewer checks the actual implementation against this handoff. Evidence must identify the commit, content version, viewport/device and test environment. A mock provider response is not live-coach evidence; a screenshot is not evidence of keyboard or screen-reader operation.

## Milestone deliverables and exit evidence

| Milestone | UI/UX and learning-design deliverables | Required evidence before acceptance |
|---|---|---|
| **M1 — Foundations** | Design tokens; shared components and states; distinct track colours; light/dark themes; English translation catalogues; sign-up/verification/reset flows; skippable onboarding; empty dashboard separating ownership/completion/mastery. | Sign-up → verify → choose background → dashboard journey; onboarding can be skipped and the designed normal path takes under 60 seconds; keyboard/focus checks; phone and desktop review; translation-key validation. |
| **M2 — Visualizer core** | Synchronized visual/code/narration layout; playback and input contracts; all §5.1 renderer families: bars/cells, linked nodes, trees, graphs, tables and call stacks; five reference algorithms; four code-language presentations; predict flow. | Reference final-state and stable-step tests; consistent step identity in all panels; keyboard-only operation; invalid input examples; reduced motion; step render latency and long-trace checks. Algorithm fixtures exercise arrays/graphs/trees/call stacks; synthetic state fixtures cover linked nodes/tables until later algorithm content uses them. |
| **M3 — Lab engine and content** | Seven activity templates; author preview; hints and immediate feedback; attempt/retry/resume states; basic build-diagram editor; transparent completion/mastery displays; 15 launch-lab drafts with reviewable skills and assessments. | Content schema rejects invalid drafts; server submission/scoring tests; mastery boundary/coverage tests; weakness creation; basic diagram keyboard/save/reload checks; 15 lab reviews. No draft becomes published merely because its schema passes. |
| **M4 — Catalogue, store and entitlements** | Track/level/skill filters; first-activity previews; four free first-track labs; owned/locked/refunded states; lab and bundle purchase flows; admin grant/revoke states. | Two overlapping bundles preserve one progress record; refund removes only its access contribution; duplicate webhooks do not duplicate state; failure/reconciliation messaging demonstrated. Product pricing/launch-market OPEN decisions must be resolved before their dependent work. |
| **M5 — Revisit and recommendations** | Five-to-ten-minute review-session layouts; weak-skill queue; prerequisite explanations; readiness breakdown; due-review states; initial advanced architecture sandbox with seeded scenario, traffic, queue and bottleneck feedback. | A missed activity appears in Revisit; passed review updates schedule; recommendation explains its skill dependency; same graph/input/seed reproduces sandbox results; drawing feedback explains each rubric dimension. |
| **M6 — Interview and coach** | Question bank; basic timed mock notes/review; lab interview angles/model outlines; contextual coach; lesson-section citations; quota/error states; conversation deletion; protected timed-mock hints. | Unsupported question abstention and exact section citations; full solutions blocked during timed mock; deletion tested; coach outage preserves lab/notes; live-provider evidence distinguished from fixture tests. Source licensing OPEN decision must be resolved for any material admitted to the approved coach corpus. |
| **M7 — Growth and polish** | Subscription/promo/referral states; lifecycle-email designs; free-visualizer landing pages; analytics-informed drop-off changes; final performance and accessibility remediation. | WCAG 2.2 AA audit; Lighthouse performance at least 90 on agreed key pages; entitlement expiry/outstanding purchase states; analytics event-schema verification. Coach commercial inclusion OPEN decision resolved before configuring it. |
| **M8 — Scale content** | 60+ reviewed labs; complete the §4 curriculum coverage tracked beyond the 15-lab seed; compare mode; additional code languages; expanded content using the M2 renderer families; scalable author review. Team seats remain LATER unless subsequently authorised. | Each published lab passes source/content/reference checks; compare views retain clear independent step counters and shared input identity; full curriculum/language/renderer coverage tests; no mass publishing from generated drafts. |

Work remains in milestone order. Authored interview angles may be prepared as M3 content, but the full interview/coach capability belongs to M6. Compare mode belongs to M8 under the explicit milestone sequence.

## Trace, code and narration synchronization

### One authoritative state

The trace player holds one active `traceId`, trace version and logical step index. The visual snapshot, highlighted code line, narration, structures and output all derive from that same step. Renderers consume snapshots; they contain no algorithm logic.

Reference implementations generate traces server-side or at build time. The trace is immutable for a given algorithm version, validated input and seed where randomness is used. Editing the input requests a new trace and clearly resets playback; it must not splice new data into a previous trace.

### Language mapping

Specification §5.1 requires pseudocode, Python, JavaScript and Java. Shipping all four from M2 also satisfies the narrower milestone wording of pseudocode plus two real languages.

The specification's single `codeLine` cannot by itself identify the appropriate line in differently formatted language implementations. Proposed technical choice for the lead to record:

```ts
type LanguageId = 'pseudocode' | 'python' | 'javascript' | 'java';
type StepCodeMapping = {
  semanticOperationId: string;
  codeLineByLanguage: Record<LanguageId, number>;
};
```

Use a documented index base consistently. The player resolves the active language's line from the mapping; switching language preserves logical step, visual state, narration and prediction state. Each mapping must be in range and must identify the statement corresponding to that operation. Translated narration uses content translation keys while retaining the same operation identity.

### Measurable playback criteria

- Play/pause, forward, back, start, scrubber and at least three speeds are available. Proposed speeds: 0.5×, 1× and 2×.
- Arrow and space shortcuts work when focus belongs to the player. They must not capture ordinary typing in inputs, textareas or other editors.
- Manual stepping/scrubbing pauses playback. Reaching the end stops cleanly. Returning to any earlier step restores the same snapshot, highlighted line, narration and output.
- A code-language change never advances the step or clears pending mastery evidence.
- Tests verify final results, stable step counts and each panel's shared step identity. Include empty/boundary/invalid inputs supported by each algorithm.
- From accepted navigation input to committed synchronized panels, step updates render in under 100 ms on the recorded target device. Test a trace above 2,000 steps using windowing rather than rendering its whole history.
- Prediction pauses before the next outcome is exposed. Code, output, structures and scrubber must not accidentally disclose the answer through another panel.
- Reduced motion displays equivalent states and text without requiring movement to communicate comparisons, swaps or path changes.
- Narration identifies the mechanism in plain language; visual roles such as current/compare/swap/found have text or shape alternatives to colour.

## Seven M3 activity contracts

Every activity definition includes its prompt, trace/diagram reference where used, answer logic, explanation, one or more skill tags, difficulty, and progressive hints with a maximum of three. Every lab has 3–8 activities. All seven types are supported by the engine; each lab need not contain every type.

| Type | Learner action and submission | Feedback and accessible equivalent | Scoring contract |
|---|---|---|---|
| `visualize` | Inspect a trace and explicitly submit acknowledgement at required checkpoints/end. | Step summary and structures available as text; all playback controls keyboard operable. | Normally unscored; acknowledgement still creates a submission for completion. |
| `predict` | Commit the next comparison, state, visited node or output before disclosure. | Reveal actual next state after submission; explain why it follows from the mechanism. | Server checks the committed outcome against the reference trace. |
| `tap-flaw` | Select a semantic component, operation or issue. | Keyboard/list selection matches pointer selection; explain the violated property. | Server checks semantic IDs and issue rules, not pixel coordinates alone. |
| `order-steps` | Submit the order of operations. | Move-up/down controls accompany dragging; correct causal order is explained. | Server checks declared valid orders/partial-order constraints. |
| `tune` | Submit configuration parameters for a fixed scenario. | Numeric inputs accompany sliders; show which scenario constraints pass/fail. | Deterministic server calculation evaluates the submitted parameters. |
| `choose` | Commit a choice among alternatives. | Explain the chosen option, rejected alternative and trade-off kindly. | Server evaluates the choice against a versioned answer rule. |
| `build-diagram` | Submit typed components and labelled connections, plus stated assumptions where required. | Component/connection list supports creating/editing/deleting without a mouse. Feedback addresses semantic requirements. | Server evaluates structural and constraint rules. Layout, neatness and freehand appearance do not determine correctness. |

Immediate feedback identifies what was wrong, why, and a useful next hint before exposing a complete answer. Retries remain available without erasing the original evidence. Do not shame a learner or deduct mastery for deliberately running an experiment that fails.

## Literal completion, mastery and hint semantics

The server decides correctness and progress; the browser presents the returned result.

1. **Completion:** every required activity has at least one submission. A correct answer is not required for completion.
2. **Threshold:** correct first submissions must cover at least 70% of scored activities. Use an integer-safe comparison or `ceil(0.70 × scoredActivityCount)`.
3. **Coverage:** require a correct first-attempt `predict` and a correct first-attempt design/defend assessment wherever those categories exist in that lab. At M3, `build-diagram` supplies design evidence; `defend` stays LATER. Any other activity counted as design must explicitly declare that assessment facet in validated content.
4. **No invented penalties:** the specification records hints used but does not say that a hinted first correct submission loses mastery eligibility. Implement the literal rule; any stricter policy requires a specification change. Maximum three progressive hints remains mandatory.
5. **Retries:** the original first-submission result survives reloads, retries, duplicate network delivery and additional bundle purchases. A later correct retry cannot replace it.
6. **Idempotency:** repeated submission of the same attempt identifier returns the original result rather than creating a new first attempt.
7. **Unscored activities:** do not enter the mastery denominator. A draft with no scored activities cannot silently become mastered through a divide-by-zero or vacuous rule; the content schema should require an explicit supported assessment policy before publication.
8. **Due for review:** scheduling preserves historical evidence while making the skill due and adjusting current readiness. A passed review returns it to the mastered/current state and advances its schedule under the documented algorithm.
9. **Weaknesses:** wrong submitted answers create/update records keyed by skill tag. Show the next practice recommendation and why that skill needs attention.

Do not expose a full pre-submission solution through a normal hint. If an explicit skip/reveal action is introduced, its submission treatment must be recorded by the lead; it must not manufacture correct first-attempt evidence.

Required tests include threshold boundaries, the missing-predict and missing-design cases, hinted first submissions, unscored acknowledgement, correct retries after an initial error, idempotent delivery, overlapping purchases, and the review transition. The progress UI explains numerator/denominator and missing coverage rather than presenting an unexplained score.

## Basic M3 drawing versus advanced M5 sandbox

### M3: a complete bounded assessment interaction

- Palette of typed components; directional labelled connections; move/delete; pan/zoom and undo/redo as appropriate to the bounded task.
- Keyboard component/connection editor alongside the visual board.
- Submit, save/resume, draft recovery and clear save/retry status. Failed saves retain the draft.
- An app-managed semantic graph separate from scene positions/styles.
- Deterministic structural scoring, such as a required request path, protected dependency or explicit failure boundary.
- Accept multiple valid arrangements; coordinates do not determine architecture correctness.
- If freehand marks are allowed, they remain unscored appearance until the learner maps them to typed semantics.

### M5: add a scenario simulation

- Scenario inputs such as request rate, capacity and component failure.
- Simulation reproducible from the submitted graph, scenario version and seed.
- Traffic flow, queue growth and bottlenecks, with textual event/state summaries.
- Rubric feedback for requirements, single points of failure, scalability and cost under the declared teaching model.
- Explain assumptions and model limits. A diagram is not a real deployment and a simulated cost is not a provider quote.

The M3 activity must work without waiting for the M5 simulation. The M5 simulator should consume the already versioned semantic graph instead of inferring architecture from arbitrary canvas strokes.

## Accessibility, internationalization and themes

Acceptance target is WCAG 2.2 AA, with an audit completed by M7 and accessibility checked from M1 onward.

- Every interaction is operable with keyboard, visible focus and screen-reader names. Focus order follows the learning task and returns sensibly after dialogs/panels close.
- Canvas interactions have semantic list/form alternatives. Dragging has a non-drag alternative.
- Colour is supplemented by text, icons, patterns or shape. All track colours, interactive states, diagrams and code highlights work in both themes.
- Visualizer panels stack on smaller screens. Complex drawings have an expanded workspace. Phone operation must not depend on hover.
- Respect reduced-motion preferences; pause movement and retain equivalent state information. Screen-reader announcements summarise the active step rather than continuously announcing animation frames.
- Do not advance or submit a scored answer merely because focus or selection changes.
- Externalize every user-facing string, including content prompts, hints, validation errors, narration, empty states, accessibility labels and email copy. Launch in English; avoid assembling translated sentences from fragments.
- Test pseudolocalization for truncation/overflow. Preserve semantic IDs independently of translated text. Format dates, numbers and currency through locale-aware formatting.
- Support system/light/dark theme selection. Persist the preference without flashing an unreadable initial state.
- Test loading, empty, invalid, offline/save-failure, unauthorised, quota and model-outage states. Recovery preserves work and offers a clear next action.

Evidence requires phone and desktop staging review, keyboard-only journeys through all seven types, screen-reader checks of steps and diagrams, reduced-motion checks, automated accessibility results plus manual findings, theme contrast/state review, and pseudolocalization review. No such evidence has been collected for this draft.

## Proposed technical choices to record

The lead should record the simplest compliant resolution for:

- Four M2 code languages and semantic-operation-to-language line mapping.
- Index base, manual-navigation pause behaviour and pending-prediction disclosure rules.
- Unscored visualization acknowledgement and explicit design-evidence facets.
- Literal hint treatment, skip/reveal treatment, and nonzero assessment publication validation.
- Stable lab identity with versioned activity/content evidence; progress must identify the version completed.
- Accessible M3 graph editor and its M5 simulation extension.
- Synthetic linked-node/table state fixtures in M2 and their later algorithm/content coverage; all §5.1 renderer families remain in M2.
- Performance test device/network profile and the readiness calculation's explainable presentation.

Do not ask the owner for these routine choices. Product name/domain/pricing, launch markets/tax, coach commercial inclusion, third-party source licensing/attribution, and company-name usage remain the specification's §14 OPEN decisions.
