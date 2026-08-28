# Eden

Eden is an intentionally minimal Nx monorepo. It begins with infrastructure for
adding projects, not preselected application frameworks or languages.

```bash
cd ~/code/eden
devcontainer cloud
nx check workspace
nx check harnesses
nx check secrets
```

Inside the container, Nx is the public interface for development and automation.
Projects may use any language or toolchain, but every supported action is exposed
as an Nx target with a short shared verb.

```text
.agents/        canonical agent workflows
.claude/        Claude harness adapters
.devcontainer/  reproducible development entrypoint
docs/           small engineering map
harnesses/      pinned agent CLI versions
secrets/        provider-neutral server selection and Vaultwarden adapter
scripts/        private implementations behind Nx
```

`secrets/config.json` selects the default Vaultwarden server. Set
`EDEN_SECRETS_SERVER` before `devcontainer cloud` to override it. Login state is
encrypted by `bw` in a persistent Docker volume; unlock tokens remain ephemeral.
