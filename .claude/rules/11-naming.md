# Rule — Naming (HNS-1)

> Neutral principle (10 §9 layer A). Enforced mechanically by `golangci-lint` (forbidigo,
> for banned tokens) and `hnslint` (structural module/package/directory naming).

Names are the cross-language join key. They are **fully spelled out, lowercase, and
hyphen-separated** at the slug level, and render to each ecosystem by a pure function — no
judgement at render time. Abbreviation is forbidden because an abbreviation is a private
dialect that the next reader, and every other ecosystem, has to decode.

## The slug

```
slug := word ("-" word)*
word := [a-z][a-z0-9]*
```

Given `slug` + ecosystem, the package/module/directory name is mechanical. For the Go
ecosystem: module path `github.com/gophersys/libs/go/<slug>`, package name = the
**separator-free lowercase** rendering of the slug, directory = the slug.

## Banned tokens → required form

These abbreviations are rejected as identifiers, package names, and directory names:

| Banned | Required |
|---|---|
| `cfg`, `config` | `configuration` |
| `deps` | `dependencies` |
| `obsv`, `o11y` | `observability` |
| `mgmt` | `management` |
| `auth` | `identity` |
| `db`, `repo`, `store` | `persistence` |
| `k8s` | `kubernetes` |
| `ts` | `typescript` |
| `golang` | `go` |
| `util`, `utils`, `common`, `core`, `misc` | **banned outright** — name the actual concept |

`util`/`common`/`core`/`misc` have no required form: a package named for a non-concept is
a junk drawer. Find the real concept it holds and name that.

## The narrow exemption

Idiomatic *exported type names* that the host language convention demands are exempt from
the slug rule, because they are type names, not pattern names — e.g. a Go type named
`Config` or `Deps` is fine; a *package* or *directory* named `config`/`deps` is not. The
ban targets pattern/module/package naming, not a language's own idiomatic type vocabulary.

## Why

The naming standard is what lets one canonical slug resolve, unchanged, across Go, Rust,
TypeScript, and the protocol layer. The `cfgtest` break — guidance present, teeth absent —
is the canonical proof that a banned token must be rejected the instant it is written.
