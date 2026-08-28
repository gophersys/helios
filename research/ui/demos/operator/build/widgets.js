/* ============================================================================
 * widgets.js — window.OpWidgets
 * Ableton Live 12 "Operator" replica: the control vocabulary.
 *
 * Every widget renders ONLY from window.OpParams (via subscribe) and mutates
 * ONLY through OpParams.set. No local value state beyond in-flight drag deltas.
 *
 * Gestures (census §1, layers L5):
 *   vertical drag  = change value (200 px = full range through the taper)
 *   shift + drag   = fine (x0.1)
 *   double-click   = reset to default
 *   wheel          = one step (int +-1, float 1/100 of range, enum next)
 *
 * Plain browser JS. One IIFE. No modules, no frameworks, no external resources.
 * ==========================================================================*/
(function (global) {
  'use strict';

  var VERSION = '1.0.0';

  /* ---- constants ------------------------------------------------------- */
  var DRAG_PX = 200;            /* px of vertical travel for a full sweep    */
  var FINE = 0.1;               /* shift multiplier                          */
  var DB_FLOOR = -70;           /* contract §2: any dB <= -70 is -inf        */
  var METER_SEGMENTS = 24;
  var METER_PEAK_DECAY = 0.985; /* per update() call — no wall-clock reads   */
  var KNOB_SIZE = 34;           /* census: ~34 px dials                      */
  var ANGLE_MIN = -135;         /* deg from 12 o'clock, clockwise: lower-left */
  var ANGLE_MAX = 135;          /* lower-right — 270 deg sweep               */
  var INT_KINDS = { int: true, st: true, pct: true };
  var SVG_NS = 'http://www.w3.org/2000/svg';

  var LED_COLORS = {
    yellow: 'var(--op-led-yellow, #e0d048)',
    green: 'var(--op-green, #79c860)',
    orange: 'var(--op-led-orange, #e08030)',
    red: 'var(--op-led-red, #d84848)',
    amber: 'var(--op-amber, #f7a827)',
    blue: 'var(--op-blue, #58a6dd)'
  };

  /* ---- parameter-tree access (fail loud) ------------------------------- */

  function P() {
    var p = global.OpParams;
    if (!p) {
      throw new Error('OpWidgets: window.OpParams is not loaded; widgets cannot render.');
    }
    return p;
  }

  function descOf(addr) {
    if (typeof addr !== 'string' || addr === '') {
      throw new Error('OpWidgets: bad parameter address ' + JSON.stringify(addr));
    }
    var d = P().desc(addr); /* OpParams throws on an unknown address */
    if (!d) {
      throw new Error('OpWidgets: OpParams.desc("' + addr + '") returned nothing.');
    }
    console.assert(typeof d.fmt === 'function',
      'OpWidgets: descriptor for "' + addr + '" has no fmt()');
    return d;
  }

  function valueOf(addr) { return P().get(addr); }

  function textOf(addr) {
    var s = P().fmt(addr);
    console.assert(typeof s === 'string',
      'OpWidgets: OpParams.fmt("' + addr + '") must return a string');
    return typeof s === 'string' ? s : String(valueOf(addr));
  }

  /* ---- numeric model --------------------------------------------------- */

  function clamp(v, lo, hi) { return v < lo ? lo : (v > hi ? hi : v); }
  function clamp01(t) { return t < 0 ? 0 : (t > 1 ? 1 : t); }

  /* A dB parameter may declare min as -Infinity; -70 is the audible floor. */
  function effMin(d) {
    if (typeof d.min !== 'number' || !isFinite(d.min)) return DB_FLOOR;
    return d.min;
  }
  function effMax(d) {
    console.assert(typeof d.max === 'number' && isFinite(d.max),
      'OpWidgets: "' + d.addr + '" needs a finite max');
    return (typeof d.max === 'number' && isFinite(d.max)) ? d.max : 1;
  }
  function isLog(d) {
    return d.taper === 'log' && effMin(d) > 0 && effMax(d) > 0;
  }
  /* Bipolar knobs (transpose, env vel, global time) sweep out from centre,
     the way Live draws them; unipolar ones sweep from the minimum. */
  function isBipolar(d) {
    return d.kind !== 'db' && isFinite(d.min) && d.min < 0 && effMax(d) > 0;
  }

  function toNorm(d, v) {
    var mn = effMin(d), mx = effMax(d);
    if (typeof v !== 'number' || isNaN(v)) v = mn;
    v = clamp(v, mn, mx);
    if (mx === mn) return 0;
    if (isLog(d)) {
      return (Math.log(v) - Math.log(mn)) / (Math.log(mx) - Math.log(mn));
    }
    return (v - mn) / (mx - mn);
  }

  function fromNorm(d, t) {
    var mn = effMin(d), mx = effMax(d);
    t = clamp01(t);
    if (isLog(d)) {
      return Math.exp(Math.log(mn) + t * (Math.log(mx) - Math.log(mn)));
    }
    return mn + t * (mx - mn);
  }

  function quantize(d, v) {
    if (INT_KINDS[d.kind]) return Math.round(v);
    return v;
  }

  /* -inf floor: hand OpParams a real -Infinity when the descriptor says the
     bottom of the range is -inf, so fmt() prints "-inf dB". */
  function landing(d, v) {
    var mn = effMin(d);
    v = clamp(quantize(d, v), mn, effMax(d));
    if (v <= mn && typeof d.min === 'number' && !isFinite(d.min)) return -Infinity;
    return v;
  }

  function stepped(d, cur, dir) {
    if (Array.isArray(d.enum) && d.enum.length) {
      var info = enumInfo(d, cur);
      var i = clamp(info.index + dir, 0, d.enum.length - 1);
      return info.usesIndex ? i : d.enum[i];
    }
    if (INT_KINDS[d.kind]) {
      var base = isFinite(cur) ? cur : effMin(d);
      return landing(d, base + dir);
    }
    return landing(d, fromNorm(d, toNorm(d, cur) + dir * 0.01));
  }

  /* Enum values may be stored as members ("Sine", 24) or as indices.
     Detect which, once, from the live value — never guess silently. */
  function enumInfo(d, cur) {
    var e = d.enum;
    if (!Array.isArray(e) || !e.length) {
      throw new Error('OpWidgets: "' + d.addr + '" is not an enum parameter.');
    }
    var i = e.indexOf(cur);
    if (i >= 0) return { index: i, usesIndex: false };
    for (var k = 0; k < e.length; k++) {
      if (String(e[k]) === String(cur)) return { index: k, usesIndex: false };
    }
    if (typeof cur === 'number' && isFinite(cur) && Math.floor(cur) === cur &&
        cur >= 0 && cur < e.length) {
      return { index: cur, usesIndex: true };
    }
    throw new Error('OpWidgets: value ' + JSON.stringify(cur) +
      ' is not a member of the enum for "' + d.addr + '".');
  }

  function enumValueAt(d, i, usesIndex) { return usesIndex ? i : d.enum[i]; }

  function enumLabelAt(d, i, usesIndex) {
    var raw = enumValueAt(d, i, usesIndex);
    if (typeof d.fmt === 'function') {
      var s = d.fmt(raw);
      if (typeof s === 'string' && s.length) return s;
    }
    return String(d.enum[i]);
  }

  /* ---- DOM helpers ------------------------------------------------------ */

  function el(tag, cls, txt) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (txt !== undefined && txt !== null) n.textContent = String(txt);
    return n;
  }

  function svg(tag, attrs) {
    var n = document.createElementNS(SVG_NS, tag);
    if (attrs) {
      for (var k in attrs) {
        if (Object.prototype.hasOwnProperty.call(attrs, k)) {
          n.setAttribute(k, String(attrs[k]));
        }
      }
    }
    return n;
  }

  /* Every widget keeps its unsubscribers so a container can be torn down. */
  function makeRoot(tag, cls) {
    var root = el(tag, cls);
    root._opUnsub = [];
    root.opDestroy = function () {
      for (var i = 0; i < root._opUnsub.length; i++) root._opUnsub[i]();
      root._opUnsub.length = 0;
    };
    return root;
  }

  function track(root, addr, fn) {
    var un = P().subscribe(addr, fn);
    console.assert(typeof un === 'function',
      'OpWidgets: OpParams.subscribe("' + addr + '") must return an unsubscribe fn');
    if (typeof un === 'function') root._opUnsub.push(un);
  }

  function r3(n) { return Math.round(n * 1000) / 1000; }

  function polar(cx, cy, r, deg) {
    var rad = deg * Math.PI / 180;              /* 0 deg = 12 o'clock, CW+ */
    return { x: cx + r * Math.sin(rad), y: cy - r * Math.cos(rad) };
  }

  function arcPath(cx, cy, r, a0, a1) {
    if (Math.abs(a1 - a0) < 0.15) return '';
    var large = Math.abs(a1 - a0) > 180 ? 1 : 0;
    var sweep = a1 > a0 ? 1 : 0;
    var p0 = polar(cx, cy, r, a0), p1 = polar(cx, cy, r, a1);
    return 'M' + r3(p0.x) + ' ' + r3(p0.y) +
      'A' + r + ' ' + r + ' 0 ' + large + ' ' + sweep + ' ' + r3(p1.x) + ' ' + r3(p1.y);
  }

  /* ---- the shared drag / wheel / reset behaviour ----------------------- */

  function bindValueGestures(node, getAddr) {
    node.addEventListener('pointerdown', function (e) {
      if (e.button !== 0) return;
      var addr = getAddr();
      var d = descOf(addr);
      var startVal = valueOf(addr);
      var startBase = isFinite(startVal) ? startVal : effMin(d);
      var startNorm = toNorm(d, startVal);
      var lastY = e.clientY;
      var acc = 0; /* accumulated *effective* pixels; shift scales each delta */

      node.setPointerCapture(e.pointerId);
      node.classList.add('is-dragging');
      e.preventDefault();

      function move(ev) {
        var dy = lastY - ev.clientY;           /* up = increase */
        lastY = ev.clientY;
        acc += dy * (ev.shiftKey ? FINE : 1);
        var v;
        if (isLog(d)) {
          v = fromNorm(d, startNorm + acc / DRAG_PX);
        } else {
          /* Contract §2 lets a descriptor state its own value-per-200 px;
             absent that, 200 px is the full range. */
          var span = (typeof d.dragScale === 'number' && isFinite(d.dragScale) && d.dragScale > 0)
            ? d.dragScale
            : (effMax(d) - effMin(d));
          v = startBase + (acc / DRAG_PX) * span;
        }
        P().set(addr, landing(d, v));
      }
      function up(ev) {
        node.removeEventListener('pointermove', move);
        node.removeEventListener('pointerup', up);
        node.removeEventListener('pointercancel', up);
        node.classList.remove('is-dragging');
        if (node.hasPointerCapture && node.hasPointerCapture(ev.pointerId)) {
          node.releasePointerCapture(ev.pointerId);
        }
      }
      node.addEventListener('pointermove', move);
      node.addEventListener('pointerup', up);
      node.addEventListener('pointercancel', up);
    });

    node.addEventListener('dblclick', function (e) {
      e.preventDefault();
      P().reset(getAddr());
    });

    node.addEventListener('wheel', function (e) {
      e.preventDefault();
      var addr = getAddr();
      var d = descOf(addr);
      var dir = e.deltaY < 0 ? 1 : -1;
      P().set(addr, stepped(d, valueOf(addr), dir));
    }, { passive: false });
  }

  /* ======================================================================
   * knob(opts) — {addr, modeSwap?:{when, addr}, label?, size?}
   * ==================================================================== */

  function knob(opts) {
    opts = opts || {};
    var baseAddr = opts.addr;
    var swap = opts.modeSwap || null;
    if (swap) {
      console.assert(typeof swap.when === 'string' && typeof swap.addr === 'string',
        'OpWidgets.knob: modeSwap needs {when, addr}');
      descOf(swap.when);
      descOf(swap.addr);
    }
    var d0 = descOf(baseAddr);
    if (Array.isArray(d0.enum) && d0.enum.length) {
      throw new Error('OpWidgets.knob: "' + baseAddr +
        '" is an enum; use dropdown() or pairToggle().');
    }

    function swapped() { return !!(swap && valueOf(swap.when)); }
    function addr() { return swapped() ? swap.addr : baseAddr; }

    var size = typeof opts.size === 'number' ? opts.size : KNOB_SIZE;
    var c = size / 2;
    var rArc = size * 0.44;
    var rBody = size * 0.30;

    var root = makeRoot('div', 'op-knob');
    root.setAttribute('data-addr', baseAddr);

    var labelEl = el('div', 'op-knob-label');
    var dial = svg('svg', {
      'class': 'op-knob-dial', width: size, height: size,
      viewBox: '0 0 ' + size + ' ' + size, 'aria-hidden': 'true'
    });
    var track0 = svg('path', {
      'class': 'op-knob-track',
      d: arcPath(c, c, rArc, ANGLE_MIN, ANGLE_MAX),
      fill: 'none', 'stroke-linecap': 'round'
    });
    var arc = svg('path', { 'class': 'op-knob-arc', fill: 'none', 'stroke-linecap': 'butt' });
    var body = svg('circle', { 'class': 'op-knob-body', cx: c, cy: c, r: r3(rBody) });
    var needle = svg('line', { 'class': 'op-knob-needle', 'stroke-linecap': 'round' });
    var zero = svg('path', { 'class': 'op-knob-zero' });
    dial.appendChild(track0);
    dial.appendChild(arc);
    dial.appendChild(body);
    dial.appendChild(needle);
    dial.appendChild(zero);

    var valueEl = el('div', 'op-knob-value');

    root.appendChild(labelEl);
    root.appendChild(dial);
    root.appendChild(valueEl);

    function render() {
      var a = addr();
      var d = descOf(a);
      var t = toNorm(d, valueOf(a));
      var ang = ANGLE_MIN + t * (ANGLE_MAX - ANGLE_MIN);
      var t0 = isBipolar(d) ? toNorm(d, 0) : 0;
      var ang0 = ANGLE_MIN + t0 * (ANGLE_MAX - ANGLE_MIN);

      labelEl.textContent = opts.label || d.label || a;
      valueEl.textContent = textOf(a);
      arc.setAttribute('d', arcPath(c, c, rArc, ang0, ang));

      /* Live's needle runs from near-center to the ring (measured at 8x) */
      var inner = polar(c, c, rArc * 0.08, ang);
      var outer = polar(c, c, rArc * 0.92, ang);
      needle.setAttribute('x1', r3(inner.x));
      needle.setAttribute('y1', r3(inner.y));
      needle.setAttribute('x2', r3(outer.x));
      needle.setAttribute('y2', r3(outer.y));

      /* bipolar knobs carry a small wedge marker at the zero position */
      if (isBipolar(d)) {
        var tip = polar(c, c, rArc * 1.05, ang0);
        var b1 = polar(c, c, rArc * 1.55, ang0 - 11);
        var b2 = polar(c, c, rArc * 1.55, ang0 + 11);
        zero.setAttribute('d', 'M' + r3(tip.x) + ' ' + r3(tip.y) +
          ' L' + r3(b1.x) + ' ' + r3(b1.y) + ' L' + r3(b2.x) + ' ' + r3(b2.y) + ' Z');
      } else {
        zero.setAttribute('d', '');
      }

      root.classList.toggle('op-knob--swapped', swapped());
      root.setAttribute('title', (opts.label || d.label || a) + ': ' + valueEl.textContent);
      root.setAttribute('data-active-addr', a);
    }

    bindValueGestures(root, addr);
    track(root, baseAddr, render);
    if (swap) {
      track(root, swap.addr, render);
      track(root, swap.when, render);   /* mode flip relabels + rebinds */
    }
    render();
    return root;
  }

  /* ======================================================================
   * numberDrag({addr}) — the dark-display value text (label is the caller's)
   * ==================================================================== */

  function numberDrag(opts) {
    opts = opts || {};
    var addr = opts.addr;
    var d = descOf(addr);
    if (Array.isArray(d.enum) && d.enum.length) {
      throw new Error('OpWidgets.numberDrag: "' + addr + '" is an enum; use dropdown().');
    }
    if (d.kind === 'bool') {
      throw new Error('OpWidgets.numberDrag: "' + addr + '" is a bool; use checkbox() or chip().');
    }

    var root = makeRoot('div', 'op-num');
    if (opts.accent === 'amber') root.classList.add('op-num--amber');
    root.setAttribute('data-addr', addr);
    root.setAttribute('role', 'slider');
    root.setAttribute('tabindex', '0');

    function render() {
      root.textContent = textOf(addr);
      root.setAttribute('aria-label', (d.label || addr) + ' ' + root.textContent);
    }

    bindValueGestures(root, function () { return addr; });
    root.addEventListener('keydown', function (e) {
      var dir = e.key === 'ArrowUp' ? 1 : (e.key === 'ArrowDown' ? -1 : 0);
      if (!dir) return;
      e.preventDefault();
      P().set(addr, stepped(d, valueOf(addr), dir));
    });

    track(root, addr, render);
    render();
    return root;
  }

  /* ======================================================================
   * checkbox({addr, label})
   * ==================================================================== */

  function checkbox(opts) {
    opts = opts || {};
    var addr = opts.addr;
    var d = descOf(addr);

    var root = makeRoot('div', 'op-check');
    root.setAttribute('data-addr', addr);
    root.setAttribute('role', 'checkbox');
    root.setAttribute('tabindex', '0');

    var box = el('span', 'op-check-box');
    root.appendChild(box);

    var text = opts.label !== undefined ? opts.label : (d.label || '');
    if (text !== '' && text !== null) root.appendChild(el('span', 'op-check-label', text));

    function toggle() { P().set(addr, !valueOf(addr)); }

    function render() {
      var on = !!valueOf(addr);
      root.classList.toggle('is-on', on);
      root.setAttribute('aria-checked', on ? 'true' : 'false');
    }

    root.addEventListener('click', function (e) { e.preventDefault(); toggle(); });
    root.addEventListener('keydown', function (e) {
      if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); toggle(); }
    });

    track(root, addr, render);
    render();
    return root;
  }

  /* ======================================================================
   * dropdown({addr, compact, icon}) — flat field + caret, dark popup menu
   * ==================================================================== */

  var openMenu = null; /* only one menu at a time */

  function closeMenu() {
    if (!openMenu) return;
    if (openMenu.node.parentNode) openMenu.node.parentNode.removeChild(openMenu.node);
    document.removeEventListener('pointerdown', openMenu.onDocDown, true);
    document.removeEventListener('keydown', openMenu.onKey, true);
    window.removeEventListener('resize', closeMenu, true);
    window.removeEventListener('scroll', closeMenu, true);
    openMenu.anchor.classList.remove('is-open');
    openMenu = null;
  }

  function spawnMenu(anchor, items, activeIndex, onPick) {
    closeMenu();
    var node = el('div', 'op-menu');
    node.setAttribute('role', 'listbox');
    var hover = activeIndex;
    var rows = [];

    function paint() {
      for (var i = 0; i < rows.length; i++) {
        rows[i].classList.toggle('is-active', i === activeIndex);
        rows[i].classList.toggle('is-hover', i === hover);
      }
    }

    items.forEach(function (label, i) {
      var row = el('div', 'op-menu-item', label);
      row.setAttribute('role', 'option');
      row.addEventListener('pointerenter', function () { hover = i; paint(); });
      row.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        closeMenu();
        onPick(i);
      });
      rows.push(row);
      node.appendChild(row);
    });
    paint();

    document.body.appendChild(node);
    var r = anchor.getBoundingClientRect();
    var mh = node.offsetHeight;
    var top = r.bottom + 2;
    if (top + mh > window.innerHeight - 4) top = Math.max(4, r.top - mh - 2);
    var left = Math.min(r.left, Math.max(4, window.innerWidth - node.offsetWidth - 4));
    node.style.left = Math.round(left) + 'px';
    node.style.top = Math.round(top) + 'px';
    node.style.minWidth = Math.round(r.width) + 'px';
    anchor.classList.add('is-open');

    function onDocDown(e) {
      if (node.contains(e.target) || anchor.contains(e.target)) return;
      closeMenu();
    }
    function onKey(e) {
      if (e.key === 'Escape') { e.preventDefault(); closeMenu(); return; }
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        hover = clamp(hover + (e.key === 'ArrowDown' ? 1 : -1), 0, rows.length - 1);
        paint();
        return;
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        var pick = hover;
        closeMenu();
        onPick(pick);
      }
    }
    openMenu = { node: node, anchor: anchor, onDocDown: onDocDown, onKey: onKey };
    document.addEventListener('pointerdown', onDocDown, true);
    document.addEventListener('keydown', onKey, true);
    window.addEventListener('resize', closeMenu, true);
    window.addEventListener('scroll', closeMenu, true);
  }

  function dropdown(opts) {
    opts = opts || {};
    var addr = opts.addr;
    var d = descOf(addr);
    enumInfo(d, valueOf(addr)); /* fail loud now, not on first click */

    var root = makeRoot('div', 'op-dd');
    if (opts.compact) root.classList.add('op-dd--compact');
    root.setAttribute('data-addr', addr);
    root.setAttribute('role', 'button');
    root.setAttribute('tabindex', '0');

    var iconEl = null;
    if (opts.icon === 'wave' || opts.icon === 'filter') {
      iconEl = svg('svg', {
        'class': 'op-dd-icon', width: 22, height: 12, viewBox: '0 0 22 12', 'aria-hidden': 'true'
      });
      var poly = svg('polyline', { fill: 'none', 'stroke-linejoin': 'round', 'stroke-linecap': 'round' });
      iconEl.appendChild(poly);
      iconEl._poly = poly;
    }

    var textEl = el('span', 'op-dd-text');
    var caret = svg('svg', {
      'class': 'op-dd-caret', width: 7, height: 4, viewBox: '0 0 7 4', 'aria-hidden': 'true'
    });
    caret.appendChild(svg('path', { d: 'M0 0 H7 L3.5 4 Z' }));

    if (opts.iconOnly && iconEl) {
      root.classList.add('op-dd--icon');
      root.appendChild(iconEl);
    } else {
      root.appendChild(textEl);
      if (iconEl) root.appendChild(iconEl);
    }
    root.appendChild(caret);

    function render() {
      var cur = valueOf(addr);
      var info = enumInfo(d, cur);
      textEl.textContent = textOf(addr);
      root.setAttribute('title', (d.label || addr) + ': ' + textEl.textContent);
      if (iconEl) {
        var name = String(d.enum[info.index]);
        var pts = opts.icon === 'filter' ? filterPoints(name) : wavePoints(name);
        iconEl._poly.setAttribute('points', pts);
      }
    }

    function open() {
      var info = enumInfo(d, valueOf(addr));
      var labels = [];
      for (var i = 0; i < d.enum.length; i++) labels.push(enumLabelAt(d, i, info.usesIndex));
      spawnMenu(root, labels, info.index, function (i) {
        P().set(addr, enumValueAt(d, i, info.usesIndex));
      });
    }

    root.addEventListener('click', function (e) {
      e.preventDefault();
      if (openMenu && openMenu.anchor === root) { closeMenu(); return; }
      open();
    });
    root.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); }
    });
    root.addEventListener('wheel', function (e) {
      e.preventDefault();
      P().set(addr, stepped(d, valueOf(addr), e.deltaY < 0 ? 1 : -1));
    }, { passive: false });

    track(root, addr, render);
    render();
    return root;
  }

  /* Deterministic little glyphs — decoration only, never a value source. */
  function samplePoints(fn) {
    var n = 33, out = [];
    for (var i = 0; i < n; i++) {
      var x = i / (n - 1);
      var y = clamp(fn(x), -1, 1);
      out.push(r3(x * 21 + 0.5) + ',' + r3(6 - y * 5));
    }
    return out.join(' ');
  }

  function wavePoints(name) {
    var s = String(name).toLowerCase();
    var m = s.match(/(\d+)/);
    var harm = m ? parseInt(m[1], 10) : 1;
    if (s.indexOf('noise') === 0 || s.indexOf('noise') > -1) {
      var seed = 1337;
      return samplePoints(function () {
        seed = (seed * 1103515245 + 12345) & 0x7fffffff;   /* fixed LCG: stable */
        return (seed / 0x7fffffff) * 2 - 1;
      });
    }
    if (s.indexOf('saw') > -1) return samplePoints(function (x) { return 1 - 2 * ((x * 2) % 1); });
    if (s.indexOf('squ') > -1) return samplePoints(function (x) { return Math.sin(2 * Math.PI * x * 2) >= 0 ? 1 : -1; });
    if (s.indexOf('tri') > -1) return samplePoints(function (x) { return 1 - 4 * Math.abs(((x * 2) % 1) - 0.5); });
    if (s.indexOf('sin') > -1) return samplePoints(function (x) { return Math.sin(2 * Math.PI * x * harm); });
    console.assert(false, 'OpWidgets: no wave glyph for "' + name + '"');
    return samplePoints(function () { return 0; });
  }

  function filterPoints(name) {
    var s = String(name).toLowerCase();
    if (s.indexOf('hp') > -1 || s.indexOf('high') > -1) {
      return samplePoints(function (x) { return x < 0.35 ? -1 + x * 4.6 : (x < 0.5 ? 0.9 : 0.6); });
    }
    if (s.indexOf('bp') > -1 || s.indexOf('band') > -1) {
      return samplePoints(function (x) { return -1 + 2 * Math.exp(-Math.pow((x - 0.5) / 0.16, 2)); });
    }
    if (s.indexOf('notch') > -1 || s.indexOf('nt') > -1) {
      return samplePoints(function (x) { return 0.6 - 1.7 * Math.exp(-Math.pow((x - 0.5) / 0.12, 2)); });
    }
    if (s.indexOf('lp') > -1 || s.indexOf('low') > -1) {
      return samplePoints(function (x) { return x < 0.5 ? 0.6 : (x < 0.62 ? 0.95 : 0.95 - (x - 0.62) * 5.2); });
    }
    console.assert(false, 'OpWidgets: no filter glyph for "' + name + '"');
    return samplePoints(function () { return 0; });
  }

  /* ======================================================================
   * chip({addr, text}) — the amber R / Q toggles
   * ==================================================================== */

  function chip(opts) {
    opts = opts || {};
    var addr = opts.addr;
    var d = descOf(addr);

    var root = makeRoot('div', 'op-chip');
    root.setAttribute('data-addr', addr);
    root.setAttribute('role', 'checkbox');
    root.setAttribute('tabindex', '0');
    root.textContent = opts.text !== undefined ? String(opts.text)
      : String(d.label || addr.split('.').pop()).charAt(0).toUpperCase();

    function toggle() { P().set(addr, !valueOf(addr)); }
    function render() {
      var on = !!valueOf(addr);
      root.classList.toggle('is-on', on);
      root.setAttribute('aria-checked', on ? 'true' : 'false');
      root.setAttribute('title', (d.label || addr) + ': ' + (on ? 'on' : 'off'));
    }

    root.addEventListener('click', function (e) { e.preventDefault(); toggle(); });
    root.addEventListener('keydown', function (e) {
      if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); toggle(); }
    });

    track(root, addr, render);
    render();
    return root;
  }

  /* ======================================================================
   * pairToggle({addr, options}) — the 12 | 24 slope pair (active = amber)
   * ==================================================================== */

  function pairToggle(opts) {
    opts = opts || {};
    var addr = opts.addr;
    var d = descOf(addr);
    var info0 = enumInfo(d, valueOf(addr));
    var usesIndex = info0.usesIndex;

    var given = Array.isArray(opts.options) ? opts.options : null;
    console.assert(!given || given.length === d.enum.length,
      'OpWidgets.pairToggle: options length must match the enum for "' + addr + '"');
    var labels = d.enum.map(function (v, i) {
      return String(given && given[i] !== undefined ? given[i] : v);
    });

    var root = makeRoot('div', 'op-pair');
    root.setAttribute('data-addr', addr);
    root.setAttribute('role', 'radiogroup');

    var btns = [];
    for (var i = 0; i < d.enum.length; i++) {
      (function (idx) {
        var b = el('button', 'op-pair-opt', labels[idx]);
        b.type = 'button';
        b.setAttribute('role', 'radio');
        b.addEventListener('click', function (e) {
          e.preventDefault();
          P().set(addr, enumValueAt(d, idx, usesIndex));
        });
        btns.push(b);
        root.appendChild(b);
      }(i));
    }

    root.addEventListener('wheel', function (e) {
      e.preventDefault();
      P().set(addr, stepped(d, valueOf(addr), e.deltaY < 0 ? 1 : -1));
    }, { passive: false });

    function render() {
      var idx = enumInfo(d, valueOf(addr)).index;
      for (var i = 0; i < btns.length; i++) {
        btns[i].classList.toggle('is-active', i === idx);
        btns[i].setAttribute('aria-checked', i === idx ? 'true' : 'false');
      }
    }

    track(root, addr, render);
    render();
    return root;
  }

  /* ======================================================================
   * led({addr, color}) — tiny square annunciator, clickable when bool
   * ==================================================================== */

  function led(opts) {
    opts = opts || {};
    var addr = opts.addr;
    var d = descOf(addr);
    var color = opts.color ? (LED_COLORS[opts.color] || opts.color) : LED_COLORS.green;

    var root = makeRoot('span', 'op-led');
    root.setAttribute('data-addr', addr);
    root.style.setProperty('--op-led-color', color);

    var toggles = (d.kind === 'bool');
    if (toggles) {
      root.setAttribute('role', 'checkbox');
      root.setAttribute('tabindex', '0');
      root.classList.add('op-led--clickable');
      root.addEventListener('click', function (e) {
        e.preventDefault();
        P().set(addr, !valueOf(addr));
      });
      root.addEventListener('keydown', function (e) {
        if (e.key === ' ' || e.key === 'Enter') {
          e.preventDefault();
          P().set(addr, !valueOf(addr));
        }
      });
    }

    function render() {
      var on = !!valueOf(addr);
      root.classList.toggle('is-on', on);
      root.setAttribute('title', (d.label || addr) + ': ' + (on ? 'on' : 'off'));
      if (toggles) root.setAttribute('aria-checked', on ? 'true' : 'false');
    }

    track(root, addr, render);
    render();
    return root;
  }

  /* ======================================================================
   * meter() -> {el, update(level01)} — segmented green output meter
   * ==================================================================== */

  function meter() {
    var root = el('div', 'op-meter');
    root.setAttribute('role', 'img');
    root.setAttribute('aria-label', 'Output level');
    var segs = [];
    for (var i = 0; i < METER_SEGMENTS; i++) {
      var s = el('i', 'op-meter-seg');
      segs.push(s);
      root.appendChild(s);   /* column-reverse: index 0 is the bottom segment */
    }
    var peakEl = el('div', 'op-meter-peak');
    root.appendChild(peakEl);

    var lastLit = -1;
    var peak = 0;

    function update(level01) {
      var v = (typeof level01 === 'number' && isFinite(level01)) ? clamp01(level01) : 0;
      var lit = Math.round(v * METER_SEGMENTS);
      if (lit !== lastLit) {
        for (var i = 0; i < METER_SEGMENTS; i++) {
          segs[i].classList.toggle('is-lit', i < lit);
        }
        lastLit = lit;
      }
      peak = v > peak ? v : peak * METER_PEAK_DECAY;   /* decays per call, not per clock */
      peakEl.style.bottom = (peak * 100).toFixed(1) + '%';
      peakEl.style.opacity = peak > 0.01 ? '1' : '0';
    }

    update(0);
    return { el: root, update: update };
  }

  /* ---- export: exactly one global ------------------------------------- */

  global.OpWidgets = {
    version: VERSION,
    knob: knob,
    numberDrag: numberDrag,
    checkbox: checkbox,
    dropdown: dropdown,
    chip: chip,
    pairToggle: pairToggle,
    led: led,
    meter: meter,
    closeMenu: closeMenu
  };

}(typeof window !== 'undefined' ? window : this));
