# FlockGo — Frontend 28-Day Plan

> Stack: React 18 + Vite + Tailwind CSS + Zustand + React Router v6 + Framer Motion + dnd-kit
> 
> **How to use this:** When you say "Day N done", I update this file and commit to GitHub with all changes for that day.

---

## WEEK 1 — Foundation & Correctness
**Goal:** Every existing page works cleanly end-to-end, no broken states, no silent failures

| Day | Task | Why It Matters |
|-----|------|----------------|
| ✅ 1 | Audit all existing pages — fix broken API calls, loading states, error states in TripDashboard, Survey, Voting, Recommendations, Results. Added NotFound page + 404 catch-all route. Fixed `useTrip` hook (`survey_submitted` was faked). Improved `ErrorBoundary` with reset + details. | Right now some pages show blank on error instead of a real message |
| 2 | Fix `useTrip` hook — add proper `survey_submitted` flag derivation from `/survey-status` endpoint (it's currently faked) | `ParticipantList` shows wrong checkmarks without this |
| 3 | Add global error boundary + 404 page + empty-state components (no trips, no participants yet) | App currently crashes or shows nothing on bad URLs |
| 4 | Wire `TripDashboard` status polling — auto-refresh trip status every 5s when status is `running_ml`, stop when done | Without this, user has to manually refresh to see analysis complete |
| 5 | Seed the local dev flow — run backend seed script, do a full click-through, fix any UI bugs found | You need to be able to demo in 30 seconds |

---

## WEEK 2 — Pages That Actually Work
**Goal:** All 7 routes are complete, polished, and handle real backend data correctly

| Day | Task | Why It Matters |
|-----|------|----------------|
| 6 | Complete `CreateTrip` page — form validation, trip month picker, duration, organizer fields, success redirect | This is the entry point — it needs to work perfectly |
| 7 | Complete `Survey` page — all preference fields from `SurveySubmit` schema, validation, already-submitted guard | Survey is what every participant touches — polish matters |
| 8 | Complete `Recommendations` page — ranked card list, ML score badge, budget range, activities list | This is the "wow" moment — it should look impressive |
| 9 | Complete `Voting` page — drag-and-drop ranking with dnd-kit (already installed), submit vote, already-voted guard | dnd-kit is installed but barely used — put it to work |
| 10 | Complete `Results` page — winner reveal with confetti (canvas-confetti installed), IRV round breakdown, final ranking | The payoff screen — make it celebratory |

---

## WEEK 3 — ML Insights UI
**Goal:** Surface the ML work the backend does — make it visible and impressive

| Day | Task | Why It Matters |
|-----|------|----------------|
| 11 | Add `GET /trips/{id}/metrics` display on TripDashboard — silhouette score, cluster count, drift status | "Shows ML output in the UI" — real talking point |
| 12 | ML Insights panel — bar chart of top 5 destinations by score (use a lightweight charting approach with Tailwind bars) | Interviewers can see the ML ranking visually |
| 13 | Cluster breakdown visualization — group participants by their assigned cluster with color coding | Makes "K-means clustering" concrete to anyone viewing |
| 14 | Drift indicator — show a subtle badge/banner when preference drift is detected for a participant | Exposes the drift detection feature |
| 15 | Wire `GET /trips/{id}/ml-insights` when it's added in backend Week 2 — compatibility pairs, outlier detection | Front-end ready to consume new endpoints as they land |

---

## WEEK 4 — Real-Time & Async UX
**Goal:** WebSocket status updates, proper job lifecycle UI (mirrors backend Week 3)

| Day | Task | Why It Matters |
|-----|------|----------------|
| 16 | Replace polling with WebSocket connection to `/ws/trips/{id}/status` — live status updates | "Real-time WebSocket" vs "polling every 5 seconds" — big difference |
| 17 | Task progress UI — pending/running/complete/failed states with animated indicators on TripDashboard | Mirrors the Celery task lifecycle the backend now tracks |
| 18 | Toast notification system upgrade — persistent toasts for long-running tasks, dismissible on completion | react-hot-toast is installed but underused |
| 19 | Optimistic UI for vote submission — immediately show "voted" state, roll back on error | Snappy feel, shows you understand optimistic updates |
| 20 | Connection state banner — show "reconnecting…" if WebSocket drops, graceful degradation to polling | Production resilience pattern |

---

## WEEK 5 — Budget Optimizer UI
**Goal:** Build the UI for the LP budget feature (mirrors backend Week 4)

| Day | Task | Why It Matters |
|-----|------|----------------|
| 21 | Budget planner entry point — add "Budget Plan" tab/section on TripDashboard, POST `/trips/{id}/budget-plan` | The novel feature nobody else has — needs a UI |
| 22 | Per-person constraint inputs — "Alice can't spend more than $400 on flights" form | Makes the optimizer actually configurable |
| 23 | Budget breakdown table — itemized per person per category (flights, hotels, activities) | This is the output — make it scannable and clear |
| 24 | Budget comparison view — show optimized total vs. unconstrained total, savings callout | Gives the optimizer a concrete value proposition |
| 25 | Export budget as CSV — client-side CSV generation from the breakdown table | Practical feature, surprisingly impressive in a demo |

---

## WEEK 6 — Analytics Dashboard
**Goal:** LLM cost visibility and A/B test results (mirrors backend Week 5)

| Day | Task | Why It Matters |
|-----|------|----------------|
| 26 | Analytics page `/analytics` — wire `GET /analytics/usage`, show total tokens, cost, requests | "Built LLM cost observability into the frontend" |
| 27 | A/B test results panel — v1 vs v2 quality score, cost, latency side-by-side from `GET /analytics/ab-test` | Real statistical comparison, visual proof the system learns |
| 28 | Cost-per-trip breakdown — spend by trip, by model, by day; API key auth header (`X-API-Key`) wired into axios interceptor | Closes the production engineering story from the frontend side |

---

## Across All Weeks — Non-Negotiables

These apply to every day of work:

- **Accessibility:** All interactive elements have proper `aria-label`, keyboard navigation works, focus states visible
- **Mobile-first:** Every page usable on a phone — the survey link is opened on mobile by participants
- **Loading states:** Every async call has a skeleton or spinner — no blank flashes
- **Error states:** Every fetch has an error case with a human-readable message, not just `console.error`
- **No dead code:** Remove `utils/mockData.js` entries as real data replaces them

---

## Resume Lines This Unlocks

- "Built real-time WebSocket UI for async ML pipeline status"
- "Implemented drag-and-drop ranked-choice voting with dnd-kit"
- "Surfaced K-means clustering and drift detection results visually"
- "Built LP budget optimizer UI with per-person constraint inputs"
- "Added LLM cost dashboard with A/B test comparison view"
- "Full responsive React SPA with Zustand, Framer Motion, and live polling fallback"

---

## Pages Map (final state)

| Route | Page | Status by Day 28 |
|-------|------|-----------------|
| `/` | Home | ✅ exists, polish week 1 |
| `/create` | CreateTrip | built day 6 |
| `/trip/:id` | TripDashboard | major upgrades weeks 1–4 |
| `/survey/:token` | Survey | completed day 7 |
| `/trip/:id/recs` | Recommendations | completed day 8 |
| `/trip/:id/vote` | Voting | completed day 9 |
| `/trip/:id/results` | Results | completed day 10 |
| `/analytics` | Analytics | built days 26–28 |
