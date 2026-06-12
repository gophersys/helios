---
meta:
  id: design-brief
  type: design-brief
  schema_version: 1.0.0
  project: linkbox
  status: approved
  version: 1
  created: 2026-06-12
  updated: 2026-06-12
  authors:
    - run: run-intake-0a91
    - human: mateo
  links:
    realizes: []
    supersedes: null
    informs:
      - artifact://design-system/linkbox/theme
  source:
    - run: run-intake-0a91
      span: "messages 38-52"
data:
  design_system_reference: artifact://design-system/linkbox/theme
  token_hints:
    - "Primary palette leans cool and high-contrast: ink-on-paper neutrals with a single saturated accent for the save action."
    - hint: "Type scale favors reading: a comfortable body size, generous line height, and a monospace face only for URLs."
    - "Spacing is roomy — the library is a calm list, not a dense dashboard."
---

## Intent

Linkbox should feel like a clean desk, not a filing cabinet. The moment of saving a link
should feel instant and almost weightless — one field, one accent button, done. The library
should feel calm and scannable, so a returning user's eye lands on what they came for without
effort. The emotional target is relief: the anxiety of "where did I save that" simply goes away.

## Audience and tone

The design speaks to two personas from the charter. The Solo collector (PER-0001) wants speed
and quiet; the interface should never get in the way of dropping a URL and moving on. The
Curator (PER-0002) wants their shared collections to look considered and trustworthy, since
they hand the link to others. The voice is plain, confident, and unfussy — minimal chrome,
no marketing tone inside the app, microcopy that states what happened ("Saved") rather than
celebrating it.

## Constraints

- Accessibility: meet WCAG 2.1 AA — contrast ratios on all text and the save button, full
  keyboard operation of save and tag, visible focus states.
- Platform: responsive web only in v1 (charter non-goal); usable from 360px phone width up to
  desktop, with the save field reachable without scrolling on a fresh page.
- Performance: the save interaction must feel instant — optimistic UI on save, first
  contentful paint of the library under one second on a warm cache.
- Brand: a single accent color reserved exclusively for the primary save action; nothing else
  competes for it.
