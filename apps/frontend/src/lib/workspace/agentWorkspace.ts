// The agent-WORKSPACE model — the data layer behind the agent-type-aware right panel of the Eden
// workspace. Two concerns, one home: (1) the AGENT-TYPE registry (which widgets a session's right
// panel renders, keyed by the agent type — the "right side changes with agent type" requirement),
// and (2) deriving the ARTIFACTS (files/folders the agent generated) LIVE from its tool-call
// stream, so the panel updates the instant the agent touches a file — no extra backend round-trip.
import type { Entry, ToolEntry } from '$lib/gateway/session.svelte';

/** The right-panel widgets a session can mount. New widgets are added here + in RightPanel. */
export type WidgetId =
  | 'workspace'
  | 'files'
  | 'activity'
  | 'documents'
  | 'decisions'
  | 'agents'
  | 'progress';

/** An out-of-the-box agent type: its label, glyph, and the ORDERED right-panel widget stack it
 *  presents. The implementer is realized today; architect/supervisor/entry-point are scaffolded so
 *  the panel composes per type (their type-specific widgets land as the framework grows). */
export interface AgentTypeDescriptor {
  id: string;
  label: string;
  glyph: string;
  widgets: WidgetId[];
}

export const AGENT_TYPES: Record<string, AgentTypeDescriptor> = {
  // "less is more": each type mounts only the widgets it needs (live activity already lives in the
  // conversation's status bars, so it is not duplicated as a panel widget). 'workspace' is the
  // tool-derived (instant) file view; 'files' is the on-disk ground-truth tree (it starts collapsed).
  implementer: {
    id: 'implementer',
    label: 'Implementer',
    glyph: '⚙',
    widgets: ['workspace', 'files'],
  },
  architect: {
    id: 'architect',
    label: 'Architect',
    glyph: '◳',
    widgets: ['documents', 'decisions', 'files'],
  },
  supervisor: {
    id: 'supervisor',
    label: 'Supervisor',
    glyph: '⌖',
    widgets: ['agents', 'progress'],
  },
  entrypoint: { id: 'entrypoint', label: 'Entry point', glyph: '⎈', widgets: ['files'] },
};

/** agentTypeFor maps a session's template (and harness) to its agent type. Today the template name
 *  carries the type (implementer-go → implementer); when the AgentTemplate declares its type
 *  explicitly (the git-backed agent-configs), this reads that field instead. Defaults to implementer. */
export function agentTypeFor(template?: string, _harness?: string): AgentTypeDescriptor {
  const name = (template ?? '').toLowerCase();
  if (name.includes('architect')) return AGENT_TYPES.architect;
  if (name.includes('supervisor')) return AGENT_TYPES.supervisor;
  if (name.includes('entry')) return AGENT_TYPES.entrypoint;
  return AGENT_TYPES.implementer;
}

/** A file/folder the agent has worked on, accreted across its tool calls. */
export interface Artifact {
  path: string;
  operations: string[]; // the distinct file tools applied (Write, Edit, Read, …), in first-seen order
  status: ToolEntry['status'];
  lastOp: string;
}

/** The tools that act on workspace files — their targets are the agent's artifacts. */
const FILE_TOOLS = new Set([
  'Write',
  'Edit',
  'MultiEdit',
  'NotebookEdit',
  'Read',
  'Create',
  'Update',
  'Delete',
]);

/** deriveArtifacts folds a session's entry timeline into the set of files the agent touched, keyed
 *  by path and ordered by first appearance — the live "files/assets generated" view. Pure + cheap,
 *  so the widget can recompute it on every streamed event. */
export function deriveArtifacts(entries: Entry[]): Artifact[] {
  const byPath = new Map<string, Artifact>();
  for (const entry of entries) {
    if (entry.role !== 'tool') continue;
    const tool = entry.tool;
    if (!FILE_TOOLS.has(tool.name)) continue;
    const path = extractPath(tool.argsSummary);
    if (!path) continue;
    const existing = byPath.get(path);
    if (existing) {
      if (!existing.operations.includes(tool.name)) existing.operations.push(tool.name);
      existing.status = tool.status;
      existing.lastOp = tool.name;
    } else {
      byPath.set(path, { path, operations: [tool.name], status: tool.status, lastOp: tool.name });
    }
  }
  return [...byPath.values()];
}

/** extractPath pulls a file path out of a tool's (redacted, possibly truncated) args summary,
 *  handling both the JSON digest of a real harness ({"path":"a.txt",…}) and the key=value form a
 *  fake/scripted harness emits (path=note.txt). Returns null when no path is present. */
export function extractPath(argsSummary?: string): string | null {
  if (!argsSummary) return null;
  const json = argsSummary.match(/"(?:path|file_path|filename|notebook_path)"\s*:\s*"([^"]+)"/);
  if (json) return json[1];
  const kv = argsSummary.match(/\b(?:path|file_path|filename)\s*=\s*([^\s,}]+)/);
  if (kv) return kv[1];
  return null;
}
