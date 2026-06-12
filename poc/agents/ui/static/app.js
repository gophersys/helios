// ── App State ─────────────────────────────────────
const App = {
  agents: {},
  selected: null,
  view: 'agents',      // 'agents' | 'bridge'
  bridge: null,
  sseConnections: {},
  eventLogs: {},
  listeners: [],

  on(fn) { this.listeners.push(fn); },
  emit(event, data) { this.listeners.forEach(fn => fn(event, data)); },

  async fetchJSON(url, options = {}) {
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    });
    if (!res.ok) {
      const text = await res.text();
      let msg = text;
      try { msg = JSON.parse(text).error || text; } catch(e) {}
      throw new Error(msg);
    }
    return res.json();
  },

  async loadAgents() {
    const list = await this.fetchJSON('/api/v1/agents');
    list.forEach(a => { this.agents[a.id] = a; });
    this.emit('agentsLoaded', list);
  },

  async createAgent(config) {
    const a = await this.fetchJSON('/api/v1/agents', {
      method: 'POST',
      body: JSON.stringify(config),
    });
    this.agents[a.id] = { id: a.id, state: a.state, ...config };
    this.emit('agentCreated', a);
    return a;
  },

  async startAgent(id) {
    const a = await this.fetchJSON(`/api/v1/agents/${id}/start`, { method: 'POST' });
    this.agents[id] = { ...this.agents[id], state: a.state };
    this.emit('agentUpdated', a);
    return a;
  },

  async promptAgent(id, message) {
    const a = await this.fetchJSON(`/api/v1/agents/${id}/prompt`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
    this.agents[id] = { ...this.agents[id], state: a.state, token_usage: a.token_usage };
    this.emit('agentUpdated', a);
    return a;
  },

  async abortAgent(id) {
    const a = await this.fetchJSON(`/api/v1/agents/${id}/abort`, { method: 'POST' });
    this.agents[id] = { ...this.agents[id], state: a.state };
    this.emit('agentUpdated', a);
    return a;
  },

  async shutdownAgent(id) {
    const a = await this.fetchJSON(`/api/v1/agents/${id}/shutdown`, { method: 'POST' });
    this.agents[id] = { ...this.agents[id], state: a.state };
    this.emit('agentUpdated', a);
    return a;
  },

  async getAgentDetail(id) {
    return this.fetchJSON(`/api/v1/agents/${id}`);
  },

  async createBridge(supervisorId, workerId) {
    const b = await this.fetchJSON('/api/v1/bridge', {
      method: 'POST',
      body: JSON.stringify({ supervisor_id: supervisorId, worker_id: workerId }),
    });
    this.bridge = b;
    this.emit('bridgeCreated', b);
    return b;
  },

  async getBridgeLog() {
    if (!this.bridge) return [];
    return this.fetchJSON('/api/v1/bridge/log');
  },

  async getBridgeQuestions() {
    if (!this.bridge) return [];
    return this.fetchJSON('/api/v1/bridge/questions');
  },

  async bridgeWorkerPrompt(message) {
    if (!this.bridge) throw new Error('No bridge');
    return this.fetchJSON('/api/v1/bridge/worker-prompt', {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
  },

  getMetricsUrl(id) {
    return `/api/v1/agents/${id}/metrics/stream?replay=20`;
  },

  getEventsUrl(id) {
    return `/api/v1/agents/${id}/events/stream`;
  },

  connectMetricsSSE(id, onEvent) {
    const url = this.getMetricsUrl(id);
    const es = new EventSource(url);
    this.sseConnections[`metrics_${id}`] = es;
    es.addEventListener('metrics', (e) => {
      try { onEvent(JSON.parse(e.data)); } catch(err) {}
    });
    es.addEventListener('keepalive', () => {});
    es.onerror = () => {
      // Will auto-reconnect
    };
    return () => es.close();
  },

  connectEventsSSE(id, onEvent) {
    const url = this.getEventsUrl(id);
    const es = new EventSource(url);
    this.sseConnections[`events_${id}`] = es;
    es.addEventListener('message', (e) => {
      try { onEvent(JSON.parse(e.data), 'message'); } catch(err) {}
    });
    es.addEventListener('keepalive', () => {});
    // Also handle named events (agent_start, agent_end, etc.)
    es.onmessage = (e) => {
      // Fallback: events without explicit event type
    };
    es.onerror = () => {};
    return () => es.close();
  },

  disconnectAllSSE() {
    Object.values(this.sseConnections).forEach(es => es.close());
    this.sseConnections = {};
  }
};

// ── Router ────────────────────────────────────────
function initRouter() {
  const path = window.location.pathname;
  const match = path.match(/\/ui\/agents\/([^/]+)/);
  const bridgeMatch = path.match(/\/ui\/bridge/);

  if (match) {
    App.selected = match[1];
    App.view = 'agents';
  } else if (bridgeMatch) {
    App.view = 'bridge';
  } else {
    App.view = 'agents';
    App.selected = null;
  }
}

function navigate(path) {
  window.history.pushState(null, '', path);
  render();
}

// ── Render ────────────────────────────────────────
function render() {
  const now = App.view;
  if (now === 'agents' && App.selected) {
    renderAgentDetail(App.selected);
  } else if (now === 'bridge') {
    renderBridgeView();
  } else {
    renderEmptyState();
  }
  renderSidebar();
  updateConnectionStatus();
}

function renderSidebar() {
  const sidebar = document.querySelector('.sidebar');
  if (!sidebar) return;

  // Agent list
  const container = sidebar.querySelector('.agent-list') || sidebar.appendChild(el('div', 'agent-list'));
  container.innerHTML = '';

  // Create agent card
  const createCard = el('div', 'create-agent-form');
  createCard.innerHTML = `
    <h3>Create Agent</h3>
    <div class="form-row">
      <select id="agent-role">
        <option value="standalone">Agent</option>
        <option value="supervisor">Supervisor</option>
        <option value="worker">Worker</option>
      </select>
      <select id="agent-model">
        <option value="openrouter/deepseek/deepseek-v4-flash">DeepSeek V4</option>
        <option value="anthropic/claude-sonnet-4-20250514">Claude Sonnet 4</option>
      </select>
    </div>
    <div class="form-row">
      <textarea id="agent-task" rows="2" placeholder="Describe the task for this agent..." style="flex:1;background:var(--bg-tertiary);border:1px solid var(--border);border-radius:var(--radius-sm);color:var(--text-primary);padding:6px 10px;font-size:13px;resize:vertical;min-height:36px;"></textarea>
    </div>
    <div class="form-row" style="justify-content:flex-end;">
      <button class="btn btn-primary btn-sm" onclick="handleCreateAgent()">Create</button>
    </div>
  `;
  container.appendChild(createCard);

  // Existing agents
  const ids = Object.keys(App.agents).sort();
  ids.forEach(id => {
    const a = App.agents[id];
    const role = a._role || 'standalone';
    const card = el('div', 'agent-card');
    if (App.selected === id) card.classList.add('active');
    card.onclick = () => { selectAgent(id); };

    const tokens = a.token_usage || {};
    card.innerHTML = `
      <div class="agent-card-header">
        <span class="agent-card-name">${escapeHtml(id)}</span>
        <span class="agent-card-role ${role}">${role}</span>
      </div>
      <div class="status-badge ${a.state || 'created'}">${a.state || 'created'}</div>
      <div class="agent-card-stats" style="margin-top:8px;">
        <span>⬆ ${tokens.input_tokens || 0}</span>
        <span>⬇ ${tokens.output_tokens || 0}</span>
        <span>$${(tokens.cost_usd || 0).toFixed(4)}</span>
        <span>${a.uptime || ''}</span>
      </div>
    `;
    container.appendChild(card);
  });

  // Bridge section
  if (App.bridge) {
    const bridgeSection = el('div', 'create-agent-form');
    bridgeSection.style.marginTop = '8px';
    bridgeSection.innerHTML = `
      <h3>Bridge Active</h3>
      <div style="font-size:12px;color:var(--text-secondary);margin-bottom:8px;">
        Supervisor: <span class="agent-card-role supervisor">${escapeHtml(App.bridge.supervisor_id)}</span>
        Worker: <span class="agent-card-role worker">${escapeHtml(App.bridge.worker_id)}</span>
      </div>
      <button class="btn btn-sm" onclick="navigate('/ui/bridge')">View Bridge</button>
    `;
    container.appendChild(bridgeSection);
  }
}

function renderEmptyState() {
  const main = document.querySelector('.main-content');
  if (!main) return;
  main.classList.add('empty');
  main.innerHTML = `
    <div class="empty-state">
      <h2>Helios Agent Runtime</h2>
      <p>Create an agent on the left to get started. Agents run headless OMP sessions with full real-time observability via SSE.</p>
    </div>
  `;
}

function selectAgent(id) {
  App.selected = id;
  App.view = 'agents';
  navigate(`/ui/agents/${id}`);
}

// ── Agent Detail View ─────────────────────────────
let currentAgentCleanups = [];

function renderAgentDetail(id) {
  const main = document.querySelector('.main-content');
  if (!main) return;
  main.classList.remove('empty');

  // Cleanup previous SSE connections
  currentAgentCleanups.forEach(fn => fn());
  currentAgentCleanups = [];

  main.innerHTML = `
    <div class="agent-view">
      <div class="agent-view-header">
        <div class="info">
          <h2>${escapeHtml(id)}</h2>
          <div class="meta">
            <span class="status-badge ${(App.agents[id] || {}).state || 'created'}">${(App.agents[id] || {}).state || 'created'}</span>
            <span style="margin-left:8px;">Model: ${(App.agents[id] || {})._model || 'default'}</span>
          </div>
        </div>
        <div class="actions">
          <button class="btn btn-sm" onclick="handleStartAgent('${id}')" id="btn-start">Start</button>
          <button class="btn btn-sm btn-danger" onclick="handleAbortAgent('${id}')" id="btn-abort">Abort</button>
          <button class="btn btn-sm btn-danger" onclick="handleShutdownAgent('${id}')" id="btn-shutdown">Shutdown</button>
        </div>
      </div>
      <div class="tabs">
        <div class="tab active" data-tab="chat">Chat</div>
        <div class="tab" data-tab="metrics">Metrics</div>
        <div class="tab" data-tab="events">Events</div>
      </div>
      <div id="tab-content" style="flex:1;display:flex;flex-direction:column;overflow:hidden;">
        <div class="chat-tab-content" style="flex:1;display:flex;flex-direction:column;overflow:hidden;">
          <div class="chat-area" id="chat-area"></div>
          <div class="task-panel">
            <div class="task-form">
              <textarea id="prompt-input" placeholder="Send a message to the agent..." rows="1"></textarea>
              <button class="btn btn-primary" onclick="handlePrompt('${id}')">Send</button>
            </div>
          </div>
        </div>
      </div>
      <div class="toolbar-stats" id="stats-bar">
        <span class="stat">Tokens: <strong id="stat-tokens">0</strong></span>
        <span class="stat">Cost: <strong id="stat-cost">$0.0000</strong></span>
        <span class="stat">Turns: <strong id="stat-turns">0</strong></span>
        <span class="stat">Tools: <strong id="stat-tools">0</strong></span>
        <span class="stat">Events: <strong id="stat-events">0</strong></span>
      </div>
    </div>
  `;

  // Tab switching
  document.querySelectorAll('.tab').forEach(tab => {
    tab.onclick = () => switchAgentTab(id, tab.dataset.tab);
  });

  // Prompt enter
  const promptInput = document.getElementById('prompt-input');
  if (promptInput) {
    promptInput.onkeydown = (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handlePrompt(id);
      }
    };
  }

  // Connect SSE for events
  const cleanupEvents = App.connectEventsSSE(id, (frame, eventType) => {
    appendAgentEvent(id, frame, eventType);
    updateStats(id);
  });
  currentAgentCleanups.push(cleanupEvents);

  // Connect SSE for metrics
  const cleanupMetrics = App.connectMetricsSSE(id, (metric) => {
    appendAgentMetric(id, metric);
    updateAgentMessage(id, metric);
  });
  currentAgentCleanups.push(cleanupMetrics);

  // Load existing detail
  App.getAgentDetail(id).then(a => {
    updateStatsBar(a);
  }).catch(() => {});
}

function switchAgentTab(id, tab) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelector(`.tab[data-tab="${tab}"]`)?.classList.add('active');

  const content = document.getElementById('tab-content');
  if (!content) return;

  if (tab === 'chat') {
    content.innerHTML = `
      <div style="flex:1;display:flex;flex-direction:column;overflow:hidden;">
        <div class="chat-area" id="chat-area"></div>
        <div class="task-panel">
          <div class="task-form">
            <textarea id="prompt-input" placeholder="Send a message..." rows="1"></textarea>
            <button class="btn btn-primary" onclick="handlePrompt('${id}')">Send</button>
          </div>
        </div>
      </div>
    `;
    const pi = document.getElementById('prompt-input');
    if (pi) pi.onkeydown = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handlePrompt(id); } };
    replayChatBuffer(id);
  } else if (tab === 'metrics') {
    content.innerHTML = `<div class="metrics-panel" id="metrics-grid"></div><div class="event-log" id="event-log" style="flex:1;"></div>`;
    renderMetricsGrid(id);
    renderEventLog(id);
  } else if (tab === 'events') {
    content.innerHTML = `<div class="event-log" id="event-log" style="flex:1;max-height:unset;"></div>`;
    renderEventLog(id);
  }
}

