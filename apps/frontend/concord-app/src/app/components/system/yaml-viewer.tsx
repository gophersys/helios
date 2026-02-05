import { useState, type ReactNode } from 'react';
import { Copy, Check } from 'lucide-react';

interface YamlViewerProps {
  yaml: string;
}

function highlightValue(val: string, keyIndex: number): ReactNode {
  const trimmed = val.trim();
  if (!trimmed) return val;

  if (/^["'].*["']$/.test(trimmed)) {
    return <>{' '}<span key={`v-${keyIndex}`} className="text-success">{trimmed}</span></>;
  }
  if (/^(true|false)$/i.test(trimmed)) {
    return <>{' '}<span key={`v-${keyIndex}`} className="text-warning">{trimmed}</span></>;
  }
  if (/^\d+(\.\d+)?$/.test(trimmed)) {
    return <>{' '}<span key={`v-${keyIndex}`} className="text-info">{trimmed}</span></>;
  }
  if (trimmed === 'null' || trimmed === '~') {
    return <>{' '}<span key={`v-${keyIndex}`} className="text-text-tertiary">{trimmed}</span></>;
  }

  return <>{' '}{trimmed}</>;
}

function highlightLine(line: string, lineIndex: number): ReactNode {
  // Comment lines
  if (line.trimStart().startsWith('#')) {
    return <span className="text-text-tertiary">{line}</span>;
  }

  // Key-value lines: indent + key + colon + value
  const kvMatch = line.match(/^(\s*)([\w.-]+)(:)(.*)$/);
  if (kvMatch) {
    const [, indent, key, colon, val] = kvMatch;
    return (
      <>
        {indent}
        <span className="text-accent">{key}</span>
        {colon}
        {highlightValue(val, lineIndex)}
      </>
    );
  }

  // List item lines: indent + dash + value
  const listMatch = line.match(/^(\s*)(- )(.*)$/);
  if (listMatch) {
    const [, indent, dash, val] = listMatch;
    return (
      <>
        {indent}
        <span className="text-warning">{dash}</span>
        {highlightValue(val, lineIndex)}
      </>
    );
  }

  return line;
}

export function YamlViewer({ yaml }: YamlViewerProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(yaml);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const lines = yaml.split('\n');

  return (
    <div className="relative">
      <button
        onClick={handleCopy}
        aria-label={copied ? 'Copied' : 'Copy to clipboard'}
        className="absolute right-3 top-3 flex items-center gap-1 rounded bg-surface-2 px-2 py-1 text-xs text-text-tertiary transition-colors hover:text-text-primary"
      >
        {copied ? <Check size={12} /> : <Copy size={12} />}
        {copied ? 'Copied' : 'Copy'}
      </button>
      <pre className="overflow-auto rounded-lg border border-border bg-surface-1 p-4 font-mono text-xs leading-5 text-text-secondary">
        {/* key={i} is intentional: static rendered output with no stable ID per line */}
        {lines.map((line, i) => (
          <div key={i} className="hover:bg-surface-2/50">
            {highlightLine(line, i)}
          </div>
        ))}
      </pre>
    </div>
  );
}
