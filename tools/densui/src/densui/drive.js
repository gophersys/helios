/* densui drive — gesture-level CDP driver. Node >=22 (global WebSocket).
 * argv: <ws-url> <scenario-json>. Scenario: array of ops —
 *   {op:"eval", js}                      -> value
 *   {op:"click", x, y}                  -> null
 *   {op:"drag", x, y, dx, dy, steps?}   -> null   (pointer down, move, up)
 *   {op:"wheel", x, y, deltaY}          -> null
 * Emits one JSON line: {results:[...]} or exits non-zero with the error.
 */
'use strict';

const [wsUrl, scenarioJson] = process.argv.slice(2);
if (!wsUrl || !scenarioJson) { console.error('usage: drive.js <ws> <scenario>'); process.exit(2); }
const scenario = JSON.parse(scenarioJson);

const ws = new WebSocket(wsUrl);
let id = 0;
const pending = new Map();

function send(method, params) {
  return new Promise((resolve, reject) => {
    const mid = ++id;
    pending.set(mid, { resolve, reject });
    ws.send(JSON.stringify({ id: mid, method, params }));
  });
}

ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) {
    const p = pending.get(msg.id);
    pending.delete(msg.id);
    if (msg.error) p.reject(new Error(msg.error.message));
    else p.resolve(msg.result);
  }
};
ws.onerror = (e) => { console.error('ws error', e.message || e); process.exit(1); };

const mouse = (type, x, y, extra = {}) =>
  send('Input.dispatchMouseEvent', { type, x, y, button: 'left', buttons: 1, ...extra });

async function run() {
  const results = [];
  for (const step of scenario) {
    if (step.op === 'eval') {
      const r = await send('Runtime.evaluate', { expression: step.js, returnByValue: true });
      if (r.exceptionDetails) throw new Error('eval threw: ' + JSON.stringify(r.exceptionDetails.exception));
      results.push(r.result.value === undefined ? null : r.result.value);
    } else if (step.op === 'click') {
      await mouse('mousePressed', step.x, step.y, { clickCount: 1 });
      await mouse('mouseReleased', step.x, step.y, { clickCount: 1, buttons: 0 });
      results.push(null);
    } else if (step.op === 'drag') {
      const steps = step.steps || 8;
      await mouse('mousePressed', step.x, step.y, { clickCount: 1 });
      for (let i = 1; i <= steps; i++) {
        await mouse('mouseMoved', step.x + (step.dx * i) / steps, step.y + (step.dy * i) / steps);
      }
      await mouse('mouseReleased', step.x + step.dx, step.y + step.dy, { buttons: 0 });
      results.push(null);
    } else if (step.op === 'wheel') {
      await send('Input.dispatchMouseEvent',
        { type: 'mouseWheel', x: step.x, y: step.y, deltaX: 0, deltaY: step.deltaY });
      results.push(null);
    } else if (step.op === 'wait_pre') {
      // Poll for a completion <pre> the page inserts when its measurement is
      // done. This replaces chrome's DOM-dump mode, whose exit hinges on its
      // quiescence heuristics — which hung (twice) and SIGABRTed (once) on
      // the fleet with font-heavy pages. CDP asks the page directly and WE
      // decide the deadline.
      const deadline = Date.now() + (step.deadlineMs || 30000);
      const expr = '(function(){var e=document.getElementById(' +
        JSON.stringify(step.id) + ');return e?e.textContent:null;})()';
      let content = null;
      while (Date.now() < deadline) {
        const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true });
        if (r.exceptionDetails) throw new Error('wait_pre eval threw: ' + JSON.stringify(r.exceptionDetails.exception));
        if (r.result.value !== null && r.result.value !== undefined) { content = r.result.value; break; }
        await new Promise((res) => setTimeout(res, 250));
      }
      if (content === null) throw new Error('wait_pre: #' + step.id + ' did not appear within ' + (step.deadlineMs || 30000) + 'ms');
      results.push(content);
    } else {
      throw new Error('unknown op ' + step.op);
    }
  }
  process.stdout.write(JSON.stringify({ results }) + '\n');
  process.exit(0);
}

ws.onopen = () => { run().catch((e) => { console.error(String(e)); process.exit(1); }); };
