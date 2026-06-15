/**
 * Compact vertical agent list for the narrow AI Reasoning Canvas column.
 * Each row is clickable when trace data is available — fires 'agent-trace-detail' event.
 */

const AGENTS = [
  { id: "A1_Intake",              label: "A1 · Triage",       desc: "Normalize & scrub"    },
  { id: "A2_Retrieval",           label: "A2 · Indexer",      desc: "KB runbooks"          },
  { id: "A2b_OperationalContext", label: "A2b · Context",     desc: "Calendar & oncall"    },
  { id: "A11_WebSearch",          label: "A11 · Search",      desc: "Bing fallback", hidden: true },
  { id: "A3_Correlation",         label: "A3 · Correlator",   desc: "Hypothesis gen"       },
  { id: "A8_AdversarialReview",   label: "A8 · Reviewer",     desc: "Adversarial critique" },
  { id: "A4_RiskAnalyzer",        label: "A4 · Risk Engine",  desc: "Blast radius"         },
  { id: "A5_ActionPlanner",       label: "A5 · Planner",      desc: "Mitigation steps"     },
  { id: "A6_Guardrail",           label: "A6 · Safety",       desc: "Policy gates"         },
  { id: "A7_Communication",       label: "A7 · Broadcaster",  desc: "Status reports"       },
  { id: "A9_Retrospective",       label: "A9 · Auditor",      desc: "Accuracy score"       },
  { id: "A10_KnowledgeIngest",    label: "A10 · Learner",     desc: "KB self-update"       },
];

