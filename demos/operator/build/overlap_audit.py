#!/usr/bin/env python3
"""Overlap/containment audit — geometry checked, never judged.

Collects the rectangle of every widget PART (labels, dials, values, boxes,
chips, dropdowns, LEDs, badges, grid cells) from the rendered DOM, then proves:
  1. No two parts intersect, except pairs that are legal BY RULE:
     - a knob's value may enter its OWN dial's box only in the dial's lower
       half (the ring is open at the bottom — that sector is the legal tuck);
     - a knob's label may sit flush above its own dial (no intersection).
  2. Sibling parts keep a >=2px gap (crowding floor; Live itself goes tight).
  3. Every part stays inside its plate / grid container (+-1.5px), except the
     display-grid labels, which may spill into their column gap by design.
Any violation fails the build and names both parts.
"""
import json
import pathlib
import re
import subprocess
import sys

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
BUILD = pathlib.Path(__file__).resolve().parent
PAGE = BUILD.parent / "operator.html"

SWEEP_JS = """
<script>
/* content sweep: every visible value at its widest string before measuring */
window.addEventListener('load', function () {
  var P = window.OpParams;
  [['osc.b.freq', 1000], ['osc.b.multi', 1000],
   ['osc.a.coarse', 48], ['osc.c.fine', 1000], ['osc.d.level', -12.3],
   ['osc.b.env.attack', 10000], ['osc.b.env.decay', 30000], ['osc.b.env.release', 30000],
   ['osc.b.env.timeVel', 100], ['osc.b.env.vel', -100], ['osc.b.env.key', 100],
   ['osc.b.env.peak', -12.3], ['osc.b.feedback', 100], ['osc.b.phase', 100],
   ['osc.b.oscVel', -48],
   ['lfo.rate', 100], ['lfo.amount', 100],
   ['filter.freq', 20000], ['filter.res', 125],
   ['pitch.env', -100], ['pitch.spread', 100], ['pitch.transpose', -48],
   ['global.time', -100], ['global.tone', 100], ['global.volume', -12.3]
  ].forEach(function (kv) { P.set(kv[0], kv[1]); });
});
</script>
"""

PROBE = """
<script>
(function () {
  function collect() {
    if (document.getElementById('overlap-audit')) return;
    var dev = document.querySelector('.device').getBoundingClientRect();
    var scale = dev.width / 1253;
    var out = { containers: [], parts: [] };
    var TEXT_KINDS = { label:1, value:1, checklabel:1, clabel:1, num:1 };
    var mctx = document.createElement('canvas').getContext('2d');
    function rawRect(el, kind) {
      if (TEXT_KINDS[kind]) {
        var rng = document.createRange();
        rng.selectNodeContents(el);
        var rr = rng.getBoundingClientRect();
        if (rr.width > 0) {
          /* glyph-exact box: x from the range, y from the actual ink extents
             of THIS string in THIS font (em boxes overlap; glyphs may not) */
          var cs = getComputedStyle(el);
          mctx.font = cs.fontStyle + ' ' + cs.fontWeight + ' ' + cs.fontSize + ' ' + cs.fontFamily;
          var mm = mctx.measureText(el.textContent);
          var baseline = rr.top + (mm.fontBoundingBoxAscent || rr.height * 0.8);
          var top = baseline - (mm.actualBoundingBoxAscent || rr.height * 0.7);
          var bot = baseline + (mm.actualBoundingBoxDescent || 0);
          return { left: rr.left, top: top, right: rr.right, bottom: bot,
                   width: rr.width, height: bot - top };
        }
      }
      var r = el.getBoundingClientRect();
      return { left: r.left, top: r.top, right: r.right, bottom: r.bottom,
               width: r.width, height: r.height };
    }
    function rect(el, kind) {
      var r = rawRect(el, kind);
      return [ (r.left - dev.left) / scale, (r.top - dev.top) / scale,
               (r.right - dev.left) / scale, (r.bottom - dev.top) / scale ];
    }
    var PART_SELS = [
      ['label', '.op-knob-label'], ['dial', '.op-knob-dial'], ['value', '.op-knob-value'],
      ['checkbox', '.op-check-box'], ['checklabel', '.op-check-label'],
      ['dd', '.op-dd'], ['chip', '.op-chip'], ['pairopt', '.op-pair-opt'],
      ['led', '.op-led'], ['badge', '.badge'], ['glyph', 'svg.p-pt-glyph'],
    ];
    var plates = document.querySelectorAll('.plate');
    for (var i = 0; i < plates.length; i++) {
      var plate = plates[i];
      var cid = 'plate:' + plate.dataset.section;
      out.containers.push({ id: cid, r: rect(plate) });
      for (var s = 0; s < PART_SELS.length; s++) {
        var found = plate.querySelectorAll(PART_SELS[s][1]);
        for (var f = 0; f < found.length; f++) {
          var el = found[f];
          var owner = el.closest('[data-addr]');
          var w = rawRect(el, PART_SELS[s][0]);
          if (w.width === 0 || w.height === 0) continue;
          out.parts.push({
            c: cid, kind: PART_SELS[s][0],
            owner: owner ? owner.getAttribute('data-addr') : (el.className.baseVal || el.className || ''),
            r: rect(el, PART_SELS[s][0])
          });
        }
      }
    }
    var dgrid = document.getElementById('dgrid');
    out.containers.push({ id: 'dgrid', r: rect(dgrid) });
    var GRID_SELS = [['clabel', '.clabel'], ['num', '.op-num'], ['dd', '.op-dd'],
                     ['chip', '.op-chip'], ['head', '.dhead'], ['thumb', 'canvas']];
    for (var g = 0; g < GRID_SELS.length; g++) {
      var els = dgrid.querySelectorAll(GRID_SELS[g][1]);
      for (var e = 0; e < els.length; e++) {
        var w2 = rawRect(els[e], GRID_SELS[g][0]);
        if (w2.width === 0 || w2.height === 0) continue;
        var own = els[e].closest('[data-addr]');
        var lbl = els[e].textContent ? els[e].textContent.slice(0, 12) : '';
        out.parts.push({ c: 'dgrid', kind: GRID_SELS[g][0],
          owner: own ? own.getAttribute('data-addr') : lbl, r: rect(els[e], GRID_SELS[g][0]) });
      }
    }
    var pre = document.createElement('pre');
    pre.id = 'overlap-audit';
    pre.textContent = JSON.stringify(out);
    document.body.appendChild(pre);
  }
  function go() {
    requestAnimationFrame(function () { requestAnimationFrame(collect); });
    setTimeout(collect, 1500);
  }
  if (document.readyState === 'complete') go();
  else window.addEventListener('load', go);
})();
</script>
"""


