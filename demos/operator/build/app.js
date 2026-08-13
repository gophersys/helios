/* app.js — assembler/integration layer. Owns the device DOM, selection,
 * the contextual grid, keyboard input, and the rAF loop.
 * Renders ONLY from OpParams; mutates ONLY via OpParams.set. */
(function () {
  'use strict';
  const P = window.OpParams, W = window.OpWidgets, E = window.OpEngine;
  if (!P || !W || !E || !window.OpDisplay) throw new Error('app: missing module');

  E.bind(P);

  /* subscribe + apply current value immediately (P.subscribe fires on change only) */
  const bindNow = (addr, fn) => { P.subscribe(addr, fn); fn(P.get(addr), addr); };

  /* measured ratio table (spec/ratios.md): knobs are Ø20 at this device scale */
  const knob = (opts) => W.knob(Object.assign({ size: 27 }, opts));

  const $ = (id) => {
    const el = document.getElementById(id);
    if (!el) throw new Error('app: missing element #' + id);
    return el;
  };

  /* ---------- left rack: oscillator rows (D, C, B, A top->bottom) ---------- */
  const SECTIONS = ['oscA', 'oscB', 'oscC', 'oscD', 'lfo', 'filter', 'pitch', 'global'];
  const plates = {};

  function makePlate(section, build) {
    const el = document.createElement('div');
    el.className = 'plate';
    el.dataset.section = section;
    build(el);
    /* pointerdown, not mousedown: widgets preventDefault their pointerdown,
       which cancels compatibility mouse events — a knob press must still
       select its plate (the whole plate is the selection target, L5) */
    el.addEventListener('pointerdown', () => P.set('ui.selected', section));
    plates[section] = el;
    return el;
  }

  const rackL = $('rackL');
  for (const x of ['d', 'c', 'b', 'a']) {
    const section = 'osc' + x.toUpperCase();
    rackL.appendChild(makePlate(section, (el) => {
      /* position classes pin each control to the measured x-centres in
         spec/ratios.md (25/125/201/252, badge 333) — flex gaps would place
         them by label width, which is the library-default look */
      const add = (widget, cls) => { widget.classList.add(cls); el.appendChild(widget); };
      add(knob({ addr: `osc.${x}.coarse`, modeSwap: { when: `osc.${x}.fixed`, addr: `osc.${x}.freq` } }), 'c-coarse');
      add(knob({ addr: `osc.${x}.fine`, modeSwap: { when: `osc.${x}.fixed`, addr: `osc.${x}.multi` } }), 'c-fine');
      add(W.checkbox({ addr: `osc.${x}.fixed`, label: 'Fixed' }), 'c-fixed');
      add(knob({ addr: `osc.${x}.level` }), 'c-level');
      const b = document.createElement('span');
      b.className = 'badge';
      b.textContent = x.toUpperCase();
      el.appendChild(b);
    }));
    bindNow(`osc.${x}.on`, (v) => plates[section].classList.toggle('off', !v));
  }

  /* ---------- right rack ---------- */
  /* right rack: Ø28 dials, positions from the gridline measurements */
  const rknob = (opts) => W.knob(Object.assign({ size: 28 }, opts));
  const cls = (widget, c) => { widget.classList.add(c); return widget; };

  const rackR = $('rackR');
  rackR.appendChild(makePlate('lfo', (el) => {
    el.appendChild(cls(W.checkbox({ addr: 'lfo.on', label: 'LFO' }), 'p-lfo-check'));
    el.appendChild(cls(W.dropdown({ addr: 'lfo.wave' }), 'p-lfo-wave'));
    el.appendChild(cls(W.dropdown({ addr: 'lfo.dest', compact: true }), 'p-lfo-dest'));
    el.appendChild(cls(W.chip({ addr: 'lfo.retrig', text: 'R' }), 'p-lfo-r'));
    el.appendChild(cls(rknob({ addr: 'lfo.rate' }), 'p-lfo-rate'));
    el.appendChild(cls(rknob({ addr: 'lfo.amount' }), 'p-lfo-amt'));
  }));
  bindNow('lfo.on', (v) => plates.lfo.classList.toggle('off', !v));

  rackR.appendChild(makePlate('filter', (el) => {
    el.appendChild(cls(W.checkbox({ addr: 'filter.on', label: 'Filter' }), 'p-fl-check'));
    el.appendChild(cls(W.dropdown({ addr: 'filter.type', compact: true, icon: 'filter', iconOnly: true }), 'p-fl-type'));
    const pair = W.pairToggle({ addr: 'filter.slope', options: ['12', '24'] });
    /* the reference draws 12|24 as two separated chips, not one joined pair */
    el.appendChild(cls(pair, 'p-fl-12'));
    el.appendChild(cls(W.dropdown({ addr: 'filter.circuit', compact: true }), 'p-fl-circ'));
    el.appendChild(cls(rknob({ addr: 'filter.freq' }), 'p-fl-freq'));
    el.appendChild(cls(rknob({ addr: 'filter.res' }), 'p-fl-res'));
  }));
  bindNow('filter.on', (v) => plates.filter.classList.toggle('off', !v));

  rackR.appendChild(makePlate('pitch', (el) => {
    const glyph = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    glyph.setAttribute('width', '30'); glyph.setAttribute('height', '13');
    glyph.setAttribute('viewBox', '0 0 30 13');
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', 'M1 12 L1 2 L22 2');
    path.setAttribute('fill', 'none'); path.setAttribute('stroke', '#24282c');
    path.setAttribute('stroke-width', '2.4');
    glyph.appendChild(path);
    el.appendChild(cls(glyph, 'p-pt-glyph'));
    el.appendChild(cls(W.checkbox({ addr: 'pitch.on', label: '' }), 'p-pt-check'));
    el.appendChild(cls(rknob({ addr: 'pitch.env' }), 'p-pt-env'));
    el.appendChild(cls(rknob({ addr: 'pitch.spread' }), 'p-pt-spread'));
    el.appendChild(cls(rknob({ addr: 'pitch.transpose' }), 'p-pt-trans'));
  }));
  bindNow('pitch.on', (v) => plates.pitch.classList.toggle('off', !v));

  rackR.appendChild(makePlate('global', (el) => {
    const leds = document.createElement('span');
    leds.classList.add('p-gl-leds');
    leds.style.display = 'inline-grid';
    leds.style.gridTemplateColumns = 'repeat(4, auto)';
    leds.style.gap = '5px';
    /* sampled: yellow / spring green / mint / orange */
    leds.appendChild(W.led({ addr: 'osc.a.on', color: '#f6d23a' }));
    leds.appendChild(W.led({ addr: 'osc.b.on', color: '#56d45c' }));
    leds.appendChild(W.led({ addr: 'osc.c.on', color: '#63e3c1' }));
    leds.appendChild(W.led({ addr: 'osc.d.on', color: '#ef8b39' }));
    el.appendChild(leds);
    el.appendChild(cls(rknob({ addr: 'global.time' }), 'p-gl-time'));
    el.appendChild(cls(rknob({ addr: 'global.tone' }), 'p-gl-tone'));
    el.appendChild(cls(rknob({ addr: 'global.volume' }), 'p-gl-vol'));
  }));

  /* ---------- meter ---------- */
  const meter = W.meter();
  $('meterlane').appendChild(meter.el);

  /* ---------- center display ---------- */
  const display = window.OpDisplay.create($('dcanvas'));
  const dgrid = $('dgrid');

  function cell(label, ...valueEls) {
    const c = document.createElement('div');
    c.className = 'cell';
    const l = document.createElement('div');
    l.className = 'clabel';
    l.textContent = label;
    const v = document.createElement('div');
    v.className = 'cval';
    for (const e of valueEls) v.appendChild(e);
    c.appendChild(l);
    c.appendChild(v);
    return c;
  }
  function col(title, filled, cellsEl) {
    const c = document.createElement('div');
    c.className = 'dcol';
    const h = document.createElement('div');
    h.className = 'dhead';
    const sq = document.createElement('span');
    sq.className = 'sq' + (filled ? ' fill' : '');
    h.appendChild(sq);
    h.appendChild(document.createTextNode(title));
    c.appendChild(h);
    c.appendChild(cellsEl);
    return c;
  }
  function cells(cols, ...items) {
    const g = document.createElement('div');
    g.className = 'cells' + (cols === 2 ? ' two' : '');
    for (const it of items) g.appendChild(it);
    return g;
  }
  const nd = (addr) => W.numberDrag({ addr });

  function waveThumb(oscX) {
    const cv = document.createElement('canvas');
    cv.width = 140; cv.height = 44;
    cv.style.width = '70px'; cv.style.height = '22px';
    const draw = () => {
      const g = cv.getContext('2d');
      g.clearRect(0, 0, cv.width, cv.height);
      g.strokeStyle = '#7cc0f0'; g.lineWidth = 1.8; g.beginPath();
      const wave = P.get(`osc.${oscX}.wave`);
      for (let i = 0; i <= 300; i++) {
        const t = i / 300, ph = t * 2 * Math.PI;
        let y;
        if (wave === 'Noise') y = Math.sin(ph * 9.7) * Math.sin(ph * 23.3);
        else if (wave === 'Saw D') y = 2 * (t % 1) - 1;
        else if (wave === 'Square D') y = t % 1 < 0.5 ? 0.9 : -0.9;
        else if (wave === 'Triangle') y = 1 - 4 * Math.abs((t % 1) - 0.5);
        else {
          /* engine reads "Sin N" as a pure sine at the Nth harmonic — draw the same */
          const n = { 'Sine': 1, 'Sin 3': 3, 'Sin 4': 4, 'Sin 6': 6, 'Sin 8': 8 }[wave] || 1;
          y = Math.sin(ph * n);
        }
        const px = i * (cv.width / 300), py = cv.height / 2 - y * (cv.height / 2 - 4);
        if (i === 0) g.moveTo(px, py); else g.lineTo(px, py);
      }
      g.stroke();
    };
    cv.opDestroy = P.subscribe(`osc.${oscX}.wave`, draw);
    draw();
    return cv;
  }

  function buildGrid(section) {
    /* unsubscribe every widget the previous grid created, or they leak */
    for (const n of dgrid.querySelectorAll('*')) {
      if (typeof n.opDestroy === 'function') n.opDestroy();
    }
    dgrid.replaceChildren();
    if (section.startsWith('osc')) {
      const x = section.slice(3).toLowerCase();
      const e = (p) => `osc.${x}.env.${p}`;
      const envCol = col('Envelope', true, cells(4,
        cell('Attack', nd(e('attack'))), cell('Decay', nd(e('decay'))),
        cell('Release', nd(e('release'))), cell('Time<Vel', nd(e('timeVel'))),
        cell('Initial', nd(e('initial'))), cell('Peak', nd(e('peak'))),
        cell('Sustain', nd(e('sustain'))), cell('Vel', nd(e('vel'))),
        cell('Loop', W.dropdown({ addr: e('loop'), compact: true })),
        cell('', document.createElement('span')),
        cell('', document.createElement('span')),
        cell('Key', nd(e('key')))
      ));
      envCol.classList.add('blue-vals');
      dgrid.appendChild(envCol);
      /* Decision (recorded): Live's Repeat dropdown is omitted — the engine has
         no repeat mechanism, and a control bound to nothing violates Gate 3. */
      const oscCol = col('Oscillator', false, cells(2,
        cell('Wave', W.dropdown({ addr: `osc.${x}.wave`, compact: true }), waveThumb(x)),
        cell('', document.createElement('span')),
        cell('Feedback', W.numberDrag({ addr: `osc.${x}.feedback`, accent: 'amber' })),
        cell('', document.createElement('span')),
        cell('Phase', W.chip({ addr: `osc.${x}.retrig`, text: 'R' }), W.numberDrag({ addr: `osc.${x}.phase`, accent: 'amber' })),
        cell('Osc<Vel', W.numberDrag({ addr: `osc.${x}.oscVel`, accent: 'amber' }), W.chip({ addr: `osc.${x}.oscVelQ`, text: 'Q' }))
      ));
      oscCol.classList.add('amber-vals');   /* census: amber is the value accent of this group */
      dgrid.appendChild(oscCol);
    } else if (section === 'lfo') {
      dgrid.appendChild(col('LFO', true, cells(4,
        cell('Rate', nd('lfo.rate')), cell('Amount', nd('lfo.amount')),
        cell('Wave', W.dropdown({ addr: 'lfo.wave', compact: true })),
        cell('Dest', W.dropdown({ addr: 'lfo.dest', compact: true })),
        cell('Retrig', W.chip({ addr: 'lfo.retrig', text: 'R' }))
      )));
    } else if (section === 'filter') {
      dgrid.appendChild(col('Filter', true, cells(4,
        cell('Freq', nd('filter.freq')), cell('Res', nd('filter.res')),
        cell('Type', W.dropdown({ addr: 'filter.type', compact: true })),
        cell('Slope', W.pairToggle({ addr: 'filter.slope', options: ['12', '24'] })),
        cell('Circuit', W.dropdown({ addr: 'filter.circuit', compact: true }))
      )));
    } else if (section === 'pitch') {
      dgrid.appendChild(col('Pitch Envelope', true, cells(4,
        cell('Pitch Env', nd('pitch.env')), cell('Spread', nd('pitch.spread')),
        cell('Transpose', nd('pitch.transpose'))
      )));
    } else if (section === 'global') {
      /* Decision (recorded): Voices is omitted — engine polyphony is fixed at 8
         slots; a dead control would violate Gate 3. Algorithm is set by clicking
         a diagram in the graph above (same address, two views, one tree). */
      dgrid.appendChild(col('Global', true, cells(4,
        cell('Time', nd('global.time')), cell('Tone', nd('global.tone')),
        cell('Volume', nd('global.volume'))
      )));
    } else {
      throw new Error('app: unknown section ' + section);
    }
  }

  function renderSelection(section) {
    for (const s of SECTIONS) plates[s].classList.toggle('selected', s === section);
    display.setMode(section);
    buildGrid(section);
  }
  P.subscribe('ui.selected', renderSelection);

  /* Reference state: reproduce the screenshot's session values (the tree's
     defaults are the contract's; the reference is one particular state). */
  P.set('osc.c.coarse', 3);
  P.set('osc.b.fixed', true);
  P.set('osc.b.freq', 468);
  P.set('osc.b.wave', 'Sin 4');
  P.set('lfo.rate', 64);
  /* #oscA…#global in the URL preselects a section (also handy for testing) */
  const hash = (location.hash || '').slice(1);
  if (SECTIONS.includes(hash)) P.set('ui.selected', hash);
  renderSelection(P.get('ui.selected'));   // set() fires on change only — render explicitly once

  /* ---------- device chrome behaviour ---------- */
  /* The activator LED is DERIVED from the tree (volume at the floor = off),
     so it can never desync; toggling off remembers the user's volume and
     toggling on restores it — never the default, never full scale. */
  const led = $('dev-led');
  let savedVolume = null;
  led.addEventListener('click', () => {
    const on = P.get('global.volume') > -70;
    if (on) {
      savedVolume = P.get('global.volume');
      P.set('global.volume', -70);
    } else {
      P.set('global.volume', savedVolume !== null && savedVolume > -70
        ? savedVolume : P.desc('global.volume').def);
    }
  });
  bindNow('global.volume', (v) => led.classList.toggle('off', v <= -70));

  const prev = $('dev-prev');
  let prevTimer = null;
  prev.addEventListener('click', () => {
    if (prevTimer) { clearInterval(prevTimer); prevTimer = null; prev.classList.remove('on'); return; }
    const seq = [48, 51, 55, 60, 55, 51];
    let i = 0;
    prev.classList.add('on');
    audioStarted = true;
    prevTimer = setInterval(() => {
      const n = seq[i % seq.length];
      E.noteOn(n, 100);
      setTimeout(() => E.noteOff(n), 180);
      i++;
    }, 220);
  });

  /* ---------- computer keyboard ---------- */
  /* Keyed by ev.code, not ev.key: a modifier pressed mid-note changes ev.key
     (A -> å under Option on macOS) and the keyup would never match — a stuck
     note and a dead key (verify finding). ev.code is layout- and
     modifier-independent. */
  const KEYMAP = {
    KeyA: 0, KeyW: 1, KeyS: 2, KeyE: 3, KeyD: 4, KeyF: 5, KeyT: 6, KeyG: 7,
    KeyY: 8, KeyH: 9, KeyU: 10, KeyJ: 11, KeyK: 12, KeyO: 13, KeyL: 14,
  };
  let base = 48;
  const down = new Map();
  window.addEventListener('keydown', (ev) => {
    if (ev.repeat || ev.metaKey || ev.ctrlKey || ev.altKey) return;
    if (ev.code === 'KeyZ') { base = Math.max(12, base - 12); return; }
    if (ev.code === 'KeyX') { base = Math.min(84, base + 12); return; }
    if (!(ev.code in KEYMAP) || down.has(ev.code)) return;
    const midi = base + KEYMAP[ev.code];
    down.set(ev.code, midi);
    E.noteOn(midi, 100);
    audioStarted = true;
  });
  window.addEventListener('keyup', (ev) => {
    if (!down.has(ev.code)) return;
    E.noteOff(down.get(ev.code));
    down.delete(ev.code);
  });
  window.addEventListener('blur', () => {
    for (const midi of down.values()) E.noteOff(midi);
    down.clear();
  });

  /* ---------- rAF loop: meter + animated display modes ---------- */
  /* Before the first note there is no engine — the meter renders a distinct
     dimmed state instead of a confident zero (unknown must not look like 0). */
  let audioStarted = false;
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  meter.el.classList.add('meter-off');
  function tick(t) {
    if (audioStarted) {
      meter.el.classList.remove('meter-off');
      meter.update(E.meterLevel());
    }
    if (P.get('ui.selected') === 'lfo' && !reduceMotion.matches) display.draw(t);
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);

  /* ---------- fit the fixed-size device to the viewport ---------- */
  const stage = $('stage'), wrap = $('stagewrap');
  const DEV_W = 1253, DEV_H = 333;   // spec/ratios.md — the device's real frame
  function fit() {
    const avail = stage.clientWidth || innerWidth;
    /* floor at 0.55: below that the panel is present but unusable — the stage
       scrolls horizontally instead (the page body never does) */
    const s = Math.max(0.55, Math.min(1, avail / DEV_W));
    wrap.style.transform = 'scale(' + s + ')';
    wrap.style.width = DEV_W + 'px';
    stage.style.height = Math.ceil(DEV_H * s) + 'px';
    stage.style.overflowX = DEV_W * s > avail ? 'auto' : 'visible';
  }
  window.addEventListener('resize', fit);
  fit();
})();
