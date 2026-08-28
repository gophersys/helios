/* =============================================================================
   engine.js  —  window.OpEngine
   Web Audio FM engine for the Operator replica (contract.md section 4).

   Public surface (the ONLY global this file attaches):
     OpEngine.bind(OpParams)      subscribe onAny once; validates the tree
     OpEngine.noteOn(midi, vel)   lazily creates the AudioContext (autoplay policy)
     OpEngine.noteOff(midi)
     OpEngine.meterLevel()        0..1 smoothed RMS; 0 before init
     OpEngine.allNotesOff()       convenience panic (extra, additive)
     OpEngine.ALGORITHMS          frozen routing table (see ROUTING below)
     OpEngine.filterQ(res)        res% -> biquad Q, so the display can mirror it

   -----------------------------------------------------------------------------
   SIGNAL PATH
     per voice:  4 ops [ source -> envGain(0..1) -> levelGain(dB x vel) ]
                 modulators: levelGain -> edgeGain -> carrier source.frequency
                 carriers:   levelGain -> carrierGain -> voiceMix
                 voiceMix -> shaper(OSR) -> biquad1 -> biquad2 -> amp -> panner
     master:     bus -> tone(one-pole-ish LP) -> masterGain -> soft-clip
                 -> AnalyserNode -> destination

   POLYPHONY
     8 note slots. Each slot owns a VOICE PAIR (contract: spread = "per-voice
     detune/pan pair"); the two halves sit at -/+ spread cents and -/+ spread pan
     and each carries 0.5 gain, so spread = 0 sums back to exactly one voice.
     Allocation order: same-note retrigger -> free slot -> releasing slot with the
     earliest free time -> oldest sounding slot (stolen).

   -----------------------------------------------------------------------------
   LIVE vs NEXT NOTE-ON  (contract section 5 rule 8 — documented, not guessed)

   Applies LIVE while a note is held (Web Audio allows the rebind):
     osc.x.on, osc.x.level                 -> levelGain.gain (and LFO level depth)
     osc.x.coarse/fine/fixed/freq/multi    -> source.frequency + dependent FM index
     osc.x.oscVel, osc.x.oscVelQ           -> recomputed from the held velocity
     osc.x.wave                            -> setPeriodicWave / noise swap
     osc.x.feedback                        -> feedback gain
     osc.x.env.* (all ten)                 -> envelope re-applied from the current
                                              value at its current stage
     global.time                           -> same path as env.* (time re-scale)
     global.algorithm                      -> edge + carrier gains
     global.tone, global.volume            -> tone cutoff / master gain
     filter.on/type/slope/circuit/freq/res -> biquads, shaper (slope 12 parks the
                                              2nd stage in 'allpass' = no magnitude)
     lfo.on/wave/dest/rate/amount          -> LFO nodes + destination gains
     pitch.on, pitch.env                   -> pitch-envelope depth (cents)
     pitch.spread                          -> pair detune + pan
     pitch.transpose                       -> source.frequency

   Applies at the NEXT NOTE-ON only (physically impossible to rebind mid-note):
     osc.x.phase        start phase is baked into the PeriodicWave; a running
                        oscillator keeps its own phase accumulator. The waveform
                        SHAPE swaps live, the START PHASE cannot.
     osc.x.retrig       ditto (chooses baked phase vs. pseudo-random phase).
     lfo.retrig         decides whether note-on restarts the LFO phase.
     pitch envelope SHAPE (its fixed decay contour is scheduled at note-on;
                        its DEPTH is live).
   ============================================================================= */

