/* Operator replica — window.OpParams
 * The single source of truth: flat map of address -> parameter descriptor + value.
 * Contract: spec/contract.md section 1 (tree), section 2 (descriptor), section 5 (binding).
 * No modules, no imports, no external resources. One IIFE, strict mode.
 */
(function () {
  'use strict';

  /* ---------------------------------------------------------------- utils */

  /* Fail loud: assert() records the invariant on the console AND throws, so a
   * violated invariant can never pass as a green result (FAIL-NOT-SKIP). */
  function assert(cond, msg) {
    console.assert(cond, msg);
    if (!cond) { throw new Error('OpParams invariant: ' + msg); }
    return cond;
  }

  var DB_FLOOR = -70;                                   /* dB <= -70 reads -inf */
  var KINDS = ['float', 'int', 'bool', 'enum', 'db', 'ms', 'hz', 'pct', 'st'];
  var INT_KINDS = { int: true, pct: true, st: true };   /* coerced to integers */

  function isKind(k) { return KINDS.indexOf(k) >= 0; }

  /* 3 significant digits, fixed-point, never exponential.
   * >=100 -> 0 decimals ("468"), >=10 -> 1 ("15.7"), <10 -> 2 ("8.61", "0.02"). */
  function sig3(v) {
    var a = Math.abs(v);
    var d = a >= 100 ? 0 : (a >= 10 ? 1 : 2);
    var s = v.toFixed(d);
    if (parseFloat(s) === 0) { s = (0).toFixed(d); }    /* kill "-0.00" */
    return s;
  }

  function fmtDb(v) {
    if (v <= DB_FLOOR) { return '-inf dB'; }
    return (Math.abs(v) < 0.05 ? '0.0' : v.toFixed(1)) + ' dB';
  }
  function fmtHz(v) {
    return v >= 1000 ? sig3(v / 1000) + ' kHz' : sig3(v) + ' Hz';
  }
  function fmtMs(v) { return v >= 1000 ? sig3(v / 1000) + ' s' : sig3(v) + ' ms'; }
  function fmtPct(v) { return String(Math.round(v)) + ' %'; }
  function fmtSt(v) { return String(Math.round(v)) + ' st'; }
  function fmtInt(v) { return String(Math.round(v)); }
  function fmtFloat(v) { return sig3(v); }
  function fmtBool(v) { return v ? 'On' : 'Off'; }
  function fmtEnum(v) { return String(v); }
  function fmtRate(v) { return v.toFixed(2); }          /* LFO rate: 2 decimals, no unit */

  function defaultFmt(kind) {
    switch (kind) {
      case 'db': return fmtDb;
      case 'hz': return fmtHz;
      case 'ms': return fmtMs;
      case 'pct': return fmtPct;
      case 'st': return fmtSt;
      case 'int': return fmtInt;
      case 'bool': return fmtBool;
      case 'enum': return fmtEnum;
      default: return fmtFloat;
    }
  }

  /* ------------------------------------------------------------- registry */

  var descs = Object.create(null);   /* addr -> frozen descriptor */
  var values = Object.create(null);  /* addr -> current value */
  var order = [];                    /* definition order, drives list() */
  var subs = Object.create(null);    /* addr -> [fn]  */
  var anySubs = [];                  /* [fn] */

  /* Define one parameter.
   * spec: {min,max,taper,def,enum,fmt,dragScale} — everything optional per kind. */
  function P(addr, label, kind, spec) {
    spec = spec || {};
    assert(typeof addr === 'string' && addr.length > 0, 'address must be a non-empty string');
    assert(!descs[addr], 'duplicate address ' + addr);
    assert(isKind(kind), 'unknown kind "' + kind + '" for ' + addr);

    var d = {
      addr: addr,
      label: label,
      kind: kind,
      min: 0,
      max: 1,
      taper: spec.taper || 'lin',
      def: undefined,
      enum: undefined,
      fmt: spec.fmt || defaultFmt(kind),
      dragScale: 0
    };

    if (kind === 'bool') {
      d.min = 0; d.max = 1;
      d.def = spec.def === true;
      d.dragScale = 1;
    } else if (kind === 'enum') {
      assert(Object.prototype.toString.call(spec.enum) === '[object Array]' && spec.enum.length > 0,
        'enum parameter ' + addr + ' needs a non-empty enum list');
      d.enum = spec.enum.slice();
      d.min = 0; d.max = d.enum.length - 1;
      d.def = spec.def === undefined ? d.enum[0] : spec.def;
      assert(d.enum.indexOf(d.def) >= 0, 'default "' + d.def + '" not in enum of ' + addr);
      d.dragScale = Math.max(1, d.enum.length - 1);
      Object.freeze(d.enum);
    } else {
      assert(typeof spec.min === 'number' && typeof spec.max === 'number',
        'numeric parameter ' + addr + ' needs min and max');
      assert(spec.max > spec.min, 'max must exceed min for ' + addr);
      d.min = spec.min; d.max = spec.max;
      d.def = spec.def === undefined ? spec.min : spec.def;
      assert(d.def >= d.min && d.def <= d.max, 'default ' + d.def + ' out of range for ' + addr);
      assert(d.taper === 'lin' || d.taper === 'log', 'unknown taper "' + d.taper + '" for ' + addr);
      /* A log taper is undefined through zero; every log parameter here has min > 0. */
      assert(d.taper !== 'log' || d.min > 0, 'log taper needs min > 0 for ' + addr);
      if (INT_KINDS[kind]) {
        assert(d.def === Math.round(d.def), 'int-kind default must be integral for ' + addr);
      }
      /* dragScale = value units per 200 px = full range. Log params must be
       * dragged through fromNorm/toNorm; dragScale is kept for descriptor shape. */
      d.dragScale = spec.dragScale === undefined ? (d.max - d.min) : spec.dragScale;
    }

    assert(typeof d.fmt === 'function', 'fmt must be a function for ' + addr);

    /* The brief names this field `def`; contract section 2 writes `default`.
     * Both are exposed, always equal, so neither reader gets undefined. */
    d['default'] = d.def;

    Object.freeze(d);
    descs[addr] = d;
    values[addr] = d.def;
    order.push(addr);
    return d;
  }

  /* ---------------------------------------------------------------- tree */

  var WAVES = ['Sine', 'Sin 3', 'Sin 4', 'Sin 6', 'Sin 8', 'Saw D', 'Square D', 'Triangle', 'Noise'];
  var LOOPS = ['None', 'Trigger', 'Loop', 'Beat', 'Sync'];
  var OSCS = ['a', 'b', 'c', 'd'];
  var LEVEL_DEF = { a: -5.4, b: -5.9, c: -14, d: DB_FLOOR };

  (function buildOscillators() {
    for (var i = 0; i < OSCS.length; i++) {
      var x = OSCS[i];
      var X = x.toUpperCase();
      var p = 'osc.' + x + '.';

      P(p + 'on', 'Osc ' + X, 'bool', { def: true });
      P(p + 'coarse', 'Coarse', 'int', { min: 0, max: 48, def: 1 });
      P(p + 'fine', 'Fine', 'int', { min: 0, max: 1000, def: 0 });
      P(p + 'fixed', 'Fixed', 'bool', { def: false });
      P(p + 'freq', 'Freq', 'hz', { min: 0.1, max: 1000, def: 440, taper: 'log' });
      P(p + 'multi', 'Multi', 'float', { min: 0.1, max: 1000, def: 0.1, taper: 'log' });
      P(p + 'level', 'Level', 'db', { min: DB_FLOOR, max: 0, def: LEVEL_DEF[x] });
      P(p + 'wave', 'Wave', 'enum', { enum: WAVES, def: 'Sine' });
      P(p + 'feedback', 'Feedback', 'pct', { min: 0, max: 100, def: 0 });
      P(p + 'phase', 'Phase', 'pct', { min: 0, max: 100, def: 0 });
      P(p + 'retrig', 'R', 'bool', { def: true });
      P(p + 'oscVel', 'Osc<Vel', 'int', { min: -48, max: 48, def: 0 });
      P(p + 'oscVelQ', 'Q', 'bool', { def: true });

      var e = p + 'env.';
      P(e + 'attack', 'Attack', 'ms', { min: 0.02, max: 10000, def: 0.02, taper: 'log' });
      P(e + 'decay', 'Decay', 'ms', { min: 1, max: 30000, def: 15.7, taper: 'log' });
      P(e + 'release', 'Release', 'ms', { min: 1, max: 30000, def: 50, taper: 'log' });
      P(e + 'initial', 'Initial', 'db', { min: DB_FLOOR, max: 0, def: DB_FLOOR });
      P(e + 'peak', 'Peak', 'db', { min: DB_FLOOR, max: 0, def: 0 });
      P(e + 'sustain', 'Sustain', 'db', { min: DB_FLOOR, max: 0, def: DB_FLOOR });
      P(e + 'timeVel', 'Time<Vel', 'pct', { min: 0, max: 100, def: 0 });
      P(e + 'vel', 'Vel', 'pct', { min: -100, max: 100, def: 0 });
      P(e + 'loop', 'Loop', 'enum', { enum: LOOPS, def: 'None' });
      P(e + 'key', 'Key', 'pct', { min: 0, max: 100, def: 0 });
    }
  }());

  P('lfo.on', 'LFO', 'bool', { def: false });
  P('lfo.wave', 'Wave', 'enum', { enum: ['Sine', 'Square', 'Triangle', 'Saw', 'Noise'], def: 'Sine' });
  P('lfo.dest', 'Dest', 'enum', { enum: ['L', 'A', 'B', 'C', 'D', 'Filter', 'Pitch'], def: 'L' });
  P('lfo.retrig', 'R', 'bool', { def: false });
  P('lfo.rate', 'Rate', 'float', { min: 0.01, max: 100, def: 6, taper: 'log', fmt: fmtRate });
  P('lfo.amount', 'Amount', 'pct', { min: 0, max: 100, def: 25 });

  P('filter.on', 'Filter', 'bool', { def: true });
  P('filter.type', 'Type', 'enum', { enum: ['LP', 'HP', 'BP', 'Notch'], def: 'LP' });
  P('filter.slope', 'Slope', 'enum', { enum: ['12', '24'], def: '24' });
  P('filter.circuit', 'Circuit', 'enum', { enum: ['Clean', 'OSR'], def: 'Clean' });
  P('filter.freq', 'Freq', 'hz', { min: 30, max: 20000, def: 8610, taper: 'log' });
  P('filter.res', 'Res', 'pct', { min: 0, max: 125, def: 20 });

  P('pitch.on', 'Pitch', 'bool', { def: true });
  P('pitch.env', 'Pitch Env', 'pct', { min: -100, max: 100, def: 81 });
  P('pitch.spread', 'Spread', 'pct', { min: 0, max: 100, def: 0 });
  P('pitch.transpose', 'Transpose', 'st', { min: -48, max: 48, def: 0 });

  /* global.algorithm stores an int 0..3 (four routing diagrams, contract section 4). */
  P('global.algorithm', 'Algorithm', 'int', { min: 0, max: 3, def: 0 });
  P('global.time', 'Time', 'pct', { min: -100, max: 100, def: 0 });
  P('global.tone', 'Tone', 'pct', { min: 0, max: 100, def: 70 });
  P('global.volume', 'Volume', 'db', { min: DB_FLOOR, max: 0, def: 0 });

  P('ui.selected', 'Selected', 'enum', {
    enum: ['oscA', 'oscB', 'oscC', 'oscD', 'lfo', 'filter', 'pitch', 'global'],
    def: 'oscB'
  });

  /* ------------------------------------------------------------- lookups */

  function must(addr) {
    var d = descs[addr];
    console.assert(!!d, 'OpParams: unknown parameter address "' + addr + '"');
    if (!d) { throw new Error('OpParams: unknown parameter address "' + addr + '"'); }
    return d;
  }

  function clamp(v, lo, hi) { return v < lo ? lo : (v > hi ? hi : v); }

  function coerce(d, value) {
    if (d.kind === 'bool') {
      if (typeof value === 'boolean') { return value; }
      if (typeof value === 'number') {
        if (!isFinite(value)) { throw new Error('OpParams: non-finite bool for ' + d.addr); }
        return value !== 0;
      }
      if (value === 'true' || value === 'on') { return true; }
      if (value === 'false' || value === 'off') { return false; }
      throw new Error('OpParams: cannot coerce ' + JSON.stringify(value) + ' to bool for ' + d.addr);
    }

    if (d.kind === 'enum') {
      if (typeof value === 'number') {                      /* index form (wheel/drag) */
        if (!isFinite(value)) { throw new Error('OpParams: non-finite enum index for ' + d.addr); }
        return d.enum[clamp(Math.round(value), 0, d.enum.length - 1)];
      }
      if (typeof value === 'string' && d.enum.indexOf(value) >= 0) { return value; }
      throw new Error('OpParams: value ' + JSON.stringify(value) + ' is not a member of ' +
        d.addr + ' enum [' + d.enum.join(', ') + ']');
    }

    var n = value;
    if (typeof n === 'string' && n.trim() !== '') { n = Number(n); }
    if (typeof n === 'boolean') { n = n ? 1 : 0; }
    if (typeof n !== 'number' || (isNaN(n))) {
      throw new Error('OpParams: cannot coerce ' + JSON.stringify(value) + ' to a number for ' + d.addr);
    }
    if (n === -Infinity) {
      /* -inf dB is a legal way to say "silence"; it lands on the floor. */
      if (d.kind !== 'db') { throw new Error('OpParams: -Infinity is only valid for dB, not ' + d.addr); }
      n = d.min;
    }
    if (!isFinite(n)) { throw new Error('OpParams: non-finite value for ' + d.addr); }
    n = clamp(n, d.min, d.max);
    if (INT_KINDS[d.kind]) { n = clamp(Math.round(n), d.min, d.max); }
    return n;
  }

  /* --------------------------------------------------------- notification */

  function notify(addr, value) {
    var list = subs[addr];
    if (list && list.length) {
      var copy = list.slice();                              /* reentrancy-safe */
      for (var i = 0; i < copy.length; i++) { copy[i](value, addr); }
    }
    if (anySubs.length) {
      var any = anySubs.slice();
      for (var j = 0; j < any.length; j++) { any[j](addr, value); }
    }
  }

  /* ----------------------------------------------------------------- API */

  function desc(addr) { return must(addr); }

  function get(addr) { must(addr); return values[addr]; }

  function set(addr, value) {
    var d = must(addr);
    var next = coerce(d, value);
    if (values[addr] === next) { return next; }             /* no-op: no repaint storm */
    values[addr] = next;
    notify(addr, next);
    return next;
  }

  function reset(addr) { return set(addr, must(addr).def); }

  function resetAll() {
    for (var i = 0; i < order.length; i++) { reset(order[i]); }
  }

  function subscribe(addr, fn) {
    must(addr);
    assert(typeof fn === 'function', 'subscribe(' + addr + ') needs a function');
    if (!subs[addr]) { subs[addr] = []; }
    var list = subs[addr];
    list.push(fn);
    var live = true;
    return function unsubscribe() {
      if (!live) { return; }
      live = false;
      var i = list.indexOf(fn);
      if (i >= 0) { list.splice(i, 1); }
    };
  }

  function onAny(fn) {
    assert(typeof fn === 'function', 'onAny needs a function');
    anySubs.push(fn);
    var live = true;
    return function unsubscribe() {
      if (!live) { return; }
      live = false;
      var i = anySubs.indexOf(fn);
      if (i >= 0) { anySubs.splice(i, 1); }
    };
  }

  function list(prefix) {
    if (prefix === undefined || prefix === null || prefix === '') { return order.slice(); }
    assert(typeof prefix === 'string', 'list(prefix) needs a string');
    var out = [];
    for (var i = 0; i < order.length; i++) {
      if (order[i].lastIndexOf(prefix, 0) === 0) { out.push(order[i]); }
    }
    return out;
  }

  function fmt(addr) {
    var d = must(addr);
    return d.fmt(values[addr]);
  }

  /* Taper mapping — the drag/knob geometry both live here so the three UI
   * modules cannot drift apart on it. 0..1 is the knob/drag domain. */
  function toNorm(addr, v) {
    var d = must(addr);
    if (v === undefined) { v = values[addr]; }
    if (d.kind === 'bool') { return v ? 1 : 0; }
    if (d.kind === 'enum') {
      var i = d.enum.indexOf(v);
      assert(i >= 0, 'toNorm: "' + v + '" is not a member of ' + addr);
      return d.enum.length < 2 ? 0 : i / (d.enum.length - 1);
    }
    var n = clamp(Number(v), d.min, d.max);
    if (d.taper === 'log') { return Math.log(n / d.min) / Math.log(d.max / d.min); }
    return (n - d.min) / (d.max - d.min);
  }

  function fromNorm(addr, t) {
    var d = must(addr);
    t = clamp(Number(t), 0, 1);
    if (isNaN(t)) { throw new Error('OpParams: fromNorm needs a number for ' + addr); }
    if (d.kind === 'bool') { return t >= 0.5; }
    if (d.kind === 'enum') { return d.enum[Math.round(t * (d.enum.length - 1))]; }
    var v = d.taper === 'log'
      ? d.min * Math.pow(d.max / d.min, t)
      : d.min + t * (d.max - d.min);
    v = clamp(v, d.min, d.max);
    if (INT_KINDS[d.kind]) { v = clamp(Math.round(v), d.min, d.max); }
    return v;
  }

  /* Wheel step, contract section 5.4: int +/-1, float 1/100 of range (through
   * the taper), enum next/previous (clamped, no wrap), bool toggles. */
  function step(addr, dir) {
    var d = must(addr);
    var s = dir < 0 ? -1 : 1;
    if (d.kind === 'bool') { return set(addr, !values[addr]); }
    if (d.kind === 'enum') { return set(addr, clamp(d.enum.indexOf(values[addr]) + s, 0, d.enum.length - 1)); }
    if (INT_KINDS[d.kind]) { return set(addr, values[addr] + s); }
    return set(addr, fromNorm(addr, toNorm(addr, values[addr]) + s * 0.01));
  }

  var OpParams = {
    desc: desc,
    get: get,
    set: set,
    reset: reset,
    resetAll: resetAll,
    subscribe: subscribe,
    onAny: onAny,
    list: list,
    fmt: fmt,
    /* additive helpers (not in the contract's minimum surface, safe to ignore) */
    toNorm: toNorm,
    fromNorm: fromNorm,
    step: step,
    DB_FLOOR: DB_FLOOR
  };

  if (typeof window !== 'undefined') {
    window.OpParams = OpParams;
    return;
  }

  /* ---------------------------------------------------- node self-test ---- */

  var checks = 0;
  function ok(cond, msg) {
    checks++;
    if (!cond) { throw new Error('FAIL: ' + msg); }
  }
  function eq(actual, expected, msg) {
    checks++;
    if (actual !== expected) {
      throw new Error('FAIL: ' + msg + ' — expected ' + JSON.stringify(expected) +
        ', got ' + JSON.stringify(actual));
    }
  }
  function near(actual, expected, tol, msg) {
    checks++;
    if (!(Math.abs(actual - expected) <= tol)) {
      throw new Error('FAIL: ' + msg + ' — expected ~' + expected + ', got ' + actual);
    }
  }
  function throws(fn, msg) {
    checks++;
    var threw = false;
    try { fn(); } catch (e) { threw = true; }
    if (!threw) { throw new Error('FAIL: expected a throw — ' + msg); }
  }

  /* --- tree completeness ------------------------------------------------- */
  /* 4 osc x (14 row + 10 env) + 6 lfo + 6 filter + 4 pitch + 5 global + 1 ui */
  eq(list().length, 113, 'total address count');
  eq(list('osc.a.env.').length, 10, 'osc.a envelope address count');
  eq(list('osc.').length, 92, 'oscillator address count');
  eq(list('global.').length, 4, 'global address count');
  eq(list('nope.').length, 0, 'unknown prefix yields no addresses');
  eq(get('ui.selected'), 'oscB', 'ui.selected default');
  eq(get('global.tone'), 70, 'global.tone default');
  eq(get('global.algorithm'), 0, 'global.algorithm default is int 0');

  /* --- descriptor invariants over the whole tree -------------------------- */
  (function () {
    var all = list();
    for (var i = 0; i < all.length; i++) {
      var a = all[i], d = desc(a);
      ok(d.addr === a, 'descriptor addr matches key for ' + a);
      ok(typeof d.label === 'string' && d.label.length > 0, 'label present for ' + a);
      ok(KINDS.indexOf(d.kind) >= 0, 'kind valid for ' + a);
      ok(d.taper === 'lin' || d.taper === 'log', 'taper valid for ' + a);
      ok(typeof d.fmt(get(a)) === 'string', 'fmt returns a string for ' + a);
      ok(d.def !== undefined, 'default present for ' + a);
      ok(d['default'] === d.def, 'def and default aliases agree for ' + a);
      ok(Object.isFrozen(d), 'descriptor frozen for ' + a);
      if (d.kind === 'enum') { ok(d.enum.indexOf(d.def) >= 0, 'enum default member for ' + a); }
      if (d.taper === 'log') { ok(d.min > 0, 'log min > 0 for ' + a); }
    }
  }());

  /* --- formatters --------------------------------------------------------- */
  eq(fmt('filter.freq'), '8.61 kHz', 'filter freq default format');
  set('filter.freq', 468); eq(fmt('filter.freq'), '468 Hz', 'sub-kHz format');
  set('filter.freq', 30); eq(fmt('filter.freq'), '30.0 Hz', '3 significant digits at 30 Hz');
  set('filter.freq', 20000); eq(fmt('filter.freq'), '20.0 kHz', 'top of filter range');
  reset('filter.freq');

  eq(fmt('osc.a.level'), '-5.4 dB', 'osc A level default');
  eq(fmt('osc.b.level'), '-5.9 dB', 'osc B level default');
  eq(fmt('osc.c.level'), '-14.0 dB', 'osc C level default (one decimal)');
  eq(fmt('osc.d.level'), '-inf dB', 'osc D level default is -inf');
  eq(fmt('global.volume'), '0.0 dB', 'volume default 0.0 dB');
  set('osc.a.level', -70.0001); eq(fmt('osc.a.level'), '-inf dB', '-inf floor at -70');
  set('osc.a.level', -69.9); eq(fmt('osc.a.level'), '-69.9 dB', 'just above the floor');
  set('osc.a.level', -0.02); eq(fmt('osc.a.level'), '0.0 dB', 'no "-0.0 dB"');
  reset('osc.a.level');

  eq(fmt('osc.b.env.attack'), '0.02 ms', 'attack default');
  eq(fmt('osc.b.env.decay'), '15.7 ms', 'decay default');
  eq(fmt('osc.b.env.release'), '50.0 ms', 'release default');
  set('osc.b.env.decay', 30000); eq(fmt('osc.b.env.decay'), '30.0 s', 'long decay');
  reset('osc.b.env.decay');

  eq(fmt('osc.b.env.timeVel'), '0 %', 'percent format');
  eq(fmt('pitch.env'), '81 %', 'pitch env percent');
  eq(fmt('filter.res'), '20 %', 'resonance percent');
  eq(fmt('pitch.transpose'), '0 st', 'semitone format');
  eq(fmt('lfo.rate'), '6.00', 'LFO rate: 2 decimals, no unit');
  set('lfo.rate', 64); eq(fmt('lfo.rate'), '64.00', 'LFO rate 64.00');
  reset('lfo.rate');
  eq(fmt('osc.a.coarse'), '1', 'int format has no unit');
  eq(fmt('osc.a.oscVel'), '0', 'osc<vel int format');
  eq(fmt('osc.a.wave'), 'Sine', 'enum format is the value');
  eq(fmt('osc.a.on'), 'On', 'bool format');
  eq(fmt('lfo.on'), 'Off', 'bool format off');
  eq(fmt('osc.b.multi'), '0.10', 'multi float format (3 significant digits)');

  /* --- clamping and coercion --------------------------------------------- */
  eq(set('osc.a.coarse', 999), 48, 'clamp above max');
  eq(set('osc.a.coarse', -5), 0, 'clamp below min');
  eq(set('osc.a.fine', 12.7), 13, 'int kind rounds');
  eq(set('osc.a.feedback', 33.4), 33, 'pct kind rounds');
  eq(set('pitch.transpose', -3.5), -3, 'st kind rounds (Math.round: halves go toward +inf)');
  eq(set('filter.res', 130), 125, 'resonance clamps at 125');
  eq(set('global.time', -500), -100, 'bipolar percent clamps');
  eq(set('global.tone', 999), 100, 'tone clamp to 100');
  eq(set('global.tone', -5), 0, 'tone clamp to 0');
  eq(set('global.tone', 70), 70, 'tone restore');
  eq(set('osc.d.level', -Infinity), DB_FLOOR, '-Infinity lands on the dB floor');
  eq(set('osc.a.coarse', '7'), 7, 'numeric string coerces');
  eq(set('osc.a.on', 0), false, 'bool coerces from 0');
  eq(set('osc.a.on', 1), true, 'bool coerces from 1');
  eq(set('lfo.wave', 2), 'Triangle', 'enum coerces from index');
  eq(set('lfo.wave', 99), 'Noise', 'enum index clamps to last');
  eq(set('lfo.wave', 'Square'), 'Square', 'enum accepts a member string');
  throws(function () { set('lfo.wave', 'Ramp'); }, 'non-member enum string must throw');
  throws(function () { set('osc.a.coarse', 'banana'); }, 'non-numeric string must throw');
  throws(function () { set('osc.a.coarse', NaN); }, 'NaN must throw');
  throws(function () { set('osc.a.coarse', Infinity); }, '+Infinity must throw');
  throws(function () { set('osc.a.coarse', -Infinity); }, '-Infinity on a non-dB must throw');
  resetAll();
  eq(get('osc.a.coarse'), 1, 'resetAll restores defaults');
  eq(get('lfo.wave'), 'Sine', 'resetAll restores enum defaults');

  /* --- taper mapping ------------------------------------------------------ */
  eq(fromNorm('global.tone', 0), 0, 'lin taper bottom');
  eq(fromNorm('global.tone', 1), 100, 'lin taper top');
  eq(fromNorm('global.tone', 0.5), 50, 'lin taper midpoint');
  eq(fromNorm('global.time', 0.5), 0, 'bipolar lin midpoint');
  near(fromNorm('filter.freq', 0), 30, 1e-9, 'log taper bottom');
  near(fromNorm('filter.freq', 1), 20000, 1e-9, 'log taper top');
  near(fromNorm('filter.freq', 0.5), Math.sqrt(30 * 20000), 1e-6, 'log taper is geometric at midpoint');
  near(toNorm('filter.freq', 8610), Math.log(8610 / 30) / Math.log(20000 / 30), 1e-12, 'toNorm log');
  near(toNorm('filter.freq', fromNorm('filter.freq', 0.37)), 0.37, 1e-12, 'log round trip');
  near(toNorm('osc.a.env.attack', fromNorm('osc.a.env.attack', 0.8)), 0.8, 1e-12, 'attack round trip');
  eq(toNorm('osc.d.level'), 0, 'toNorm reads the current value when v is omitted');
  eq(toNorm('global.volume'), 1, 'volume default sits at the top of its range');
  eq(fromNorm('filter.slope', 1), '24', 'enum fromNorm');
  eq(toNorm('filter.slope', '12'), 0, 'enum toNorm');
  eq(fromNorm('filter.freq', -3), 30, 'fromNorm clamps below 0');
  eq(fromNorm('filter.freq', 7), 20000, 'fromNorm clamps above 1');
  eq(desc('global.tone').dragScale, 100, 'dragScale is the full range per 200 px');

  /* --- wheel step --------------------------------------------------------- */
  eq(step('osc.a.coarse', +1), 2, 'int steps by one');
  eq(step('osc.a.coarse', -1), 1, 'int steps back');
  eq(step('lfo.wave', +1), 'Square', 'enum steps to the next member');
  set('lfo.wave', 'Noise'); eq(step('lfo.wave', +1), 'Noise', 'enum step clamps, never wraps');
  reset('lfo.wave');
  eq(step('lfo.on', +1), true, 'bool step toggles');
  reset('lfo.on');
  ok(step('filter.freq', +1) > 8610, 'float step moves up through the taper');
  reset('filter.freq');

  /* --- subscribe / unsubscribe / onAny ------------------------------------ */
  (function () {
    var seen = [], anySeen = [];
    var off = subscribe('filter.freq', function (v, a) { seen.push(a + '=' + v); });
    var offAny = onAny(function (a, v) { anySeen.push(a + '=' + v); });

    set('filter.freq', 1000);
    eq(seen.length, 1, 'per-address subscriber fired once');
    eq(seen[0], 'filter.freq=1000', 'subscriber receives (value, addr)');
    eq(anySeen.length, 1, 'onAny fired once');
    eq(anySeen[0], 'filter.freq=1000', 'onAny receives (addr, value)');

    set('filter.freq', 1000);
    eq(seen.length, 1, 'setting the same value notifies nobody');

    set('global.tone', 42);
    eq(seen.length, 1, 'per-address subscriber ignores other addresses');
    eq(anySeen.length, 2, 'onAny sees every address');

    off();
    set('filter.freq', 2000);
    eq(seen.length, 1, 'unsubscribe stops delivery');
    eq(anySeen.length, 3, 'onAny still live after the per-address unsubscribe');
    off();                                             /* idempotent */

    offAny();
    set('filter.freq', 3000);
    eq(anySeen.length, 3, 'onAny unsubscribe stops delivery');

    /* a subscriber added during a notification must not receive that same event */
    var late = 0, offOuter, offLate;
    offOuter = subscribe('global.tone', function () {
      offLate = subscribe('global.tone', function () { late++; });
    });
    set('global.tone', 43);
    eq(late, 0, 'reentrant subscribe does not receive the in-flight event');
    offOuter(); if (offLate) { offLate(); }
    resetAll();
  }());

  /* --- unknown address is loud everywhere --------------------------------- */
  (function () {
    var bad = ['osc.e.level', 'osc.a.nope', 'lfo.rat', '', 'filter', 'osc.a.env'];
    for (var i = 0; i < bad.length; i++) {
      (function (a) {
        throws(function () { get(a); }, 'get(' + JSON.stringify(a) + ')');
        throws(function () { set(a, 1); }, 'set(' + JSON.stringify(a) + ')');
        throws(function () { desc(a); }, 'desc(' + JSON.stringify(a) + ')');
        throws(function () { fmt(a); }, 'fmt(' + JSON.stringify(a) + ')');
        throws(function () { reset(a); }, 'reset(' + JSON.stringify(a) + ')');
        throws(function () { subscribe(a, function () {}); }, 'subscribe(' + JSON.stringify(a) + ')');
        throws(function () { toNorm(a, 1); }, 'toNorm(' + JSON.stringify(a) + ')');
        throws(function () { fromNorm(a, 1); }, 'fromNorm(' + JSON.stringify(a) + ')');
      }(bad[i]));
    }
    throws(function () { subscribe('lfo.rate', 'not a function'); }, 'subscribe needs a function');
    throws(function () { onAny(null); }, 'onAny needs a function');
  }());

  /* --- descriptors are immutable ------------------------------------------ */
  throws(function () { desc('filter.freq').min = 1; }, 'frozen descriptor rejects mutation');

  /* --- the self-test can fail (proof the assertions are load-bearing) ------ */
  throws(function () { eq(1, 2, 'deliberate'); }, 'eq() itself throws on mismatch');

  console.log('PASS — OpParams: ' + checks + ' assertions over ' + list().length +
    ' parameters (' + list('osc.').length + ' oscillator, ' +
    list('lfo.').length + ' lfo, ' + list('filter.').length + ' filter, ' +
    list('pitch.').length + ' pitch, ' + list('global.').length + ' global, ' +
    list('ui.').length + ' ui).');
}());
