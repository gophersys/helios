#!/usr/bin/env python3
# Render the OTA soak JSONL into a self-contained live dashboard.
import json, sys, os

SRC = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ota_soak.jsonl"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/tmp/soak_report.html"
TARGET = int(sys.argv[3]) if len(sys.argv) > 3 else 100

rows = []
for line in open(SRC) if os.path.exists(SRC) else []:
    line = line.strip()
    if not line:
        continue
    try:
        rows.append(json.loads(line))
    except Exception:
        pass

runs = [r for r in rows if "ota_s" in r]                       # completed OTA runs
n = len(runs)
ok = sum(1 for r in runs if r.get("swap_ok") is True)
csum_ok = sum(1 for r in runs if r.get("csum_ok") in (True, "true"))
retried = sum(1 for r in runs if r.get("ota_attempts", 1) > 1)
aborted = any(r.get("stage") == "disk_guard" for r in rows)
rate = [float(r.get("kib_s", 0) or 0) for r in runs]
ota = [float(r.get("ota_s", 0) or 0) for r in runs]
bld = [float(r.get("build_s", 0) or 0) for r in runs]
disk = [float(r.get("disk_pct", 0) or 0) for r in runs]
avg = lambda xs: (sum(xs) / len(xs)) if xs else 0
pct = (100.0 * ok / n) if n else 0
done = n >= TARGET or aborted
status = "COMPLETE" if n >= TARGET else ("ABORTED (disk guard)" if aborted else "RUNNING")

def spark(vals, w=760, h=90, color="#2fd8c6", fill=True):
    if not vals:
        return ""
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1
    n = len(vals)
    step = w / max(n - 1, 1)
    pts = [(i * step, h - 8 - (v - lo) / rng * (h - 20)) for i, v in enumerate(vals)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = ""
    if fill:
        area = f'<polygon points="0,{h} {line} {w},{h}" fill="{color}" opacity="0.10"/>'
    dots = f'<circle cx="{pts[-1][0]:.1f}" cy="{pts[-1][1]:.1f}" r="3" fill="{color}"/>'
    grid = "".join(f'<line x1="0" y1="{h*k/4:.0f}" x2="{w}" y2="{h*k/4:.0f}" stroke="#26333f" stroke-width="1"/>' for k in range(1,4))
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" preserveAspectRatio="none" style="display:block">'
            f'{grid}{area}<polyline points="{line}" fill="none" stroke="{color}" stroke-width="2"/>{dots}</svg>')

# swap-success strip: one cell per run
cells = ""
for r in runs:
    c = "#56d364" if r.get("swap_ok") is True else "#e5688a"
    rn = r.get("run")
    iv = r.get("imgver", "")
    cells += '<span class="cell" style="background:%s" title="run %s: %s"></span>' % (c, rn, iv)
for _ in range(max(0, TARGET - n)):
    cells += '<span class="cell pending"></span>'

