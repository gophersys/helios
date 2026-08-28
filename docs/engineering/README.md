# Engineering

The repository has one workflow boundary:

```text
host:      devcontainer cloud
container: nx <verb> <project> [-c <configuration>]
```

Nx owns project discovery, dependencies, caching, affected analysis, and
parallelism. Project targets may call small scripts or compiled tools, but those
implementations are not separate user interfaces.

Add structure only when real code requires it. A new application, library, tool,
or deployment unit begins as an Nx project with explicit inputs, outputs,
dependencies, and the smallest useful targets.

## Harnesses

Shared agent behavior lives in `.agents/skills`. Codex reads it directly; the
Claude and OMP discovery trees contain generated routing adapters. Use
`nx run harnesses:sync` to regenerate them and `nx check harnesses` to reject
drift.

## Secrets

`EDEN_SECRETS_SERVER` overrides the checked-in server in `secrets/config.json`.
The default provider is the Bitwarden-compatible Vaultwarden service. Use
`nx run secrets:configure`, `nx check secrets`, and `nx run secrets:status`.
Credentials and `BW_SESSION` never belong in the repository.

For an interactive development shell, authenticate once with `bw login`, then
unlock only the shell that needs secrets:

```bash
export BW_SESSION="$(bw unlock --raw)"
```

Vaultwarden implements the Bitwarden Password Manager protocol, not Bitwarden
Secrets Manager. Do not use `bws` machine accounts unless the selected provider
actually exposes the Secrets Manager API.

## Upstream contracts

- [Nx project configuration](https://nx.dev/docs/reference/project-configuration)
- [Nx synchronization](https://nx.dev/docs/concepts/sync-generators)
- [Codex repository instructions](https://developers.openai.com/codex/guides/agents-md)
- [Codex skills](https://developers.openai.com/codex/skills)
- [Claude Code memory](https://code.claude.com/docs/en/memory)
- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [OMP project skill discovery](https://github.com/can1357/oh-my-pi/blob/main/packages/coding-agent/examples/sdk/04-skills.ts)
- [Bitwarden self-hosted CLI configuration](https://bitwarden.com/help/cli/#config)
