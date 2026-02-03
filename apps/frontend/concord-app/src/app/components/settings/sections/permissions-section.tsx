import { useAuth } from '../../../auth-provider';

// ── Action color mapping ──────────────────────────────────────

const ACTION_COLORS: Record<
  string,
  { bg: string; text: string; dot: string }
> = {
  Create: { bg: 'bg-success-muted', text: 'text-success', dot: 'bg-success' },
  View: { bg: 'bg-info-muted', text: 'text-info', dot: 'bg-info' },
  Read: { bg: 'bg-info-muted', text: 'text-info', dot: 'bg-info' },
  Update: { bg: 'bg-warning-muted', text: 'text-warning', dot: 'bg-warning' },
  Delete: { bg: 'bg-error-muted', text: 'text-error', dot: 'bg-error' },
  Manage: { bg: 'bg-accent-muted', text: 'text-accent', dot: 'bg-accent' },
  Run: { bg: 'bg-accent-muted', text: 'text-accent', dot: 'bg-accent' },
};

const DEFAULT_COLOR = {
  bg: 'bg-surface-2',
  text: 'text-text-secondary',
  dot: 'bg-text-tertiary',
};

function getActionColor(action: string) {
  return ACTION_COLORS[action] || DEFAULT_COLOR;
}

// ── Tree structure ────────────────────────────────────────────

interface TreeNode {
  label: string;
  permKey?: string;
  children: TreeNode[];
}

function buildTree(permissions: string[]): TreeNode[] {
  const root: TreeNode = { label: 'root', children: [] };

  for (const perm of permissions) {
    const parts = perm.split('.');
    const segments = parts.slice(1); // skip "Concord"

    let current = root;
    for (let i = 0; i < segments.length; i++) {
      const seg = segments[i];
      const isLeaf = i === segments.length - 1;

      let child = current.children.find((c) => c.label === seg);
      if (!child) {
        child = {
          label: seg,
          children: [],
          ...(isLeaf ? { permKey: perm } : {}),
        };
        current.children.push(child);
      }
      if (isLeaf) child.permKey = perm;
      current = child;
    }
  }

  return root.children;
}

function TreeDisplayNode({ node, depth }: { node: TreeNode; depth: number }) {
  const isLeaf = !!node.permKey;

  if (isLeaf) {
    const color = getActionColor(node.label);
    return (
      <span
        className={[
          'inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-2xs font-medium',
          color.bg,
          color.text,
        ].join(' ')}
      >
        <span className={['h-1.5 w-1.5 rounded-full', color.dot].join(' ')} />
        {node.label}
      </span>
    );
  }

  const leafChildren = node.children.filter((c) => c.permKey);
  const branchChildren = node.children.filter((c) => !c.permKey);

  return (
    <div style={{ paddingLeft: depth > 0 ? '16px' : '0' }}>
      <div className="flex items-center gap-2 py-1">
        <span className="text-2xs font-semibold text-text-primary">
          {node.label}
        </span>
        {leafChildren.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {leafChildren.map((child) => (
              <TreeDisplayNode key={child.label} node={child} depth={0} />
            ))}
          </div>
        )}
      </div>
      {branchChildren.map((child) => (
        <TreeDisplayNode key={child.label} node={child} depth={depth + 1} />
      ))}
    </div>
  );
}

// ── Component ─────────────────────────────────────────────────

export function PermissionsSection() {
  const { user } = useAuth();

  if (!user) return null;

  const hasPermissions = user.permissions && user.permissions.length > 0;
  const tree = buildTree(user.permissions ?? []);

  return (
    <div>
      <p className="mb-4 text-sm text-text-secondary">
        Your current access level in Concord.
      </p>

      {/* Permission set badge */}
      <div className="mb-5 flex items-center justify-between rounded-lg border border-border-subtle px-4 py-3">
        <div>
          <div className="text-2xs text-text-tertiary">Permission set</div>
          <div className="mt-0.5 text-sm font-semibold text-text-primary">
            {user.permissionSetName || 'None assigned'}
          </div>
        </div>
        <span className="rounded-full bg-accent-muted px-2.5 py-0.5 text-2xs font-medium text-accent">
          {user.permissions?.length ?? 0} permission{(user.permissions?.length ?? 0) !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Tree display */}
      {hasPermissions ? (
        <div className="rounded-lg border border-border-subtle p-3">
          {tree.map((node) => (
            <TreeDisplayNode key={node.label} node={node} depth={0} />
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-border-subtle px-4 py-6 text-center text-sm text-text-tertiary">
          No permissions assigned. Contact an administrator.
        </div>
      )}
    </div>
  );
}