statuscolor = {"COMPLETE": "#56d364", "RUNNING": "#2fd8c6"}.get(status, "#e3b341")
html = f"""<style>
:root {{ --bg:#0e1621; --panel:#18232f; --line:#26333f; --ink:#d7e2ee; --muted:#7b8da3; --faint:#4d5d70;
  --cyan:#2fd8c6; --pass:#56d364; --warn:#e3b341; --crit:#e5688a;
  --mono:ui-monospace,"SF Mono","JetBrains Mono",Menlo,monospace; --sans:system-ui,-apple-system,sans-serif; }}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);font-variant-numeric:tabular-nums}}
.wrap{{max-width:60rem;margin:0 auto;padding:2.2rem 1.5rem 4rem}}
.eyebrow{{font-family:var(--mono);font-size:.72rem;letter-spacing:.22em;text-transform:uppercase;color:var(--cyan)}}
h1{{font-family:var(--mono);font-size:clamp(1.5rem,4vw,2.1rem);margin:.4rem 0 .2rem;letter-spacing:-.01em}}
.sub{{color:var(--muted);font-size:.95rem;max-width:60ch}}
.live{{display:inline-flex;align-items:center;gap:.4rem;font-family:var(--mono);font-size:.75rem;color:{statuscolor};margin-top:.6rem}}
.dot{{width:8px;height:8px;border-radius:50%;background:{statuscolor}}}
{".dot{animation:pulse 1.4s infinite}" if status=="RUNNING" else ""}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.25}}}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1px;background:var(--line);border:1px solid var(--line);border-radius:10px;overflow:hidden;margin:1.6rem 0}}
.c{{background:var(--panel);padding:1rem 1.1rem}} .c .n{{font-family:var(--mono);font-size:1.7rem;font-weight:700;letter-spacing:-.02em}}
.c .k{{font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.09em;margin-top:.15rem}}
.n.pass{{color:var(--pass)}} .n.cyan{{color:var(--cyan)}} .n.warn{{color:var(--warn)}}
section{{margin-top:2rem}} h2{{font-family:var(--mono);font-size:.95rem;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;margin:0 0 .8rem;font-weight:600}}
.panel{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:1.2rem 1.3rem}}
.strip{{display:flex;flex-wrap:wrap;gap:3px}} .cell{{width:14px;height:14px;border-radius:3px}} .cell.pending{{background:#1e2b39;border:1px solid var(--line)}}
.meta{{font-family:var(--mono);font-size:.75rem;color:var(--faint);display:flex;justify-content:space-between;margin-top:.5rem}}
.legend{{font-family:var(--mono);font-size:.72rem;color:var(--muted);margin-top:.7rem;display:flex;gap:1.2rem}}
.sw{{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:.3rem;vertical-align:middle}}
footer{{margin-top:2.5rem;font-family:var(--mono);font-size:.72rem;color:var(--faint);border-top:1px solid var(--line);padding-top:1rem}}
</style>
<div class="wrap">
  <div class="eyebrow">Cipher OTA · endurance soak</div>
  <h1>100&times; OTA over cipher &mdash; MCUboot A/B</h1>
  <p class="sub">Each run builds a fresh firmware (bumped image version), streams it over the cipher protocol to a
  live STM32&nbsp;H743, and verifies via the MCUboot header that the node actually swapped and booted the new image.
  Real hardware, real flash wear, back to back.</p>
  <div class="live"><span class="dot"></span>{status} &mdash; {n}/{TARGET} runs</div>

  <div class="grid">
    <div class="c"><div class="n {'pass' if pct==100 else 'warn'}">{pct:.0f}%</div><div class="k">swap success</div></div>
    <div class="c"><div class="n {'pass' if ok==n and n else ''}">{ok}/{n}</div><div class="k">swaps verified</div></div>
    <div class="c"><div class="n {'pass' if csum_ok==n and n else ''}">{csum_ok}/{n}</div><div class="k">checksums ok</div></div>
    <div class="c"><div class="n cyan">{avg(rate):.1f}</div><div class="k">avg KiB/s</div></div>
    <div class="c"><div class="n">{avg(ota):.1f}s</div><div class="k">avg OTA time</div></div>
    <div class="c"><div class="n">{n*2}</div><div class="k">flash write-cycles</div></div>
  </div>

  <section>
    <h2>Per-run swap result</h2>
    <div class="panel">
      <div class="strip">{cells}</div>
      <div class="legend"><span><span class="sw" style="background:#56d364"></span>swap verified</span>
      <span><span class="sw" style="background:#e5688a"></span>failed</span>
      <span><span class="sw" style="background:#1e2b39;border:1px solid #26333f"></span>pending</span>
      {"<span>&nbsp;&middot;&nbsp;"+str(retried)+" run(s) needed an OTA retry</span>" if retried else ""}</div>
    </div>
  </section>

  <section>
    <h2>Throughput per run &mdash; KiB/s</h2>
    <div class="panel">{spark(rate)}<div class="meta"><span>run 1</span><span>avg {avg(rate):.1f} &middot; last {rate[-1] if rate else 0:.1f}</span><span>run {n}</span></div></div>
  </section>

  <section>
    <h2>OTA stream time per run &mdash; seconds</h2>
    <div class="panel">{spark(ota, color="#e3b341")}<div class="meta"><span>run 1</span><span>avg {avg(ota):.1f}s</span><span>run {n}</span></div></div>
  </section>

  <section>
    <h2>Fresh-build time per run &mdash; seconds</h2>
    <div class="panel">{spark(bld, color="#7b8da3", fill=False)}<div class="meta"><span>run 1</span><span>avg {avg(bld):.1f}s</span><span>run {n}</span></div></div>
  </section>

  <section>
    <h2>Devbox disk &mdash; % (guard aborts at 83)</h2>
    <div class="panel">{spark(disk, color="#56d364", fill=False)}<div class="meta"><span>run 1</span><span>max {max(disk) if disk else 0:.0f}%</span><span>run {n}</span></div></div>
  </section>

  <footer>cipher OTA soak &middot; nucleo_h743zi over Ethernet &middot; swap verified from the MCUboot image header, checksum via FNV-1a</footer>
</div>"""
open(OUT, "w").write(html)
print(f"rendered {n}/{TARGET} runs ({ok} ok) -> {OUT}")