function renderMetricsGrid(id) {
  const grid = document.getElementById('metrics-grid');
  if (!grid) return;
  grid.innerHTML = `
    <div class="metric-card"><div class="value blue" id="m-tokens-in">0</div><div class="label">Tokens In</div></div>
    <div class="metric-card"><div class="value blue" id="m-tokens-out">0</div><div class="label">Tokens Out</div></div>
    <div class="metric-card"><div class="value green" id="m-cost">$0</div><div class="label">Cost</div></div>
    <div class="metric-card"><div class="value yellow" id="m-turns">0</div><div class="label">Turns</div></div>
    <div class="metric-card"><div class="value purple" id="m-tools">0</div><div class="label">Tool Calls</div></div>
    <div class="metric-card"><div class="value cyan" id="m-events">0</div><div class="label">Total Events</div></div>
  `;
}

function renderEventLog(id) {
  const log = document.getElementById('event-log');
  if (!log) return;
  log.innerHTML = '';
  const events = App.eventLogs[id] || [];
  events.forEach(evt => {
    const row = el('div', 'event');
    row.innerHTML = `<span class="event-time">${evt.time}</span><span class="event-type ${evt.type}">${escapeHtml(evt.type)}</span>`;
    log.appendChild(row);
  });
}

// Message buffer — persists across tab switches
const messageBuffers = {};

