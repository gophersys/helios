# Tier 3 — Advanced Operations: Exec, YAML, RBAC

## Goal

Give super admins full operational control: interactive pod exec (terminal in browser), YAML viewing/editing for any resource, and an RBAC viewer. This brings the system monitor close to k9s parity.

---

## Architecture

### Backend — New Files

```
src/services/kubernetes/
  serializers.py     MODIFY  — add serialize_resource_yaml, RBAC serializers
  exec.py            CREATE  — pod exec session management
  resources.py       CREATE  — generic resource get/apply/patch/delete by kind
  rbac.py            CREATE  — roles, role bindings, service accounts, cluster roles

src/api/v2/system/
  exec.py            CREATE  — SocketIO handlers for pod exec
  resources.py       CREATE  — GET/PUT/DELETE for arbitrary resource YAML
  rbac.py            CREATE  — REST endpoints for RBAC resources
```

### Frontend — New Files

```
src/app/pages/system/
  system-page.tsx        MODIFY  — add RBAC tab
  rbac.tsx               CREATE  — RBAC viewer page

src/app/components/system/
  terminal.tsx           CREATE  — xterm.js terminal component for pod exec
  yaml-viewer.tsx        CREATE  — read-only YAML display with syntax highlighting
  yaml-editor.tsx        CREATE  — editable YAML with apply/cancel
  resource-yaml-dialog.tsx CREATE — modal for viewing/editing resource YAML
```

### Dependencies

```
# Frontend (package.json)
@xterm/xterm          — terminal emulator
@xterm/addon-fit      — auto-resize terminal
socket.io-client      — already installed from Tier 2

# Backend (setup.py)
pyyaml                — YAML serialization (already a transitive dep of kubernetes client)
```

---

## Permissions

| Permission | Actions |
|---|---|
| `Concord.Admin.System.View` | View YAML, view RBAC |
| `Concord.Admin.System.Manage` | Pod exec, apply/edit YAML, delete resources |

---

## API Contracts

### Pod Exec (SocketIO)

**Namespace:** `/system`

**Events:**
- Client → `exec_start` `{ namespace, pod, container, command? }`
  - `command` defaults to `["/bin/sh"]`
- Server → `exec_output` `{ data }` (binary/text output from container)
- Client → `exec_input` `{ data }` (keyboard input from user)
- Client → `exec_resize` `{ cols, rows }`
- Client → `exec_stop`
- Server → `exec_error` `{ message }`
- Server → `exec_exit` `{ code }`

### Resource YAML

**GET /v2/system/resources/\<kind\>/\<namespace\>/\<name\>**

```json
{
  "ok": true,
  "data": {
    "kind": "Deployment",
    "apiVersion": "apps/v1",
    "yaml": "apiVersion: apps/v1\nkind: Deployment\n..."
  }
}
```

Supported kinds: `pod`, `deployment`, `service`, `job`, `configmap`, `secret`, `daemonset`, `statefulset`, `ingress`

**PUT /v2/system/resources/\<kind\>/\<namespace\>/\<name\>** — requires `System.Manage`

```json
{
  "yaml": "apiVersion: apps/v1\nkind: Deployment\n..."
}
```

Returns the updated resource YAML.

**DELETE /v2/system/resources/\<kind\>/\<namespace\>/\<name\>** — requires `System.Manage`

### RBAC

**GET /v2/system/rbac/roles?namespace=\<ns\>**

```json
{
  "ok": true,
  "data": [
    {
      "name": "pod-reader",
      "namespace": "default",
      "rules": [
        { "apiGroups": [""], "resources": ["pods"], "verbs": ["get", "list", "watch"] }
      ],
      "createdAt": "2024-01-10T08:00:00Z"
    }
  ]
}
```

**GET /v2/system/rbac/clusterroles**

Same shape as roles, but no namespace.

**GET /v2/system/rbac/bindings?namespace=\<ns\>**

```json
{
  "ok": true,
  "data": [
    {
      "name": "read-pods",
      "namespace": "default",
      "roleRef": { "kind": "Role", "name": "pod-reader" },
      "subjects": [
        { "kind": "ServiceAccount", "name": "my-sa", "namespace": "default" }
      ],
      "createdAt": "2024-01-10T08:00:00Z"
    }
  ]
}
```

**GET /v2/system/rbac/clusterrolebindings**

Same shape as bindings, but no namespace.

**GET /v2/system/rbac/serviceaccounts?namespace=\<ns\>**

```json
{
  "ok": true,
  "data": [
    {
      "name": "my-sa",
      "namespace": "default",
      "secrets": ["my-sa-token-xxxxx"],
      "createdAt": "2024-01-10T08:00:00Z"
    }
  ]
}
```

---

## Frontend Component Tree

```
/system (SystemPage — MODIFIED)
  ├── Sub-navigation: [...existing tabs, RBAC]
  │
  ├── /system/rbac → RBAC
  │     ├── Tab toggle: [Roles, ClusterRoles, Bindings, ClusterRoleBindings, ServiceAccounts]
  │     ├── NamespaceSelector (for namespaced resources)
  │     └── ResourceTable per tab
  │
  ├── Pod Detail — MODIFIED
  │     └── Exec button → opens Terminal component (System.Manage only)
  │
  └── All detail pages — MODIFIED
        └── "View YAML" button → opens ResourceYamlDialog modal
```

---

## Phase Checklist

- [x] Phase 1 — Backend: generic resource YAML get/apply service
- [x] Phase 2 — Backend: RBAC service module
- [x] Phase 3 — Backend: API routes for resources + RBAC, pod exec SocketIO
- [x] Phase 4 — Frontend: YAML viewer/editor components + resource YAML dialog
- [x] Phase 5 — Frontend: terminal component + pod exec integration
- [x] Phase 6 — Frontend: RBAC viewer page + final polish
