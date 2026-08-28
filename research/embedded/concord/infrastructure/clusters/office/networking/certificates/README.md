# Ingress TLS — manual rotation against the corp CA

Concord's ingress TLS is **not managed by cert-manager**. The wildcard cert covering all `*.concord.ad.corekinect.com` and `*.staging.concord.ad.corekinect.com` hostnames is issued by the **CoreKinect Sub-CA** (Windows AD CS — `CoreKinectSubCA-WINSRV01`) and pushed manually into both namespaces as the `concord-tls` Secret.

This folder is intentionally empty of `Certificate` manifests. The `concord-ca-issuer` ClusterIssuer (set up by `../cert-manager-ca.yaml`) is kept available for future internal-only certs (e.g., service-to-service mTLS) but is not wired to ingress.

## Current cert

| Property | Value |
|---|---|
| Subject CN | `*.concord.ad.corekinect.com` |
| Subject Alt Names | `*.concord.ad.corekinect.com`, `concord.ad.corekinect.com`, `*.staging.concord.ad.corekinect.com`, `staging.concord.ad.corekinect.com` |
| Issuer | `CoreKinectSubCA-WINSRV01` (corp Windows CA) |
| Valid through | **2028-04-14** |
| K8s home | `Secret/concord-tls` in both `staging` and `production` namespaces |
| Referenced by | `deploy/production/helm/concord/templates/ingress.yaml` (`secretName: concord-tls`) |

## Rotation procedure

When the cert nears expiry (next: April 2028):

1. **Generate a CSR** for the wildcard on a Windows machine that can talk to the corp CA, OR request via `certreq` against `CoreKinectSubCA-WINSRV01`. Include the full SAN list above.
2. **Receive `.crt` + `.key`** from the CA (PEM format).
3. **Push to both namespaces**:
   ```bash
   kubectl -n staging create secret tls concord-tls --cert=path/to/concord-tls.crt --key=path/to/concord-tls.key --dry-run=client -o yaml | kubectl apply -f -
   kubectl -n production create secret tls concord-tls --cert=path/to/concord-tls.crt --key=path/to/concord-tls.key --dry-run=client -o yaml | kubectl apply -f -
   ```
4. **Roll Traefik** (in `kube-system`) to pick up the new cert. K3s reloads automatically; otherwise: `kubectl -n kube-system rollout restart deploy/traefik`.
5. **Verify** with `curl -vIk https://staging.concord.ad.corekinect.com/` — `notAfter` should reflect the new expiry.

## Monitoring

There is no automated alert for cert expiry today. Until that's wired up, set a calendar reminder for **2028-02-01** (60 days before expiry) to start the renewal cycle.

To check expiry programmatically:

```bash
KUBECONFIG=~/.kube/config-concord-remote \
  kubectl -n production get secret concord-tls -o jsonpath='{.data.tls\.crt}' \
  | base64 -d | openssl x509 -noout -enddate
```

## History

A `staging-cert.yaml` (cert-manager `Certificate` referencing the local `concord-ca-issuer` and producing a `*.concord.local` cert) used to live here. It was never wired to the Ingress (the chart only references `concord-tls`), so the resulting `staging-concord-tls` Secret was an orphan. Removed in commit `<this commit>`; see [`.claude/knowledge/deploy/network.md`](../../../../../.claude/knowledge/deploy/network.md) for context.
