interface ProgressRingProps {
  value: number;
  max: number;
  size?: number;
  strokeWidth?: number;
  color?: 'success' | 'warning' | 'error' | 'accent' | 'info';
  label?: string;
  sublabel?: string;
  /** Custom center text. Defaults to percentage. */
  centerText?: string;
}

// SVG stroke colors use Tailwind opacity modifiers (e.g. stroke-success/15) on semantic tokens
// because there are no dedicated stroke-muted design tokens for SVG elements.
const COLOR_MAP: Record<string, { stroke: string; trail: string; text: string }> = {
  success: { stroke: 'stroke-success', trail: 'stroke-success/15', text: 'text-success' },
  warning: { stroke: 'stroke-warning', trail: 'stroke-warning/15', text: 'text-warning' },
  error: { stroke: 'stroke-error', trail: 'stroke-error/15', text: 'text-error' },
  accent: { stroke: 'stroke-accent', trail: 'stroke-accent/15', text: 'text-accent' },
  info: { stroke: 'stroke-info', trail: 'stroke-info/15', text: 'text-info' },
};

function getAutoColor(value: number, max: number): 'success' | 'warning' | 'error' {
  if (max === 0) return 'success';
  const pct = value / max;
  if (pct >= 0.9) return 'error';
  if (pct >= 0.7) return 'warning';
  return 'success';
}

export function ProgressRing({
  value,
  max,
  size = 120,
  strokeWidth = 10,
  color,
  label,
  sublabel,
  centerText,
}: ProgressRingProps) {
  const resolvedColor = color || getAutoColor(value, max);
  const { stroke, trail, text } = COLOR_MAP[resolvedColor];

  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const pct = max > 0 ? Math.min(value / max, 1) : 0;
  const pctDisplay = Math.round(pct * 100);
  const offset = circumference * (1 - pct);

  const displayText = centerText ?? `${pctDisplay}%`;

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          {/* Trail */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            strokeWidth={strokeWidth}
            className={trail}
          />
          {/* Progress */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className={`${stroke} transition-all duration-700 ease-out`}
          />
        </svg>
        {/* Center text */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={`text-xl font-bold leading-tight ${text}`}>
            {displayText}
          </span>
        </div>
      </div>
      {label && (
        <span className="text-xs font-medium text-text-primary">{label}</span>
      )}
      {sublabel && (
        <span className="text-2xs text-text-tertiary">{sublabel}</span>
      )}
    </div>
  );
}
