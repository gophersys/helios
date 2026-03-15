# Tier 4 — System Monitor & Advanced

## Goal

Port the System Monitor feature — the most complex part of the app. Includes cluster overview, node/pod/deployment/service/job management, log streaming (WebSocket), pod exec terminal (WebSocket + xterm.js), RBAC viewer, and YAML editor.

---

## Architecture

### New Routes

```
src/routes/system/
├── +layout.svelte                  # System layout with sub-nav
├── +page.svelte                    # Overview
├── nodes/
│   ├── +page.svelte               # Nodes list
│   └── [nodeName]/+page.svelte    # Node detail
├── pods/
│   ├── +page.svelte               # Pods list
│   └── [namespace]/[name]/+page.svelte  # Pod detail
├── deployments/
│   ├── +page.svelte               # Deployments list
│   └── [namespace]/[name]/+page.svelte  # Deployment detail
├── services/
│   ├── +page.svelte               # Services list
│   └── [namespace]/[name]/+page.svelte  # Service detail
├── jobs/
│   ├── +page.svelte               # Jobs list
│   └── [namespace]/[name]/+page.svelte  # Job detail
├── config/+page.svelte            # ConfigMaps and Secrets
├── rbac/+page.svelte              # RBAC viewer
└── events/+page.svelte            # Events feed
```

### New Components

```
src/lib/components/system/
├── metric-card.svelte
├── status-indicator.svelte
├── resource-age.svelte
├── usage-bar.svelte
├── progress-ring.svelte
├── label-list.svelte
├── info-row.svelte
├── resource-table.svelte
├── collapsible-section.svelte
├── namespace-selector.svelte
├── action-button.svelte
├── log-viewer.svelte              # WebSocket log streaming
├── terminal.svelte                # xterm.js pod exec
├── yaml-viewer.svelte
├── yaml-editor.svelte
└── resource-yaml-dialog.svelte
```

---

## Components

| React Component | Svelte Target | Notes |
|-----------------|---------------|-------|
| **Layout** |||
| `system-page.tsx` | `routes/system/+layout.svelte` | System layout with tabs |
| **Overview** |||
| `overview.tsx` | `routes/system/+page.svelte` | Cluster dashboard |
| **Nodes** |||
| `nodes-list.tsx` | `routes/system/nodes/+page.svelte` | Node list |
| `node-detail.tsx` | `routes/system/nodes/[nodeName]/+page.svelte` | Node detail |
| **Pods** |||
| `pods-list.tsx` | `routes/system/pods/+page.svelte` | Pod list |
| `pod-detail.tsx` | `routes/system/pods/[namespace]/[name]/+page.svelte` | Pod detail + logs + exec |
| **Deployments** |||
| `deployments-list.tsx` | `routes/system/deployments/+page.svelte` | Deployment list |
| `deployment-detail.tsx` | `routes/system/deployments/[namespace]/[name]/+page.svelte` | Deployment detail |
| **Services** |||
| `services-list.tsx` | `routes/system/services/+page.svelte` | Service list |
| `service-detail.tsx` | `routes/system/services/[namespace]/[name]/+page.svelte` | Service detail |
| **Jobs** |||
| `jobs-list.tsx` | `routes/system/jobs/+page.svelte` | Job list |
| `job-detail.tsx` | `routes/system/jobs/[namespace]/[name]/+page.svelte` | Job detail |
| **Config** |||
| `config-list.tsx` | `routes/system/config/+page.svelte` | ConfigMaps + Secrets |
| **Events** |||
| `events-list.tsx` | `routes/system/events/+page.svelte` | Events feed |
| **RBAC** |||
| `rbac.tsx` | `routes/system/rbac/+page.svelte` | RBAC viewer |
| **Components** |||
| `metric-card.tsx` | `lib/components/system/metric-card.svelte` | Stat card |
| `status-indicator.tsx` | `lib/components/system/status-indicator.svelte` | Status dot |
| `resource-age.tsx` | `lib/components/system/resource-age.svelte` | Age display |
| `usage-bar.tsx` | `lib/components/system/usage-bar.svelte` | Usage bar |
| `progress-ring.tsx` | `lib/components/system/progress-ring.svelte` | SVG ring |
| `label-list.tsx` | `lib/components/system/label-list.svelte` | Label chips |
| `info-row.tsx` | `lib/components/system/info-row.svelte` | Key-value row |
| `resource-table.tsx` | `lib/components/system/resource-table.svelte` | Generic table |
| `collapsible-section.tsx` | `lib/components/system/collapsible-section.svelte` | Collapsible |
| `namespace-selector.tsx` | `lib/components/system/namespace-selector.svelte` | NS dropdown |
| `action-button.tsx` | `lib/components/system/action-button.svelte` | Action btn |
| `log-viewer.tsx` | `lib/components/system/log-viewer.svelte` | Log streaming |
| `terminal.tsx` | `lib/components/system/terminal.svelte` | Pod exec |
| `yaml-viewer.tsx` | `lib/components/system/yaml-viewer.svelte` | YAML display |
| `yaml-editor.tsx` | `lib/components/system/yaml-editor.svelte` | YAML edit |
| `resource-yaml-dialog.tsx` | `lib/components/system/resource-yaml-dialog.svelte` | YAML modal |