const ReasoningChain = {
  _traces: {},   // keyed by agent_id → full trace detail object

  render(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const rows = AGENTS.map((a, i) => {
      const isLast = i === AGENTS.length - 1;
      return `
        <div id="node-${a.id}"
             class="agent-row${a.hidden ? ' hidden' : ''}"
             data-agent-id="${a.id}">
          <div class="agent-row-timeline${isLast ? '' : ' has-line'}">
            <div class="agent-dot" id="dot-${a.id}"></div>
          </div>
          <div class="agent-row-body">
            <div class="agent-row-name">${a.label}</div>
            <div class="agent-row-desc">${a.desc}</div>
            <div class="agent-row-status" id="status-${a.id}">Waiting</div>
          </div>
          <div class="agent-row-chevron" id="chevron-${a.id}" style="display:none;">›</div>
        </div>
      `;
    }).join('');

    container.innerHTML = `<div class="agent-list">${rows}</div>`;

    // Bind click handlers — trace detail on row click, retry on button click
    container.querySelectorAll('.agent-row').forEach(row => {
      row.addEventListener('click', (e) => {
        if (e.target.closest('.agent-retry-btn')) return; // handled separately
        const id = row.dataset.agentId;
        const trace = this._traces[id];
        if (trace) {
          document.dispatchEvent(new CustomEvent('agent-trace-detail', { detail: trace }));
        }
      });
    });

    // Delegated retry button clicks
    container.addEventListener('click', (e) => {
      const btn = e.target.closest('.agent-retry-btn');
      if (!btn) return;
      e.stopPropagation();
      document.dispatchEvent(new CustomEvent('agent-retry', { detail: { agentId: btn.dataset.agentId } }));
    });
  },

  setAgentState(agentId, state, details = {}) {
    const node      = document.getElementById(`node-${agentId}`);
    const dot       = document.getElementById(`dot-${agentId}`);
    const statusEl  = document.getElementById(`status-${agentId}`);
    const chevronEl = document.getElementById(`chevron-${agentId}`);
    if (!node || !statusEl) return;

    // Show A11 WebSearch row when invoked
    if (agentId === 'A11_WebSearch') node.classList.remove('hidden');

    node.classList.remove('running', 'completed', 'failed');
    if (dot) dot.className = 'agent-dot';

    if (state === 'running') {
      node.classList.add('running');
      statusEl.innerHTML = '<span class="pulsing-dot" style="background:var(--primary);margin-right:3px;"></span>Working…';
      if (dot) dot.classList.add('running');

    } else if (state === 'completed') {
      node.classList.add('completed');
      const dur = details.duration_ms ? `${(details.duration_ms / 1000).toFixed(1)}s` : 'done';
      statusEl.textContent = `✓ ${dur}`;
      if (dot) dot.classList.add('completed');

      const agent = AGENTS.find(a => a.id === agentId);
      this._traces[agentId] = { agent_id: agentId, agent_label: agent ? agent.label : agentId, ...details };
      if (chevronEl) chevronEl.style.display = 'block';
      node.classList.add('clickable');

    } else if (state === 'failed') {
      node.classList.add('failed');
      statusEl.innerHTML = `✗ Error <button class="agent-retry-btn" data-agent-id="${agentId}" title="Retry this agent" style="margin-left:6px;padding:1px 7px;font-size:0.68rem;border:1px solid var(--danger-text);border-radius:4px;background:transparent;color:var(--danger-text);cursor:pointer;vertical-align:middle;">⟳ Retry</button>`;
      if (dot) dot.classList.add('failed');
      const agent = AGENTS.find(a => a.id === agentId);
      this._traces[agentId] = { agent_id: agentId, agent_label: agent ? agent.label : agentId, ...details };
      if (chevronEl) chevronEl.style.display = 'block';
      node.classList.add('clickable');
    }
  },

  /** Pre-load trace details for historical incident view */
  setTraceData(agentId, traceData) {
    const agent = AGENTS.find(a => a.id === agentId);
    this._traces[agentId] = {
      agent_id:    agentId,
      agent_label: agent ? agent.label : agentId,
      ...traceData
    };
    const node    = document.getElementById(`node-${agentId}`);
    const chevron = document.getElementById(`chevron-${agentId}`);
    if (node) node.classList.add('clickable');
    if (chevron) chevron.style.display = 'block';
  },

  /** Map DB agent_name string → AGENTS id */
  resolveAgentId(dbName) {
    const name = (dbName || '').toLowerCase().replace(/[^a-z0-9]/g, '');
    const MAP = {
      a1intake:              'A1_Intake',
      a1triage:              'A1_Intake',
      a2foundryiq:           'A2_Retrieval',
      a2retrieval:           'A2_Retrieval',
      a2bindexer:            'A2_Retrieval',
      a2bworkiq:             'A2b_OperationalContext',
      a2boperationalcontext: 'A2b_OperationalContext',
      a2bcontext:            'A2b_OperationalContext',
      a11websearch:          'A11_WebSearch',
      a11search:             'A11_WebSearch',
      a3correlation:         'A3_Correlation',
      a3correlator:          'A3_Correlation',
      a8adversarialreview:   'A8_AdversarialReview',
      a8reviewer:            'A8_AdversarialReview',
      a4riskanalyzer:        'A4_RiskAnalyzer',
      a4riskengine:          'A4_RiskAnalyzer',
      a5actionplanner:       'A5_ActionPlanner',
      a5planner:             'A5_ActionPlanner',
      a6guardrail:           'A6_Guardrail',
      a6safety:              'A6_Guardrail',
      a7communication:       'A7_Communication',
      a7broadcaster:         'A7_Communication',
      a9retrospective:       'A9_Retrospective',
      a9auditor:             'A9_Retrospective',
      a10knowledgeingest:    'A10_KnowledgeIngest',
      a10learner:            'A10_KnowledgeIngest',
    };
    if (MAP[name]) return MAP[name];
    const found = AGENTS.find(a => a.id.toLowerCase().replace(/[^a-z0-9]/g, '') === name);
    return found ? found.id : null;
  },

  reset() {
    this._traces = {};
    AGENTS.forEach(agent => {
      const node    = document.getElementById(`node-${agent.id}`);
      const dot     = document.getElementById(`dot-${agent.id}`);
      const status  = document.getElementById(`status-${agent.id}`);
      const chevron = document.getElementById(`chevron-${agent.id}`);
      if (node) {
        node.classList.remove('running', 'completed', 'failed', 'clickable');
        if (agent.hidden) node.classList.add('hidden');
      }
      if (dot)     dot.className = 'agent-dot';
      if (status)  status.textContent = 'Waiting';
      if (chevron) chevron.style.display = 'none';
    });
  }
};

export default ReasoningChain;
