# M1 learner experience contract

Planning only; specification §§5.8, 6, 7.1, 12, 13, 15. FND-002–008, NFR-002/003/007. M1 has no real lab, score, catalogue purchase or coach. US-02/03/04 and their flat tasks in plan.json own the implementation. UX tasks produce final field/component/key inventories before coding.

## Journeys and states

| Screen | Normal action / destination | Loading, empty, failure and recovery | Focus and accessibility |
|---|---|---|---|
| Signup | Email/password + consent where applicable → inbox instructions | Validate required fields; neutral duplicate result; bounded bot/rate checks; mail outage/retry; submit pending prevents duplicate request | Persistent labels; password rules before input; accessible bot alternative; summary links to invalid fields |
| Inbox / verify | Resend or follow mail → verified onboarding | Sent/pending; expired/reused/malformed token; resend throttled with retry timing; provider outage | Initial heading; polite sent status; actionable expired-link recovery; no token in telemetry |
| Signin | Email/password or Google/GitHub → safe internal destination | Wrong credentials neutral; pending; offline; unverified → resend; expired session → signin | Preserve safe email on failure, password never in logs; error summary focus; buttons named by keys |
| Provider return | Successful supported linking → onboarding or dashboard | Cancel, denied scopes, state mismatch, account collision, provider unavailable → signin/retry | Heading explains safe next action; no raw provider error/details exposed |
| Forgot password | Email → neutral sent instructions | Empty/invalid; pending; rate limit/outage → retry | Do not disclose account existence; status live region |
| Reset | New password → signin | Invalid/expired/replayed token → request another; pending/error; successful reset revokes relevant sessions | Rules and field errors associated; success heading focus; no automatic unsafe return |
| Onboarding | Background, level, goal, optional interview date → dashboard; explicit skip available | Defaults unselected, date optional; save pending; offline/validation errors preserve values; stale version → reload saved values or review draft | Fieldset/legend and date help; keyboard order follows visual order; first invalid field via summary |
| Profile edit | Dashboard one-action profile link → save → dashboard | Saved/skipped state distinguished; loading/empty optional fields; concurrent update returns conflict and preserves draft until explicit resolution | Clear cancel/save and status; focus restored to triggering control after dialog |
| Empty dashboard | Complete/edit profile is primary action | Separately labelled no owned labs, no completed labs, no mastered labs; no reviews/weak skills/streak/readiness yet; skeleton then error/retry with preserved navigation | Semantic sections, no invented zero readiness percentage; no disabled future-feature promise; one clear next action |
| Privacy settings | Export or delete after recent-auth challenge | Export pending/download/error; deletion confirmation/cancel/pending/idempotent success; expired session → re-auth; outage retry | Destructive action names consequence; accessible dialog focus trap/Escape/return; completion focus signin heading |
| Global protected route | Session guard → intended internal destination | Anonymous signin; unverified verify instructions; expired re-auth; safe errors for DB/Redis outage | Navigation landmarks, skip link and consistent focus; no client-only authorization |

All screens have designed loading, empty/not-applicable, invalid, success, offline and server-error states. Recovery never silently loses a profile draft or exposes secrets. Never use raw library errors as learner copy. English keys cover labels, errors, help, status, a11y names, theme controls, bot alternatives and mail subject/body; namespaces common/auth/mail/profile/dashboard/privacy. Pseudolocalization and missing-key checks include accessibility text. Synthetic data is test-only and never presented as earned progress.

## Fields and navigation

Background enum: frontend, backend, mobile, data, new-to-tech. Level: beginner, intermediate, experienced. Goal: job-search, promotion, learning. Optional interview date is an ISO calendar date (not a timezone-shifted timestamp). Locale defaults en. Final schema/UX contracts must use identical enum values. Display name optional and bounded; password limits follow verified pinned library security configuration. Onboarding state is not-started, skipped or completed; skip persists explicitly, returns do not reprompt indefinitely. Profile updates include version; conflict offers safe reload/reapply, never last-writer silent loss.

The designed normal path is background → level → goal → optional date → save, targeted under 60 seconds (FND-006 SHOULD). UX measures design walkthrough; implementation/browser/staging usability timings are separate evidence. Dashboard-to-profile takes one action; active-lab continuation belongs to M3 and is only a reserved layout slot here. Internal return URLs must be normalized/allowlisted by server.

## Responsive, themes and accessible interactions

Review at 320px phone, 768px tablet and 1280px desktop. Single-column auth/profile on narrow screens; dashboard sections stack in reading order. No horizontal page scrolling at supported zoom, hover-only actions or colour-only status. WCAG 2.2 AA includes visible unobscured focus, 4.5:1 normal text, 3:1 large text/nontext, 24px targets or compliant spacing, error association, keyboard order, screen-reader status and accessible authentication. Light/dark/system theme preferences must render readable first paint. Four track colours have textual identifiers; token values and measured contrast are delivered in UX-101 and CODE-108. Respect reduced motion; avoid mandatory animation.

Unit/component/Storybook and browser scans accompany implementation tasks; manual keyboard/screen-reader and physical phone + desktop hosted staging evidence are release QA stage requirements. Tablet/emulated checks are supplemental and labelled. QA never appears as an implementation story and cannot be gated on a final acceptance story. Changed UI or candidate invalidates affected evidence; real email and Google/GitHub success cannot be inferred from these designs or fixtures.
