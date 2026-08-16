# Cluster Secrets

Scripts in this directory manage K8s secrets that must be created manually (not via Helm).

## Scripts

### create-theta-keys.sh

Creates the `theta-mcuboot-keys` secret containing MCUboot encryption keys for firmware signing. Required for FUOTA (firmware-over-the-air) operations.

```bash
# Create in staging namespace
bash infrastructure/clusters/office/secrets/create-theta-keys.sh staging

# Create in production namespace
bash infrastructure/clusters/office/secrets/create-theta-keys.sh production
```

## Adding New Secrets

1. Create a script in this directory that uses `kubectl create secret`
2. Use `--dry-run=client -o yaml | kubectl apply -f -` for idempotency
3. Document the secret's purpose and which services consume it
4. Never commit secret values to this repository
