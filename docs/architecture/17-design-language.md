# 17 — The Eden Design Language (the UI ruling)

> Status: Draft · 2026-07-07 · Canonical home for: the interface design language (tokens,
> atomic hierarchy, information architecture, motion), the one-shell ruling, and the wizard/
> settings/theming patterns. Grounded in an eyes-on screenshot audit of every screen (2026-07-07)
> plus the code survey; realizes the reusable-UI standing bar (components live in
> `libs/typescript`, the app consumes) and the math-is-source-of-truth dimension (ADR-0024,
> `@eden/scale`). Amends nothing; it gives the frontend what doc 10 gave the libraries: one
> engineering bar.

## 1. Diagnosis — why it reads "AI generated" ✅ (eyes-on evidence)

The bones are good: the serif display face, the ◆ mark, the deep-forest accent, and the
Clusters screen — which is genuinely excellent (dense, purposeful, scannable) and is hereby the
**taste north star**. The failures are systemic, not cosmetic:

1. **Two shells.** `/chat` is a parallel app (own header, own session rail, own "New project",
   its own microcopy vocabulary) — "New project" on the Projects page **leaves the app** and
   opens a modal over the other world. The product feels like two demos stapled together.
2. **Empty states as pages.** Projects/Sessions/Chat render a centered sentence and one button
   in ~1,300px of void. An empty state is a product surface, not an apology.
3. **The wizard is a cramped modal**: small type, dead space, tiny progress dots, over a
   context-switched background. The ask is the opposite: full-screen, huge type, fewer words.
4. **The login is the default AI card**: two *disabled fake* OAuth buttons ("coming soon" — a
   dishonest UI), a washed-out submit that looks disabled, a floating card in a void.
5. **Unmanaged type system**: serif display + sans body + mono data exist but nothing governs
   when each appears; sizes are ad-hoc per component.
6. **No proportional discipline**: no content max-widths, a 3-item nav owning a full column of
   dead vertical space, hairline full-width rules that cut pages arbitrarily.

## 2. Principles 🔶

- **P-D1 · One shell.** Every surface lives inside one chrome. Chat is a *view of a project*
  (or a global list), never a second app.
- **P-D2 · The project is the spine.** A project owns its build conversation, workspace,
  sessions, and insight. Global lists (Sessions, Clusters) are cross-cuts, not silos.
- **P-D3 · Math sets proportion.** Spacing, type, radii come from the `@eden/scale` modular
  ramps rendered as CSS custom properties by `@eden/theme` — a hardcoded px/hex in app code is
  a defect (enforced, not aspirational: the cohesion/lint lane greps for it).
- **P-D4 · Three voices of type.** Serif display for *identity moments* (page titles, wizard
  questions, empty-state headlines). Sans for *interface*. Mono for *data* (ids, chips, counts,
  paths). Never mixed within one text block.
- **P-D5 · Density where the work is.** Clusters-grade density for working surfaces; generosity
  only for focus moments (wizard, login). Voids are never generous, just empty.
- **P-D6 · Honest chrome.** Nothing disabled-that-looks-enabled, nothing enabled-that-looks
  disabled, no "coming soon" controls. If it doesn't work, it isn't rendered.
- **P-D7 · Components live in the library.** The app composes `@eden/primitives`; it defines no
  atom/molecule of its own. Promotion (app → lib) is the normal flow for anything used twice.

## 3. Tokens & themes 🔶

`@eden/theme` renders the DTCG tokens to CSS custom properties under `:root[data-theme=light]`
and `:root[data-theme=dark]`; the app mounts a `ThemeProvider` (persisted preference:
light/dark/system) and consumes **only** `var(--eden-*)` values.

- **Color:** one neutral ramp (warm gray to pair with the serif), the forest-green accent as a
  full ramp (50–950) not a single flat, plus the four status hues already living on Clusters
  (healthy/updating/degraded/down). Dark theme derives from the same ramps (not inverted grays).
- **Type ramp:** `@eden/scale.stepAt` over the base — display steps for serif moments, a 4-step
  interface ramp, one mono size. Line-heights ride the same ramp.
