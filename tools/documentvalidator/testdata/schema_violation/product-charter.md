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
      description: A persona for the schema-violation fixture.
---

## Vision

A minimal charter for the schema-violation fixture.

## Problem

A requirement carries an out-of-enum priority value.

## Success criteria

- The validator reports a JSON Schema shape violation on the priority field.

## Non-goals

- Nothing beyond exercising shape validation.