function getBuffer(id) {
  if (!messageBuffers[id]) messageBuffers[id] = [];
  return messageBuffers[id];
}

function appendAgentEvent(id, frame, eventType) {
  const time = new Date().toLocaleTimeString();
  if (!App.eventLogs[id]) App.eventLogs[id] = [];
  App.eventLogs[id].push({ time, type: frame.type || eventType || 'event' });

  const log = document.getElementById('event-log');
  if (log) {
    const row = el('div', 'event');
    row.innerHTML = `<span class="event-time">${time}</span><span class="event-type ${frame.type || eventType}">${escapeHtml(frame.type || eventType)}</span>`;
    log.appendChild(row);
    log.scrollTop = log.scrollHeight;
  }

  // Buffer AND render chat messages
  const buf = getBuffer(id);

  if (frame.type === 'message_update' && frame.assistantMessageEvent) {
    const text = extractText(frame.assistantMessageEvent);
    if (text) {
      const lastBuf = buf[buf.length - 1];
      if (lastBuf && lastBuf.role === 'assistant') {
        lastBuf.text += text;
      } else {
        buf.push({ role: 'assistant', text });
      }
      renderChatMessage(id, text, 'assistant');
    }
  }

  if (frame.type === 'tool_execution_start') {
    buf.push({ role: 'tool', toolName: frame.toolName || 'tool', args: {}, result: '' });
    renderToolCall(id, buf[buf.length - 1]);
  }

  if (frame.type === 'tool_execution_update' && frame.partialResult) {
    const lastBuf = buf[buf.length - 1];
    if (lastBuf && lastBuf.role === 'tool') {
      lastBuf.args = frame.partialResult;
      updateToolCallDOM(id, lastBuf);
    }
  }

  if (frame.type === 'tool_execution_end' && frame.result) {
    const lastBuf = buf[buf.length - 1];
    if (lastBuf && lastBuf.role === 'tool') {
      lastBuf.result = frame.result;
      finishToolCallDOM(id, lastBuf);
    }
  }

  if (frame.type === 'agent_start') {
    buf.push({ role: 'thinking', text: '🤖 Agent turn started...' });
    renderThinkingBlock(id, '🤖 Agent turn started...');
  }

  if (frame.type === 'agent_end') {
    buf.push({ role: 'thinking', text: '✅ Agent turn complete' });
    renderThinkingBlock(id, '✅ Agent turn complete');
  }
}

