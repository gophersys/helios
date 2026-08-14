#!/usr/bin/env python3
"""Gate 2 ratio audit — executable, not asserted.

Renders the assembled page headlessly, measures the real boxes, and compares
them against the measured reference table (spec/ratios.md). Any row outside
tolerance fails the build. A missing Chrome fails the build (FAIL-NOT-SKIP).
"""
import json
import pathlib
import re
import sys

from densui.probe import ProbeError, dump_dom
BUILD = pathlib.Path(__file__).resolve().parent
PAGE = BUILD.parent / "operator.html"

PROBE = """
<script>
(function () {
  function collect() {
    if (document.getElementById('ratio-audit')) return;
    var q = function (s) {
      var el = document.querySelector(s);
      if (!el) throw new Error('ratio-audit: missing ' + s);
      return el;
    };
    var dev = q('.device').getBoundingClientRect();
    var scale = dev.width / 1253;
    var pr = q('#rackL .plate').getBoundingClientRect();
    var rel = function (el) {
      var r = el.getBoundingClientRect();
      return { cx: ((r.left + r.right) / 2 - pr.left) / scale,
               w: r.width / scale, h: r.height / scale };
    };
    var fs = function (s) { return parseFloat(getComputedStyle(q(s)).fontSize); };
    var cv = q('#dcanvas');
    var px = cv.getContext('2d').getImageData(5, 5, 1, 1).data;
    var out = {
      device_w: dev.width / scale, device_h: dev.height / scale,
      titlebar_h: q('.titlebar').getBoundingClientRect().height / scale,
      plate_h: pr.height / scale,
      knob: rel(q('#rackL .c-coarse .op-knob-dial')),
      centers: {
        coarse: rel(q('#rackL .c-coarse .op-knob-dial')).cx,
        fine: rel(q('#rackL .c-fine .op-knob-dial')).cx,
        fixed: rel(q('#rackL .c-fixed .op-check-box')).cx,
        level: rel(q('#rackL .c-level .op-knob-dial')).cx,
        badge: rel(q('#rackL .badge')).cx,
      },
      badge_w: rel(q('#rackL .badge')).w,
      label_fs: fs('.device .op-knob-label'),
      value_fs: fs('.device .op-knob-value'),
      num_fs: fs('.device .op-num'),
      display_bg: getComputedStyle(q('.display')).backgroundColor,
      canvas_ground: 'rgb(' + px[0] + ', ' + px[1] + ', ' + px[2] + ')',
      display_top: (q('.display').getBoundingClientRect().top - dev.top) / scale,
      dgrid_scrollH: q('#dgrid').scrollHeight, dgrid_clientH: q('#dgrid').clientHeight,
      graph_h: q('#dcanvas').clientHeight,
      page_scrollW: document.documentElement.scrollWidth, page_innerW: window.innerWidth,
    };
    var pre = document.createElement('pre');
    pre.id = 'ratio-audit';
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


def die(msg: str) -> None:
    print(f"RATIO AUDIT FAILED: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    tmp = BUILD.parent / "_ratio_audit.html"
    tmp.write_text(PAGE.read_text() + PROBE)
    # dump_dom is the ONE sanctioned chrome runner: file-captured (crashpad
    # orphans held pipe-captured output open forever — hung the fleet twice),
    # crashpad-disabled, and bounded by a named ProbeError timeout.
    try:
        rc, stdout, _ = dump_dom(tmp)
    except ProbeError as exc:
        die(f"{exc} — the audit cannot run, so the build fails (never skips)")
    m = re.search(r'<pre id="ratio-audit">(.*?)</pre>', stdout, re.S)
    if not m:
        die(f"probe produced no output (chrome rc={rc})")
    import html
    d = json.loads(html.unescape(m.group(1)))
    # A reported grid autoscale changes grid type sizes BY DESIGN; the
    # expectation follows the report (the page carries the comment).
    m_scale = re.search(r"/\* grid autoscale ([0-9.]+):", PAGE.read_text())
    grid_scale = float(m_scale.group(1)) if m_scale else 1.0

    failures = []
    def check(name, got, want, tol):
        if abs(got - want) > tol:
            failures.append(f"{name}: {got:.2f} vs {want} (tol ±{tol})")
        else:
            print(f"  PASS {name}: {got:.2f} (want {want})")

    check("device_w", d["device_w"], 1253, 5)
    check("device_h", d["device_h"], 333, 5)
    check("titlebar_h", d["titlebar_h"], 26, 2)
    check("plate_h", d["plate_h"], 67, 67 * 0.05)
    check("knob_diameter", d["knob"]["w"], 27, 1)
    for name, want in (("coarse", 25), ("fine", 125), ("fixed", 201),
                       ("level", 252), ("badge", 333)):
        check(f"center_{name}", d["centers"][name], want, max(5, want * 0.05))
    check("badge_w", d["badge_w"], 18, 1)
    check("label_fs", d["label_fs"], 16, 0.5)
    check("value_fs", d["value_fs"], 16, 0.5)
    check("num_fs", d["num_fs"], 16 * grid_scale, 0.5)
    check("text_knob_ratio", d["label_fs"] / d["knob"]["h"], 0.593, 0.06)
    check("display_top", d["display_top"], 14, 3)
    check("graph_h", d["graph_h"], 151, 3)
    if d["display_bg"] != "rgb(36, 36, 36)":
        failures.append(f"display_bg {d['display_bg']} != rgb(36, 36, 36)")
    if d["canvas_ground"] != "rgb(36, 36, 36)":
        failures.append(f"canvas_ground {d['canvas_ground']} != rgb(36, 36, 36)")
    if d["dgrid_scrollH"] > d["dgrid_clientH"]:
        failures.append(f"dgrid clips: scrollHeight {d['dgrid_scrollH']} > clientHeight {d['dgrid_clientH']}")
    else:
        print(f"  PASS dgrid_no_clip: {d['dgrid_scrollH']} <= {d['dgrid_clientH']}")
    if d["page_scrollW"] > d["page_innerW"]:
        failures.append(f"horizontal page scroll: {d['page_scrollW']} > {d['page_innerW']}")
    tmp.unlink()
    if failures:
        die("\n  " + "\n  ".join(failures))
    print("ratio audit: all rows PASS")


if __name__ == "__main__":
    main()
