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
      description: A persona that exists so a dangling reference is detectable.
---

## Vision

A minimal charter for the dangling-link fixture.

## Problem

The requirement links to a persona id that is not defined anywhere.

## Success criteria

- The validator reports a T1 dangling-reference violation.

## Non-goals

- Nothing beyond exercising T1.
