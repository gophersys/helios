# CoreKinect Provisioning Secrets

Place the following files in this directory **before** building the image.
These files are excluded from git via `.gitignore` and must be provided manually.

```
secrets/
├── README.md                   ← this file (tracked)
├── corekinect-root-ca.crt      ← CoreKinect Root CA 2024
├── corekinect-sub-ca.crt       ← CoreKinect Sub CA 2024 (WINSRV01)
├── k3s-server-url              ← e.g. "https://10.4.45.10:6443"
└── k3s-token                   ← node join token from control plane
```

## How to obtain each file

### CA Certificates
Export from the CoreKinect AD Certificate Authority (WINSRV01):
- `corekinect-root-ca.crt` — Root CA certificate in PEM format
- `corekinect-sub-ca.crt` — Subordinate/Issuing CA certificate in PEM format

### K3s Server URL
The HTTPS endpoint of the K3s control plane. Get this from the server node:
```bash
# On the K3s server node:
echo "https://$(hostname -I | awk '{print $1}'):6443"
```
Write the URL (and nothing else) into `k3s-server-url`.

### K3s Token
The node join token. Get this from the server node:
```bash
# On the K3s server node:
sudo cat /var/lib/rancher/k3s/server/node-token
```
Write the token (and nothing else) into `k3s-token`.
