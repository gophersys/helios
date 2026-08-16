# Phase 4 — Frontend: YAML Viewer/Editor + Resource YAML Dialog

## Objective

Build the YAML display and editing components, plus a modal dialog that can be opened from any resource detail page to view/edit that resource's YAML.

---

## 1. Install dependency

Add `@xterm/xterm` and `@xterm/addon-fit` to `package.json` (needed for Phase 5, install now):

```bash
yarn add @xterm/xterm @xterm/addon-fit
```

---

## 2. Create `src/app/components/system/yaml-viewer.tsx`

Read-only YAML display with basic syntax highlighting via CSS classes.

```tsx
import { useRef, useEffect } from 'react';
import { Copy, Check } from 'lucide-react';
import { useState } from 'react';

interface YamlViewerProps {
  yaml: string;
}

export function YamlViewer({ yaml }: YamlViewerProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(yaml);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const highlightedLines = yaml.split('\n').map((line, i) => {
    // Basic YAML syntax highlighting
    let html = line;

    // Comments
    if (line.trimStart().startsWith('#')) {
      html = `<span class="text-text-tertiary">${escapeHtml(line)}</span>`;
    }
    // Keys (word followed by colon)
    else if (/^(\s*)([\w.-]+)(:)(.*)$/.test(line)) {
      html = line.replace(
        /^(\s*)([\w.-]+)(:)(.*)$/,
        (_, indent, key, colon, val) =>
          `${indent}<span class="text-accent">${escapeHtml(key)}</span>${colon}${highlightValue(val)}`
      );
    }
    // List items
    else if (/^(\s*)(- )(.*)$/.test(line)) {
      html = line.replace(
        /^(\s*)(- )(.*)$/,
        (_, indent, dash, val) =>
          `${indent}<span class="text-warning">${dash}</span>${highlightValue(val)}`
      );
    }

    return html;
  });

  return (
    <div className="relative">
      <button
        onClick={handleCopy}
        className="absolute right-3 top-3 flex items-center gap-1 rounded bg-surface-2 px-2 py-1 text-xs text-text-tertiary transition-colors hover:text-text-primary"
      >
        {copied ? <Check size={12} /> : <Copy size={12} />}
        {copied ? 'Copied' : 'Copy'}
      </button>
      <pre className="overflow-auto rounded-lg border border-border bg-surface-1 p-4 font-mono text-xs leading-5 text-text-secondary">
        {highlightedLines.map((line, i) => (
          <div key={i} className="hover:bg-surface-2/50" dangerouslySetInnerHTML={{ __html: line }} />
        ))}
      </pre>
    </div>
  );
}

function escapeHtml(str: string): string {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function highlightValue(val: string): string {
  const trimmed = val.trim();
  if (!trimmed) return val;

  // Strings in quotes
  if (/^["'].*["']$/.test(trimmed)) {
    return ` <span class="text-success">${escapeHtml(trimmed)}</span>`;
  }
  // Booleans
  if (/^(true|false)$/i.test(trimmed)) {
    return ` <span class="text-warning">${escapeHtml(trimmed)}</span>`;
  }
  // Numbers
  if (/^\d+(\.\d+)?$/.test(trimmed)) {
    return ` <span class="text-info">${escapeHtml(trimmed)}</span>`;
  }
  // Null
  if (trimmed === 'null' || trimmed === '~') {
    return ` <span class="text-text-tertiary">${escapeHtml(trimmed)}</span>`;
  }

  return ` ${escapeHtml(trimmed)}`;
}
```

---

## 3. Create `src/app/components/system/yaml-editor.tsx`

Editable textarea for YAML with apply/cancel buttons.

```tsx
import { useState } from 'react';
import { Save, X, AlertTriangle } from 'lucide-react';

interface YamlEditorProps {
  initialYaml: string;
  onApply: (yaml: string) => Promise<void>;
  onCancel: () => void;
}

export function YamlEditor({ initialYaml, onApply, onCancel }: YamlEditorProps) {
  const [yaml, setYaml] = useState(initialYaml);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasChanges = yaml !== initialYaml;

  const handleApply = async () => {
    setSaving(true);
    setError(null);
    try {
      await onApply(yaml);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to apply changes');
    } finally {
      setSaving(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Allow Tab in textarea
    if (e.key === 'Tab') {
      e.preventDefault();
      const target = e.target as HTMLTextAreaElement;
      const start = target.selectionStart;
      const end = target.selectionEnd;
      setYaml(yaml.substring(0, start) + '  ' + yaml.substring(end));
      setTimeout(() => {
        target.selectionStart = target.selectionEnd = start + 2;
      }, 0);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-xs text-error">
          <AlertTriangle size={14} />
          {error}
        </div>
      )}

      <textarea
        value={yaml}
        onChange={(e) => setYaml(e.target.value)}
        onKeyDown={handleKeyDown}
        spellCheck={false}
        className="h-[500px] w-full resize-none rounded-lg border border-border bg-surface-1 p-4 font-mono text-xs leading-5 text-text-primary focus:border-accent focus:outline-none focus:ring-1 focus:ring-focus-ring"
      />

      <div className="flex items-center justify-between">
        <div className="text-xs text-text-tertiary">
          {hasChanges ? 'Unsaved changes' : 'No changes'}
        </div>
        <div className="flex gap-2">
          <button
            onClick={onCancel}
            disabled={saving}
            className="flex items-center gap-1 rounded px-3 py-1.5 text-xs font-medium text-text-tertiary transition-colors hover:text-text-primary"
          >
            <X size={12} />
            Cancel
          </button>
          <button
            onClick={handleApply}
            disabled={!hasChanges || saving}
            className="flex items-center gap-1 rounded bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Save size={12} />
            {saving ? 'Applying...' : 'Apply'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

---

## 4. Create `src/app/components/system/resource-yaml-dialog.tsx`

Modal dialog that fetches and displays resource YAML. Users with `System.Manage` can switch to edit mode.

```tsx
import { useCallback, useEffect, useState } from 'react';
import { X, Pencil, Eye } from 'lucide-react';
import { api } from '../../api';
import { type ApiResponse } from '../../types';
import { useAuth } from '../../auth-provider';
import { LoadingState } from '../ui/loading-state';
import { YamlViewer } from './yaml-viewer';
import { YamlEditor } from './yaml-editor';

