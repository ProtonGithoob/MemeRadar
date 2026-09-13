# MemeRadar — Precision Alpha Workstation

This is the frontend design contract for the operator console. It describes
how canonical evidence is presented; it never creates evidence or decision
semantics in the browser.

## 1. Visual Theme & Atmosphere

MemeRadar is a dark-first, evidence-first research workstation. The mood is
quiet, precise, and operational: dense enough for scanning, calm enough for
long sessions, and explicit when data is missing or unsafe to trust.

The visual direction combines restrained Linear-like surface hierarchy,
financial number legibility, crypto-native status treatment, and MemeRadar's
teal accent. It is not a marketing page and does not use a hero, WebGL,
parallax, glassmorphism, or decorative gradients.

Light mode is a supported operator theme, not an inversion afterthought.

## 2. Color Palette & Roles

All component colors use the CSS variables in `globals.css`.

- Canvas and shell surfaces establish the background hierarchy.
- Teal is reserved for active navigation, selected controls, links, and fresh
  evidence emphasis.
- Green means an explicitly positive/verified backend state.
- Amber means warning, degraded, stale, or incomplete evidence.
- Red means blocked, down, critical, or invalid evidence.
- Violet means a protected/advisory boundary.
- Gray means unknown, unavailable, or disabled.

State is always communicated with text and a marker/shape in addition to
color. UNKNOWN is never styled as a successful or safe state.

## 3. Typography Rules

The primary stack is `Inter`, then the platform UI sans stack. No remote font
is required. Numeric and address fields use the local monospace stack with
tabular numerals.

- Page title: 20–24px.
- Section title: 15–17px.
- Card heading: 13–15px.
- Body: 13–14px.
- Metadata: 11–12px.
- KPI: 24–34px where the existing data supports a KPI.
- Token and wallet identities: 11–13px monospace.

Uppercase eyebrow labels are metadata, not body copy. They stay short and do
not compete with the value they describe.

## 4. Component Stylings

Panels use a quiet border, one surface level, and a small radius. Elevation is
reserved for the shell, drawers, and transient focus—not every card.

Shared states are rendered with the existing semantic badges, pills, read
states, tables, and boundary strips. Interactive controls have visible hover,
focus, disabled, and selected states. Tables use local scrolling and sticky
headers; the page itself must not acquire horizontal overflow.

## 5. Layout Principles

The shell has a 220–248px desktop navigation rail, a 56–60px topbar, and a
bounded analytical workspace. Page sections use 20–28px separation; dense
grids use 8–16px gaps; panel padding uses 12–18px.

The reading order is:

`system truth → candidate priority → early evidence → risk → provenance → boundary`

The existing backend read models own content order and meaning. The browser
may format, sort, filter, expand, and group only.

## 6. Depth & Elevation

Use the canvas, shell, panel, raised-panel, and hover surfaces in that order.
Borders do most of the work. Shadows are small and limited to navigation
drawers and overlays. Avoid stacked translucent panels and permanent glows.

## 7. Animation & Interaction

Interaction is L1 / restrained L2. Use 120–180ms CSS transitions for hover,
focus, selection, drawer movement, and small state changes. Do not use
scroll-reveal, continuous animation, or client-side animation libraries.

`prefers-reduced-motion: reduce` disables nonessential motion and smooth
scrolling. Server components remain server components; client boundaries are
limited to controls that need state or browser APIs.

## 8. Do's and Don'ts

Do:

- show the source state, quality, freshness, as-of time, and reason codes;
- keep UNKNOWN, STALE, DEGRADED, BLOCKED, and EMPTY visibly distinct;
- show protected modes and the NO LIVE ORDERS boundary without making it a
  disruptive error banner;
- make long addresses safe to read, copy, and wrap locally;
- use accessible headings, table headers, labels, focus rings, and status text.

Do not:

- calculate alpha, risk, insider suspicion, provider health, readiness, or
  winner/rug labels in TypeScript;
- turn null/missing evidence into zero, false, safe, ready, or healthy;
- fabricate charts, deltas, sample counts, URLs, provider payloads, or labels;
- render secrets or use a provider-specific branch when a generic component
  already expresses the canonical model.

## 9. Responsive Behavior

The target matrix is 1440×900, 1024×768, 768×1024, and 390×844 in both
themes.

- Desktop keeps the full navigation rail and dense multi-column surfaces.
- Tablet uses a compact rail and collapses grids intentionally.
- Mobile uses the accessible navigation drawer, one-column summaries, and
  locally scrollable dense tables. Critical identity/state/risk information
  stays before secondary metadata.
- Touch targets are at least 44px where practical, especially the mobile
  navigation control and action buttons.

## Data Density Rules

Prefer compact labels and aligned numbers over decorative whitespace. A KPI
must have a canonical value, quality, and timestamp where available. A table
row should answer identity, state, score/confidence, risk, freshness, and
reason/provenance questions without requiring a second page when the API owns
those fields.

## Evidence Semantics

The frontend is a projection of canonical backend truth. It may not infer
business state from the absence of a field. `UNKNOWN != ZERO`,
`UNKNOWN != SAFE`, and `MISSING != PASS`.

Provider health is evidence quality, not alpha quality. Alpha evidence is not
production readiness. Research labels remain measurement-only and cannot
authorize execution.

## Operator Accessibility

Every status has a text label and a non-color marker. Focus is visible in both
themes. Navigation exposes `aria-current`, tables expose headers, errors keep
`role="alert"` or `role="status"`, and controls remain usable with a keyboard
and a touch viewport.