def die(msg):
    print(f"OVERLAP AUDIT FAILED: {msg}", file=sys.stderr)
    sys.exit(1)


def inter(a, b):
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    if x1 - x0 > 0.5 and y1 - y0 > 0.5:
        return (x0, y0, x1, y1)
    return None


def hgap(a, b):
    if a[3] <= b[1] or b[3] <= a[1]:
        return None                       # no vertical overlap: not neighbors
    return b[0] - a[2] if a[2] <= b[0] else a[0] - b[2]


def main(page=PAGE, sweep=False):
    if not pathlib.Path(CHROME).exists():
        die("Chrome not found — audit cannot run, so it fails")
    tmp = BUILD.parent / "_overlap_audit.html"
    tmp.write_text(pathlib.Path(page).read_text() + (SWEEP_JS if sweep else "") + PROBE)
    r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--mute-audio",
                        "--window-size=1600,900", "--virtual-time-budget=6000",
                        "--dump-dom", f"file://{tmp}"], capture_output=True, text=True)
    m = re.search(r'<pre id="overlap-audit">(.*?)</pre>', r.stdout, re.S)
    if not m:
        die(f"probe produced no output (rc={r.returncode})")
    import html
    d = json.loads(html.unescape(m.group(1)))
    tmp.unlink()

    parts = d["parts"]
    containers = {c["id"]: c["r"] for c in d["containers"]}
    fails, checked = [], 0

    # 1+2: pairwise, within each container
    bycont = {}
    for p in parts:
        bycont.setdefault(p["c"], []).append(p)
    for cid, plist in bycont.items():
        for i in range(len(plist)):
            for j in range(i + 1, len(plist)):
                a, b = plist[i], plist[j]
                checked += 1
                ix = inter(a["r"], b["r"])
                if not ix:
                    continue
                same = a["owner"] == b["owner"] and a["owner"]
                kinds = {a["kind"], b["kind"]}
                if same and kinds == {"value", "dial"}:
                    dial = a if a["kind"] == "dial" else b
                    cx = (dial["r"][0] + dial["r"][2]) / 2
                    if ix[3] - ix[1] <= 2.5 and ix[0] >= cx + 8:
                        continue          # a 2px graze at the ring's lower-right only
                    fails.append(f"{cid}: value of {a['owner']} sits ON its dial "
                                 f"(intersection {ix[2]-ix[0]:.1f}x{ix[3]-ix[1]:.1f} at x{ix[0]:.1f})")
                    continue
                if same and kinds == {"checkbox", "checklabel"}:
                    continue              # one composite widget
                fails.append(f"{cid}: {a['kind']}({a['owner']}) overlaps {b['kind']}({b['owner']}) "
                             f"by {(ix[2]-ix[0]):.1f}x{(ix[3]-ix[1]):.1f}px")
    # 2b: sibling horizontal gap floor (different owners, vertically adjacent)
    for cid, plist in bycont.items():
        for i in range(len(plist)):
            for j in range(i + 1, len(plist)):
                a, b = plist[i], plist[j]
                if a["owner"] == b["owner"]:
                    continue
                g = hgap(a["r"], b["r"])
                if g is not None and 0 <= g < 2.0:
                    fails.append(f"{cid}: gap {g:.1f}px < 2px between {a['kind']}({a['owner']}) "
                                 f"and {b['kind']}({b['owner']})")
    # 3a: breathing floor — text ink never presses against its container edge
    TEXTK = {"label", "value", "checklabel", "clabel", "num"}
    for p in parts:
        if p["kind"] not in TEXTK:
            continue
        c = containers[p["c"]]
        clear = c[3] - p["r"][3]
        if clear < 2.5:
            fails.append(f"{p['c']}: {p['kind']}({p['owner']}) ink presses the bottom edge "
                         f"(clearance {clear:.1f}px < 2.5)")

    # 3: containment
    for p in parts:
        c = containers[p["c"]]
        slack = 12.0 if (p["c"] == "dgrid" and p["kind"] == "clabel") else 1.5
        if (p["r"][0] < c[0] - slack or p["r"][1] < c[1] - 1.5 or
                p["r"][2] > c[2] + slack or p["r"][3] > c[3] + 1.5):
            fails.append(f"{p['c']}: {p['kind']}({p['owner']}) escapes its container "
                         f"({[round(v,1) for v in p['r']]} vs {[round(v,1) for v in c]})")

    # 4: the gap law (forbidden zone): control gaps in one plate line are
    #    equal (±3%, +1px rounding slack) or hierarchical (>=1.45x).
    # Similarity gates proximity: the law binds between ADJACENT SAME-KIND
    #    control units (dial<->dial, led<->led, dd<->dd ...), because the eye
    #    first fuses each control with its label/value into one object and only
    #    compares gaps between like objects (Gestalt similarity + proximity).
    RHYTHM = {"dial", "checkbox", "dd", "chip", "pairopt", "led"}
    for cid, plist in bycont.items():
        if not cid.startswith("plate:"):
            continue
        byline = {}
        for q in [q for q in plist if q["kind"] in RHYTHM]:
            byline.setdefault(q["kind"], []).append(q)
        allctrl = [q for q in plist if q["kind"] in RHYTHM]
        for kind, ctrls in byline.items():
            ctrls.sort(key=lambda q: q["r"][0])
            gaps = []
            for i in range(len(ctrls) - 1):
                a, b = ctrls[i], ctrls[i + 1]
                if a["r"][3] <= b["r"][1] or b["r"][3] <= a["r"][1]:
                    continue                  # different lines
                # a third control between them breaks the neighbourhood
                mid = [q for q in allctrl if q is not a and q is not b
                       and a["r"][2] < (q["r"][0] + q["r"][2]) / 2 < b["r"][0]
                       and not (q["r"][3] <= a["r"][1] or a["r"][3] <= q["r"][1])]
                if mid:
                    continue
                g = b["r"][0] - a["r"][2]
                if g > 0.5:
                    gaps.append((g, f"{a['owner']}->{b['owner']}"))
            for i in range(len(gaps)):
                for j in range(i + 1, len(gaps)):
                    g1, g2 = sorted([gaps[i][0], gaps[j][0]])
                    if g2 - g1 <= max(0.06 * g2, 1.0):
                        continue              # equal: one rhythm
                    if g2 / g1 >= 1.45:
                        continue              # hierarchical: two rhythms
                    fails.append(f"{cid}: sloppy {kind} gap pair {g1:.1f}px vs {g2:.1f}px "
                                 f"[{gaps[i][1]} | {gaps[j][1]}] — equal or >=1.45x required")

    # 5: alignment: dial centres level within a plate; columns level across osc rows
    for cid, plist in bycont.items():
        dials = [p for p in plist if p["kind"] == "dial"]
        if len(dials) > 1:
            cys = [(p["r"][1] + p["r"][3]) / 2 for p in dials]
            if max(cys) - min(cys) > 1.0:
                fails.append(f"{cid}: dial centres not level (spread {max(cys)-min(cys):.1f}px)")
    bykey = {}
    for p in parts:
        if p["c"].startswith("plate:osc") and p["kind"] in RHYTHM:
            leaf = p["owner"].split(".")[-1] if p["owner"] else p["kind"]
            bykey.setdefault((p["kind"], leaf), []).append((p["r"][0] + p["r"][2]) / 2)
    for (kind, leaf), xs in bykey.items():
        if len(xs) > 1 and max(xs) - min(xs) > 1.0:
            fails.append(f"osc rows: column {kind}.{leaf} not aligned across rows "
                         f"(spread {max(xs)-min(xs):.1f}px)")

    tag = "sweep" if sweep else "audit"
    print(f"overlap {tag}: {len(parts)} parts, {checked} pairs checked")
    if fails:
        die(f"[{tag}] {len(fails)} geometry violations:\n  " + "\n  ".join(fails))
    print(f"overlap {tag}: no illegal overlap, no crowding, no escape")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--sweep"]
    main(args[0] if args else PAGE, sweep="--sweep" in sys.argv)
