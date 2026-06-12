---
meta:
  id: product-charter
  type: product-charter
  schema_version: 1.0.0
  project: fixture
  status: draft
  version: 1
  created: 2026-06-12
  updated: 2026-06-12
  authors:
    - human: fixture
  links:
    realizes: []
    supersedes: null
    informs: []
  source:
    - run: run-fixture
      span: "messages 1-2"
data:
  personas:
    - id: PER-0001
      name: Fixture persona
      description: A persona for the wrong-direction fixture.
---

## Vision

A minimal charter for the wrong-direction fixture.

## Problem

A product-tier requirement links downstream to an architecture component.

## Success criteria

- The validator reports a T2 wrong-direction violation.

## Non-goals

- Nothing beyond exercising T2.
