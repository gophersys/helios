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
  /* The string whose advance identifies a face, byte-identical to
   * densui.audit.FONT_SENTINEL (a test pins that): the expectation is computed
   * in Python from the TTF and the measurement is taken here from the canvas,
   * and a drift between the two copies compares different sentences and calls
   * the difference a substitution. */
  var SENTINEL = "ABCDEFGHIJKLMNOPQRSTUVWXYZ abcdefghijklmnopqrstuvwxyz 0123456789 AV To Wa";
  var GENERIC = ['serif', 'sans-serif', 'monospace', 'cursive', 'fantasy', 'system-ui',
                 'ui-serif', 'ui-sans-serif', 'ui-monospace', 'ui-rounded', 'math', 'emoji',
                 'fangsong'];
  /* Three bases, not one: a family whose advances happen to match the base it
   * is tested against would read as absent, and the next entry in the stack
   * would be reported as the rendered face. */
  var BASES = ['monospace', 'serif', 'sans-serif'];

  function collect() {
    if (document.getElementById('densui-probe')) return;
    var root = document.querySelector(cfg.root);
    if (!root) throw new Error('densui-probe: missing root ' + cfg.root);
    var rr = root.getBoundingClientRect();
    var scale = cfg.rootWidth ? rr.width / cfg.rootWidth : 1;
    var textKinds = {};
    (cfg.textKinds || []).forEach(function (k) { textKinds[k] = 1; });
    var mctx = document.createElement('canvas').getContext('2d');

    function fontSpec(cs) {
      return cs.fontStyle + ' ' + cs.fontWeight + ' ' + cs.fontSize + ' ' + cs.fontFamily;
    }
    /* Which face the browser DREW. getComputedStyle returns the declared list
     * verbatim — a stack headed by a family that exists on no machine reports
     * that family — and document.fonts.check() answers true for a nonsense
     * name, so neither API can carry this: each declared entry is tested by
     * MEASUREMENT, and the first one that moves a width off its base is the one
     * chrome resolved to. */
    function present(entry) {
      for (var i = 0; i < BASES.length; i++) {
        mctx.font = '72px ' + BASES[i];
        var bare = mctx.measureText(SENTINEL).width;
        mctx.font = '72px ' + entry + ', ' + BASES[i];
        if (mctx.measureText(SENTINEL).width !== bare) return true;
      }
      return false;
    }
    function resolvedFamily(cs) {
      /* the computed value is a correctly serialized CSS list, so an entry goes
       * back into the font shorthand as it stands, quotes and all */
      var list = cs.fontFamily.split(',');
      for (var i = 0; i < list.length; i++) {
        var entry = list[i].trim();
        var name = entry.replace(/^['"]|['"]$/g, '');
        if (GENERIC.indexOf(name) >= 0 || present(entry)) return name;
      }
      return '(default)';
    }

    function rawRect(el, kind) {
      if (textKinds[kind]) {
        var rng = document.createRange();
        rng.selectNodeContents(el);
        var r = rng.getBoundingClientRect();
        if (r.width > 0) {
          var cs = getComputedStyle(el);
          mctx.font = fontSpec(cs);
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

    /* root: the panel itself, which is neither a part nor a container — the
     * only thing panel_w/panel_h ratio rows can measure. Same convention as
     * containers[i].r, so x0/y0 are 0 and w/h are the design dimensions. */
    var out = { scale: scale, root: rect(root, null), containers: [], parts: [], fonts: {} };
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
    /* Font identity per text kind: the face drawn, and the sentinel advance the
     * reserved boxes were computed from. `fonts` is emitted whatever the
     * configuration says — a table that came and went with it would make "no
     * measurement" indistinguishable from "no text kinds". resolvedFamily()
     * leaves mctx on a probe font, so the measuring font is set AFTER it, and
     * kerning is off: Face.adv() sums glyph advances, and a kerned width is a
     * different quantity (3.55-5.05px on this sentinel). */
    (cfg.textKinds || []).forEach(function (kind) {
      var sel = cfg.parts[kind];
      var el = sel ? root.querySelector(sel) : null;
      if (!el) return;
      var cs = getComputedStyle(el);
      var family = resolvedFamily(cs);
      mctx.font = fontSpec(cs);
      mctx.fontKerning = 'none';
      out.fonts[kind] = { family: family, size_px: parseFloat(cs.fontSize),
                          advance_px: mctx.measureText(SENTINEL).width };
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
