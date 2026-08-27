# RUNBOOK — reproduce the mini's buildkitd from scratch

This procedure rebuilds the native arm64 build node on the Mac mini. The node is
a standalone `buildkitd` container. It exposes the BUILD API only, over mutual
TLS. It does not expose the Docker Engine API.

Use this runbook when you set up a new mini, rotate the certificates, or recover
the node after a wipe. The design and the workflow step are in
`docs/ci-substrate.md`. The machine facts are in `README.md`.

## The security model — one line

The client certificate can submit a sandboxed build and nothing else. Proven on
the mini on 2026-08-14: no Engine API on the port, `--privileged --pid=host` does
NOT give root, and `--allow security.insecure` is refused. See
`docs/ci-substrate.md` for the full table.

## Two things that will trip you up

1. **The server certificate MUST carry the mini's IP in its SAN.** buildx checks
   the certificate against `tcp://10.168.0.92`, so the SAN needs
   `IP:10.168.0.92`. A certificate with a CN only is refused.
2. **Docker Desktop rejects a bind mount of a home path.** Its file-sharing
   layer does not share an arbitrary home directory, so a `-v $HOME/certs:/certs`
   bind mount fails. Seed named volumes with `docker cp` instead.
3. **Do not inherit DNS from the current house.** The checked-in
   `buildkitd.toml` uses Cloudflare and Google public anycast resolvers. Neither
   address belongs to the router or ISP, so moving the mini does not change the
   daemon's resolver contract. This still requires internet access that permits
   public DNS on port 53. Captive, filtered, and split-DNS networks may block
   these resolvers or require internal names; on such a network, update this
   explicit config deliberately rather than silently inheriting DHCP DNS.

## Step 1 — the certificates (on any machine with openssl)

```sh
openssl genrsa -out ca-key.pem 4096
openssl req -new -x509 -days 3650 -key ca-key.pem -sha256 -out ca.pem -subj "/CN=eden-buildkit-ca"

openssl genrsa -out daemon-key.pem 4096
openssl req -new -key daemon-key.pem -out daemon.csr -subj "/CN=macos-ci-runner"
# server SAN MUST carry the mini's IP — buildx verifies the cert against tcp://10.168.0.92
printf 'subjectAltName=IP:10.168.0.92,IP:127.0.0.1,DNS:macos-ci-runner\nextendedKeyUsage=serverAuth\n' > d.cnf
openssl x509 -req -days 3650 -in daemon.csr -CA ca.pem -CAkey ca-key.pem -CAcreateserial -out daemon.pem -sha256 -extfile d.cnf

openssl genrsa -out client-key.pem 4096
openssl req -new -key client-key.pem -out client.csr -subj "/CN=eden-ci-buildx-client"
printf 'extendedKeyUsage=clientAuth\n' > c.cnf
openssl x509 -req -days 3650 -in client.csr -CA ca.pem -CAkey ca-key.pem -CAcreateserial -out client.pem -sha256 -extfile c.cnf
```

The daemon keeps `ca.pem`, `daemon.pem` and `daemon-key.pem`. The client keeps
`ca.pem`, `client.pem` and `client-key.pem`.

## Step 2 — the daemon (on the mini)

The credential helper must be on `PATH`. From this directory, seed the
certificates and the checked-in daemon configuration into separate named
volumes, because a home-path bind mount fails.

For an existing daemon, capture its state volume before replacing it. Stop if
the printed destination or volume name is not the expected BuildKit state; do
not turn the removal into a broad volume prune.

```sh
docker inspect eden-buildkitd --format \
  '{{range .Mounts}}{{if eq .Destination "/var/lib/buildkit"}}{{.Name}}{{end}}{{end}}'
docker rm -f eden-buildkitd
```

On the 2026-08-27 repair this printed the anonymous volume
`a4e519f717ba7d186a399f02c0de3b3b5d9b49c0e1252310036e64c042286da7`.
Five older seed/daemon recreations had left these verified dangling BuildKit
volumes: `9e324d96ac6d341ed14c2cd0a148d16d39f2e8a7e41aac4e6e1ed7456b29b002`,
`45d5e4cda4d3f0be8f6557f11c18519c4ce9896262d27c7af79ca31842657a69`,
`976c764a89d59eaf751ec9b0643541498d8464a198028785d0d439e4b28a55b4`,
`aed53eb028775e8cc6355fff4fd83765a1ecee3ea2096186d516044034178553`, and
`c28b386937613d5d1550d1e66975733bc502de3d08b0590100cd66e67b956cff`.
Those six exact volumes were removed after the new daemon was running. They are
incident evidence, not a command to reuse on another machine.

