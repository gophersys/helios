---
meta:
  id: product-charter
  type: product-charter
  schema_version: 1.0.0
  project: linkbox
  status: approved
  version: 2
  created: 2026-06-12
  updated: 2026-06-12
  authors:
    - run: run-intake-0a91
    - human: mateo
  links:
    realizes: []
    supersedes: null
    informs: []
  source:
    - run: run-intake-0a91
      span: "messages 4-37"
data:
  personas:
    - id: PER-0001
      name: Solo collector
      description: |
        Someone who reads widely and saves links all day — articles, repos, docs — across
        a browser, a phone, and a chat app. They want one trusted place to drop a URL and
        find it again later by tag, without grooming folders.
    - id: PER-0002
      name: Curator
      description: |
        A power user who assembles themed reading lists and shares them with a team or an
        audience. They care about a clean public view and a stable share link they can hand
        out without exposing their whole library.
---

## Vision

Saving a link should take one second and finding it should take none. Linkbox is the
single inbox for everything worth coming back to: drop a URL, give it a tag or two, and
trust that it is searchable and shareable forever. When it works, people stop emailing
themselves links and stop losing them in twenty open tabs.

## Problem

Capable people lose the links they care about. Browser bookmarks rot into deep folders no
one revisits; "save for later" services bury the link behind a feed; chat apps swallow URLs
in scrollback. The collector ends up with the same article saved in four places and findable
in none. Curators have it worse: there is no clean way to gather a themed set and share just
that set without exposing an entire account. The cost is quiet but constant — re-finding,
re-searching, re-sending links that were already saved once.

## Success criteria

- A logged-in user can save a link and have it appear in their library in under one second.
- A user can find any saved link by one of its tags with no folder navigation.
- A curator can publish a collection as a read-only share link and revoke it at any time.
- Eight of ten pilot users report they stopped using browser bookmarks within two weeks.

## Non-goals

- Not a read-it-later reader: Linkbox stores and organizes links, it does not reformat or
  archive page content for offline reading.
- Not a social network: no following, feeds, likes, or comments in v1.
- Not a team workspace with roles and permissions beyond a single share-link per collection.
- No browser-extension or native mobile app in v1; the web app and a save endpoint suffice.
