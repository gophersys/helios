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
        <div className="flex items-center gap-2 rounded-lg border border-error bg-error-muted px-3 py-2 text-xs text-error">
          <AlertTriangle size={14} />
          {error}
        </div>
      )}

      <textarea
        value={yaml}
        onChange={(e) => setYaml(e.target.value)}
        onKeyDown={handleKeyDown}
        spellCheck={false}
        aria-label="YAML editor"
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
            className="flex items-center gap-1 rounded bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Save size={12} />
            {saving ? 'Applying...' : 'Apply'}
          </button>
        </div>
      </div>
    </div>
  );
}