---

## Phase Checklist

- [ ] Phase 1 — System layout and overview
- [ ] Phase 2 — Nodes and events pages
- [ ] Phase 3 — Pods and deployments pages
- [ ] Phase 4 — Services, jobs, config pages
- [ ] Phase 5 — Log viewer and terminal (WebSocket)
- [ ] Phase 6 — RBAC page and YAML editor

---

## Key Patterns

### WebSocket with SocketIO

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import { io, type Socket } from 'socket.io-client';
  import { getToken } from '$lib/api';

  let { namespace, podName, containerName }: Props = $props();

  let logs = $state<string[]>([]);
  let socket: Socket | null = null;

  onMount(() => {
    const token = getToken();
    socket = io('/system', {
      auth: { token }
    });

    socket.on('connect', () => {
      socket?.emit('subscribe_logs', {
        namespace,
        pod: podName,
        container: containerName
      });
    });

    socket.on('log_line', (data: { line: string }) => {
      logs = [...logs, data.line];
    });

    return () => {
      socket?.disconnect();
    };
  });
</script>
```

### xterm.js Terminal

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import { Terminal } from '@xterm/xterm';
  import { FitAddon } from '@xterm/addon-fit';
  import { io, type Socket } from 'socket.io-client';
  import { getToken } from '$lib/api';

  let { namespace, podName, containerName }: Props = $props();

  let terminalEl: HTMLDivElement;
  let terminal: Terminal | null = null;
  let socket: Socket | null = null;

  onMount(() => {
    terminal = new Terminal({
      cursorBlink: true,
      theme: {
        background: '#151518',
        foreground: '#ededf0'
      }
    });

    const fitAddon = new FitAddon();
    terminal.loadAddon(fitAddon);
    terminal.open(terminalEl);
    fitAddon.fit();

    const token = getToken();
    socket = io('/system', { auth: { token } });

    socket.on('connect', () => {
      socket?.emit('exec_start', {
        namespace,
        pod: podName,
        container: containerName
      });
    });

    socket.on('exec_output', (data: { output: string }) => {
      terminal?.write(data.output);
    });

    terminal.onData((data) => {
      socket?.emit('exec_input', { input: data });
    });

    return () => {
      terminal?.dispose();
      socket?.disconnect();
    };
  });
</script>

<div bind:this={terminalEl} class="h-96 w-full"></div>
```

### System Layout with Tabs

```svelte
<!-- routes/system/+layout.svelte -->
<script lang="ts">
  import { page } from '$app/stores';
  import { getAuth } from '$lib/stores/auth.svelte';
  import NamespaceSelector from '$lib/components/system/namespace-selector.svelte';

  let { children } = $props();

  const auth = getAuth();
  let namespace = $state('default');

  const tabs = [
    { path: '/system', label: 'Overview', end: true },
    { path: '/system/nodes', label: 'Nodes' },
    { path: '/system/pods', label: 'Pods' },
    { path: '/system/deployments', label: 'Deployments' },
    { path: '/system/services', label: 'Services' },
    { path: '/system/jobs', label: 'Jobs' },
    { path: '/system/config', label: 'Config' },
    { path: '/system/rbac', label: 'RBAC' },
    { path: '/system/events', label: 'Events' }
  ];

  function isActive(path: string, end = false): boolean {
    if (end) return $page.url.pathname === path;
    return $page.url.pathname.startsWith(path);
  }
</script>

<div class="animate-fade-in">
  <div class="mb-6 flex items-center justify-between">
    <h1 class="text-xl font-semibold text-text-primary">System Monitor</h1>
    <NamespaceSelector bind:value={namespace} />
  </div>

  <!-- Tab navigation -->
  <div class="mb-6 flex gap-1 overflow-x-auto rounded-lg bg-surface-2 p-1">
    {#each tabs as { path, label, end }}
      <a
        href={path}
        class="whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium transition-colors"
        class:bg-surface-1={isActive(path, end)}
        class:text-text-primary={isActive(path, end)}
        class:shadow-sm={isActive(path, end)}
        class:text-text-secondary={!isActive(path, end)}
        class:hover:text-text-primary={!isActive(path, end)}
      >
        {label}
      </a>
    {/each}
  </div>

  {@render children()}
</div>
```

---

## Verification

After Tier 4:
1. System overview shows cluster health metrics
2. Progress rings and usage bars display correctly
3. Node list shows all nodes with status
4. Node detail shows conditions, labels, capacity
5. Pod list shows all pods with filtering
6. Pod detail shows containers, logs (streaming), exec terminal
7. Deployment list and detail with scale/restart actions
8. Service list and detail
9. Job list and detail with delete action
10. ConfigMaps and Secrets list
11. Events feed with type filtering
12. RBAC viewer shows roles, bindings, service accounts
13. YAML viewer/editor works with apply/delete
14. WebSocket connections for logs and exec are stable
15. Visual parity with React app verified

---

## Migration Complete

After Tier 4, the migration is complete. All features from the React app are now available in Svelte.

### Final Steps

1. Delete the old React app directory
2. Rename `concord-app-svelte` to `concord-app`
3. Update any CI/CD pipelines
4. Update documentation
5. Remove React-specific dependencies from root package.json