function renderChatMessage(id, text, role) {
  const area = document.getElementById('chat-area');
  if (!area) return;
  if (!text) return;
  const last = area.lastElementChild;
  if (last && last.classList.contains('message') && last.classList.contains(role || 'assistant')) {
    const textEl = last.querySelector('.text');
    if (textEl) { textEl.textContent += text; area.scrollTop = area.scrollHeight; return; }
  }
  const msg = el('div', 'message');
  msg.classList.add(role || 'assistant');
  msg.innerHTML = `<div class="sender">${role === 'assistant' ? 'Agent' : role === 'user' ? 'You' : ''}</div><div class="text">${escapeHtml(text)}</div>`;
  area.appendChild(msg);
  area.scrollTop = area.scrollHeight;
}

function renderThinkingBlock(id, text) {
  const area = document.getElementById('chat-area');
  if (!area) return;
  const msg = el('div', 'thinking-block');
  msg.textContent = text;
  area.appendChild(msg);
  area.scrollTop = area.scrollHeight;
}

function renderToolCall(id, data) {
  const area = document.getElementById('chat-area');
  if (!area) return;
  const tc = el('div', 'tool-call');
  tc.dataset.bufIndex = (getBuffer(id).indexOf(data)) || '0';
  tc.innerHTML = `<div class="tool-name">🔧 ${escapeHtml(data.toolName)}</div>`;
  if (data.args && Object.keys(data.args).length > 0) {
    tc.innerHTML += `<div class="tool-args">${escapeHtml(JSON.stringify(data.args, null, 2))}</div>`;
  }
  if (data.result) {
    tc.innerHTML += `<div style="margin-top:4px;color:var(--accent-green);font-size:12px;">→ ${escapeHtml(data.result)}</div>`;
    tc.style.borderLeftColor = 'var(--accent-green)';
  }
  area.appendChild(tc);
  area.scrollTop = area.scrollHeight;
}