- **Space ramp:** the scale's spacing steps as `--eden-space-*`; component insets and page
  gutters name steps, never px.
- **Radii/elevation:** 3 radii (control, surface, sheet), 2 shadows (raised, overlay). No more.

## 4. Atomic hierarchy 🔶 (what lives in `@eden/primitives`)

- **Atoms:** Button (accent/neutral/ghost/destructive), Input, Textarea, Badge, Chip (the mono
  data chip from Clusters), Kbd, Avatar, Spinner, Divider, Icon slots.
- **Molecules:** Field (label+input+hint+error), Card, StatRow (the Clusters header numbers),
  EmptyState (headline · body · primary action · *content slot* — templates/recents, never a
  bare void), Tabs, Toast, HealthBadge.
- **Organisms:** AppShell (rail + header + content grid), SessionRail, Sheet (right-side panel —
  replaces most modals), Modal (confirm-only), CommandPalette (the ⌘K that today only exists in
  the chat shell — it becomes global), WizardShell (§6), SettingsSurface (§7).

The app's existing near-twins get merged into these; every promotion carries the design-math
tests (contrast/proportion assertions) the primitives lane already enforces.

## 5. Information architecture — the one-shell ruling ✅

```
AppShell (one chrome: rail · header · content)
├── Projects                       ← home
│   └── [project]                  ← the spine
│       ├── Overview               (status, activity, coordinates)
│       ├── Build                  ← THE CHAT, embedded (session rail scoped to the project)
│       ├── Workspace              (3-pane: files · conversation · viewer — exists today)
│       └── Insight                (codeinsight Report — the endpoint shipped 2026-07-07)
├── Sessions                       ← global cross-cut (all projects' sessions, filterable)
├── Clusters                       ← unchanged (the north star)
└── Settings                       (§7)
```

`/chat` becomes a redirect into the owning project's **Build** view (or the global Sessions
list when unscoped). The chat shell's capabilities move into the one shell: the ⌘K palette goes
global, the gateway-status chip joins the header, the session rail becomes the Build view's
left column. The `/p/[slug]` legacy surface stays parked (unlinked) pending its own ruling.

## 6. The wizard pattern 🔶 ("larger, simpler words")

Full-screen focus route (not a modal): one question per screen, serif display at the largest
step, a single input, a thin progress bar, `1 / 3` in mono, Enter advances, Esc offers exit.
Copy budget: question ≤ 6 words, helper ≤ 1 sentence. The create flow keeps its wire contract
(propose → review → build) but the review step renders the proposal as editable *cards*, not a
form wall. The setup questionnaire reuses the same WizardShell.

## 7. Settings & themes ✅ (new surface)

A real Settings route in the shell: **Profile** (the platform identity), **Appearance** (theme
light/dark/system, accent), **Agents** (the `GET/PUT /agent-configs` surface that already
exists server-side), **Connections** (gateway/platform endpoints, read-only status). The login
screen is rebuilt honest: brand moment (◆ + serif), email+password, solid accent submit; OAuth
appears only when it works.

## 8. Verification bar (every wave) ✅

svelte-check 0/0 · vitest green · the e2e suite ≥ its 14-passed baseline (copy-assertion updates
land in the same commit as deliberate copy changes) · the primitives design-math/a11y lane green
for every promoted component · a fresh screenshot sweep diffed against the previous wave —
**eyes on every screen before a wave merges**.

## 9. Wave plan ✅

- **W-UI-1 Foundation:** theme CSS emission + ThemeProvider + token adoption in the shell;
  the atoms; kill hardcoded hex/px in the shell chrome.
- **W-UI-2 One shell:** AppShell organism; chat absorbed as the Build view; ⌘K global;
  redirects; the disconnect dies here.
- **W-UI-3 Focus moments:** the WizardShell + create/setup flows rebuilt full-screen; login
  rebuilt honest.
- **W-UI-4 Surfaces:** EmptyStates become product surfaces; project Overview/Insight views;
  Settings + themes shipped.
- **W-UI-5 Polish:** motion (the `@eden/theme` motion tokens), density tuning against the
  north star, the final screenshot review.
