/* =============================================================================
 * OpDisplay — the contextual dark display of the Operator replica.
 *
 * Owns ONE global: window.OpDisplay.
 *   OpDisplay.create(canvas) -> { setMode(section), draw(tMs), destroy() }
 *
 * Reads and writes state ONLY through window.OpParams. Never touches the audio
 * engine, never touches any other module's DOM. Fails loud: unknown section,
 * unknown enum value, or a missing OpParams throws.
 *
 * Sections: oscA oscB oscC oscD | lfo | filter | pitch | global
 *   oscX    interactive ADSR editor  -> writes osc.<x>.env.*
 *   filter  analytic RBJ biquad magnitude response (read-only)
 *   lfo     animated 2-cycle scope, scrolled by the tMs handed to draw()
 *   pitch   pitch-envelope glide curve (read-only)
 *   global  four clickable routing diagrams -> writes global.algorithm
 * ========================================================================== */
(function () {
  'use strict';

  /* ---------------------------------------------------------------- tokens */
  /* census.md §5 — exact values, no invention. */
  var TOK = {
    ground: '#242424',   // display — measured (spec/ratios.md); census's #161616 was an estimate
    line: '#333333',   // display-line: grid + baseline (visible on the #242424 ground)
    bracket: '#3a3a3a',   // corner bracket (dim chrome)
    curve: '#7cc0f0',   // blue-bright: envelope/response curves, handles
    blue: '#58a6dd',   // blue: secondary/active accent
    amber: '#f7a827',   // amber: hot values, selected algorithm
    text: '#cfcfcf',   // light-text
    textDim: '#6f6f6f',
    fill: 'rgba(124,192,240,0.10)',
    ghost: 'rgba(124,192,240,0.28)',
    handleHot: '#eaf5ff'
  };
  var FONT = '10px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, ' +
    'Helvetica, Arial, sans-serif';
  var FONT_SM = '9px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, ' +
    'Helvetica, Arial, sans-serif';

  var DB_FLOOR = -70;          // contract §2: any dB <= -70 is -inf
  var HANDLE = 8;              // census §3a: 8 px square handles
  var GRAB = 7;                // hit radius around a handle centre (CSS px)
  var FS = 44100;              // analysis sample rate for the filter response
  var FILT_TOP = 24, FILT_BOT = -66;   // filter response dB window
  var PITCH_ST = 48;                   // pitch display window, +/- semitones

  var MODES = ['oscA', 'oscB', 'oscC', 'oscD', 'lfo', 'filter', 'pitch', 'global'];
  var MODE_BY_KEY = {};
  (function () {
    for (var i = 0; i < MODES.length; i++) {
      MODE_BY_KEY[MODES[i].toLowerCase().replace(/[\s_-]/g, '')] = MODES[i];
    }
  }());

  /* ----------------------------------------------------------------- maths */
  function clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }
  function db2lin(db) { return db <= DB_FLOOR ? 0 : Math.pow(10, db / 20); }
  function lin2db(a) { return a > 0 ? 20 * Math.log10(a) : -Infinity; }
  function isNum(v) { return typeof v === 'number' && isFinite(v); }

  /* log-time weight: monotone, finite at t=0, ~1 decade per unit. */
  function tWeight(ms) { return Math.log10(1 + Math.max(0, ms)); }
  function tFromWeight(w) { return Math.pow(10, Math.max(0, w)) - 1; }

  /* ------------------------------------------------------- OpParams access */
  function P() {
    var p = window.OpParams;
    if (!p) {
      throw new Error('OpDisplay: window.OpParams is not loaded — the display ' +
        'renders only from the parameter tree.');
    }
    return p;
  }

  function requireParams() {
    var p = P();
    var need = ['desc', 'get', 'set', 'reset', 'subscribe', 'onAny', 'fmt'];
    for (var i = 0; i < need.length; i++) {
      if (typeof p[need[i]] !== 'function') {
        throw new Error('OpDisplay: window.OpParams.' + need[i] + ' is missing — ' +
          'the shared contract is not satisfied.');
      }
    }
    return p;
  }

  function desc(addr) {
    var d = P().desc(addr);
    if (!d) throw new Error('OpDisplay: no descriptor for "' + addr + '"');
    return d;
  }

  function num(addr) {
    var v = P().get(addr);
    if (typeof v === 'boolean') return v ? 1 : 0;
    if (typeof v !== 'number') {
      throw new Error('OpDisplay: "' + addr + '" is not numeric (got ' +
        JSON.stringify(v) + ')');
    }
    return v;
  }

  function bool(addr) { return !!P().get(addr); }

  /* dB read: -Infinity and anything <= -70 collapse onto the display floor. */
  function dbOf(addr) {
    var v = P().get(addr);
    if (typeof v !== 'number') {
      throw new Error('OpDisplay: "' + addr + '" is not a dB number');
    }
    return (!isFinite(v) || v <= DB_FLOOR) ? DB_FLOOR : clamp(v, DB_FLOOR, 0);
  }

  /* dB write: at the floor, hand back whatever "-inf" the tree actually stores. */
  function setDb(addr, db) {
    var d = desc(addr);
    var lo = isNum(d.min) ? d.min : DB_FLOOR;
    var hi = isNum(d.max) ? d.max : 0;
    if (db <= DB_FLOOR + 0.5) {
      P().set(addr, isNum(d.min) ? lo : -Infinity);
      return;
    }
    P().set(addr, clamp(db, Math.max(lo, DB_FLOOR), hi));
  }

  function setNum(addr, v) {
    var d = desc(addr);
    var lo = isNum(d.min) ? d.min : -Infinity;
    var hi = isNum(d.max) ? d.max : Infinity;
    P().set(addr, clamp(v, lo, hi));
  }

  /* Enum values may arrive as the member itself ("LP", 24) or as an index.
     Resolve both; anything else is a hard error. */
  function enumStr(addr) {
    var d = desc(addr);
    var v = P().get(addr);
    var list = d.enum;
    if (!list || !list.length) return String(v);
    var i;
    for (i = 0; i < list.length; i++) {
      if (String(list[i]) === String(v)) return String(list[i]);
    }
    if (typeof v === 'number' && v === Math.round(v) && v >= 0 && v < list.length) {
      return String(list[v]);
    }
    throw new Error('OpDisplay: "' + addr + '" = ' + JSON.stringify(v) +
      ' is neither a member nor an index of [' + list.join(', ') + ']');
  }

  function enumIdx(addr) {
    var d = desc(addr);
    var v = P().get(addr);
    var list = d.enum;
    if (!list || !list.length) {
      if (typeof v === 'number') return Math.round(v);
      throw new Error('OpDisplay: "' + addr + '" has no enum list and is not numeric');
    }
    var i;
    for (i = 0; i < list.length; i++) {
      if (String(list[i]) === String(v)) return i;
    }
    if (typeof v === 'number' && v === Math.round(v) && v >= 0 && v < list.length) {
      return v;
    }
    throw new Error('OpDisplay: "' + addr + '" = ' + JSON.stringify(v) +
      ' is neither a member nor an index of [' + list.join(', ') + ']');
  }

  function setEnumIdx(addr, i) {
    var d = desc(addr);
    var list = d.enum;
    if (!list || !list.length) { P().set(addr, i); return; }
    if (i < 0 || i >= list.length) {
      throw new RangeError('OpDisplay: enum index ' + i + ' out of range for "' + addr + '"');
    }
    var cur = P().get(addr);
    var curIsMember = false, k;
    for (k = 0; k < list.length; k++) {
      if (String(list[k]) === String(cur)) { curIsMember = true; break; }
    }
    /* Mirror the representation the tree already uses: member, else index. */
    P().set(addr, curIsMember ? list[i] : i);
  }

  /* ------------------------------------------------------------- canvas io */
  function crisp(v, dpr) { return (Math.round(v * dpr) + 0.5) / dpr; }

  function hairline(ctx, x1, y1, x2, y2, color, dpr) {
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.beginPath();
    if (Math.abs(y1 - y2) < 0.01) {
      var y = crisp(y1, dpr);
      ctx.moveTo(x1, y); ctx.lineTo(x2, y);
    } else if (Math.abs(x1 - x2) < 0.01) {
      var x = crisp(x1, dpr);
      ctx.moveTo(x, y1); ctx.lineTo(x, y2);
    } else {
      ctx.moveTo(x1, y1); ctx.lineTo(x2, y2);
    }
    ctx.stroke();
  }

  function cornerBracket(ctx, w, dpr) {
    /* census §3a — display-zoom affordance, top-right. */
    var m = 5, len = 13;
    ctx.strokeStyle = TOK.bracket;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(w - m - len, crisp(m, dpr));
    ctx.lineTo(crisp(w - m, dpr), crisp(m, dpr));
    ctx.lineTo(crisp(w - m, dpr), m + len);
    ctx.stroke();
  }

  function squareHandle(ctx, x, y, hot, color) {
    var h = HANDLE / 2;
    ctx.fillStyle = TOK.ground;
    ctx.fillRect(x - h - 1, y - h - 1, HANDLE + 2, HANDLE + 2);
    ctx.fillStyle = hot ? TOK.handleHot : (color || TOK.curve);
    ctx.fillRect(x - h, y - h, HANDLE, HANDLE);
  }

  function label(ctx, text, x, y, color, align, font) {
    ctx.font = font || FONT;
    ctx.textAlign = align || 'left';
    ctx.textBaseline = 'alphabetic';
    ctx.fillStyle = color || TOK.textDim;
    ctx.fillText(text, x, y);
  }

  /* ------------------------------------------------------------- envelopes */
  function envAddrs(mode) {
    var x = mode.charAt(3).toLowerCase();          // 'oscB' -> 'b'
    var p = 'osc.' + x + '.env.';
    return {
      osc: x,
      attack: p + 'attack', decay: p + 'decay', release: p + 'release',
      initial: p + 'initial', peak: p + 'peak', sustain: p + 'sustain'
    };
  }

  /* x layout: log-time widths for A/D/R plus a fixed sustain plateau.
     Each time segment keeps a floor of `minSeg` px so its handle stays
     grabbable at minimum time. Total width is constant by construction. */
  function envLayout(rect, ta, td, tr) {
    var W = rect.w;
    var plateau = clamp(W * 0.16, 10, 90);
    var minSeg = W > 240 ? 10 : Math.max(2, W * 0.04);
    var usable = W - plateau;
    var K = usable - 3 * minSeg;
    if (K < 8) { minSeg = Math.max(0, usable / 8); K = usable - 3 * minSeg; }
    var wa = tWeight(ta), wd = tWeight(td), wr = tWeight(tr);
    var S = wa + wd + wr;
    var Wa, Wd, Wr;
    if (!(S > 0) || !(K > 0)) {
      Wa = Wd = Wr = usable / 3;
    } else {
      Wa = minSeg + K * wa / S;
      Wd = minSeg + K * wd / S;
      Wr = minSeg + K * wr / S;
    }
    var L = {
      plateau: plateau, minSeg: minSeg, K: K, S: S, wa: wa, wd: wd, wr: wr,
      Wa: Wa, Wd: Wd, Wr: Wr,
      x0: rect.x,
      xPeak: rect.x + Wa,
      xSus: rect.x + Wa + Wd,
      xSusEnd: rect.x + Wa + Wd + plateau,
      xEnd: rect.x + Wa + Wd + plateau + Wr
    };
    console.assert(Math.abs(L.xEnd - (rect.x + W)) < 0.5,
      'OpDisplay: envelope layout must fill the graph width exactly');
    return L;
  }

  /* Inverse of the layout above. The other two weights are held fixed, so the
     dragged handle lands exactly under the pointer. */
  function weightForCum(cum, K, others) {
    /* cum/K = w / (w + others)  ->  w = cum*others / (K - cum) */
    var u = clamp(cum, 0, K - 0.5);
    var R = others > 1e-9 ? others : 1e-9;
    if (K - u <= 1e-9) return 1e9;
    return u * R / (K - u);
  }

  /* -------------------------------------------------------- filter maths  */
  /* RBJ audio-EQ-cookbook biquads; magnitude evaluated on the unit circle. */
  function biquadCoefs(type, f0, Q) {
    var w0 = 2 * Math.PI * clamp(f0, 10, FS * 0.45) / FS;
    var cw = Math.cos(w0), sw = Math.sin(w0);
    var alpha = sw / (2 * Math.max(0.05, Q));
    var b0, b1, b2;
    if (type === 'HP') { b0 = (1 + cw) / 2; b1 = -(1 + cw); b2 = (1 + cw) / 2; }
    else if (type === 'BP') { b0 = alpha; b1 = 0; b2 = -alpha; }
    else if (type === 'NOTCH') { b0 = 1; b1 = -2 * cw; b2 = 1; }
    else { b0 = (1 - cw) / 2; b1 = 1 - cw; b2 = (1 - cw) / 2; }
    return { b0: b0, b1: b1, b2: b2, a0: 1 + alpha, a1: -2 * cw, a2: 1 - alpha };
  }

  function biquadMagDb(c, f) {
    var w = 2 * Math.PI * clamp(f, 1, FS * 0.5) / FS;
    var c1 = Math.cos(-w), s1 = Math.sin(-w);
    var c2 = Math.cos(-2 * w), s2 = Math.sin(-2 * w);
    var nr = c.b0 + c.b1 * c1 + c.b2 * c2, ni = c.b1 * s1 + c.b2 * s2;
    var dr = c.a0 + c.a1 * c1 + c.a2 * c2, di = c.a1 * s1 + c.a2 * s2;
    var den = Math.sqrt(dr * dr + di * di);
    if (!(den > 0)) return FILT_BOT;
    var mag = Math.sqrt(nr * nr + ni * ni) / den;
    return 20 * Math.log10(Math.max(mag, 1e-6));
  }

  function filterTypeKey(s) {
    var c = String(s).trim().charAt(0).toUpperCase();
    if (c === 'H') return 'HP';
    if (c === 'B') return 'BP';
    if (c === 'N') return 'NOTCH';
    return 'LP';
  }

  /* res 0..125 %  ->  Q 0.5..8 (brief) */
  function qFromRes(res, d) {
    var lo = isNum(d.min) ? d.min : 0;
    var hi = isNum(d.max) ? d.max : 125;
    var t = hi > lo ? (clamp(res, lo, hi) - lo) / (hi - lo) : 0;
    return 0.5 + t * 7.5;
  }

  /* ------------------------------------------------------------ LFO shapes */
  function noiseHash(n) {
    var h = Math.sin(n * 127.1 + 311.7) * 43758.5453;
    return 2 * (h - Math.floor(h)) - 1;
  }

  function lfoSample(waveKey, g) {
    var p = g - Math.floor(g);              // 0..1 within the cycle
    switch (waveKey) {
      case 'SQUARE': return p < 0.5 ? 1 : -1;
      case 'TRIANGLE':
        if (p < 0.25) return 4 * p;
        if (p < 0.75) return 2 - 4 * p;
        return 4 * p - 4;
      case 'SAW': return 2 * p - 1;
      case 'NOISE': return noiseHash(Math.floor(g * 8));
      default: return Math.sin(2 * Math.PI * p);
    }
  }

  function lfoWaveKey(s) {
    var t = String(s).trim().toUpperCase();
    if (t.charAt(0) === 'Q' || t.indexOf('SQ') === 0) return 'SQUARE';
    if (t.charAt(0) === 'T') return 'TRIANGLE';
    if (t.charAt(0) === 'W' || t.indexOf('SAW') === 0) return 'SAW';
    if (t.charAt(0) === 'N') return 'NOISE';
    return 'SINE';
  }

  /* ------------------------------------------------ algorithm diagrams §4 */
  /* nodes: [letter, columnFraction, rowIndex]; edges index into nodes. */
  var ALGOS = [
    { /* 0: D->C->B->A serial */
      rows: 4, bus: false,
      nodes: [['D', 0.5, 0], ['C', 0.5, 1], ['B', 0.5, 2], ['A', 0.5, 3]],
      edges: [[0, 1], [1, 2], [2, 3]], out: 3
    },
    { /* 1: D->B, C->B, B->A  (fan-in) */
      rows: 3, bus: false,
      nodes: [['D', 0.27, 0], ['C', 0.73, 0], ['B', 0.5, 1], ['A', 0.5, 2]],
      edges: [[0, 2], [1, 2], [2, 3]], out: 3
    },
    { /* 2: D->C, B->A — two independent stacks, carriers C and A.
         Authority: OpEngine.ALGORITHMS (the audible routing); the contract's
         literal text for 2 was self-contradictory and the engine resolved it. */
      rows: 2, bus: false,
      nodes: [['D', 0.3, 0], ['C', 0.3, 1], ['B', 0.7, 0], ['A', 0.7, 1]],
      edges: [[0, 1], [2, 3]], out: [1, 3]
    },
    { /* 3: A+B+C+D additive */
      rows: 3, bus: true,
      nodes: [['D', 0.12, 0], ['C', 0.37, 0], ['B', 0.63, 0], ['A', 0.88, 0]],
      edges: [], out: -1
    }
  ];

  function arrow(ctx, x1, y1, x2, y2, color) {
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
    var a = Math.atan2(y2 - y1, x2 - x1), s = 3.6;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(x2, y2);
    ctx.lineTo(x2 - s * Math.cos(a - 0.42), y2 - s * Math.sin(a - 0.42));
    ctx.lineTo(x2 - s * Math.cos(a + 0.42), y2 - s * Math.sin(a + 0.42));
    ctx.closePath();
    ctx.fill();
  }

  /* ====================================================================== */
  /*                              instance                                   */
  /* ====================================================================== */
  function create(canvas) {
    if (!canvas || String(canvas.tagName).toLowerCase() !== 'canvas') {
      throw new TypeError('OpDisplay.create(canvas): a <canvas> element is required');
    }
    var params = requireParams();
    var ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('OpDisplay: 2d canvas context unavailable');

    var st = {
      mode: 'oscB',
      lastT: 0,
      dirty: true,
      cssW: canvas.width || 300,
      cssH: canvas.height || 150,
      dpr: 1,
      handles: [],      // envelope handles from the last render
      cells: [],        // algorithm cells from the last render
      hover: null,      // {kind:'handle'|'cell', id}
      drag: null,       // {id, lastX, lastY}
      unsubs: [],
      dead: false
    };

    canvas.style.touchAction = 'none';

    /* ---------------------------------------------------------- geometry */
    function syncSize() {
      var dpr = window.devicePixelRatio || 1;
      var w = canvas.clientWidth || st.cssW;
      var h = canvas.clientHeight || st.cssH;
      if (!(w > 0) || !(h > 0)) return false;
      var pw = Math.max(1, Math.round(w * dpr));
      var ph = Math.max(1, Math.round(h * dpr));
      if (canvas.width !== pw || canvas.height !== ph) {
        canvas.width = pw;
        canvas.height = ph;
      }
      st.cssW = w; st.cssH = h; st.dpr = dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      return true;
    }

    function rectOf() {
      var w = st.cssW, h = st.cssH;
      var padL = clamp(w * 0.035, 8, 16);
      var padR = clamp(w * 0.035, 10, 18);
      var padT = clamp(h * 0.14, 10, 18);
      var padB = clamp(h * 0.14, 10, 16);
      return { x: padL, y: padT, w: Math.max(4, w - padL - padR), h: Math.max(4, h - padT - padB) };
    }

    /* ------------------------------------------------------- render: osc */
    function ydbOf(r) {
      return function (db) {
        var v = (!isFinite(db) || db < DB_FLOOR) ? DB_FLOOR : clamp(db, DB_FLOOR, 0);
        return r.y + r.h - ((v - DB_FLOOR) / -DB_FLOOR) * r.h;
      };
    }

    function segTo(path, x0, x1, db0, db1, ydb, steps) {
      var a0 = db2lin(db0), a1 = db2lin(db1);
      var k = 4.6, norm = 1 - Math.exp(-k);
      for (var i = 1; i <= steps; i++) {
        var u = i / steps;
        var a = a0 + (a1 - a0) * (1 - Math.exp(-k * u)) / norm;
        path(x0 + (x1 - x0) * u, ydb(lin2db(a)));
      }
    }

    function renderOsc() {
      var A = envAddrs(st.mode);
      var r = rectOf();
      var ta = num(A.attack), td = num(A.decay), tr = num(A.release);
      var dbI = dbOf(A.initial), dbP = dbOf(A.peak), dbS = dbOf(A.sustain);
      var L = envLayout(r, ta, td, tr);
      var ydb = ydbOf(r);
      var i;

      /* grid: dB rows + segment separators */
      for (i = 0; i <= 3; i++) {
        var g = ydb(DB_FLOOR + (i / 3) * -DB_FLOOR);
        hairline(ctx, r.x, g, r.x + r.w, g, TOK.line, st.dpr);
      }
      var seps = [L.xPeak, L.xSus, L.xSusEnd];
      for (i = 0; i < seps.length; i++) {
        hairline(ctx, seps[i], r.y, seps[i], r.y + r.h, TOK.line, st.dpr);
      }

      /* curve */
      var pts = [];
      var push = function (x, y) { pts.push(x, y); };
      push(L.x0, ydb(dbI));
      segTo(push, L.x0, L.xPeak, dbI, dbP, ydb, 40);
      segTo(push, L.xPeak, L.xSus, dbP, dbS, ydb, 44);
      push(L.xSusEnd, ydb(dbS));
      segTo(push, L.xSusEnd, L.xEnd, dbS, DB_FLOOR, ydb, 40);

      var base = r.y + r.h;
      ctx.beginPath();
      ctx.moveTo(pts[0], base);
      for (i = 0; i < pts.length; i += 2) ctx.lineTo(pts[i], pts[i + 1]);
      ctx.lineTo(pts[pts.length - 2], base);
      ctx.closePath();
      ctx.fillStyle = TOK.fill;
      ctx.fill();

      ctx.beginPath();
      ctx.moveTo(pts[0], pts[1]);
      for (i = 2; i < pts.length; i += 2) ctx.lineTo(pts[i], pts[i + 1]);
      ctx.strokeStyle = TOK.curve;
      ctx.lineWidth = 1.4;
      ctx.lineJoin = 'round';
      ctx.stroke();

      /* baseline last so it reads over the fill */
      hairline(ctx, r.x, base, r.x + r.w, base, TOK.line, st.dpr);

      st.handles = [
        {
          id: 'initial', x: L.x0, y: ydb(dbI), axis: 'y', cursor: 'ns-resize',
          addrs: [A.initial]
        },
        {
          id: 'peak', x: L.xPeak, y: ydb(dbP), axis: 'xy', cursor: 'move',
          addrs: [A.attack, A.peak]
        },
        {
          id: 'sustain', x: L.xSus, y: ydb(dbS), axis: 'xy', cursor: 'move',
          addrs: [A.decay, A.sustain]
        },
        {
          id: 'release', x: L.xEnd, y: base, axis: 'x', cursor: 'ew-resize',
          addrs: [A.release]
        }
      ];
      for (i = 0; i < st.handles.length; i++) {
        var hd = st.handles[i];
        var hot = (st.drag && st.drag.id === hd.id) ||
          (!st.drag && st.hover && st.hover.kind === 'handle' && st.hover.id === hd.id);
        squareHandle(ctx, hd.x, hd.y, hot);
      }

      /* live readout while dragging (uses OpParams.fmt — the one format owner) */
      var active = st.drag ? st.drag.id : (st.hover && st.hover.kind === 'handle' ? st.hover.id : null);
      if (active) {
        for (i = 0; i < st.handles.length; i++) {
          if (st.handles[i].id !== active) continue;
          var ad = st.handles[i].addrs, parts = [];
          for (var j = 0; j < ad.length; j++) parts.push(params.fmt(ad[j]));
          var txt = parts.join('  ');
          ctx.font = FONT;
          var tw = ctx.measureText(txt).width;
          var tx = clamp(st.handles[i].x - tw / 2, 2, st.cssW - tw - 2);
          var ty = clamp(st.handles[i].y - 9, 11, st.cssH - 2);
          label(ctx, txt, tx, ty, TOK.text, 'left', FONT);
        }
      }
    }

    /* ---------------------------------------------------- render: filter */
    function renderFilter() {
      var r = rectOf();
      var on = bool('filter.on');
      var type = filterTypeKey(enumStr('filter.type'));
      var slope = parseInt(enumStr('filter.slope'), 10);
      var stages = (slope === 24) ? 2 : 1;
      var f0 = num('filter.freq');
      var q = qFromRes(num('filter.res'), desc('filter.res'));
      var c = biquadCoefs(type, f0, q);
      var fMin = 20, fMax = 20000;
      var lgMin = Math.log10(fMin), lgSpan = Math.log10(fMax) - lgMin;
      var i;

      function xf(f) { return r.x + (Math.log10(clamp(f, fMin, fMax)) - lgMin) / lgSpan * r.w; }
      function ydB(db) {
        return r.y + r.h - (clamp(db, FILT_BOT, FILT_TOP) - FILT_BOT) /
          (FILT_TOP - FILT_BOT) * r.h;
      }

      /* decade grid + 0 dB */
      var decades = [100, 1000, 10000];
      for (i = 0; i < decades.length; i++) {
        var gx = xf(decades[i]);
        hairline(ctx, gx, r.y, gx, r.y + r.h, TOK.line, st.dpr);
        label(ctx, decades[i] >= 1000 ? (decades[i] / 1000) + 'k' : String(decades[i]),
          gx + 3, r.y + r.h + 10, TOK.textDim, 'left', FONT_SM);
      }
      var y0 = ydB(0);
      hairline(ctx, r.x, y0, r.x + r.w, y0, TOK.line, st.dpr);
      hairline(ctx, r.x, ydB(-48), r.x + r.w, ydB(-48), TOK.line, st.dpr);
      hairline(ctx, r.x, r.y + r.h, r.x + r.w, r.y + r.h, TOK.line, st.dpr);

      /* cutoff marker */
      var cx = xf(f0);
      hairline(ctx, cx, r.y, cx, r.y + r.h, TOK.line, st.dpr);

      /* magnitude response */
      var n = Math.max(64, Math.round(r.w));
      ctx.beginPath();
      for (i = 0; i <= n; i++) {
        var f = Math.pow(10, lgMin + (i / n) * lgSpan);
        var db = biquadMagDb(c, f) * stages;
        var x = r.x + (i / n) * r.w, y = ydB(db);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = TOK.curve;
      ctx.globalAlpha = on ? 1 : 0.4;              // contract §5.7
      ctx.lineWidth = 1.4;
      ctx.lineJoin = 'round';
      ctx.stroke();
      ctx.globalAlpha = 1;

      label(ctx, type + '  ' + (stages === 2 ? '24' : '12') + ' dB  ' +
        params.fmt('filter.freq') + '  Q ' + q.toFixed(2),
        r.x, r.y - 4, on ? TOK.text : TOK.textDim, 'left', FONT_SM);
    }

    /* ------------------------------------------------------- render: LFO */
    function renderLfo() {
      var r = rectOf();
      var on = bool('lfo.on');
      var wave = lfoWaveKey(enumStr('lfo.wave'));
      var rate = num('lfo.rate');
      var amt = num('lfo.amount') / 100;
      var cy = r.y + r.h / 2;
      var half = r.h / 2 - 1;
      var cycles = 2;
      var phase = (st.lastT / 1000) * rate;
      var n = Math.max(64, Math.round(r.w));
      var i, g, x;

      hairline(ctx, r.x, cy, r.x + r.w, cy, TOK.line, st.dpr);
      hairline(ctx, r.x, r.y, r.x + r.w, r.y, TOK.line, st.dpr);
      hairline(ctx, r.x, r.y + r.h, r.x + r.w, r.y + r.h, TOK.line, st.dpr);
      for (i = 1; i < cycles * 2; i++) {
        var vx = r.x + (i / (cycles * 2)) * r.w;
        hairline(ctx, vx, r.y, vx, r.y + r.h, TOK.line, st.dpr);
      }

      ctx.globalAlpha = on ? 1 : 0.4;

      /* full-amplitude shape (dim) then the amount-scaled signal (bright) */
      ctx.beginPath();
      for (i = 0; i <= n; i++) {
        x = r.x + (i / n) * r.w;
        g = phase + (i / n) * cycles;
        var yv = cy - lfoSample(wave, g) * half;
        if (i === 0) ctx.moveTo(x, yv); else ctx.lineTo(x, yv);
      }
      ctx.strokeStyle = TOK.ghost;
      ctx.lineWidth = 1;
      ctx.stroke();

      ctx.beginPath();
      for (i = 0; i <= n; i++) {
        x = r.x + (i / n) * r.w;
        g = phase + (i / n) * cycles;
        var ya = cy - lfoSample(wave, g) * half * amt;
        if (i === 0) ctx.moveTo(x, ya); else ctx.lineTo(x, ya);
      }
      ctx.strokeStyle = TOK.curve;
      ctx.lineWidth = 1.4;
      ctx.lineJoin = 'round';
      ctx.stroke();
      ctx.globalAlpha = 1;

      label(ctx, enumStr('lfo.wave') + '  ' + params.fmt('lfo.rate') + '  ' +
        params.fmt('lfo.amount'), r.x, r.y - 4,
        on ? TOK.text : TOK.textDim, 'left', FONT_SM);
    }

    /* ----------------------------------------------------- render: pitch */
    function renderPitch() {
      var r = rectOf();
      var on = bool('pitch.on');
      var envPct = num('pitch.env') / 100;
      var transpose = num('pitch.transpose');
      var spread = num('pitch.spread') / 100;
      var amount = envPct * PITCH_ST;
      var cy, i;

      function yst(stv) {
        return r.y + r.h - (clamp(stv, -PITCH_ST, PITCH_ST) + PITCH_ST) /
          (2 * PITCH_ST) * r.h;
      }

      cy = yst(0);
      hairline(ctx, r.x, r.y, r.x + r.w, r.y, TOK.line, st.dpr);
      hairline(ctx, r.x, cy, r.x + r.w, cy, TOK.line, st.dpr);
      hairline(ctx, r.x, r.y + r.h, r.x + r.w, r.y + r.h, TOK.line, st.dpr);
      var tl = yst(transpose);
      hairline(ctx, r.x, tl, r.x + r.w, tl, TOK.line, st.dpr);

      var n = Math.max(48, Math.round(r.w));
      function curve(offset, color, width) {
        ctx.beginPath();
        for (i = 0; i <= n; i++) {
          var u = i / n;
          var v = transpose + offset + amount * Math.exp(-4.6 * u);
          var x = r.x + u * r.w, y = yst(v);
          if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.strokeStyle = color;
        ctx.lineWidth = width;
        ctx.lineJoin = 'round';
        ctx.stroke();
      }

      ctx.globalAlpha = on ? 1 : 0.4;
      if (spread > 0) {
        var off = spread * 2;                    // spread drawn as a detuned pair
        curve(+off, TOK.ghost, 1);
        curve(-off, TOK.ghost, 1);
      }
      curve(0, TOK.curve, 1.4);
      ctx.globalAlpha = 1;

      /* no square handle here: the pitch curve is read-only, and a handle
         glyph affords a drag that does nothing (verify finding) */

      label(ctx, params.fmt('pitch.env') + '  ' + params.fmt('pitch.transpose') +
        '  spread ' + params.fmt('pitch.spread'),
        r.x, r.y - 4, on ? TOK.text : TOK.textDim, 'left', FONT_SM);
    }

    /* ---------------------------------------------------- render: global */
    function renderGlobal() {
      var sel = enumIdx('global.algorithm');
      console.assert(sel >= 0 && sel < ALGOS.length,
        'OpDisplay: global.algorithm out of the 4-diagram range');
      var w = st.cssW, h = st.cssH;
      var padX = clamp(w * 0.02, 4, 12), padY = clamp(h * 0.10, 6, 14);
      var gap = clamp(w * 0.012, 3, 10);
      var cellW = (w - 2 * padX - 3 * gap) / 4;
      var cellH = h - 2 * padY;
      st.cells = [];
      for (var a = 0; a < 4; a++) {
        var cx = padX + a * (cellW + gap);
        st.cells.push({ i: a, x: cx, y: padY, w: cellW, h: cellH });
        drawAlgo(ALGOS[a], cx, padY, cellW, cellH, a === sel,
          !!(st.hover && st.hover.kind === 'cell' && st.hover.id === a));
      }
    }

    function drawAlgo(alg, x, y, w, h, selected, hovered) {
      var color = selected ? TOK.amber : (hovered ? TOK.text : TOK.textDim);
      var frame = selected ? TOK.amber : (hovered ? TOK.bracket : TOK.line);
      ctx.strokeStyle = frame;
      ctx.lineWidth = 1;
      ctx.strokeRect(crisp(x, st.dpr), crisp(y, st.dpr),
        Math.round(w) - 1, Math.round(h) - 1);

      var ix = x + 6, iy = y + 6, iw = Math.max(8, w - 12), ih = Math.max(8, h - 12);
      var rows = alg.rows;
      var nodeH = clamp(ih / rows - 6, 7, 14);
      var nodeW = clamp(alg.bus ? iw / 4.6 : iw / 3.2, 10, 22);
      var fontPx = Math.max(7, Math.min(10, Math.round(nodeH - 3)));
      var i, p;

      function rowY(rI) { return iy + (rI + 0.5) * (ih / rows); }
      function nodeAt(idx) {
        var nd = alg.nodes[idx];
        return { cx: ix + nd[1] * iw, cy: rowY(nd[2]), letter: nd[0] };
      }

      for (i = 0; i < alg.edges.length; i++) {
        var from = nodeAt(alg.edges[i][0]), to = nodeAt(alg.edges[i][1]);
        arrow(ctx, from.cx, from.cy + nodeH / 2, to.cx, to.cy - nodeH / 2 - 1, color);
      }

      if (alg.bus) {
        var busY = rowY(1);
        var lx = nodeAt(0).cx, rx = nodeAt(alg.nodes.length - 1).cx;
        for (i = 0; i < alg.nodes.length; i++) {
          p = nodeAt(i);
          hairline(ctx, p.cx, p.cy + nodeH / 2, p.cx, busY, color, st.dpr);
        }
        hairline(ctx, lx, busY, rx, busY, color, st.dpr);
        arrow(ctx, (lx + rx) / 2, busY, (lx + rx) / 2, rowY(2) + nodeH / 2, color);
      } else {
        var outs = Array.isArray(alg.out) ? alg.out : (alg.out >= 0 ? [alg.out] : []);
        for (i = 0; i < outs.length; i++) {
          p = nodeAt(outs[i]);
          arrow(ctx, p.cx, p.cy + nodeH / 2, p.cx, Math.min(iy + ih, p.cy + nodeH / 2 + 9), color);
        }
      }

      for (i = 0; i < alg.nodes.length; i++) {
        p = nodeAt(i);
        ctx.fillStyle = TOK.ground;
        ctx.fillRect(p.cx - nodeW / 2, p.cy - nodeH / 2, nodeW, nodeH);
        ctx.strokeStyle = color;
        ctx.lineWidth = 1;
        ctx.strokeRect(crisp(p.cx - nodeW / 2, st.dpr), crisp(p.cy - nodeH / 2, st.dpr),
          Math.round(nodeW), Math.round(nodeH));
        ctx.fillStyle = color;
        ctx.font = fontPx + 'px -apple-system, BlinkMacSystemFont, "Segoe UI", ' +
          'Roboto, Helvetica, Arial, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(p.letter, p.cx, p.cy + 0.5);
      }
      ctx.textAlign = 'left';
      ctx.textBaseline = 'alphabetic';
    }

    /* --------------------------------------------------------- render all */
    function render() {
      if (st.dead) return;
      if (!syncSize()) return;
      ctx.clearRect(0, 0, st.cssW, st.cssH);
      ctx.fillStyle = TOK.ground;
      ctx.fillRect(0, 0, st.cssW, st.cssH);

      st.handles = [];
      st.cells = [];

      if (st.mode.indexOf('osc') === 0) renderOsc();
      else if (st.mode === 'filter') renderFilter();
      else if (st.mode === 'lfo') renderLfo();
      else if (st.mode === 'pitch') renderPitch();
      else if (st.mode === 'global') renderGlobal();
      else throw new Error('OpDisplay: unreachable mode "' + st.mode + '"');

      cornerBracket(ctx, st.cssW, st.dpr);
      st.dirty = false;
    }

    /* ------------------------------------------------------- interaction */
    function localPoint(ev) {
      var rc = canvas.getBoundingClientRect();
      var sx = rc.width > 0 ? st.cssW / rc.width : 1;
      var sy = rc.height > 0 ? st.cssH / rc.height : 1;
      return { x: (ev.clientX - rc.left) * sx, y: (ev.clientY - rc.top) * sy };
    }

    function hitTest(pt) {
      var i;
      for (i = 0; i < st.handles.length; i++) {
        var hd = st.handles[i];
        if (Math.abs(pt.x - hd.x) <= GRAB && Math.abs(pt.y - hd.y) <= GRAB) {
          return { kind: 'handle', id: hd.id, cursor: hd.cursor };
        }
      }
      for (i = 0; i < st.cells.length; i++) {
        var c = st.cells[i];
        if (pt.x >= c.x && pt.x <= c.x + c.w && pt.y >= c.y && pt.y <= c.y + c.h) {
          return { kind: 'cell', id: c.i, cursor: 'pointer' };
        }
      }
      return null;
    }

    function handleById(id) {
      for (var i = 0; i < st.handles.length; i++) {
        if (st.handles[i].id === id) return st.handles[i];
      }
      return null;
    }

    /* dB from a pointer y, absolute on the -70..0 axis */
    function dbFromY(y) {
      var r = rectOf();
      var t = clamp((r.y + r.h - y) / r.h, 0, 1);
      return DB_FLOOR + t * -DB_FLOOR;
    }

    function applyEnvDrag(id, pt, dx) {
      var A = envAddrs(st.mode);
      var r = rectOf();
      var ta = num(A.attack), td = num(A.decay), tr = num(A.release);
      var L = envLayout(r, ta, td, tr);
      var cum, w, others, t;

      if (id === 'initial') {
        setDb(A.initial, dbFromY(pt.y));
        return;
      }
      if (id === 'peak') {
        setDb(A.peak, dbFromY(pt.y));
        cum = clamp(pt.x - r.x - L.minSeg, 0, L.K);
        others = L.wd + L.wr;
        w = weightForCum(cum, L.K, others);
        setNum(A.attack, tFromWeight(w));
        return;
      }
      if (id === 'sustain') {
        setDb(A.sustain, dbFromY(pt.y));
        /* cumulative (attack+decay) share of K, attack weight held fixed */
        var v = clamp((pt.x - r.x - 2 * L.minSeg) / L.K, 0, 0.999);
        var sumAD = (1 - v) > 1e-6 ? v * L.wr / (1 - v) : 1e9;
        t = tFromWeight(Math.max(0, sumAD - L.wa));
        setNum(A.decay, t);
        return;
      }
      if (id === 'release') {
        /* The last handle sits at a fixed x (total width is constant), so the
           release time follows the pointer DELTA, in the same px-per-weight
           scale the layout uses. */
        if (!(L.K > 0) || !(L.S > 0)) return;
        var dw = (dx / L.K) * L.S;
        setNum(A.release, tFromWeight(Math.max(0, L.wr + dw)));
        return;
      }
      throw new Error('OpDisplay: unknown envelope handle "' + id + '"');
    }

    function onDown(ev) {
      if (ev.button !== undefined && ev.button !== 0) return;
      var pt = localPoint(ev);
      var hit = hitTest(pt);
      if (!hit) return;
      ev.preventDefault();
      if (hit.kind === 'cell') {
        setEnumIdx('global.algorithm', hit.id);
        return;
      }
      var hd = handleById(hit.id);
      if (!hd) throw new Error('OpDisplay: hit an envelope handle that is not in the layout');
      /* Grab offset: the value must not jump when the press lands a few px off
         the handle centre. Subsequent absolute mapping uses pointer + offset. */
      st.drag = { id: hit.id, offX: hd.x - pt.x, offY: hd.y - pt.y, lastX: pt.x };
      if (canvas.setPointerCapture && ev.pointerId !== undefined) {
        canvas.setPointerCapture(ev.pointerId);
      }
      st.dirty = true;
      render();
    }

    function onMove(ev) {
      var pt = localPoint(ev);
      if (st.drag) {
        var dx = pt.x - st.drag.lastX;
        applyEnvDrag(st.drag.id,
          { x: pt.x + st.drag.offX, y: pt.y + st.drag.offY }, dx);
        st.drag.lastX = pt.x;
        st.dirty = true;
        render();
        return;
      }
      var hit = hitTest(pt);
      var key = hit ? hit.kind + ':' + hit.id : null;
      var prev = st.hover ? st.hover.kind + ':' + st.hover.id : null;
      canvas.style.cursor = hit ? hit.cursor : 'default';
      if (key !== prev) {
        st.hover = hit ? { kind: hit.kind, id: hit.id } : null;
        st.dirty = true;
        render();
      }
    }

    function onUp(ev) {
      if (!st.drag) return;
      if (canvas.releasePointerCapture && ev.pointerId !== undefined &&
        canvas.hasPointerCapture && canvas.hasPointerCapture(ev.pointerId)) {
        canvas.releasePointerCapture(ev.pointerId);
      }
      st.drag = null;
      st.dirty = true;
      render();
    }

    function onLeave() {
      if (st.drag) return;
      if (st.hover) { st.hover = null; st.dirty = true; render(); }
      canvas.style.cursor = 'default';
    }

    function onDbl(ev) {
      var pt = localPoint(ev);
      var hit = hitTest(pt);
      if (!hit || hit.kind !== 'handle') return;
      ev.preventDefault();
      var hd = handleById(hit.id);
      if (!hd) return;
      for (var i = 0; i < hd.addrs.length; i++) params.reset(hd.addrs[i]);
      st.dirty = true;
      render();
    }

    canvas.addEventListener('pointerdown', onDown);
    canvas.addEventListener('pointermove', onMove);
    canvas.addEventListener('pointerup', onUp);
    canvas.addEventListener('pointercancel', onUp);
    canvas.addEventListener('pointerleave', onLeave);
    canvas.addEventListener('dblclick', onDbl);

    /* ------------------------------------------------------ subscriptions */
    function relevant(addr) {
      if (st.mode.indexOf('osc') === 0) {
        return addr.indexOf('osc.' + st.mode.charAt(3).toLowerCase() + '.env.') === 0;
      }
      if (st.mode === 'filter') return addr.indexOf('filter.') === 0;
      if (st.mode === 'lfo') return addr.indexOf('lfo.') === 0;
      if (st.mode === 'pitch') return addr.indexOf('pitch.') === 0;
      if (st.mode === 'global') return addr === 'global.algorithm';
      return false;
    }

    st.unsubs.push(params.onAny(function (addr) {
      if (st.dead) return;
      if (!relevant(addr)) return;
      st.dirty = true;
      render();
    }));

    /* Follow ui.selected when the tree carries it, so the display can never
       show a section other than the selected one. Explicit setMode still works
       and remains the documented entry point for the assembler. */
    var hasSelected = false;
    if (typeof params.list === 'function') {
      var ui = params.list('ui.');
      hasSelected = !!ui && ui.indexOf('ui.selected') >= 0;
    }
    if (hasSelected) {
      st.mode = normalizeMode(enumStr('ui.selected'));
      st.unsubs.push(params.subscribe('ui.selected', function () {
        if (st.dead) return;
        setMode(enumStr('ui.selected'));
      }));
    }

    /* -------------------------------------------------------------- API */
    function setMode(section) {
      var m = normalizeMode(section);
      if (m === st.mode) { st.dirty = true; render(); return; }
      st.mode = m;
      st.drag = null;
      st.hover = null;
      st.handles = [];
      st.cells = [];
      canvas.style.cursor = 'default';
      st.dirty = true;
      render();
    }

    function draw(tMs) {
      if (st.dead) return;
      console.assert(typeof tMs === 'number' && isFinite(tMs),
        'OpDisplay.draw(tMs): a finite millisecond timestamp is required');
      if (typeof tMs === 'number' && isFinite(tMs)) st.lastT = tMs;
      /* only the LFO scope animates; everything else repaints on change */
      if (st.mode === 'lfo' || st.dirty) render();
    }

    function destroy() {
      st.dead = true;
      for (var i = 0; i < st.unsubs.length; i++) {
        if (typeof st.unsubs[i] === 'function') st.unsubs[i]();
      }
      st.unsubs = [];
      canvas.removeEventListener('pointerdown', onDown);
      canvas.removeEventListener('pointermove', onMove);
      canvas.removeEventListener('pointerup', onUp);
      canvas.removeEventListener('pointercancel', onUp);
      canvas.removeEventListener('pointerleave', onLeave);
      canvas.removeEventListener('dblclick', onDbl);
    }

    render();

    return { setMode: setMode, draw: draw, destroy: destroy };
  }

  function normalizeMode(section) {
    var key = String(section).toLowerCase().replace(/[\s_-]/g, '');
    var m = MODE_BY_KEY[key];
    if (!m) {
      throw new Error('OpDisplay: unknown display section "' + section +
        '" (expected one of ' + MODES.join(', ') + ')');
    }
    return m;
  }

  window.OpDisplay = { create: create, MODES: MODES.slice() };
}());