function updateToolCallDOM(id, data) {
  // Update the matching tool-call element in the DOM
  const idx = getBuffer(id).indexOf(data);
  const area = document.getElementById('chat-area');
  if (!area) return;
  const tcs = area.querySelectorAll('.tool-call');
  const tc = tcs[tcs.length - 1]; // always the last tool call
  if (!tc) return;
  const argsEl = tc.querySelector('.tool-args');
  if (argsEl && data.args) {
    argsEl.textContent = JSON.stringify(data.args, null, 2);
  } else if (data.args && !argsEl) {
    const div = document.createElement('div');
    div.className = 'tool-args';
    div.textContent = JSON.stringify(data.args, null, 2);
    tc.appendChild(div);
  }
}

function finishToolCallDOM(id, data) {
  const area = document.getElementById('chat-area');
  if (!area) return;
  const tcs = area.querySelectorAll('.tool-call');
  const tc = tcs[tcs.length - 1];
  if (!tc) return;
  tc.style.borderLeftColor = 'var(--accent-green)';
  tc.style.opacity = '0.85';
  if (data.result) {
    const resEl = document.createElement('div');
    resEl.style.cssText = 'margin-top:4px;color:var(--accent-green);font-size:12px;';
    resEl.textContent = '→ ' + (typeof data.result === 'string' ? data.result : JSON.stringify(data.result, null, 2));
    tc.appendChild(resEl);
  }
}

