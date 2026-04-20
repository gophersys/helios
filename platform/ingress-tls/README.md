# platform/ingress-tls

Ingress controller + certificate issuance for every cluster.

Default stack:

- `ingress-nginx` as the controller (Helm chart: ingress-nginx/ingress-nginx).
- `cert-manager` for ACME certificate issuance (Helm chart:
  jetstack/cert-manager).
- ClusterIssuers for Let's Encrypt staging + prod, DNS-01 when the cluster
  has a Route53/Azure DNS/Cloud DNS credential, HTTP-01 otherwise.

Status: stub. No `ctl.sh` or `project.json` yet — arrive once a cluster
is ready for install.

TODO:
- Pin chart versions in `values/<cluster>.yaml`.
- Decide traefik vs nginx (default nginx unless a cluster has a strong
  traefik signal).
- Add ClusterIssuer manifests parameterized by cluster domain.
