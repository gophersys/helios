#!/usr/bin/env bash
# Stage: ai-review-architecture
# Gate:  INFORMATIONAL — weekly deep analysis.
#
# Analyzes codebase architecture for: circular dependencies, god objects,
# coupling hotspots, and dead code. Uses Nx project graph, git log
# forensics, and file metrics as inputs for Claude.
set -euo pipefail

source "$(dirname "$0")/../lib/log.sh"
source "$(dirname "$0")/../lib/context.sh"
source "$(dirname "$0")/../lib/ai-review.sh"

STAGE="architecture"

log_stage "ai-review-architecture — architecture drift detection"

if ! ai_review_available; then
  log_stage_end
  exit 0
fi

# ── Collect data inputs ────────────────────────────────────────

# 1. Nx project dependency graph (use unique temp file to avoid race conditions)
log_info "Collecting Nx project graph..."
NX_GRAPH_FILE=$(mktemp /tmp/nx-graph-XXXXXX.json)
NX_DEPS=$(npx nx graph --file="$NX_GRAPH_FILE" 2>/dev/null && \
  python3 -c "
import json
g = json.load(open('$NX_GRAPH_FILE'))
deps = g.get('graph', {}).get('dependencies', {})
lines = []
for src, targets in deps.items():
    for t in targets:
        lines.append(f'{src} -> {t.get(\"target\",\"?\")} ({t.get(\"type\",\"?\")})')
print('\n'.join(lines[:100]))
" 2>/dev/null || echo "(nx graph unavailable)")
rm -f "$NX_GRAPH_FILE"

# 2. File coupling — files that change together in last 90 days
log_info "Analyzing file coupling (90 days)..."
COUPLING=$(python3 << 'PYEOF'
import subprocess, collections

result = subprocess.run(
    ["git", "log", "--name-only", "--format=COMMIT", "--since=90 days ago"],
    capture_output=True, text=True, timeout=30
)

commits = []
current = []
for line in result.stdout.splitlines():
    if line == "COMMIT":
        if current:
            commits.append(current)
        current = []
    elif line.strip():
        current.append(line.strip())
if current:
    commits.append(current)

# Count file pairs
pair_counts = collections.Counter()
for files in commits:
    files = sorted(set(f for f in files if not f.startswith('.')))[:20]  # Cap per commit
    for i, a in enumerate(files):
        for b in files[i+1:]:
            pair_counts[(a, b)] += 1

# Top coupled pairs (changed together 3+ times)
top = [(a, b, c) for (a, b), c in pair_counts.most_common(20) if c >= 3]
for a, b, count in top:
    print(f"  {count}x: {a} <-> {b}")
if not top:
    print("  (no significant coupling detected)")
PYEOF
)

# 3. Largest files (god objects)
log_info "Finding largest files..."
GOD_OBJECTS=$(find apps/ libs/ -name "*.py" -o -name "*.ts" -o -name "*.svelte" 2>/dev/null | \
  xargs wc -l 2>/dev/null | sort -rn | head -15 | grep -v "total$" || echo "(unavailable)")

# ── Build prompt ───────────────────────────────────────────────
read -r -d '' PROMPT << 'PROMPT_HEREDOC' || true
You are performing a weekly architecture review of the Concord monorepo.

Analyze the data below for architectural health issues.

## What to Look For

1. **Circular dependencies** — projects that depend on each other (A->B->A)
2. **God objects** — files >500 lines that do too many things
3. **Coupling hotspots** — files that always change together (may need extraction)
4. **Missing abstractions** — when 3+ projects import the same utility pattern
5. **Dead code indicators** — projects with no dependents and no recent changes

## Response Format

Respond with ONLY valid JSON — no markdown fences, no prose:
{"verdict":"pass"|"fail","severity":"critical"|"high"|"medium"|"low"|"info","summary":"<one line>","findings":[{"file":"<project-or-file>","severity":"<level>","message":"<issue and recommendation>"}]}

critical = circular dependency between projects.
high = god object >1000 lines with 5+ responsibilities.
medium = coupling hotspot suggesting missing abstraction.
low = minor structural concern. info = healthy.
PROMPT_HEREDOC

PROMPT="${PROMPT}

## Nx Project Dependencies

${NX_DEPS}

## File Coupling (last 90 days — files that change together)

${COUPLING}

## Largest Files (potential god objects)

${GOD_OBJECTS}"

# ── Run, parse, report ────────────────────────────────────────
log_info "Running AI architecture review..."
RESULT=$(ai_review_run "$PROMPT" 5)

ai_review_parse "$RESULT"
ai_review_save_report "$STAGE" "$RESULT"
ai_review_log_result "$STAGE"

log_stage_end
exit 0