// Replay all buffered messages into chat-area (called when switching to Chat tab)
function replayChatBuffer(id) {
  const area = document.getElementById('chat-area');
  if (!area) return;
  area.innerHTML = '';
  const buf = getBuffer(id);
  for (const entry of buf) {
    if (entry.role === 'assistant' || entry.role === 'user') {
      const msg = el('div', 'message');
      msg.classList.add(entry.role);
      msg.innerHTML = `<div class="sender">${entry.role === 'assistant' ? 'Agent' : 'You'}</div><div class="text">${escapeHtml(entry.text)}</div>`;
      area.appendChild(msg);
    } else if (entry.role === 'thinking') {
      const tb = el('div', 'thinking-block');
      tb.textContent = entry.text;
      area.appendChild(tb);
    } else if (entry.role === 'tool') {
      renderToolCall(id, entry);
    }
  }
  area.scrollTop = area.scrollHeight;
}

function extractText(data) {
  if (!data) return '';
  if (data.delta && typeof data.delta === 'string') return data.delta;
  if (data.text && typeof data.text === 'string') return data.text;
  if (data.delta && typeof data.delta === 'object') return data.delta.text || '';
  if (data.partial_json) return data.partial_json;
  return '';
}

function appendAgentMetric(id, metric) {
  const byId = (sel) => document.getElementById(sel);
  const m = metric;
  if (!m) return;

  // Token tracking — always present (even 0), so check !== undefined
  if (m.input_tokens !== undefined) {
    const v = byId('m-tokens-in'); if (v) v.textContent = m.input_tokens;
    const v2 = byId('stat-tokens'); if (v2) v2.textContent = m.input_tokens;
  }
  if (m.output_tokens !== undefined) {
    const v = byId('m-tokens-out'); if (v) v.textContent = m.output_tokens;
  }
  if (m.cost_usd !== undefined) {
    const v = byId('m-cost'); if (v) v.textContent = `$${m.cost_usd.toFixed(6)}`;
    const v2 = byId('stat-cost'); if (v2) v2.textContent = `$${m.cost_usd.toFixed(6)}`;
  }
  if (m.turn_count !== undefined) {
    const v = byId('m-turns'); if (v) v.textContent = m.turn_count;
    const v2 = byId('stat-turns'); if (v2) v2.textContent = m.turn_count;
  }
  if (m.tool_call_count !== undefined) {
    const v = byId('m-tools'); if (v) v.textContent = m.tool_call_count;
    const v2 = byId('stat-tools'); if (v2) v2.textContent = m.tool_call_count;
  }
  if (m.filesystem_ops !== undefined) {
    const v = byId('stat-fs'); if (v) v.textContent = m.filesystem_ops;
  }

  // State transitions update the status badge
  if (m.type === 'state_transition') {
    const badge = document.querySelector('.status-badge');
    if (badge && m.state_to) {
      badge.className = `status-badge ${m.state_to}`;
      badge.textContent = m.state_to;
    }
  }
}

function updateStats(id) {
  const count = (App.eventLogs[id] || []).length;
  const v = document.getElementById('stat-events');
  if (v) v.textContent = count;
}

function updateStatsBar(a) {
  const tokens = a.tokens_in || 0;
  const cost = a.cost_usd || 0;
  const v1 = document.getElementById('stat-tokens'); if (v1) v1.textContent = tokens;
  const v2 = document.getElementById('stat-cost'); if (v2) v2.textContent = `$${cost.toFixed(4)}`;
}


