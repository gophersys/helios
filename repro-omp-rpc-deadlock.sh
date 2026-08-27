#!/usr/bin/env bash
# Live repro for the omp rpc turn-boundary stall (libs task #24), with a
# two-direction frame tap.
#
#   OPENROUTER_API_KEY=$(bw get password "shared/eden/openrouter-api-key") bash repro-omp-rpc-deadlock.sh
#
# The key is read from the environment ONLY. It is never written to a file, never
# echoed, and the tap redacts any occurrence of it from the frame log before the
# log is written. NOT COMMITTED — a diagnostic scaffold.
#
# What it does:
#   1. installs the PINNED omp (eden harnesses/versions.env OMP_VERSION) into a
#      throwaway prefix; the host's own `omp` is never touched;
#   2. puts a shim named `omp` first on PATH that proxies stdin/stdout to the
#      pinned binary while writing BOTH directions, timestamped, to a log;
#   3. runs TestIntegration_LiveOmp_Gated exactly once against it;
#   4. prints the log path and the tail of the stream.
set -Eeuo pipefail

OMP_VERSION="${OMP_VERSION:-17.2.5}"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
out="${REPRO_OUT:-${TMPDIR:-/tmp}/omp-rpc-deadlock-$(date +%Y%m%dT%H%M%S)}"
mkdir -p "$out/bin" "$out/prefix"
log="$out/frames.log"

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
  echo "FAIL: OPENROUTER_API_KEY is not set. The live arm would SKIP, which proves nothing." >&2
  echo "  run: OPENROUTER_API_KEY=\$(bw get password \"shared/eden/openrouter-api-key\") bash $0" >&2
  exit 2
fi
for tool in npm node go; do
  command -v "$tool" >/dev/null || { echo "FAIL: required tool '$tool' is not installed." >&2; exit 127; }
done

echo "==> installing pinned omp@${OMP_VERSION} into $out/prefix (host omp untouched)"
npm install --prefix "$out/prefix" "@oh-my-pi/pi-coding-agent@${OMP_VERSION}" \
  --no-audit --no-fund --silent
real="$out/prefix/node_modules/.bin/omp"
[[ -x "$real" ]] || { echo "FAIL: pinned omp not executable at $real" >&2; exit 1; }
echo "==> pinned binary reports: $("$real" --version)"

# ---- the tap shim -----------------------------------------------------------
# Proxies argv/stdin/stdout/stderr to the pinned omp. Every NDJSON line in either
# direction is written to $OMP_TAP_LOG with a monotonic ms timestamp and the gap
# since the previous line, so a stall is visible as a large gap with no successor.
cat > "$out/bin/tap.mjs" <<'TAPEOF'
import { spawn } from "node:child_process";
import { appendFileSync } from "node:fs";
const real = process.env.OMP_TAP_REAL;
const log = process.env.OMP_TAP_LOG;
const secret = process.env.OPENROUTER_API_KEY || "";
const t0 = Date.now();
let last = t0;
const redact = (s) => (secret && s.includes(secret) ? s.split(secret).join("«REDACTED»") : s);
const rec = (dir, text) => {
  const now = Date.now();
  const line = `[${String(now - t0).padStart(8)}ms +${String(now - last).padStart(7)}ms] ${dir} ${redact(text)}\n`;
  last = now;
  try { appendFileSync(log, line); } catch {}
};
const args = process.argv.slice(2);
rec("SPAWN", `omp ${args.join(" ")}`);
const child = spawn(real, args, { stdio: ["pipe", "pipe", "inherit"] });
let inBuf = "", outBuf = "";
process.stdin.on("data", (d) => {
  inBuf += d.toString();
  let i; while ((i = inBuf.indexOf("\n")) >= 0) { const l = inBuf.slice(0, i); inBuf = inBuf.slice(i + 1); if (l.trim()) rec("HOST->OMP", l); }
  child.stdin.write(d);
});
process.stdin.on("end", () => { rec("HOST->OMP", "<stdin EOF>"); child.stdin.end(); });
child.stdout.on("data", (d) => {
  outBuf += d.toString();
  let i; while ((i = outBuf.indexOf("\n")) >= 0) { const l = outBuf.slice(0, i); outBuf = outBuf.slice(i + 1); if (l.trim()) rec("OMP->HOST", l); }
  process.stdout.write(d);
});
child.on("exit", (c, s) => { rec("EXIT", `code=${c} signal=${s}`); process.exit(c ?? 0); });
TAPEOF

cat > "$out/bin/omp" <<EOF
#!/usr/bin/env bash
exec node "$out/bin/tap.mjs" "\$@"
EOF
chmod +x "$out/bin/omp"

export OMP_TAP_REAL="$real"
export OMP_TAP_LOG="$log"
export PATH="$out/bin:$PATH"
: > "$log"

echo "==> PATH omp is now: $(command -v omp)  ($(omp --version))"
echo "==> frame log: $log"
echo "==> running TestIntegration_LiveOmp_Gated once (bounded by the test's own 8m idle / 10m total)"

set +e
( cd "$here/go/agentsession" && go test -tags integration -count=1 -timeout 20m \
    -run 'TestIntegration_LiveOmp_Gated' -v ./ompadapter/... )
rc=$?
set -e

echo
echo "==================== RESULT ===================="
echo "go test exit: $rc"
echo "frames captured: $(wc -l < "$log" | tr -d ' ')"
echo "frame log: $log"
echo
echo "---- last 15 frames (the stall is the final line + its gap) ----"
tail -15 "$log" | cut -c1-220
echo
echo "---- largest inter-frame gaps ----"
grep -o '+ *[0-9]*ms' "$log" | tr -d '+ms ' | sort -rn | head -5 | sed 's/^/  /'
echo "==============================================="
exit "$rc"
