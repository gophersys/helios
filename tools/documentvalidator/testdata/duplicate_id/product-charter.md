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
      description: A persona for the duplicate-id fixture.
---

## Vision

A minimal charter for the duplicate-id fixture.

## Problem

Two requirement items share the same id.

## Success criteria

- The validator reports a T5 duplicate-id violation.

## Non-goals

- Nothing beyond exercising T5.
