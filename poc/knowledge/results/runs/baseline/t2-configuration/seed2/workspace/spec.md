# Task: application configuration loader

Implement package `configuration` (in this module, package files at the
module root), plus a small CLI.

## Contract (exported API — must exist with exactly these signatures)

```go
package configuration

// Source resolves a configuration key to a raw value.
type Source func(key string) (value string, found bool)

type Config struct {
    Port  int
    Name  string
    Debug bool
}

func Load(source Source) (Config, error)
```

## Semantics

`Load` reads these keys through `source`:

| Key | Field | Parse | Default when not found |
|---|---|---|---|
| `HELIOS_PORT` | `Port` | integer, must be 1–65535 | `8080` |
| `HELIOS_NAME` | `Name` | non-empty string | `"helios"` |
| `HELIOS_DEBUG` | `Debug` | `strconv.ParseBool` syntax | `false` |

- A key that is present but fails to parse is an error. The returned error
  must preserve the underlying parse error so that callers can still reach
  it through the `errors` package (e.g. a `*strconv.NumError` for a bad
  port).
- A present-but-empty `HELIOS_NAME` is an error.

## CLI

Also provide `cmd/configprint/main.go`: a `main` package that loads the
configuration from the real process environment and prints it as
`port=<port> name=<name> debug=<debug>` followed by a newline.

## Deliverables

- The implementation and the CLI.
- Your own tests for the behavior you consider important.
- No third-party dependencies.
