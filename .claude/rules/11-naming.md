# Rule — Naming (HNS-1)

> Neutral principle (10 §9 layer A). Enforced mechanically by `golangci-lint` (forbidigo,
> for banned tokens) and `hnslint` (structural module/package/directory naming).
>
> `hnslint` is the public repository `gophersys/hnslint`. The base image
> `ghcr.io/gophersys/base` installs it, pinned by `ARG HNSLINT_VERSION` in
> `.devcontainer/base/Dockerfile`, so every gate that runs in the container has it. To change
> the check, cut a release in `gophersys/hnslint` and raise the pin. Do not build it from a
> working tree: a binary in `GOPATH/bin` takes precedence on `PATH` and hides the pinned one.

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
the slug rule, because they are type names, not pattern names. The ban targets
pattern/module/package naming, not a language's own idiomatic type vocabulary.

### The two spine types are pinned: `Config` and `Deps`

The constructor spine (10 §9) is `New(configuration, dependencies)`. Its two parameter
**types** ARE named `Config` and `Deps`. This is **required**, not merely permitted:
`Configuration` and `Dependencies` are rejected as full-spelled spine outliers, and
`hnslint` fails a library that declares them.

The rule follows the practice. Across the **16 libraries** in this repository — every directory
under `go/` except `go/_ctl`, the shared gate library the other 16 source, which is not itself
a library under gate:

| declaration | count | libraries |
|---|---|---|
| `type Config struct` | 26 | 14 |
| `type Deps struct` | 22 | the same 14 |
| `type Configuration struct` | 0 | — |
| `type Dependencies struct` | 0 | — |

**16, not 17.** `ls -d go/*/` returns 17 because `_ctl` is one of them, and 17 is separately the
verb-conservation PROJECT count — which does include `templates/go/http-gateway`. A template is
an application skeleton, not a library at `go/<slug>`, so the two sets differ and neither number
substitutes for the other. The rows above are measured over the 16.

There is no counter-example to weigh against, so the shorter form is not a concession to
brevity — it is the only form this codebase has ever used, and pinning it deletes a
per-library judgement call.

**The slug ban is untouched.** A *package* or *directory* named `config`/`deps` is still
forbidden, and the required slug forms in the table above (`configuration`, `dependencies`)
still stand. Only these two exported **type** names are pinned. A field, a variable, a
parameter and a package keep the fully-spelled word: `configuration.Region`, not
`config.Region`.

## Why

The naming standard is what lets one canonical slug resolve, unchanged, across Go, Rust,
TypeScript, and the protocol layer. The `cfgtest` break — guidance present, teeth absent —
is the canonical proof that a banned token must be rejected the instant it is written.
