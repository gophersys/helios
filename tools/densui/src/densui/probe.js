/* densui probe — measures a rendered page's true geometry.
 * Called by densui.probe.collect(), which appends `densuiProbe(cfg)` after
 * this file. Standalone-valid JS so `node --check` can gate it.
 *
 * Text parts are measured as GLYPH INK: x-extent from a DOM Range, y-extent
 * from canvas measureText actual ascent/descent — em boxes overlap where
 * glyphs do not (LAYOUT-MATH A-4). Output: a pre element (id densui-probe).
 */
function densuiProbe(cfg) {
  'use strict';
  function collect() {
    if (document.getElementById('densui-probe')) return;
    var root = document.querySelector(cfg.root);
    if (!root) throw new Error('densui-probe: missing root ' + cfg.root);
    var rr = root.getBoundingClientRect();
    var scale = cfg.rootWidth ? rr.width / cfg.rootWidth : 1;
    var textKinds = {};
    (cfg.textKinds || []).forEach(function (k) { textKinds[k] = 1; });
    var mctx = document.createElement('canvas').getContext('2d');

    function rawRect(el, kind) {
      if (textKinds[kind]) {
        var rng = document.createRange();
        rng.selectNodeContents(el);
        var r = rng.getBoundingClientRect();
        if (r.width > 0) {
          var cs = getComputedStyle(el);
          mctx.font = cs.fontStyle + ' ' + cs.fontWeight + ' ' + cs.fontSize + ' ' + cs.fontFamily;
          var m = mctx.measureText(el.textContent);
          var baseline = r.top + (m.fontBoundingBoxAscent || r.height * 0.8);
          return { left: r.left, right: r.right,
                   top: baseline - (m.actualBoundingBoxAscent || r.height * 0.7),
                   bottom: baseline + (m.actualBoundingBoxDescent || 0) };
        }
      }
      var b = el.getBoundingClientRect();
      return { left: b.left, top: b.top, right: b.right, bottom: b.bottom };
    }
    function rect(el, kind) {
      var r = rawRect(el, kind);
      return [(r.left - rr.left) / scale, (r.top - rr.top) / scale,
              (r.right - rr.left) / scale, (r.bottom - rr.top) / scale];
    }

    var out = { scale: scale, containers: [], parts: [] };
    Object.keys(cfg.containers).forEach(function (cid) {
      var els = document.querySelectorAll(cfg.containers[cid]);
      for (var i = 0; i < els.length; i++) {
        var id = els.length > 1 ? cid + ':' + i : cid;
        out.containers.push({ id: id, r: rect(els[i], null) });
        Object.keys(cfg.parts).forEach(function (kind) {
          var found = els[i].querySelectorAll(cfg.parts[kind]);
          for (var f = 0; f < found.length; f++) {
            var el = found[f];
            var w = rawRect(el, kind);
            if (w.right - w.left <= 0 || w.bottom - w.top <= 0) continue;
            var owner = cfg.ownerAttr ? el.closest('[' + cfg.ownerAttr + ']') : null;
            out.parts.push({
              c: id, kind: kind,
              owner: owner ? owner.getAttribute(cfg.ownerAttr)
                           : (el.textContent || '').slice(0, 16),
              r: rect(el, kind)
            });
          }
        });
      }
    });
    var pre = document.createElement('pre');
    pre.id = 'densui-probe';
    pre.textContent = JSON.stringify(out);
    document.body.appendChild(pre);
  }
  function go() {
    requestAnimationFrame(function () { requestAnimationFrame(collect); });
    setTimeout(collect, 1500);
  }
  if (document.readyState === 'complete') go();
  else window.addEventListener('load', go);
}