// ── Bridge View ───────────────────────────────────
function renderBridgeView() {
  const main = document.querySelector('.main-content');
  if (!main) return;
  main.classList.remove('empty');

  if (!App.bridge) {
    main.innerHTML = `<div class="empty-state"><h2>No Bridge Active</h2><p>Create a supervisor and worker agent, then create a bridge from the sidebar.</p></div>`;
    return;
  }

  const supId = App.bridge.supervisor_id;
  const wrkId = App.bridge.worker_id;

  main.innerHTML = `
    <div class="bridge-view">
      <div class="bridge-view-header" style="padding:12px 16px;background:var(--bg-secondary);border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px;">
        <div class="info" style="flex:1;">
          <h2 style="font-size:16px;font-weight:600;">Supervisor / Worker Bridge</h2>
          <div style="font-size:12px;color:var(--text-muted);margin-top:2px;">
            <span class="agent-card-role supervisor">${escapeHtml(supId)}</span>
            ↔
            <span class="agent-card-role worker">${escapeHtml(wrkId)}</span>
          </div>
        </div>
        <div class="actions">
          <button class="btn btn-sm btn-primary" onclick="handleBridgeWorkerPrompt()">Prompt Worker</button>
        </div>
      </div>
      <div class="bridge-layout">
        <div class="bridge-column">
          <div class="bridge-column-header supervisor">Supervisor: ${escapeHtml(supId)}</div>
          <div class="bridge-column-chat" id="supervisor-chat"></div>
        </div>
        <div class="bridge-center">
          <div class="bridge-arrow to-supervisor">Worker asks<br><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg></div>
          <div class="bridge-arrow to-worker" style="animation-delay:1s;">Supervisor answers<br><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg></div>
        </div>
        <div class="bridge-column">
          <div class="bridge-column-header worker">Worker: ${escapeHtml(wrkId)}</div>
          <div class="bridge-column-chat" id="worker-chat"></div>
        </div>
      </div>
      <div class="bridge-question-log" id="bridge-log" style="max-height:150px;">
        <div style="font-size:11px;color:var(--text-muted);margin-bottom:4px;">Question Log</div>
      </div>
      <div class="toolbar-stats">
        <span class="stat">Questions: <strong id="bridge-q-count">0</strong></span>
        <button class="btn btn-sm" onclick="refreshBridgeLog()">Refresh Log</button>
      </div>
    </div>
  `;

  // Connect SSE for both agents
  [supId, wrkId].forEach(id => {
    const cleanup = App.connectEventsSSE(id, (frame) => {
      const chatId = id === supId ? 'supervisor-chat' : 'worker-chat';
      const chat = document.getElementById(chatId);
      if (!chat || !frame) return;

      if (frame.type === 'message_update' && frame.assistantMessageEvent) {
        const delta = frame.assistantMessageEvent.delta || frame.assistantMessageEvent.text || '';
        if (!delta) return;
        const last = chat.lastElementChild;
        if (last && last.classList.contains('message')) {
          last.innerHTML = `<div class="sender">${escapeHtml(id)}</div><div class="text">${escapeHtml(delta)}</div>`;
          chat.scrollTop = chat.scrollHeight;
          return;
        }
        const msg = el('div', 'message');
        msg.innerHTML = `<div class="sender">${escapeHtml(id)}</div><div class="text">${escapeHtml(delta)}</div>`;
        chat.appendChild(msg);
        chat.scrollTop = chat.scrollHeight;
      }
    });
    currentAgentCleanups.push(cleanup);
  });

  refreshBridgeLog();
}

async function refreshBridgeLog() {
  try {
    const log = await App.getBridgeLog();
    const container = document.getElementById('bridge-log');
    const countEl = document.getElementById('bridge-q-count');
    if (container) {
      container.innerHTML = '<div style="font-size:11px;color:var(--text-muted);margin-bottom:4px;">Question Log</div>';
      log.slice(-20).forEach(entry => {
        const div = el('div', 'bridge-log-entry');
        div.innerHTML = `
          <div class="time">${new Date(entry.timestamp).toLocaleTimeString()}</div>
          <div class="q">Q: ${escapeHtml(entry.question || '')}</div>
          <div class="a">A: ${escapeHtml(entry.answer || '')}</div>
          ${entry.error ? `<div style="color:var(--accent-red);">Error: ${escapeHtml(entry.error)}</div>` : ''}
        `;
        container.appendChild(div);
      });
    }
    if (countEl) countEl.textContent = log.length;
  } catch(e) {}
}