(function () {
  'use strict';

  if (window.OpEngine) {
    throw new Error('OpEngine: global already defined (engine.js included twice)');
  }

  /* ---------------------------------------------------------------- constants */

  var OPS = ['a', 'b', 'c', 'd'];
  var IDX = { a: 0, b: 1, c: 2, d: 3 };

  var POLYPHONY = 8;          // note slots; each slot is a voice PAIR
  var PARTIALS = 64;          // harmonics in every PeriodicWave
  var DB_FLOOR = -70;         // contract: any dB <= -70 sounds as -inf
  var FM_DEPTH = 4.0;         // index = level x FM_DEPTH x carrier base freq
  var FB_DEPTH = 4.0;         // self-feedback index ceiling (x carrier base freq)
  var PITCH_ENV_CENTS = 1200; // pitch.env 100% = one octave
  var PITCH_ENV_DECAY = 0.25; // s, fixed contour (tree has no pitch env times)
  var LFO_PITCH_CENTS = 400;  // lfo dest Pitch, amount 100%
  var LFO_FILTER_CENTS = 2400;// lfo dest Filter, amount 100%
  var LFO_LEVEL_DEPTH = 0.5;  // lfo dest level: gain swings level x (1 +/- 0.5)
  var SPREAD_CENTS = 25;      // pitch.spread 100% = +/-25 cents
  var SPREAD_PAN = 0.9;       // pitch.spread 100% = +/-0.9 pan
  var ENV_TC = 4.6;           // setTargetAtTime tc = segment/4.6 -> ~1% residue
  var LOOP_HORIZON = 30;      // s of Loop-mode cycles scheduled at note-on
  var LOOP_MAX_CYCLES = 256;
  var VOICE_GAIN = 0.5;       // each half of the pair
  var BUS_HEADROOM = 0.5;
  var GLIDE = 0.004;          // s, note-on pre-roll (click-free steal)

  /* ROUTING — the 4 algorithms (contract section 4, ambiguity resolved in the
     report: algorithm 2 is read as "parallel pairs", i.e. two independent
     2-op stacks, which is the only reading that makes it distinct from 1). */
  var EDGE_KEYS = ['dc', 'cb', 'ba', 'db'];   // every edge any algorithm uses
  var ALGORITHMS = [
    { name: 'D>C>B>A serial', edges: ['dc', 'cb', 'ba'], carriers: ['a'] },
    { name: 'D>B, C>B, B>A',  edges: ['db', 'cb', 'ba'], carriers: ['a'] },
    { name: 'D>C, B>A pairs', edges: ['dc', 'ba'],       carriers: ['c', 'a'] },
    { name: 'A+B+C+D additive', edges: [],               carriers: ['a', 'b', 'c', 'd'] }
  ];
  (function freezeAlgs() {
    for (var i = 0; i < ALGORITHMS.length; i++) {
      Object.freeze(ALGORITHMS[i].edges);
      Object.freeze(ALGORITHMS[i].carriers);
      Object.freeze(ALGORITHMS[i]);
    }
    Object.freeze(ALGORITHMS);
  }());

  /* --------------------------------------------------------------- module state */

  var params = null;
  var unsubAny = null;

  var ctx = null;
  var bus = null, toneNode = null, masterGain = null, clipNode = null, analyser = null;
  var meterFloat = null, meterByte = null, meterUseFloat = true;
  var meterVal = 0, meterT = 0;

  var lfoNodes = null;          // { osc, oscGain, sh, shGain, out }
  var slots = [];               // POLYPHONY x { voices: [v-, v+], ... }
  var waveCache = null;         // key -> PeriodicWave
  var noiseBuffer = null;       // white noise, looped, for wave "Noise"
  var shNoiseBuffer = null;     // stepped random, for LFO wave "Noise"
  var osrCurve = null, clipCurve = null;

  var prng = 0x2f6e2b1;         // deterministic; never Date.now

  /* ------------------------------------------------------------- small helpers */

  function clamp(v, lo, hi) { return v < lo ? lo : (v > hi ? hi : v); }

  function rnd() {              // xorshift32 -> [0,1)
    prng ^= prng << 13; prng |= 0;
    prng ^= prng >>> 17;
    prng ^= prng << 5; prng |= 0;
    return ((prng >>> 0) / 4294967296);
  }

  function db2lin(db) {
    if (typeof db !== 'number' || Number.isNaN(db)) {
      throw new Error('OpEngine: dB value is not a number: ' + String(db));
    }
    if (db <= DB_FLOOR) return 0;
    return Math.pow(10, (db > 24 ? 24 : db) / 20);
  }

  function midiHz(m) { return 440 * Math.pow(2, (m - 69) / 12); }

  function cancelAndHold(param, t) {
    if (typeof param.cancelAndHoldAtTime === 'function') {
      param.cancelAndHoldAtTime(t);
    } else {
      var v = param.value;
      param.cancelScheduledValues(t);
      param.setValueAtTime(v, t);
    }
  }

  /* Exponential approach to `to`, snapped exactly at start+dur (the residue after
     4.6 time constants is ~1%, i.e. inaudible, and the snap keeps segment ends
     deterministic). Returns the segment end time. */
  function approach(param, to, start, dur) {
    if (dur <= 0.0005) { param.setValueAtTime(to, start); return start; }
    param.setTargetAtTime(to, start, dur / ENV_TC);
    param.setValueAtTime(to, start + dur);
    return start + dur;
  }

  /* ------------------------------------------------------- parameter tree access
     Every read goes through OpParams. Unknown addresses throw (fail loud);
     values are type-normalised because the tree may legitimately hold an enum
     as its string member or as its index. */

  function requireBound() {
    if (!params) {
      throw new Error('OpEngine: not bound — call OpEngine.bind(OpParams) first');
    }
  }

  function rawv(addr) {
    requireBound();
    var v = params.get(addr);            // OpParams throws on unknown addr
    console.assert(v !== undefined && v !== null, 'OpEngine: empty param', addr);
    if (v === undefined || v === null) {
      throw new Error('OpEngine: no value for parameter ' + addr);
    }
    return v;
  }

  function num(addr) {
    var v = rawv(addr);
    if (typeof v === 'number') {
      if (Number.isNaN(v)) throw new Error('OpEngine: NaN value for ' + addr);
      return v;
    }
    if (typeof v === 'boolean') return v ? 1 : 0;
    if (typeof v === 'string') {
      var s = v.trim().toLowerCase();
      if (s === '-inf' || s === '-infinity') return -Infinity;
      if (s === 'inf' || s === 'infinity') return Infinity;
      var n = parseFloat(s);
      if (!Number.isNaN(n)) return n;
    }
    throw new Error('OpEngine: non-numeric value for ' + addr + ': ' + String(v));
  }

  function bool(addr) {
    var v = rawv(addr);
    if (typeof v === 'boolean') return v;
    if (typeof v === 'number') return v !== 0;
    if (typeof v === 'string') {
      var s = v.trim().toLowerCase();
      if (s === 'true' || s === 'on' || s === '1' || s === 'yes') return true;
      if (s === 'false' || s === 'off' || s === '0' || s === 'no') return false;
    }
    throw new Error('OpEngine: non-boolean value for ' + addr + ': ' + String(v));
  }

  /* A range-guarded read. The tree clamps too, but a non-finite value
     reaching an AudioParam is a hard TypeError in the browser, and
     0 * Infinity is NaN — so every ranged read is re-clamped here. */
  function pct(addr, lo, hi) {
    var v = num(addr);
    if (!isFinite(v)) v = (v > 0) ? hi : lo;
    return clamp(v, lo, hi);
  }

  function enumOf(addr) {
    var v = rawv(addr);
    if (typeof v === 'string') return v;
    if (typeof v === 'number') {
      var d = params.desc(addr);
      var list = d && d.enum;
      if (list && list.length) {
        for (var i = 0; i < list.length; i++) {
          if (list[i] === v) return String(v);           // numeric member (12/24)
        }
        if (v >= 0 && v < list.length && v === Math.floor(v)) return String(list[v]);
      }
      return String(v);
    }
    throw new Error('OpEngine: non-enum value for ' + addr + ': ' + String(v));
  }

  function algIndex() {
    var v = rawv('global.algorithm');
    var n;
    if (typeof v === 'number') { n = Math.floor(v); }
    else {
      var m = /(\d+)/.exec(String(v));
      if (!m) throw new Error('OpEngine: cannot read global.algorithm: ' + String(v));
      n = parseInt(m[1], 10);
    }
    return clamp(n, 0, ALGORITHMS.length - 1);
  }

  /* ------------------------------------------------------------- wave selection */

  function waveKind(i) {
    var raw = enumOf('osc.' + OPS[i] + '.wave');
    var s = String(raw).toLowerCase().replace(/[\s_\-]/g, '');
    if (s.indexOf('noise') === 0) return { kind: 'noise', h: 1 };
    var m = /^sin(?:e)?(\d+)/.exec(s);
    if (m) return { kind: 'sinN', h: clamp(parseInt(m[1], 10), 1, PARTIALS) };
    if (s === 'sin' || s === 'sine') return { kind: 'sine', h: 1 };
    if (s.indexOf('saw') === 0) return { kind: 'saw', h: 1 };
    if (s.indexOf('squ') === 0) return { kind: 'square', h: 1 };
    if (s.indexOf('tri') === 0) return { kind: 'triangle', h: 1 };
    throw new Error('OpEngine: unknown waveform "' + raw + '" for osc.' + OPS[i]);
  }

  function getWave(kind, h, phase01) {
    var key = kind + h + '|' + Math.round(phase01 * 100);
    var cached = waveCache.get(key);
    if (cached) return cached;

    var n, N = PARTIALS;
    var real = new Float32Array(N + 1);
    var imag = new Float32Array(N + 1);

    if (kind === 'sine') {
      imag[1] = 1;
    } else if (kind === 'sinN') {
      imag[clamp(h, 1, N)] = 1;
    } else if (kind === 'saw') {
      for (n = 1; n <= N; n++) imag[n] = ((n % 2) ? 1 : -1) / n;
    } else if (kind === 'square') {
      for (n = 1; n <= N; n += 2) imag[n] = 1 / n;
    } else if (kind === 'triangle') {
      for (n = 1; n <= N; n += 2) imag[n] = ((n % 4 === 1) ? 1 : -1) / (n * n);
    } else {
      throw new Error('OpEngine: getWave got unknown kind ' + kind);
    }

    // Bake the start phase into the coefficients (OscillatorNode has no phase).
    var ph = 2 * Math.PI * phase01;
    for (n = 1; n <= N; n++) {
      var a = real[n], b = imag[n];
      if (a === 0 && b === 0) continue;
      var c = Math.cos(n * ph), s = Math.sin(n * ph);
      real[n] = a * c + b * s;
      imag[n] = -a * s + b * c;
    }

    var w = ctx.createPeriodicWave(real, imag);   // normalisation on
    waveCache.set(key, w);
    return w;
  }

  /* --------------------------------------------------------- per-op value model */

  function opRatioFreq(i, midi, vel01) {
    var p = 'osc.' + OPS[i] + '.';
    if (bool(p + 'fixed')) {
      // Fixed: freq x multi, note pitch / transpose / spread / Osc<Vel ignored.
      return clamp(pct(p + 'freq', 0.1, 1000) * pct(p + 'multi', 0.1, 1000), 0.01, 20000);
    }
    var ratio = pct(p + 'coarse', 0, 48) + pct(p + 'fine', 0, 1000) / 1000;
    if (ratio <= 0) ratio = 0.5;                 // Operator's lowest coarse ratio
    var semis = pct(p + 'oscVel', -48, 48) * vel01;
    if (bool(p + 'oscVelQ')) semis = Math.round(semis);
    var base = midiHz(midi + pct('pitch.transpose', -48, 48));
    return clamp(base * ratio * Math.pow(2, semis / 12), 0.01, 20000);
  }

  function velLevelFactor(i, vel01) {
    var ev = pct('osc.' + OPS[i] + '.env.vel', -100, 100) / 100;  // -1..1
    var atten = (ev >= 0) ? ev * (1 - vel01) : (-ev) * vel01;
    return db2lin(-36 * clamp(atten, 0, 1));
  }

  function opLevelLin(i, vel01) {
    if (!bool('osc.' + OPS[i] + '.on')) return 0;
    return db2lin(num('osc.' + OPS[i] + '.level')) * velLevelFactor(i, vel01);
  }

  function timeScale(i, midi, vel01) {
    var p = 'osc.' + OPS[i] + '.env.';
    var g = Math.pow(4, pct('global.time', -100, 100) / 100);
    var v = Math.pow(2, -(pct(p + 'timeVel', 0, 100) / 100) * 2 * vel01);
    var k = Math.pow(2, -(pct(p + 'key', 0, 100) / 100) * ((midi - 60) / 12));
    return clamp(g * v * k, 0.01, 100);
  }

  function normLoop(s) {
    var t = String(s).trim().toLowerCase();
    if (t === 'none') return 'None';
    if (t === 'trigger') return 'Trigger';
    if (t === 'loop') return 'Loop';
    if (t === 'beat' || t === 'sync') return 'Loop';   // census extras -> Loop
    throw new Error('OpEngine: unknown env loop mode "' + s + '"');
  }

  function envValues(i, midi, vel01) {
    var p = 'osc.' + OPS[i] + '.env.';
    var sc = timeScale(i, midi, vel01);
    return {
      init: db2lin(num(p + 'initial')),
      peak: db2lin(num(p + 'peak')),
      sus: db2lin(num(p + 'sustain')),
      a: clamp(num(p + 'attack') / 1000, 0, 60) * sc,
      d: clamp(num(p + 'decay') / 1000, 0, 60) * sc,
      r: clamp(num(p + 'release') / 1000, 0, 60) * sc,
      loop: normLoop(enumOf(p + 'loop'))
    };
  }

  function filterQ(res) {
    return 0.7071 + clamp(res, 0, 125) / 125 * 11.3;   // 0.71 .. 12.0
  }

  function normFilterType(s) {
    var t = String(s).trim().toLowerCase();
    if (t === 'lp' || t.indexOf('low') === 0) return 'lowpass';
    if (t === 'hp' || t.indexOf('high') === 0) return 'highpass';
    if (t === 'bp' || t.indexOf('band') === 0) return 'bandpass';
    if (t === 'notch' || t === 'br' || t.indexOf('not') === 0) return 'notch';
    throw new Error('OpEngine: unknown filter type "' + s + '"');
  }

  function lfoOscType() {
    var w = String(enumOf('lfo.wave')).trim().toLowerCase();
    if (w.indexOf('noise') === 0) return 'noise';
    if (w.indexOf('squ') === 0) return 'square';
    if (w.indexOf('tri') === 0) return 'triangle';
    if (w.indexOf('saw') === 0) return 'sawtooth';
    if (w.indexOf('sin') === 0) return 'sine';
    throw new Error('OpEngine: unknown lfo.wave "' + w + '"');
  }

  function lfoDest() {
    var s = String(enumOf('lfo.dest')).trim().toLowerCase();
    if (s.charAt(0) === 'l') return 'L';
    if (s.charAt(0) === 'f') return 'F';
    if (s.charAt(0) === 'p') return 'P';
    if (s === 'a' || s === 'b' || s === 'c' || s === 'd') return s.toUpperCase();
    throw new Error('OpEngine: unknown lfo.dest "' + s + '"');
  }

  /* -------------------------------------------------------------- graph builders */

  function makeCurve(fn, n) {
    var c = new Float32Array(n), i;
    for (i = 0; i < n; i++) c[i] = fn((i / (n - 1)) * 2 - 1);
    return c;
  }

  function buildBuffers() {
    var i, sr = ctx.sampleRate;

    var nb = ctx.createBuffer(1, Math.floor(sr * 2), sr);
    var nd = nb.getChannelData(0);
    for (i = 0; i < nd.length; i++) nd[i] = rnd() * 2 - 1;
    noiseBuffer = nb;

    // Sample & hold for LFO wave "Noise": 64 steps across exactly 1 second.
    var sb = ctx.createBuffer(1, Math.floor(sr), sr);
    var sd = sb.getChannelData(0);
    var step = Math.floor(sd.length / 64), v = 0;
    for (i = 0; i < sd.length; i++) {
      if (i % step === 0) v = rnd() * 2 - 1;
      sd[i] = v;
    }
    shNoiseBuffer = sb;

    clipCurve = makeCurve(function (x) { return Math.tanh(2 * x) / Math.tanh(2); }, 1024);
    // OSR circuit: asymmetric soft saturation (odd + a little even harmonics).
    osrCurve = makeCurve(function (x) { return Math.tanh(2.2 * x + 0.15 * x * x); }, 1024);
  }

  function makeVoice(side) {
    var v = {
      side: side, midi: -1, vel01: 0, t0: 0, active: false, released: false,
      ops: [], edges: {},
      mix: ctx.createGain(),
      shaper: ctx.createWaveShaper(),
      f1: ctx.createBiquadFilter(),
      f2: ctx.createBiquadFilter(),
      amp: ctx.createGain(),
      pan: (typeof ctx.createStereoPanner === 'function') ? ctx.createStereoPanner() : null,
      pitchCS: ctx.createConstantSource(),
      pitchDepth: ctx.createGain(),
      pitchLfo: ctx.createGain(),
      filtLfo: ctx.createGain()
    };

    v.mix.gain.value = 1;
    v.amp.gain.value = VOICE_GAIN;
    v.f1.type = 'lowpass'; v.f2.type = 'lowpass';
    v.shaper.curve = null;                 // Clean = no shaping at all
    v.shaper.oversample = '2x';

    var i;
    for (i = 0; i < 4; i++) {
      var op = {
        envGain: ctx.createGain(),
        levelGain: ctx.createGain(),
        carrierGain: ctx.createGain(),
        fbDelay: ctx.createDelay(0.05),
        fbGain: ctx.createGain(),
        lfoLevel: ctx.createGain(),
        src: null,
        waveKey: null
      };
      op.envGain.gain.value = 0;
      op.levelGain.gain.value = 0;
      op.carrierGain.gain.value = 0;
      op.fbGain.gain.value = 0;
      op.lfoLevel.gain.value = 0;
      op.fbDelay.delayTime.value = 128 / ctx.sampleRate;   // one render quantum

      op.envGain.connect(op.levelGain);
      op.levelGain.connect(op.carrierGain);
      op.carrierGain.connect(v.mix);
      op.levelGain.connect(op.fbDelay);
      op.fbDelay.connect(op.fbGain);
      op.lfoLevel.connect(op.levelGain.gain);
      v.ops.push(op);
    }

    // One persistent gain per possible modulation edge; algorithm switching is
    // then just a gain change (live), never a re-wire.
    for (i = 0; i < EDGE_KEYS.length; i++) {
      var g = ctx.createGain();
      g.gain.value = 0;
      v.edges[EDGE_KEYS[i]] = g;
      v.ops[IDX[EDGE_KEYS[i].charAt(0)]].levelGain.connect(g);
    }

    v.pitchCS.offset.value = 0;
    v.pitchCS.connect(v.pitchDepth);
    v.pitchDepth.gain.value = 0;
    v.pitchCS.start();

    v.pitchLfo.gain.value = 0;
    v.filtLfo.gain.value = 0;
    v.filtLfo.connect(v.f1.detune);
    v.filtLfo.connect(v.f2.detune);

    v.mix.connect(v.shaper);
    v.shaper.connect(v.f1);
    v.f1.connect(v.f2);
    v.f2.connect(v.amp);
    if (v.pan) { v.amp.connect(v.pan); v.pan.connect(bus); }
    else { v.amp.connect(bus); }

    return v;
  }

  function buildLfo() {
    var out = ctx.createGain(); out.gain.value = 0;
    var oscGain = ctx.createGain(); oscGain.gain.value = 1;
    var shGain = ctx.createGain(); shGain.gain.value = 0;
    oscGain.connect(out);
    shGain.connect(out);

    lfoNodes = { osc: null, oscGain: oscGain, sh: null, shGain: shGain, out: out };
    startLfoSources(ctx.currentTime);

    // Persistent LFO fan-out into every voice's destination gains.
    for (var s = 0; s < slots.length; s++) {
      for (var k = 0; k < 2; k++) {
        var v = slots[s].voices[k];
        out.connect(v.filtLfo);
        out.connect(v.pitchLfo);
        for (var i = 0; i < 4; i++) out.connect(v.ops[i].lfoLevel);
      }
    }
  }

  function retireNode(node, t) {
    if (!node) return;
    node.stop(t);
    node.onended = function () { node.disconnect(); };
  }

  /* Rebuilds both LFO sources so their phase restarts at `t` (lfo.retrig).
     A running OscillatorNode has no phase reset, so a fresh node is the only
     way to do this — the rate and wave are re-read here so a retrigger can
     never revert them to a build-time placeholder. */
  function startLfoSources(t) {
    var type = lfoOscType();
    var rate = clamp(num('lfo.rate'), 0.01, 200);

    retireNode(lfoNodes.osc, t);
    var o = ctx.createOscillator();
    o.type = (type === 'noise') ? 'sine' : type;
    o.frequency.value = rate;
    o.connect(lfoNodes.oscGain);
    o.start(t);
    lfoNodes.osc = o;

    retireNode(lfoNodes.sh, t);
    var s = ctx.createBufferSource();
    s.buffer = shNoiseBuffer;
    s.loop = true;
    s.playbackRate.value = rate / 64;      // 64 steps per buffer -> 1 step/cycle
    s.connect(lfoNodes.shGain);
    s.start(t);
    lfoNodes.sh = s;
  }

  function ensureCtx() {
    if (ctx) {
      if (ctx.state === 'suspended') {
        ctx.resume().catch(function (e) {
          console.error('OpEngine: AudioContext.resume failed', e);
          throw e;
        });
      }
      return;
    }
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) throw new Error('OpEngine: this browser has no Web Audio API');

    ctx = new AC();
    if (typeof ctx.createConstantSource !== 'function') {
      throw new Error('OpEngine: this browser lacks ConstantSourceNode ' +
        '(needed for the per-voice pitch envelope)');
    }
    waveCache = new Map();
    buildBuffers();

    bus = ctx.createGain(); bus.gain.value = BUS_HEADROOM;
    toneNode = ctx.createBiquadFilter();
    toneNode.type = 'lowpass';
    toneNode.Q.value = 0.5;                 // closest live-tunable one-pole shape
    masterGain = ctx.createGain(); masterGain.gain.value = 1;
    clipNode = ctx.createWaveShaper();
    clipNode.curve = clipCurve;
    clipNode.oversample = '2x';
    analyser = ctx.createAnalyser();
    analyser.fftSize = 1024;
    analyser.smoothingTimeConstant = 0;
    meterUseFloat = (typeof analyser.getFloatTimeDomainData === 'function');
    meterFloat = new Float32Array(analyser.fftSize);
    meterByte = new Uint8Array(analyser.fftSize);

    bus.connect(toneNode);
    toneNode.connect(masterGain);
    masterGain.connect(clipNode);
    clipNode.connect(analyser);
    analyser.connect(ctx.destination);

    for (var s = 0; s < POLYPHONY; s++) {
      slots.push({
        index: s, voices: [makeVoice(-1), makeVoice(1)],
        midi: -1, on: false, startT: 0, freeT: 0, seq: 0
      });
    }
    buildLfo();

    console.assert(slots.length === POLYPHONY, 'OpEngine: voice slot count');
    applyAll();

    if (ctx.state === 'suspended') {
      ctx.resume().catch(function (e) {
        console.error('OpEngine: AudioContext.resume failed', e);
        throw e;
      });
    }
  }

  /* ------------------------------------------------------------------ refreshers
     Each one reads the tree and writes AudioParams. All are no-ops before the
     context exists (values are read again in applyAll() at creation time). */

  function eachVoice(fn) {
    for (var s = 0; s < slots.length; s++) {
      fn(slots[s].voices[0], slots[s]);
      fn(slots[s].voices[1], slots[s]);
    }
  }

  function refreshLevel(i) {
    if (!ctx) return;
    var amount = pct('lfo.amount', 0, 100) / 100;
    var dest = lfoDest();
    var lfoOnLevel = bool('lfo.on') && (dest === 'L' || dest === OPS[i].toUpperCase());
    var t = ctx.currentTime;
    eachVoice(function (v) {
      var lin = v.active ? opLevelLin(i, v.vel01) : opLevelLin(i, 1);
      v.ops[i].levelGain.gain.setTargetAtTime(lin, t, 0.005);
      v.ops[i].lfoLevel.gain.setTargetAtTime(
        lfoOnLevel ? lin * amount * LFO_LEVEL_DEPTH : 0, t, 0.005);
    });
  }

  function refreshAllLevels() { for (var i = 0; i < 4; i++) refreshLevel(i); }

  /* Frequency of one op on one voice + everything that scales with it:
     the FM index of every edge INTO it, and its own feedback depth. */
  function refreshVoiceOpFreq(v, i) {
    if (!v.active || !v.ops[i].src) return;
    var t = ctx.currentTime;
    var f = opRatioFreq(i, v.midi, v.vel01);
    var src = v.ops[i].src;
    if (src.frequency) src.frequency.setValueAtTime(f, t);

    var fb = pct('osc.' + OPS[i] + '.feedback', 0, 100) / 100;
    v.ops[i].fbGain.gain.setTargetAtTime(fb * fb * f * FB_DEPTH, t, 0.01);

    var alg = ALGORITHMS[algIndex()];
    for (var e = 0; e < EDGE_KEYS.length; e++) {
      var key = EDGE_KEYS[e];
      if (key.charAt(1) !== OPS[i]) continue;          // edges INTO this op
      var on = alg.edges.indexOf(key) >= 0 && src.frequency;
      v.edges[key].gain.setTargetAtTime(on ? f * FM_DEPTH : 0, t, 0.01);
    }
  }

  function refreshFreq(i) {
    if (!ctx) return;
    eachVoice(function (v) {
      refreshVoiceOpFreq(v, i);
      // an edge FROM op i does not depend on op i's own frequency, but every op
      // it feeds does — recompute the targets too when a ratio moves.
      for (var e = 0; e < EDGE_KEYS.length; e++) {
        if (EDGE_KEYS[e].charAt(0) === OPS[i]) {
          refreshVoiceOpFreq(v, IDX[EDGE_KEYS[e].charAt(1)]);
        }
      }
    });
  }

  function refreshAllFreqs() { for (var i = 0; i < 4; i++) refreshFreq(i); }

  function refreshAlgorithm() {
    if (!ctx) return;
    var alg = ALGORITHMS[algIndex()];
    var t = ctx.currentTime;
    eachVoice(function (v) {
      for (var i = 0; i < 4; i++) {
        v.ops[i].carrierGain.gain.setTargetAtTime(
          alg.carriers.indexOf(OPS[i]) >= 0 ? 1 : 0, t, 0.008);
      }
    });
    refreshAllFreqs();          // edge gains live on the carrier frequency
  }

  function refreshWave(i) {
    if (!ctx) return;
    var t = ctx.currentTime;
    eachVoice(function (v) {
      var op = v.ops[i];
      if (!op.src) return;
      var w = waveKind(i);
      if ((w.kind === 'noise') !== (op.waveKey === 'noise')) {
        rebuildSource(v, i, t);          // tone <-> noise: swap the source live
        return;
      }
      if (w.kind === 'noise') return;    // same noise source, nothing to reshape
      op.src.setPeriodicWave(getWave(w.kind, w.h, op.phase01));
    });
  }

  function refreshFilter() {
    if (!ctx) return;
    var on = bool('filter.on');
    var type = normFilterType(enumOf('filter.type'));
    var slope = (parseFloat(enumOf('filter.slope')) >= 24) ? 24 : 12;
    var circuit = String(enumOf('filter.circuit')).trim().toLowerCase();
    var f = clamp(num('filter.freq'), 10, ctx.sampleRate * 0.45);
    var q = filterQ(pct('filter.res', 0, 125));
    var t = ctx.currentTime;
    var amount = pct('lfo.amount', 0, 100) / 100;
    var lfoOnFilter = bool('lfo.on') && lfoDest() === 'F';
    eachVoice(function (v) {
      v.f1.type = on ? type : 'allpass';
      v.f2.type = (on && slope === 24) ? type : 'allpass';
      v.f1.frequency.setTargetAtTime(f, t, 0.008);
      v.f2.frequency.setTargetAtTime(f, t, 0.008);
      v.f1.Q.setTargetAtTime(q, t, 0.008);
      v.f2.Q.setTargetAtTime(q, t, 0.008);
      v.shaper.curve = (on && circuit === 'osr') ? osrCurve : null;
      v.filtLfo.gain.setTargetAtTime(
        lfoOnFilter ? amount * LFO_FILTER_CENTS : 0, t, 0.01);
    });
  }

  function refreshLfo() {
    if (!ctx) return;
    var t = ctx.currentTime;
    var kind = lfoOscType();
    var rate = clamp(num('lfo.rate'), 0.01, 200);
    var isNoise = (kind === 'noise');

    lfoNodes.osc.type = isNoise ? 'sine' : kind;
    lfoNodes.osc.frequency.setTargetAtTime(rate, t, 0.01);
    lfoNodes.sh.playbackRate.setTargetAtTime(rate / 64, t, 0.01);
    lfoNodes.oscGain.gain.setTargetAtTime(isNoise ? 0 : 1, t, 0.005);
    lfoNodes.shGain.gain.setTargetAtTime(isNoise ? 1 : 0, t, 0.005);
    lfoNodes.out.gain.setTargetAtTime(bool('lfo.on') ? 1 : 0, t, 0.005);

    var dest = lfoDest();
    var amount = pct('lfo.amount', 0, 100) / 100;
    var pitchDepthCents = (bool('lfo.on') && dest === 'P') ? amount * LFO_PITCH_CENTS : 0;
    eachVoice(function (v) {
      v.pitchLfo.gain.setTargetAtTime(pitchDepthCents, t, 0.01);
    });
    refreshAllLevels();      // dest L / A-D
    refreshFilter();         // dest F
  }

  function refreshPitch() {
    if (!ctx) return;
    var t = ctx.currentTime;
    var depth = bool('pitch.on') ? (pct('pitch.env', -100, 100) / 100) * PITCH_ENV_CENTS : 0;
    var spread = pct('pitch.spread', 0, 100) / 100;
    eachVoice(function (v) {
      v.pitchDepth.gain.setTargetAtTime(depth, t, 0.01);
      if (v.pan) v.pan.pan.setTargetAtTime(v.side * spread * SPREAD_PAN, t, 0.02);
      for (var i = 0; i < 4; i++) {
        var src = v.ops[i].src;
        if (!src || !src.detune) continue;
        var fixed = bool('osc.' + OPS[i] + '.fixed');
        src.detune.setTargetAtTime(fixed ? 0 : v.side * spread * SPREAD_CENTS, t, 0.02);
      }
    });
    refreshAllFreqs();       // pitch.transpose lives in the base frequency
  }

  function refreshTone() {
    if (!ctx) return;
    var tone = pct('global.tone', 0, 100) / 100;
    var f = 800 * Math.pow(25, tone);      // 800 Hz .. 20 kHz
    toneNode.frequency.setTargetAtTime(
      clamp(f, 20, ctx.sampleRate * 0.45), ctx.currentTime, 0.01);
  }

  function refreshVolume() {
    if (!ctx) return;
    masterGain.gain.setTargetAtTime(db2lin(num('global.volume')), ctx.currentTime, 0.01);
  }

  function applyAll() {
    refreshAlgorithm();
    refreshAllLevels();
    refreshAllFreqs();
    refreshFilter();
    refreshLfo();
    refreshPitch();
    refreshTone();
    refreshVolume();
  }

  /* -------------------------------------------------------------- envelope logic */

  /* Schedules the whole contour at t0. Returns the time the op is guaranteed
     silent (Infinity while a None-mode note is still held). */
  function scheduleEnv(v, i, t0) {
    var e = envValues(i, v.midi, v.vel01);
    var g = v.ops[i].envGain.gain;
    cancelAndHold(g, t0);
    g.setValueAtTime(e.init, t0);

    var t = approach(g, e.peak, t0, e.a);
    t = approach(g, e.sus, t, e.d);

    if (e.loop === 'Trigger') {
      t = approach(g, 0, t, e.r);
      return t;
    }
    if (e.loop === 'Loop') {
      var cycle = e.a + e.d;
      var n = 0;
      if (cycle > 0.001) {
        while (n < LOOP_MAX_CYCLES && (t - t0) + cycle < LOOP_HORIZON) {
          g.setValueAtTime(e.init, t);
          t = approach(g, e.peak, t, e.a);
          t = approach(g, e.sus, t, e.d);
          n++;
        }
      }
      return Infinity;      // still held; release ends it
    }
    return Infinity;
  }

  /* Live edit of a held note: re-aim the envelope from wherever it is now. */
  function reapplyEnv(v, i) {
    if (!v.active || v.released || !v.ops[i].src) return;
    var e = envValues(i, v.midi, v.vel01);
    var g = v.ops[i].envGain.gain;
    var t = ctx.currentTime;
    var el = t - v.t0;

    if (e.loop === 'Trigger' || e.loop === 'Loop') {
      scheduleEnv(v, i, t);          // restart the contour from now
      return;
    }
    cancelAndHold(g, t);
    if (el < e.a) {
      var t1 = approach(g, e.peak, t, e.a - el);
      approach(g, e.sus, t1, e.d);
    } else if (el < e.a + e.d) {
      approach(g, e.sus, t, (e.a + e.d) - el);
    } else {
      approach(g, e.sus, t, 0.02);
    }
  }

  function reapplyEnvAll(i) {
    if (!ctx) return;
    eachVoice(function (v) { reapplyEnv(v, i); });
  }

  function releaseEnv(v, i, t) {
    var e = envValues(i, v.midi, v.vel01);
    if (e.loop === 'Trigger') {
      return v.t0 + e.a + e.d + e.r;      // already scheduled at note-on
    }
    var g = v.ops[i].envGain.gain;
    cancelAndHold(g, t);
    approach(g, 0, t, e.r);
    return t + e.r;
  }

  /* ------------------------------------------------------------- note lifecycle */

  function makeSource(v, i, t0) {
    var op = v.ops[i];
    var w = waveKind(i);
    var p = 'osc.' + OPS[i] + '.';
    var retrig = bool(p + 'retrig');
    var phase01 = retrig ? clamp(num(p + 'phase'), 0, 100) / 100 : rnd();
    var src;

    if (w.kind === 'noise') {
      src = ctx.createBufferSource();
      src.buffer = noiseBuffer;
      src.loop = true;
      op.waveKey = 'noise';
    } else {
      src = ctx.createOscillator();
      src.setPeriodicWave(getWave(w.kind, w.h, phase01));
      src.frequency.value = opRatioFreq(i, v.midi, v.vel01);
      op.waveKey = w.kind + w.h;
    }
    op.phase01 = phase01;

    if (src.detune) {
      var spread = pct('pitch.spread', 0, 100) / 100;
      src.detune.value = bool(p + 'fixed') ? 0 : v.side * spread * SPREAD_CENTS;
      v.pitchDepth.connect(src.detune);
      v.pitchLfo.connect(src.detune);
    }

    src.connect(op.envGain);
    src.onended = function () {
      src.disconnect();
      if (op.src !== src) return;            // already replaced by a newer note
      op.src = null;
      for (var k = 0; k < 4; k++) { if (v.ops[k].src) return; }
      v.active = false;                      // the voice is genuinely finished
    };
    if (w.kind === 'noise') src.start(t0, retrig ? 0 : rnd() * noiseBuffer.duration);
    else src.start(t0);
    return src;
  }

  /* Swap one op's source in place, mid-note (used when the waveform changes
     between a tone and Noise, which are different node types). */
  function rebuildSource(v, i, t) {
    var op = v.ops[i];
    if (op.src) {
      if (op.src.detune) {                 // drop the two pitch feeds precisely
        v.pitchDepth.disconnect(op.src.detune);
        v.pitchLfo.disconnect(op.src.detune);
      }
      op.src.stop(t);
    }
    op.src = makeSource(v, i, t);
    op.fbGain.disconnect();
    if (op.src.frequency) op.fbGain.connect(op.src.frequency);
    for (var e = 0; e < EDGE_KEYS.length; e++) {
      var key = EDGE_KEYS[e];
      if (key.charAt(1) !== OPS[i]) continue;
      v.edges[key].disconnect();
      if (op.src.frequency) v.edges[key].connect(op.src.frequency);
    }
    refreshVoiceOpFreq(v, i);
  }

  function startVoice(v, midi, vel01, t0) {
    var i, op;

    // Kill anything still sounding on this half of the slot, exactly at t0, and
    // fade its envelope out over the pre-roll so a stolen voice cannot click.
    var now = ctx.currentTime;
    for (i = 0; i < 4; i++) {
      op = v.ops[i];
      if (!op.src) continue;
      op.src.stop(t0);
      cancelAndHold(op.envGain.gain, now);
      op.envGain.gain.linearRampToValueAtTime(0, t0);
    }
    v.pitchDepth.disconnect();
    v.pitchLfo.disconnect();

    v.midi = midi; v.vel01 = vel01; v.t0 = t0;
    v.active = true; v.released = false;

    for (i = 0; i < 4; i++) {
      op = v.ops[i];
      op.src = makeSource(v, i, t0);

      // (re)point every persistent modulation gain at the new source
      op.fbGain.disconnect();
      if (op.src.frequency) op.fbGain.connect(op.src.frequency);
    }
    for (i = 0; i < EDGE_KEYS.length; i++) {
      var key = EDGE_KEYS[i];
      var target = v.ops[IDX[key.charAt(1)]].src;
      v.edges[key].disconnect();
      if (target && target.frequency) v.edges[key].connect(target.frequency);
    }

    // pitch envelope: fixed decay contour, depth set by refreshPitch()
    var pd = PITCH_ENV_DECAY * Math.pow(4, pct('global.time', -100, 100) / 100);
    cancelAndHold(v.pitchCS.offset, t0);
    v.pitchCS.offset.setValueAtTime(1, t0);
    approach(v.pitchCS.offset, 0, t0, pd);

    var endT = 0;
    for (i = 0; i < 4; i++) {
      var e = scheduleEnv(v, i, t0);
      if (e > endT) endT = e;
    }
    return endT;
  }

  /* Schedules the stop; `active` drops in the source's onended handler, so a
     still-ringing release keeps following live parameter changes. */
  function stopVoiceSources(v, t) {
    for (var i = 0; i < 4; i++) {
      if (v.ops[i].src) v.ops[i].src.stop(t);
    }
  }

  function pickSlot(midi, now) {
    var i, s, best = null;
    for (i = 0; i < slots.length; i++) {                  // same note -> retrigger
      if (slots[i].on && slots[i].midi === midi) return slots[i];
    }
    for (i = 0; i < slots.length; i++) {                  // fully free
      s = slots[i];
      if (!s.on && now >= s.freeT) return s;
    }
    for (i = 0; i < slots.length; i++) {                  // releasing, oldest tail
      s = slots[i];
      if (!s.on && (best === null || s.freeT < best.freeT)) best = s;
    }
    if (best) return best;
    for (i = 0; i < slots.length; i++) {                  // steal oldest sounding
      s = slots[i];
      if (best === null || s.startT < best.startT) best = s;
    }
    console.assert(best, 'OpEngine: no slot could be chosen');
    return best;
  }

  /* ------------------------------------------------------------- change routing */

  function onParam(addr) {
    if (typeof addr !== 'string' || !addr) {
      throw new Error('OpEngine: change notification with a non-string address');
    }
    if (!ctx) return;                       // nothing built yet; applyAll() covers it
    if (addr.indexOf('ui.') === 0) return;  // documented UI-only namespace

    var m = /^osc\.([abcd])\.env\.([A-Za-z]+)$/.exec(addr);
    if (m) {
      var ei = IDX[m[1]];
      switch (m[2]) {
        case 'vel':
          refreshLevel(ei); reapplyEnvAll(ei); return;
        case 'attack': case 'decay': case 'release': case 'initial':
        case 'peak': case 'sustain': case 'timeVel': case 'loop': case 'key':
          reapplyEnvAll(ei); return;
        default:
          throw new Error('OpEngine: unknown parameter address ' + addr);
      }
    }

    m = /^osc\.([abcd])\.([A-Za-z]+)$/.exec(addr);
    if (m) {
      var oi = IDX[m[1]];
      switch (m[2]) {
        case 'on': case 'level': refreshLevel(oi); return;
        case 'coarse': case 'fine': case 'fixed': case 'freq': case 'multi':
        case 'oscVel': case 'oscVelQ':
          refreshFreq(oi);
          if (m[2] === 'fixed') refreshPitch();
          return;
        case 'feedback': refreshFreq(oi); return;
        case 'wave': refreshWave(oi); return;
        case 'phase': case 'retrig': return;   // next note-on (see header block)
        default:
          throw new Error('OpEngine: unknown parameter address ' + addr);
      }
    }

    m = /^(lfo|filter|pitch|global)\.([A-Za-z]+)$/.exec(addr);
    if (m) {
      var grp = m[1], leaf = m[2];
      if (grp === 'lfo') {
        switch (leaf) {
          case 'on': case 'wave': case 'dest': case 'rate': case 'amount':
            refreshLfo(); return;
          case 'retrig': return;               // next note-on
          default: throw new Error('OpEngine: unknown parameter address ' + addr);
        }
      }
      if (grp === 'filter') {
        switch (leaf) {
          case 'on': case 'type': case 'slope': case 'circuit': case 'freq': case 'res':
            refreshFilter(); return;
          default: throw new Error('OpEngine: unknown parameter address ' + addr);
        }
      }
      if (grp === 'pitch') {
        switch (leaf) {
          case 'on': case 'env': case 'spread': refreshPitch(); return;
          case 'transpose': refreshAllFreqs(); return;
          default: throw new Error('OpEngine: unknown parameter address ' + addr);
        }
      }
      switch (leaf) {                           // global.*
        case 'algorithm': refreshAlgorithm(); return;
        case 'time': for (var i = 0; i < 4; i++) reapplyEnvAll(i); return;
        case 'tone': refreshTone(); return;
        case 'volume': refreshVolume(); return;
        default: throw new Error('OpEngine: unknown parameter address ' + addr);
      }
    }

    throw new Error('OpEngine: unknown parameter address ' + addr);
  }

  /* ------------------------------------------------------------------ public API */

  function requiredAddresses() {
    var list = [], i, p;
    for (i = 0; i < 4; i++) {
      p = 'osc.' + OPS[i] + '.';
      list.push(p + 'on', p + 'coarse', p + 'fine', p + 'fixed', p + 'freq',
        p + 'multi', p + 'level', p + 'wave', p + 'feedback', p + 'phase',
        p + 'retrig', p + 'oscVel', p + 'oscVelQ',
        p + 'env.attack', p + 'env.decay', p + 'env.release', p + 'env.initial',
        p + 'env.peak', p + 'env.sustain', p + 'env.timeVel', p + 'env.vel',
        p + 'env.loop', p + 'env.key');
    }
    list.push('lfo.on', 'lfo.wave', 'lfo.dest', 'lfo.retrig', 'lfo.rate', 'lfo.amount');
    list.push('filter.on', 'filter.type', 'filter.slope', 'filter.circuit',
      'filter.freq', 'filter.res');
    list.push('pitch.on', 'pitch.env', 'pitch.spread', 'pitch.transpose');
    list.push('global.algorithm', 'global.time', 'global.tone', 'global.volume');
    return list;
  }

  function bind(tree) {
    if (!tree || typeof tree.get !== 'function' || typeof tree.onAny !== 'function' ||
      typeof tree.desc !== 'function') {
      throw new Error('OpEngine.bind: needs an OpParams with get/desc/onAny');
    }
    console.assert(!params || params === tree, 'OpEngine: re-bound to a new tree');

    // Fail loud, and say exactly WHICH addresses are missing, not just "one is".
    var missing = [], list = requiredAddresses(), i;
    for (i = 0; i < list.length; i++) {
      var ok = false;
      try { ok = !!tree.desc(list[i]); } catch (e) { ok = false; }
      if (!ok) missing.push(list[i]);
    }
    if (missing.length) {
      throw new Error('OpEngine.bind: parameter tree is missing ' + missing.length +
        ' address(es): ' + missing.join(', '));
    }

    if (unsubAny) { unsubAny(); unsubAny = null; }
    params = tree;
    unsubAny = tree.onAny(function (addr) { onParam(addr); });
    if (ctx) applyAll();
    return true;
  }

  function noteOn(midi, vel) {
    requireBound();
    midi = Math.round(+midi);
    if (!isFinite(midi) || midi < 0 || midi > 127) {
      throw new Error('OpEngine.noteOn: bad midi note ' + String(midi));
    }
    var v127 = (vel === undefined || vel === null) ? 100 : +vel;
    if (Number.isNaN(v127)) throw new Error('OpEngine.noteOn: bad velocity ' + String(vel));
    if (v127 <= 0) { noteOff(midi); return; }
    var vel01 = clamp(v127 / 127, 0.0001, 1);

    ensureCtx();
    var now = ctx.currentTime;
    var t0 = now + GLIDE;
    var slot = pickSlot(midi, now);
    console.assert(slot && slot.voices.length === 2, 'OpEngine: slot invariant');

    if (bool('lfo.retrig')) startLfoSources(t0);

    slot.midi = midi;
    slot.on = true;
    slot.startT = t0;
    slot.freeT = Infinity;
    slot.seq++;

    var e0 = startVoice(slot.voices[0], midi, vel01, t0);
    var e1 = startVoice(slot.voices[1], midi, vel01, t0);
    var end = Math.max(e0, e1);
    if (isFinite(end)) {
      // Every op is in Trigger loop mode: the note is a one-shot that completes
      // without a note-off, so the slot books its own release time now.
      slot.on = false;
      slot.freeT = end + 0.05;
      stopVoiceSources(slot.voices[0], slot.freeT);
      stopVoiceSources(slot.voices[1], slot.freeT);
    }

    // The new note's velocity changes level/index scaling — re-derive both.
    refreshAllLevels();
    refreshAllFreqs();
    refreshPitch();
  }

  function releaseSlot(slot, t) {
    var end = t, i, k;
    for (k = 0; k < 2; k++) {
      var v = slot.voices[k];
      if (!v.active) continue;
      for (i = 0; i < 4; i++) {
        var e = releaseEnv(v, i, t);
        if (e > end) end = e;
      }
      v.released = true;
    }
    slot.on = false;
    slot.freeT = end + 0.05;
    stopVoiceSources(slot.voices[0], slot.freeT);
    stopVoiceSources(slot.voices[1], slot.freeT);
  }

  function noteOff(midi) {
    requireBound();
    if (!ctx) return;                 // nothing was ever played
    midi = Math.round(+midi);
    var t = ctx.currentTime;
    for (var i = 0; i < slots.length; i++) {
      if (slots[i].on && slots[i].midi === midi) releaseSlot(slots[i], t);
    }
  }

  function allNotesOff() {
    if (!ctx) return;
    var t = ctx.currentTime;
    for (var i = 0; i < slots.length; i++) {
      if (slots[i].on) releaseSlot(slots[i], t);
    }
  }

  function meterLevel() {
    if (!ctx || !analyser) return 0;
    var i, n, x, sum = 0;
    if (meterUseFloat) {
      analyser.getFloatTimeDomainData(meterFloat);
      n = meterFloat.length;
      for (i = 0; i < n; i++) { x = meterFloat[i]; sum += x * x; }
    } else {
      analyser.getByteTimeDomainData(meterByte);
      n = meterByte.length;
      for (i = 0; i < n; i++) { x = (meterByte[i] - 128) / 128; sum += x * x; }
    }
    var rms = Math.sqrt(sum / n);
    var db = 20 * Math.log10(rms + 1e-9);
    var target = clamp((db + 60) / 60, 0, 1);

    var t = ctx.currentTime;                       // never Date.now
    var dt = t - meterT;
    meterT = t;
    if (!(dt > 0)) dt = 1 / 60;   // polled faster than the audio clock ticks:
    dt = clamp(dt, 0, 0.5);       // one nominal frame, so the meter never freezes
    var tau = (target > meterVal) ? 0.01 : 0.25;
    meterVal += (target - meterVal) * (1 - Math.exp(-dt / tau));
    return clamp(meterVal, 0, 1);
  }

  window.OpEngine = {
    bind: bind,
    noteOn: noteOn,
    noteOff: noteOff,
    allNotesOff: allNotesOff,
    meterLevel: meterLevel,
    filterQ: filterQ,
    ALGORITHMS: ALGORITHMS
  };
}());
