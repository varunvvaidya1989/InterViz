# M1 interaction contract — proposed

Source: specification §§5.8, 6, 12, 13, 15; FND-002–008 and NFR-002/003. This is design input for founder review, not implemented-screen evidence. M1-UX-001 produces the final measured tokens, component specifications and string catalogue under docs/design/M1 before coding.

## Navigation and flows

Public `/sign-up`, `/sign-in`, `/verify-email`, `/forgot-password`, `/reset-password` and provider callback screens lead to verified, session-protected `/onboarding`, `/dashboard`, `/profile` and `/settings/privacy`. Routes are proposed Next.js route-group members, with URLs independent of group names. Unauthenticated deep links go to sign-in with a validated internal return path; unverified users go to verification. Never redirect to a caller-supplied external URL.

A fresh verified account sees onboarding. Saving or explicitly skipping persists a terminal onboarding state and opens dashboard; subsequent sign-ins go directly there. Interrupted drafts can be retried. Dashboard links directly to profile, privacy settings and sign-out. M1 has no current learning activity; reserve a future continuation component but do not show a dead Continue button or claim M3 resume evidence.

| Screen | Primary action and success | Required states and recovery |
| --- | --- | --- |
| Sign-up | Submit email/password and required library-supported fields; display verification instructions | Empty form, invalid email/password, submitting, existing-account-safe response, bot check, throttled countdown, service unavailable; disable duplicate submissions, keep safe fields and clear password after unsafe failure |
| Verify email | Open single-use link; continue to onboarding or sign-in as required by session policy | Awaiting inbox, resend pending, sent, invalid/expired/reused token, mail outage, throttled; resend with cooldown, switch account, sign-in link; no token shown in UI/logs |
| Sign-in | Password or Google/GitHub; reach internal destination | Empty/invalid credentials, pending, unverified, provider cancelled/error/linking conflict, locked/rate-limited, expired session; generic safe error and reset/resend options |
| Forgot password | Request reset email | Empty/invalid email, pending, generic sent response regardless of existence, throttled/provider failure; retry after delay and return to sign-in |
| Reset password | Submit new password with valid token; return to sign-in | Invalid/expired/used link, invalid password, pending, success, network failure; request new reset and never retain token in analytics |
| OAuth return | Library validates state/code and returns to app | Pending, rejected state, cancelled consent, provider outage, account collision; translated safe reason with sign-in retry; never silently link unverified identity |
| Onboarding | Save background, level, goal, optional date or skip | New/partial, saving, validation, save failure, session expiry, conflict, success; preserve non-sensitive form state, announce errors, offer retry/skip |
| Profile | Edit same fields and locale | Loading, loaded, no optional values, saving, success, conflict, failure; reload on conflict without overwriting another tab silently |
| Dashboard | Complete/edit profile | Loading skeleton labelled busy, empty, fetch error/retry, session expiry; empty sections distinctly label owned, completed, mastered, due, weak skills, streak and readiness as unavailable/no evidence; no score, purchased lab or skill fabricated |
| Privacy settings | Download export or confirm deletion after recent authentication | Loading, export preparing/ready/error, recent-auth challenge, deletion confirmation with cancel, deleting, complete, failure/retry; deletion returns to signed-out entry and invalidates sessions |

No new content, catalog or store routes are built. Empty dashboard copy explains that learning content is not part of this foundation; next action remains functional profile/settings navigation. Failure copy describes recovery kindly and never exposes whether an arbitrary account exists.

## Field and form contract

Background is one of frontend/backend/mobile/data/new-to-tech. Experience level defaults to unset and offers beginner/intermediate/experienced; goal offers job-search/promotion/learning. Optional interview date is an ISO calendar date, not a timezone-dependent timestamp. All onboarding fields may remain unset when skipped. Full save requests background, level and goal; profile updates validate partial fields. Locale defaults to `en`. Date parsing rejects impossible dates; past dates are allowed for retrospective goals with neutral helper text. No employer, company target, payment details or source corpus collected.

Normal onboarding is one compact screen with a skip action and optional date collapsed behind a clear label. Measure with a new participant following a scripted normal path; report elapsed time, device and assistance. Under 60 seconds is a SHOULD; a failed timing trial needs recorded UX follow-up, never a fabricated pass.

## Components and presentation

Use one shared owner for Button, Field, Select/RadioGroup, Alert, Status, Skeleton, Card, Dialog and navigation. Each has default/focus/hover/disabled/loading/error/success variants with translated accessible names. Theme selector supports system/light/dark and persists preference; first paint is readable without a theme flash. Four track colour tokens are present for future consistency but do not imply delivered tracks/content.

At 320px use a single form column with wrapping navigation, full-width actions and no hover-only content. At 768px retain readable field widths and generous spacing. At 1280px constrain forms to a comfortable reading width; dashboard may use a grid with semantic heading order. Browser zoom at 200% and reflow at 400% must retain actions and labels. Use at least WCAG-compliant 24px targets/spacing; aim for 44px touch controls. No information relies on track colour alone.

WCAG 2.2 AA checks cover 4.5:1 ordinary text contrast, 3:1 large text/non-text indicators, visible unobscured focus, keyboard order, form labels, autocomplete and error associations, accessible names, and status announcements. On submit failure focus the error summary with links to fields; success status is polite, destructive confirmations trap/restore focus correctly. Do not continuously announce skeletons. Password controls permit paste/password managers and have labelled reveal buttons. Any signup bot protection must offer an accessible path and fail safely. Reduced motion removes decorative transitions without losing information.

## Translation and analytics contract

Suggested keys: `auth.signup.*`, `auth.signin.*`, `auth.verify.*`, `auth.reset.*`, `auth.oauth.*`, `onboarding.*`, `profile.*`, `dashboard.empty.*`, `privacy.*`, `common.loading`, `common.retry`, `errors.*`, `a11y.*`, `mail.welcome.*`, `mail.verify.*`, `mail.reset.*`. Final catalogue includes every validation message, email subject/body, helper text, toast, theme label and consent text. No user-facing raw library errors or literal fallback sentences. Build checks reject missing keys; pseudolocalized text checks wrapping in both themes.

Document event names/payloads for signup and onboarding start/complete/skip/failure, dashboard view, profile update, and navigation drop-off. Operational audit events are separate from optional analytics. Do not send form field values or secrets to analytics. Missing M2+ completion/hint events remain deferred with their features.

## Review evidence

For every screen/state record commit/build, URL, timestamp, browser/version, viewport, theme and input method. Screenshots supplement keyboard and screen-reader observations. Automated accessibility scans are supplemented by manual checks. Desktop browser and actual phone staging review are required; emulation is explicitly labelled and does not substitute for the phone. No browser evidence exists for this plan.