interface ResourceYamlDialogProps {
  kind: string;
  namespace: string;
  name: string;
  open: boolean;
  onClose: () => void;
}

interface ResourceYamlData {
  kind: string;
  apiVersion: string;
  yaml: string;
}

export function ResourceYamlDialog({ kind, namespace, name, open, onClose }: ResourceYamlDialogProps) {
  const { hasPermission } = useAuth();
  const [data, setData] = useState<ResourceYamlData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  const canManage = hasPermission('Concord.Admin.System.Manage');

  const fetchYaml = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api<ApiResponse<ResourceYamlData>>(
        `/v2/system/resources/${kind}/${namespace}/${name}`
      );
      setData(res.data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load YAML');
    } finally {
      setLoading(false);
    }
  }, [kind, namespace, name]);

  useEffect(() => {
    if (open) {
      fetchYaml();
      setEditing(false);
    }
  }, [open, fetchYaml]);

  const handleApply = async (yaml: string) => {
    await api(`/v2/system/resources/${kind}/${namespace}/${name}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ yaml }),
    });
    await fetchYaml();
    setEditing(false);
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="mx-4 max-h-[85vh] w-full max-w-4xl overflow-hidden rounded-xl border border-border bg-surface-1 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-text-primary">
              {data?.kind || kind} — {namespace}/{name}
            </h3>
            {data?.apiVersion && (
              <span className="rounded bg-surface-2 px-2 py-0.5 text-2xs text-text-tertiary">
                {data.apiVersion}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {canManage && data && (
              <button
                onClick={() => setEditing(!editing)}
                className="flex items-center gap-1 rounded px-2 py-1 text-xs text-text-tertiary transition-colors hover:text-text-primary"
              >
                {editing ? <Eye size={12} /> : <Pencil size={12} />}
                {editing ? 'View' : 'Edit'}
              </button>
            )}
            <button
              onClick={onClose}
              className="rounded p-1 text-text-tertiary transition-colors hover:text-text-primary"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="max-h-[75vh] overflow-auto p-4">
          {loading ? (
            <LoadingState message="Loading YAML..." />
          ) : error ? (
            <div className="text-center text-sm text-error">{error}</div>
          ) : data ? (
            editing ? (
              <YamlEditor
                initialYaml={data.yaml}
                onApply={handleApply}
                onCancel={() => setEditing(false)}
              />
            ) : (
              <YamlViewer yaml={data.yaml} />
            )
          ) : null}
        </div>
      </div>
    </div>
  );
}
```

---

## 5. Add "View YAML" button to existing detail pages

Add a YAML button to each detail page header. This is the same pattern for all detail pages.

**Example modification for `pod-detail.tsx`:**

Add import:
```tsx
import { ResourceYamlDialog } from '../../components/system/resource-yaml-dialog';
```

Add state:
```tsx
const [showYaml, setShowYaml] = useState(false);
```

Add button next to existing action buttons in the header:
```tsx
<button
  onClick={() => setShowYaml(true)}
  className="flex items-center gap-1 rounded px-3 py-1.5 text-xs font-medium text-text-tertiary transition-colors hover:bg-surface-2 hover:text-text-primary"
>
  YAML
</button>
```

Add dialog before closing `</div>`:
```tsx
{namespace && name && (
  <ResourceYamlDialog
    kind="pod"
    namespace={namespace}
    name={name}
    open={showYaml}
    onClose={() => setShowYaml(false)}
  />
)}
```

**Apply the same pattern to:**
- `deployment-detail.tsx` (kind="deployment")
- `service-detail.tsx` (kind="service")
- `job-detail.tsx` (kind="job")
- `node-detail.tsx` — skip this, nodes are cluster-scoped and use a different API pattern

---

## Verification

1. Frontend compiles without errors
2. Pod/deployment/service/job detail pages show "YAML" button
3. Clicking "YAML" opens modal with syntax-highlighted YAML
4. Copy button works
5. Users with System.Manage see "Edit" toggle
6. Editing YAML and clicking "Apply" patches the resource
7. Modal closes cleanly, no memory leaks

---

## Overview Update

```
- [x] Phase 4 — Frontend: YAML viewer/editor components + resource YAML dialog
```
