# apps/music — TRANSITIONAL

The `music` project's app manifests (qBittorrent+VPN today; *arr + Jellyfin
later), kept in the infra monorepo **only for the zero-downtime migration**.

> These are NOT the IDP end-state. Per the IDP, apps live in their own repo and
> consume `charts/*` archetypes. In migration Phase 5 these graduate to a
> dedicated `music` repo as a `stateful-app`/`ingress-app` archetype (a windowed,
> non-byte-identical change). Until then they live here byte-identical so Argo can
> repoint to `main` as a no-op. See `docs/migration-homelab-to-idp.md`.
