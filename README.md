# hnslint

The structural linter for **HNS-1**, the naming and structure standard of the
gophersys Go code. It reads a directory tree and it fails when the structure
disagrees with the standard.

It checks what a compiler cannot: that a name says what a thing is, and that one
concept has one home.

## Install

```sh
go install github.com/gophersys/hnslint/cmd/hnslint@v0.1.0
```

## Use

```sh
hnslint <directory>
```

Exit 0 means the tree agrees with HNS-1. Exit 1 means it does not, and each line
names the file and the rule.

```
$ hnslint ./go/util
./go/util: directory name "util" is a banned HNS-1 token; use (name the actual pattern)
./go/util: package name "util" is a banned HNS-1 token; use (name the actual pattern)
```

## The rules

- **A banned token is a refusal to name the thing.** `util`, `common`, `core`,
  `helper`, `misc` and their relatives say only that the author did not decide
  what the package is. Name the pattern instead.
- **Use the full word.** `configuration`, not `config`. `kubernetes`, not `k8s`.
  `dependencies`, not `deps`. An abbreviation saves the writer 6 characters and
  costs every later reader a guess.
- **One concept, one home.** An exported type or port that is defined in more
  than 1 package has no home, and the 2 copies drift.
- **An entry point is where the reader looks for it**, and the package layout
  matches the shape the standard describes.

## Why this repository stands alone

It was extracted from `gophersys/eden`, where it was `tools/hnslint`. It moved
because the container images that run the gates cannot authenticate to a private
repository, so a private linter could never be installed into them. Every
consumer had to build it from a bind mount, and CI, which has no bind mount,
silently had no linter at all.

`gophersys/cictl` is public for the same reason.

## Development

```sh
go build ./...
go test ./...
```

The tool has 1 dependency, `golang.org/x/mod`, and it needs no network.