// ── Action Handlers ───────────────────────────────
async function handleCreateAgent() {
  const roleSelect = document.getElementById('agent-role');
  const modelSelect = document.getElementById('agent-model');
  const taskInput = document.getElementById('agent-task');
  const role = roleSelect?.value || 'standalone';
  const model = modelSelect?.value || 'openrouter/deepseek/deepseek-v4-flash';
  const task = taskInput?.value || '';

  try {
    const a = await App.createAgent({
      model,
      thinking_level: 'high',
      in_memory: true,
      labels: { role },
    });
    a._role = role;
    a._model = model;
    App.agents[a.id]._role = role;
    App.agents[a.id]._model = model;
    if (taskInput) taskInput.value = '';

    // Start the agent
    await App.startAgent(a.id);

    // Auto-create bridge if both supervisor and worker exist
    const sup = Object.values(App.agents).find(a => a._role === 'supervisor');
    const wrk = Object.values(App.agents).find(a => a._role === 'worker');
    if (sup && wrk && !App.bridge) {
      await App.createBridge(sup.id, wrk.id);
    }

    // If there's a task, prompt the agent
    if (task) {
      if (role === 'worker' && App.bridge) {
        await App.bridgeWorkerPrompt(task);
      } else if (role === 'standalone') {
        await App.promptAgent(a.id, task);
      } else if (role === 'supervisor') {
        await App.promptAgent(a.id, task);
      }
    }

    selectAgent(a.id);
    renderSidebar();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

async function handleStartAgent(id) {
  try {
    await App.startAgent(id);
    render();
  } catch (e) { showToast(e.message, 'error'); }
}

async function handlePrompt(id) {
  const input = document.getElementById('prompt-input');
  if (!input || !input.value.trim()) return;
  const msg = input.value;
  input.value = '';

  // Add user message to chat
  const area = document.getElementById('chat-area');
  if (area) {
    const msgEl = el('div', 'message');
    msgEl.classList.add('user');
    msgEl.innerHTML = `<div class="sender">You</div><div class="text">${escapeHtml(msg)}</div>`;
    area.appendChild(msgEl);
    area.scrollTop = area.scrollHeight;
  }

  try {
    await App.promptAgent(id, msg);
  } catch (e) { showToast(e.message, 'error'); }
}

async function handleAbortAgent(id) {
  try {
    await App.abortAgent(id);
    render();
  } catch (e) { showToast(e.message, 'error'); }
}

async function handleShutdownAgent(id) {
  try {
    await App.shutdownAgent(id);
    render();
  } catch (e) { showToast(e.message, 'error'); }
}

async function handleBridgeWorkerPrompt() {
  const msg = prompt('Message to worker:');
  if (!msg) return;
  try {
    await App.bridgeWorkerPrompt(msg);
    refreshBridgeLog();
  } catch (e) { showToast(e.message, 'error'); }
}

// ── Toast ─────────────────────────────────────────
function showToast(msg, type = 'info') {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = el('div', 'toast-container');
    document.body.appendChild(container);
  }
  const toast = el('div', 'toast');
  if (type) toast.classList.add(type);
  toast.textContent = msg;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

// ── Connection Status ─────────────────────────────
function updateConnectionStatus() {
  const dot = document.querySelector('.connection-dot');
  if (dot) {
    dot.classList.add('connected');
    dot.classList.remove('reconnecting');
  }
}

// ── Utilities ─────────────────────────────────────
function el(tag, cls) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  return e;
}

function escapeHtml(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

// ── Init ──────────────────────────────────────────
function init() {
  // Create app structure
  const app = document.getElementById('app');
  app.innerHTML = `
    <header class="app-header">
      <h1><span class="logo">⚡</span> Helios Agent Runtime</h1>
      <div class="connection-status">
        <span class="connection-dot"></span>
        <span>Connected</span>
      </div>
    </header>
    <div class="app-body">
      <aside class="sidebar">
        <div class="sidebar-header">
          <h2>Agents</h2>
        </div>
        <div class="agent-list"></div>
      </aside>
      <main class="main-content empty"></main>
    </div>
  `;

  initRouter();

  // Load agents
  App.loadAgents().then(() => {
    render();
  }).catch(() => {});

  // Handle browser back/forward
  window.onpopstate = () => {
    initRouter();
    render();
  };
}

document.addEventListener('DOMContentLoaded', init);