import { useAuth } from '../../../auth-provider';

// Group permissions by category for display
function groupPermissions(permissions: string[]) {
  const groups: Record<string, string[]> = {};
  for (const perm of permissions) {
    const parts = perm.split('.');
    const group = parts.length >= 3 ? parts[1] : 'Other';
    if (!groups[group]) groups[group] = [];
    // Show the tail portion: e.g. "AppID.Create" from "Concord.Firmware.AppID.Create"
    groups[group].push(parts.slice(2).join('.'));
  }
  return groups;
}

export function PermissionsSection() {
  const { user } = useAuth();

  if (!user) return null;

  const groups = groupPermissions(user.permissions ?? []);
  const hasPermissions = user.permissions && user.permissions.length > 0;

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

      {/* Grouped permissions */}
      {hasPermissions ? (
        <div className="space-y-4">
          {Object.entries(groups).map(([group, perms]) => (
            <div key={group}>
              <div className="mb-1.5 text-xs font-semibold text-text-primary">
                {group}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {perms.map((p) => (
                  <span
                    key={p}
                    className="rounded-full bg-surface-2 px-2 py-0.5 text-2xs text-text-secondary"
                  >
                    {p}
                  </span>
                ))}
              </div>
            </div>
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
