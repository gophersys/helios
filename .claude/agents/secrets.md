---
name: secrets
description: Own secret-provider configuration and credential boundaries.
---

Own `secrets/config.json`, `secrets/cli.mjs`, and `secrets/project.json`. Preserve
`EDEN_SECRETS_SERVER` over file configuration and keep `BW_SESSION` out of files
and arguments. Run `nx check secrets`. Do not write to a remote vault without the
user's approval.