```sh
export PATH="/Applications/Docker.app/Contents/Resources/bin:$HOME/bin:$PATH"
BUILDKIT_IMAGE="moby/buildkit@sha256:28a898719c18a33f4e8000685287fa36fd0dd9560c6440227d3a732d79bb41d8"
docker volume create eden-bk-certs
docker create --name bkseed --entrypoint /bin/sh -v eden-bk-certs:/certs "$BUILDKIT_IMAGE"
docker cp ca.pem bkseed:/certs/
docker cp daemon.pem bkseed:/certs/
docker cp daemon-key.pem bkseed:/certs/
docker rm -v bkseed
docker volume create eden-bk-config
docker create --name bkconfig --entrypoint /bin/sh -v eden-bk-config:/config "$BUILDKIT_IMAGE"
docker cp buildkitd.toml bkconfig:/config/buildkitd.toml
docker rm -v bkconfig
docker volume create eden-bk-state
docker run -d --name eden-buildkitd --restart unless-stopped --privileged -p 1234:1234 \
  -v eden-bk-certs:/certs:ro -v eden-bk-config:/etc/buildkit:ro \
  -v eden-bk-state:/var/lib/buildkit \
  "$BUILDKIT_IMAGE" --addr tcp://0.0.0.0:1234 \
  --tlscacert /certs/ca.pem --tlscert /certs/daemon.pem --tlskey /certs/daemon-key.pem
```

The state volume is named so recreating the daemon reuses one cache instead of
leaving an unreachable anonymous volume behind. `buildkitd.toml` keeps that
cache between 8 GB and 20 GB and asks garbage collection to preserve 12 GB of
free Docker VM disk. The two seed containers use `docker rm -v` because the
BuildKit image declares its own state volume even though those containers only
copy configuration.

Verify the replacement on the mini:

```sh
docker inspect eden-buildkitd --format \
  'status={{.State.Status}} state={{range .Mounts}}{{if eq .Destination "/var/lib/buildkit"}}{{.Name}}{{end}}{{end}}'
docker exec eden-buildkitd cat /etc/buildkit/buildkitd.toml
docker exec eden-buildkitd df -h /var/lib/buildkit
docker system df
```

Then run the client proof below. `docker buildx inspect --bootstrap eden-mini`
must advertise the configured GC policy, and the uncached ARM64 build must pass.

The daemon survives a reboot with `--restart unless-stopped` plus the
Docker-autostart chain (the LaunchAgent `com.gophersys.docker-autostart` and
auto-login). See the reboot table in `README.md`.

## Step 3 — the client credential (into Vaultwarden)

The cluster reads the client certificate from Vaultwarden. Store the three client
PEM files as three items, one body per item:

| vault item | body |
| --- | --- |
| `shared/eden/buildkit-client-ca` | `ca.pem` |
| `shared/eden/buildkit-client-cert` | `client.pem` |
| `shared/eden/buildkit-client-key` | `client-key.pem` |

The ExternalSecret `40-buildkit-client-certs-externalsecret.yaml` pulls all three
into one Kubernetes Secret with the keys `ca.pem`, `cert.pem` and `key.pem`. Never
commit a PEM file. Verify the three names with
`bash ctl.sh verify-vault-refs` — each must resolve to exactly one item.

## Prove the node from a client

```sh
docker buildx create --name eden-mini --driver remote \
  --driver-opt cacert=ca.pem,cert=client.pem,key=client-key.pem tcp://10.168.0.92:1234
```

A build through `--builder eden-mini --platform linux/arm64` must succeed. A build
with no certificate must be refused. The repository verifier makes the positive
proof exercise DNS inside a real BuildKit executor:

```sh
BUILDKIT_DNS_BUILDER=eden-mini bash ../../../ctl.sh verify-buildkit-dns --live
```

The static form, `bash ../../../ctl.sh verify-buildkit-dns`, proves the portable
configuration and daemon wiring without contacting the node.
