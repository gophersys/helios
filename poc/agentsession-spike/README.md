# agentsession-spike — headless Claude Code in a container

> Status: Spike (donor material) · 2026-06-12 · De-risks **REQ-0021**: can a normal
> Claude **membership** user (like Mateo) drive a headless Claude Code session inside an
> isolated, non-root container, authenticated by a long-lived `setup-token`, with **no
> credential ever entering an image layer, a transcript, or agent context**? This is the
> plumbing under the F4 agent connector (05 §2, ADR-0008) and the C22 directive: "wrap
> Claude via `setup-token` so a normal membership user works from the start."
>
> Not a library; not on the `main` path (poc rules, ADR-0009 D). Mines prior art:
> `poc/codingharness` (the headless-flag set) and `poc/agents/deploy` (the container
> shape — inverted here to dial-out-only, non-root, no ports).

---

## 1. The token flow (exact commands + env vars, cited)

The mechanics below are verified against the official authentication docs
([code.claude.com/docs/en/authentication](https://code.claude.com/docs/en/authentication))
and the local CLI's own `--help` (`claude` v2.1.176).

### Step 1 — mint the token ONCE, interactively, on a workstation

```bash
claude setup-token
```

- Requires a **Claude subscription** — Pro, Max, Team, or Enterprise. (`claude
  setup-token --help`: "Set up a long-lived authentication token (requires Claude
  subscription)".)
- Walks you through **OAuth authorization in a browser** and **prints the token to the
  terminal**. It **does not save the token anywhere** — you must copy it yourself.
- The token is **valid for one year**, **scoped to inference only**, and **cannot
  establish Remote Control sessions**.
- This is the only interactive step, and it happens **outside** the container. The spike
  never launches an OAuth flow itself.

> Billing note (docs, dated): **starting 2026-06-15**, Agent SDK and `claude -p` usage on
> subscription plans draws from a **separate monthly Agent SDK credit**, distinct from
> interactive limits. Relevant to the F4 usage meter / `TokenBudget` (02 §2) — headless
> runs may meter against a different bucket than a human's interactive use.

### Step 2 — hand the token to the headless harness via env var

The headless harness (here: the container) consumes the token from one environment
variable:

```bash
export CLAUDE_CODE_OAUTH_TOKEN=<the-token-from-step-1>
```

`CLAUDE_CODE_OAUTH_TOKEN` is the **correct** variable for the subscription-token flow —
**not** `ANTHROPIC_API_KEY` (that is a Console API key, a different billing path) and not
`ANTHROPIC_AUTH_TOKEN` (a bearer token for an LLM gateway/proxy). All three are real and
distinct; this spike uses `CLAUDE_CODE_OAUTH_TOKEN` exclusively.

In this spike the variable lives in a **gitignored `.env`** that compose injects at
`docker run` time (`env_file:` in `compose.yaml`). It is **never** an `ARG`/`ENV` in the
Dockerfile, so it is absent from every image layer and from `docker history`.

### Authentication precedence (the load-bearing gotcha)

When several credentials are present, the CLI picks one in this order (docs §"Authentication
precedence"):

| Rank | Source |
|---|---|
| 1 | Cloud provider (`CLAUDE_CODE_USE_BEDROCK` / `_VERTEX` / `_FOUNDRY`) |
| 2 | `ANTHROPIC_AUTH_TOKEN` (Bearer; gateway/proxy) |
| 3 | `ANTHROPIC_API_KEY` (X-Api-Key; Console key) — **in `-p` mode, always used when present** |
| 4 | `apiKeyHelper` script output |
| **5** | **`CLAUDE_CODE_OAUTH_TOKEN`** ← the subscription `setup-token` value |
| 6 | `/login` subscription OAuth credentials in `~/.claude` |

Two consequences this spike acts on:

1. **A stray `ANTHROPIC_API_KEY` in the environment silently wins** over our OAuth token
   (rank 3 > 5), and in `-p` mode it is used without a prompt. So `entrypoint.sh`
   **`unset`s `ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN`** before invoking `claude` —
   the run is provably exercising the subscription-token path.
2. **`--bare` mode does NOT read `CLAUDE_CODE_OAUTH_TOKEN`** (it accepts only
   `ANTHROPIC_API_KEY` / `apiKeyHelper`; OAuth and keychain are never read). The
   codingharness "clean-room context" open question floated `--bare`/`--safe-mode`; that
   path is **incompatible** with the subscription-token flow. This spike does **not** pass
   `--bare`. (`--safe-mode` is fine — it disables customizations but "Auth … work[s]
   normally".) The hermetic-context goal must be met another way (explicit
   `--system-prompt`, `CLAUDE_CONFIG_DIR`, pinned `--model`) — see open risks.

### Step 3 — the session invocation (mirrors `poc/codingharness`)

`entrypoint.sh` runs exactly one session with the codingharness flag set:

```bash
claude -p "<task>" \
  --output-format stream-json \
  --verbose \
  --allowedTools Write Read "Bash(ls *)" "Bash(cat *)" \
  --permission-mode acceptEdits
```

Rationale per flag is in `poc/codingharness/README.md` §"Flags used to drive Claude
Code". Differences from codingharness: the `Bash(...)` allowlist is `ls`/`cat` (this
task only needs to verify a file), not `go *`. `acceptEdits` + a tight `--allowedTools`
gives unattended execution **without** `--dangerously-skip-permissions`.

---

## 2. Container recipe (the four files)

| File | Role |
|---|---|
| `Dockerfile` | `node:22-slim` + pinned `@anthropic-ai/claude-code`; non-root `node` user; `/workspace` the only writable dir; **no `EXPOSE`**. |
| `entrypoint.sh` | Requires `CLAUDE_CODE_OAUTH_TOKEN`; scrubs higher-precedence creds; runs `claude -p` with stream-json + narrow `--allowedTools`; never prints the token. |
| `compose.yaml` | Workspace bind mount + `env_file: .env`; no ports; `read_only` rootfs, `cap_drop: ALL`, `no-new-privileges`. |
| `README.md` | This runbook. |

### Security notes (why it is shaped this way)

- **Token never in image layers.** It is neither `ARG` nor `ENV`; it arrives only at
  runtime via `env_file`. `docker history` shows no credential. (07 §2: credentials never
  serialized into agent workspaces or configuration baked alongside the agent.)
- **Token never in transcripts.** `entrypoint.sh` redacts it from its own banner ("value
  redacted") and the CLI does not echo the token into the stream-json output. (07 §2:
  transcripts redact by construction; the real adapter still owes redaction-on-capture for
  tool results.)
- **Non-root, minimal blast radius.** Runs as uid 1000 (`node`); root fs is read-only; all
  Linux capabilities dropped; `no-new-privileges`. The agent can write only to the mounted
  `/workspace`. (07 §3: one sandbox per execution, workspace mounted, nothing else.)
- **Dial-out only.** No `EXPOSE`, no `ports:`. The container opens no listening sockets; it
  connects OUT to the model provider. (07 §3 "dial-out only".) **Caveat:** compose does not
  implement L3 **egress filtering** (default-deny + model-endpoint allowlist) — that is an
  F1 network-policy obligation at the pod/cluster layer, noted in open risks.

---

## 3. How to run

### Real run (requires a real token — done by Mateo, not by automation)

```bash
# once, on a workstation:
claude setup-token                 # prints a token; copy it

# in this directory:
echo "CLAUDE_CODE_OAUTH_TOKEN=<paste-token>" > .env   # .env is gitignored
mkdir -p workspace
docker compose run --rm agentsession                  # one-shot; --rm cleans up
```

The stream-json transcript prints to stdout (one JSON object per line); the agent's
file write lands in `./workspace`.

### Plumbing test (no real token; proves the failure mode is clean)

```bash
echo "CLAUDE_CODE_OAUTH_TOKEN=dummy-not-a-real-token" > .env
mkdir -p workspace
docker compose run --rm agentsession
# expect: a clean authentication error and a non-zero exit — NOT a crash, NOT a hang,
# NOT an interactive prompt. This proves the plumbing (env -> CLI -> auth attempt) works.
```

---

## 4. What was tested (build/run results)

Tested on Docker 29.4.0 (daemon up), macOS. **No real authenticated run was attempted**
(hard rule). Host CLI `2.1.176`; image CLI pinned `2.1.153`.

| Check | Result |
|---|---|
| `docker build` | **PASS.** Image `eden/agentsession-spike:pinned`, 803 MB. CLI inside reports `2.1.153 (Claude Code)`. |
| Non-root | **PASS.** `id` inside → `uid=1000(node) gid=1000(node)`. |
| No credential in layers | **PASS.** `docker history --no-trunc` has no `OAUTH`/`TOKEN`/`SECRET`/`ANTHROPIC_API`/credential string. |
| **Missing token** | **PASS / clean.** Entrypoint catches it, prints guidance, exits **78** (`EX_CONFIG`) before any `claude` invocation or network call. |
| **Dummy token** | **Plumbing PASS, with a sharp caveat (below).** Entrypoint runs, `unset`s stray creds, invokes `claude -p`. |

### ⚠️ Finding: a bad OAuth token fails *silently* (exit 0, no output)

With `CLAUDE_CODE_OAUTH_TOKEN=<garbage>`, `claude -p "…"` produces **zero stdout, zero
stderr, and exits 0** — no error, no `init` event, no `result` event, no transcript.
Reproduced across **every** variation tried on CLI `2.1.153`:

- `--output-format stream-json` (our flag set) → exit 0, empty
- `--output-format json` and plain text → exit 0, empty
- `--debug` → exit 0, empty (no auth diagnostic surfaced)
- `--network none` → exit 0, empty (so the CLI **rejects the malformed token locally**,
  before dialing out — the failure isn't even an HTTP 401 we could see)

So the dummy-token test **does** prove the env→CLI plumbing (the token reaches the CLI and
changes its behavior vs. the missing-token branch), but it also surfaces a **silent-failure
trap**: an orchestrator that branches on `claude`'s **exit code alone would treat a bad
token as success.**

**Mitigation (already the right design):** `poc/codingharness` does **not** trust the exit
code — it exits non-zero unless it sees a `result` event with `subtype: success`. That
defense is **load-bearing for auth too**, not just task failure. The F4 adapter MUST treat
"no `init`/`result` event on stdout" as a hard failure regardless of exit code, and SHOULD
validate the token shape (or do a cheap warm-up call whose `init` event it requires) before
committing a Run to a possibly-unauthenticated session. Filed in open risks.

> Caveat on scope: this is the **invalid-token** failure mode. An **expired** (formerly
> valid) token, or a structurally-valid token rejected server-side, may surface differently
> (an HTTP 401 in the stream) — untested here because it needs a real-then-revoked token.
> The adapter's conformance suite should cover both.

---

## 5. Open risks / handoffs to the real F4 adapter

- **Bad-token = silent success (exit 0, no output).** Measured on CLI `2.1.153` (§4). The
  F4 adapter cannot trust `claude -p`'s exit code for auth; it must require an `init`/`result`
  event on stdout and/or a token-shape check or warm-up call before committing a Run.
- **Egress is not yet filtered.** Dial-out-only is structural (no listeners), but
  default-deny egress with a model-endpoint + granted-tool allowlist (07 §3) is **not**
  enforced by compose. The real pod needs a `NetworkPolicy` (or equivalent). Until then a
  compromised agent could reach arbitrary hosts.
- **Token is long-lived, not short-lived.** 07 §2 wants **short-lived, scoped tokens minted
  per use** via the `secrets` port. `setup-token` yields a **one-year** token — acceptable
  for a spike and for Mateo's own membership use, but the production F4 adapter should front
  it with `apiKeyHelper` (precedence rank 4, called on 401 / every `CLAUDE_CODE_API_KEY_
  HELPER_TTL_MS`) pulling a short-lived token from the vault, rather than a year-long static
  secret in an env file.
- **Hermetic context vs. `--bare` conflict.** Clean-room runs (codingharness open question)
  want minimal ambient context, but `--bare` cannot read the OAuth token. Resolve via
  `--safe-mode` and/or explicit `--system-prompt` + a scoped `CLAUDE_CONFIG_DIR`, not
  `--bare`.
- **Version pinning + schema drift.** Image pins CLI `2.1.153` (`stable` dist-tag); host
  used `2.1.176` (`latest`). The adapter needs a pinned-and-tested version and a
  conformance suite over the stream-json event schema (the `rate_limit_event` surprise in
  codingharness is the warning).
- **Billing bucket change (2026-06-15).** Headless `claude -p` on subscription moves to a
  separate Agent SDK credit. The F4 usage meter must account for this so FinOps (S9) is
  correct for headless runs.
- **Transcript redaction on capture.** The CLI does not echo the token, but tool *results*
  can carry secrets; persisting the stream (02 §1 first-class transcripts) still owes
  redaction-on-capture before storage (07 §2).
