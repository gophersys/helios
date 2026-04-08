# Obsidian LiveSync — Self-Hosted Setup

Self-hosted note sync using CouchDB on the shared K3s cluster with the
Obsidian LiveSync community plugin.

**Endpoint:** `https://notes.mateosegura.com`
**Database:** `obsidian-livesync`
**CouchDB version:** 3.x (ARM64, runs on agent-00)

## Architecture

```
Obsidian (phone/laptop/tablet)
  └─ Self-hosted LiveSync plugin
       └─ HTTPS ──▶ notes.mateosegura.com
                      └─ ingress-nginx (TLS via cert-manager)
                           └─ couchdb.shared-services:5984
                                └─ PVC (10Gi persistent storage)
```

## 1. Deploy CouchDB

### Store the admin password in Vaultwarden

1. Log in to `https://secrets.mateosegura.com`
2. Create a new secure note named `couchdb-admin-password` in the Infrastructure folder
3. Generate and store a strong password

### Install the Helm chart

```bash
# From the infrastructure repo root
helm install couchdb kubernetes/shared-services/couchdb \
  -n shared-services \
  --set auth.adminPassword="<password-from-vaultwarden>"
```

### Verify the deployment

```bash
# Pod is running
kubectl get pods -n shared-services -l app.kubernetes.io/name=shared-couchdb

# Service is reachable inside cluster
kubectl run -n shared-services curl-test --rm -it --image=curlimages/curl -- \
  curl -s -u admin:<password> http://couchdb.shared-services:5984/_up

# Ingress + TLS working (from outside cluster)
curl -s https://notes.mateosegura.com/ -u admin:<password>
```

## 2. Initialize CouchDB for LiveSync

After the pod is running, create the required system databases and the
LiveSync database. These are one-time operations.

```bash
COUCHDB_URL="https://notes.mateosegura.com"
AUTH="admin:<password>"

# Create system databases (required for single-node CouchDB)
curl -X PUT "$COUCHDB_URL/_users" -u "$AUTH"
curl -X PUT "$COUCHDB_URL/_replicator" -u "$AUTH"
curl -X PUT "$COUCHDB_URL/_global_changes" -u "$AUTH"

# Create the LiveSync database
curl -X PUT "$COUCHDB_URL/obsidian-livesync" -u "$AUTH"
```

Verify all four return `{"ok":true}` (or `{"error":"file_exists"}` if already created).

## 3. Run Validation Tests

The chart includes a test suite that validates health, auth, CORS, and
LiveSync functionality.

### Local test (Docker)

```bash
cd kubernetes/shared-services/couchdb
./tests/validate.sh
```

### Live deployment test

```bash
export COUCHDB_PASSWORD="<password>"
./tests/validate.sh --live https://notes.mateosegura.com
```

All 17 tests should pass before proceeding to Obsidian setup.

## 4. Configure Obsidian (per device)

Repeat these steps on every device where you use Obsidian (laptop, phone,
tablet, etc.).

### Install the plugin

1. Open Obsidian **Settings** > **Community plugins** > **Browse**
2. Search for **"Self-hosted LiveSync"** (by vrtmrz)
3. Click **Install**, then **Enable**

### Configure the connection

1. Open **Settings** > **Self-hosted LiveSync** (in the sidebar)
2. You'll see the setup wizard on first open. Choose **Manual setup**
3. Fill in the connection settings:

| Field | Value |
|-------|-------|
| Server URL | `https://notes.mateosegura.com` |
| Username | `admin` |
| Password | `<password-from-vaultwarden>` |
| Database name | `obsidian-livesync` |

4. Click **Test** — should show "Connected to CouchDB"
5. Click **Apply**

### Choose a sync mode

| Mode | Behavior | Best for |
|------|----------|----------|
| **LiveSync** | Real-time, bidirectional | Primary devices you use actively |
| **Periodic** | Syncs every N seconds | Devices used occasionally |
| **On trigger** | Manual sync only | Rarely used devices |

**Recommended:** Use **LiveSync** on your laptop and phone (the two you use
most), and **Periodic** (every 60s) on anything else.

To set the mode:
1. In LiveSync settings, go to the **Sync Settings** tab
2. Select your preferred mode
3. Toggle **Sync on Launch** to ON

### First sync

On the **first device** (the one with your existing notes):
1. Go to the **Sync Settings** tab
2. Click **Send all to server** (this uploads your existing vault)
3. Wait for it to finish — progress shows in the status bar

On **every subsequent device**:
1. Open Obsidian with a fresh (empty) vault
2. Configure the LiveSync plugin with the same settings above
3. Click **Fetch all from server** in Sync Settings
4. Your notes will appear within seconds

### Hidden files and settings sync

To sync Obsidian settings, themes, and plugin configs across devices:

1. In LiveSync settings, go to **Hatch** > **Hidden File Sync**
2. Enable **Sync hidden files**
3. Choose which folders to sync (recommended: `.obsidian/themes`,
   `.obsidian/snippets`; skip `.obsidian/workspace.json` as it's
   device-specific)

## 5. Maintenance

### Backup

CouchDB data lives on a 10Gi PVC. Back it up with:

```bash
# Dump all docs from the LiveSync database
kubectl exec -n shared-services couchdb-shared-couchdb-0 -- \
  curl -s http://localhost:5984/obsidian-livesync/_all_docs?include_docs=true \
  -u admin:<password> > obsidian-backup-$(date +%Y%m%d).json
```

### Compaction

Over time, CouchDB accumulates revision history. Compact periodically:

```bash
curl -X POST "https://notes.mateosegura.com/obsidian-livesync/_compact" \
  -u admin:<password> \
  -H "Content-Type: application/json"
```

### Upgrading CouchDB

Update the image tag in `values.yaml` and run:

```bash
helm upgrade couchdb kubernetes/shared-services/couchdb \
  -n shared-services \
  --set auth.adminPassword="<password>"
```

### Resource usage

CouchDB with LiveSync is lightweight for personal use:

| Metric | Typical |
|--------|---------|
| CPU | 10-50m (idle/sync) |
| Memory | 100-200Mi |
| Storage | 2-5x vault size (due to revision history) |
| Network | Negligible (delta sync) |

## Troubleshooting

**Plugin shows "Unauthorized"**
- Verify credentials match what was set during `helm install`
- Check CORS: `curl -I -X OPTIONS -H "Origin: app://obsidian.md" https://notes.mateosegura.com/`

**Sync is slow on mobile**
- Switch to Periodic mode (every 60s) instead of LiveSync
- Enable "Batch database update" in plugin settings

**Conflict markers in notes**
- LiveSync handles conflicts automatically with a merge dialog
- If you see duplicates, open the plugin's **Conflict resolution** pane

**Pod won't start**
- Check PVC is bound: `kubectl get pvc -n shared-services`
- Check logs: `kubectl logs -n shared-services couchdb-shared-couchdb-0`
