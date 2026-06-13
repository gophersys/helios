---
meta:
  id: design-brief
  type: design-brief
  schema_version: 1.0.0
  project: eden
  status: draft
  version: 1
  created: 2026-06-12
  updated: 2026-06-12
  authors:
    - run: founder-intake-01
    - human: mateo
  links:
    realizes: []
    supersedes: null
    informs: ["artifact://design-system/eden-tokens-v0"]
  source:
    - run: founder-intake-01
      span: "C10, C11"
data:
  design_system_reference: "artifact://design-system/eden-tokens-v0"
  token_hints:
    - "Visual identity LOCKED per intake C21 (2026-06-12-design-assets.pdf): palette Deep Forest #243D2C (primary surface) · Moss #5C7F5C (accent) · Sage #A8B89C (support) · Bone #F4F1E8 (background/text-on-dark) · Ink #1A1A1A (text-on-light); light-first."
    - "Typography locked, three families/three roles (C21): Fraunces (display), Inter (text), JetBrains Mono (code); scale per the tokens artifact (artifact://design-system/eden-tokens-v0, materialized at documents/design-system/tokens.json). Component/behavior layer remains OPEN (OD-1)."
    - "Density as the default: the engineer's views (PER-0002) carry information at high density; the founder's views (PER-0001) lift the non-technical signal out of that density without forking the tool."
    - "Diagrams are a primary type, not decoration: the architecture diagram is a working surface that doubles as a live production view (C10)."
---

## Intent

Eden should feel like Ableton (C11): deep, dense, and professional — a mega-tool (C11) whose depth
justifies its learning curve. The thesis is that there is a *way to do things* here, and that the way is worth
learning; the product does not apologize for its depth by hiding it behind a thin "simple mode."
Instead it makes the depth navigable. A user is not expected to discover the tool on their own — it
is learnable via an in-app tutorial and guided onboarding (C11, REQ-0015) — but once learned, the
density is the point: more of the system is visible and operable in one place than a shallower tool
could ever offer.

The intent ties directly to charter 00 §1: Eden is the discipline layer packaged as a product, with
a low-code/no-code interface over a full-code output. The design's job is to make that discipline —
documents, gates, evidence, observability — feel like a precise working instrument rather than a
compliance burden. The emotional target for the founder is *trust without operating*; for the
engineer it is *control with leverage*. Both are served by the same dense surface, viewed at
different altitudes.

Documents and diagrams are first-class surfaces, not exports. A user reads, navigates, and
downloads project documents in a clear, organized presentation (C10, REQ-0007), and the same
architecture diagram that expresses a system's design renders its live production telemetry
(C10, REQ-0014). The design must treat "read the spec" and "watch production" as two views of one
artifact, never two separate screens.

## Audience and tone

The design speaks to two charter personas at once, at different altitudes of the same surface.

- **The product founder (PER-0001)** needs the non-technical views: the maturity ladder, the
  observability dashboard (deploys, health, infra spend, token spend), the gate queue, and the
  document reading surface. The tone for them is calm and confident — the release-engineering
  burden is invisible, and the views state what is happening (deployed, healthy, gated) without
  demanding they understand the machinery (C9, C11).
- **The picky platform engineer (PER-0002)** needs density: drift detail across connector families,
  enforced-vs-advisory guarantee badges, the full release machinery, and the connect/conformance
  surfaces. The tone for them is precise and honest — nothing is rounded off, and when a guarantee
  is off the surface says so permanently and plainly (C8, C18).

The shared voice is that of a serious instrument: plain, exact microcopy; no marketing tone inside
the app; depth presented as capability, not clutter. The tutorial layer carries the warmth — it
teaches the way to do things — so the working surfaces can stay dense and quiet.

## Constraints

- **Platform:** A desktop shell (Tauri) is encouraged for full-screen use of a deep tool, and the
  web client must be at functional parity with it (C11, REQ-0016). The desktop shell wraps the same
  Svelte bundle as the web client (charter 00 §5, ADR-0006); the design must not fork the
  experience between the two.
- **Stack:** Built on Svelte 5 with the **photosphere** design system as the reference
  implementation (ADR-0004 Svelte re-platform; ADR-0005 photosphere re-founded on Svelte as the
  same standalone asset). The design language must be expressible through photosphere's F6 contract
  (DTCG ThemeDoc + component manifest + usage rules, doc 05 F6) so it composes with user-supplied
  design systems on the same contract (REQ-0017).
- **Documents and diagrams are first-class surfaces:** the design must make document reading,
  navigation, and download (C10, REQ-0007) and diagram rendering (C10, REQ-0014) primary, supported
  views — and the *same* diagram must serve both system design and live production observation, not
  two hand-built artifacts (C10).
- **Density with two altitudes:** the same surface must serve the founder's non-technical altitude
  and the engineer's dense altitude without forking into two products; the learning curve is
  acceptable and is carried by the in-app tutorial (C11, REQ-0015).
- **🔶 Visual language is deliberately OPEN, pending photosphere's re-founding (OD-1).** Palette, type scale, and
  surface treatment are not committed in v1; this brief fixes the *experience* (Ableton-thesis
  density, dual-altitude audience, first-class documents and diagrams) and leaves the *look* to that
  research. `data.design_system_reference` now points at the v0 tokens artifact (intake C21); photosphere absorbs it as its seed theme when re-founded (OD-1). Earlier draft note, superseded in place while in
  flight (OD-1: the Svelte behavior layer for photosphere is an open ruling); the F6 artifact this
  brief will inform does not yet exist, so no `informs` edge is asserted (doc 11 §2, §4).
