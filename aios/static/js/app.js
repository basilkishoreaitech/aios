import apiFetch, { apiStream } from './utils/api.js?v=2';
import ChatInterface from './components/chatInterface.js?v=6';
import EvidencePanel from './components/evidencePanel.js?v=3';
import ReasoningChain from './components/reasoningChain.js?v=5';
import DecisionPanel from './components/decisionPanel.js?v=5';
import ObservabilityPanel from './components/observability.js?v=2';
import IncidentExplorer from './components/incidentExplorer.js?v=2';
import ExecutiveView from './components/executiveView.js?v=2';
import Timeline from './components/timeline.js?v=2';

let appState = {
  currentUser: null,
  userRole: null,
  activeIncidentId: null,
  activeIncidentDetails: null,
  currentView: 'engineer' // 'engineer' or 'executive'
};

/** Update both pipeline-status-indicator (col1) and canvas-run-badge (col3). */
function setPipelineStatus(text, type = 'idle') {
  const STYLES = {
    idle:    'var(--border-color)',
    loading: 'var(--primary-light)',
    running: 'var(--warning-bg)',
    success: 'var(--success-bg)',
    error:   'var(--danger-bg)',
  };
  const TEXT_COLORS = {
    idle:    'var(--text-secondary)',
    loading: 'var(--primary)',
    running: 'var(--warning-text)',
    success: 'var(--success-text)',
    error:   'var(--danger-text)',
  };
  for (const id of ['pipeline-status-indicator', 'canvas-run-badge']) {
    const el = document.getElementById(id);
    if (el) {
      el.textContent = text;
      el.style.background = STYLES[type] || STYLES.idle;
      el.style.color = TEXT_COLORS[type] || TEXT_COLORS.idle;
    }
  }
  // Mirror pipeline activity to explorer FAB notification dot
  const isActive = (type === 'running' || type === 'loading');
  if (window.setExplorerFabAlert) window.setExplorerFabAlert(isActive);
}

// Toast Notification System (QA Standard)
window.showToast = function(msg, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = msg;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.animation = 'fadeOut 0.3s ease forwards';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
};

// Check authentication status on startup
function checkAuth() {
  const token = localStorage.getItem('aios_token');
  if (token) {
    showAppScreen();
  } else {
    showLoginScreen();
  }
}

function showLoginScreen() {
  document.getElementById('login-screen').style.display = 'flex';
  document.getElementById('app-screen').style.display = 'none';
}

function showAppScreen() {
  document.getElementById('login-screen').style.display = 'none';
  document.getElementById('app-screen').style.display = 'flex';
  
  // Initialize SPA Components
  initApp();
}

async function initApp() {
  // 1. Render permanent chat panel
  ChatInterface.render('chat-interface-container', true);
  
  // 2. Render empty agent list
  ReasoningChain.render('reasoning-chain-container');
  EvidencePanel.render('evidence-panel-container', null, null);
  DecisionPanel.render('decision-panel-container', null, null, null, null);
  
  // 3. Show KB Upload button only for admin / operator
  const role = localStorage.getItem('aios_role') || '';
  appState.userRole = role;
  const kbBtn = document.getElementById('btn-kb-upload-header');
  if (kbBtn && (role === 'admin' || role === 'operator')) {
    kbBtn.style.display = 'inline-flex';
  }

  // 4. Load past incident histories list
  refreshHistory();
}

async function refreshHistory() {
  IncidentExplorer.render('incident-explorer-container', loadIncidentDetails);
}

async function loadIncidentDetails(incidentId) {
  appState.activeIncidentId = incidentId;
  IncidentExplorer.setSelectedIncident(incidentId);
  setPipelineStatus('LOADING…', 'loading');

  try {
    const details = await apiFetch(`/incident/${incidentId}`);
    appState.activeIncidentDetails = details;
    
    const statusType = details.status === 'resolved' ? 'success' : 'error';
    setPipelineStatus(details.status.toUpperCase(), statusType);

    // Update visibility of action buttons
    document.getElementById('btn-export-postmortem').style.display = 'inline-block';
    document.getElementById('btn-resolve-outage').style.display = details.status === 'resolved' ? 'none' : 'inline-block';

    // Update visibility of hint panel
    document.getElementById('collaborative-hint-panel').style.display = details.status === 'resolved' ? 'none' : 'block';

    // Renders panels
    renderActiveState();
  } catch (e) {
    window.showToast("Failed loading incident details: " + e.message, "error");
  }
}

function renderActiveState() {
  const details = appState.activeIncidentDetails;
  if (!details) return;

  if (appState.currentView === 'engineer') {
    // Fill agent nodes with trace state — also stores trace data for click-to-detail
    ReasoningChain.reset();
    details.traces.forEach(trace => {
      const agentId = ReasoningChain.resolveAgentId(trace.agent_name) || trace.agent_name;
      ReasoningChain.setAgentState(agentId, trace.status, {
        duration_ms:    trace.duration_ms,
        model_used:     trace.model_used,
        tokens_used:    trace.tokens_used,
        input_summary:  trace.input_summary,
        output_summary: trace.output_summary,
        error_message:  trace.error_message,
      });
    });

    EvidencePanel.render('evidence-panel-container', details.evidence_bundle, details.operational_context);
    DecisionPanel.render('decision-panel-container', details.action_plan, details.id, () => {
      loadIncidentDetails(details.id);
    }, details.hypotheses ? details.hypotheses.convergence_score : null, details.accuracy_score, details.status,
       details.risk_assessment, details.service_name, details.actions || []);
    ObservabilityPanel.render('observability-container', details.traces);
  } else {
    // Executive Mode
    EvidencePanel.render('evidence-panel-container', null, null);
    ExecutiveView.render('evidence-panel-container', details.executive_view);
    DecisionPanel.render('decision-panel-container', details.action_plan, details.id, () => {
      loadIncidentDetails(details.id);
    }, details.hypotheses ? details.hypotheses.convergence_score : null, details.accuracy_score, details.status,
       details.risk_assessment, details.service_name, details.actions || []);
    ObservabilityPanel.render('observability-container', details.traces);
  }
}

// Expose Login handler (attach to form submit)
document.querySelector('#login-screen form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const u = document.getElementById('login-username').value;
  const p = document.getElementById('login-password').value;
  const btn = document.getElementById('btn-login-submit');

  btn.disabled = true;
  btn.textContent = 'Signing in…';
  btn.style.opacity = '0.8';

  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: u, password: p })
    });
    
    if (res.ok) {
      const data = await res.json();
      localStorage.setItem('aios_token', data.access_token);
      localStorage.setItem('aios_role', data.role || '');
      localStorage.setItem('aios_username', data.username || '');
      btn.textContent = '✓ Welcome back';
      btn.style.background = 'linear-gradient(135deg,#059669,#10b981)';
      setTimeout(showAppScreen, 350);
    } else {
      const err = await res.json();
      window.showToast(err.detail || "Authentication failed", "error");
      btn.disabled = false;
      btn.textContent = 'Sign In';
      btn.style.opacity = '1';
    }
  } catch (e) {
    window.showToast("Auth server unreachable: " + e.message, "error");
    btn.disabled = false;
    btn.textContent = 'Sign In';
    btn.style.opacity = '1';
  }
});

// Logout handler
document.getElementById('btn-logout').addEventListener('click', () => {
  localStorage.removeItem('aios_token');
  localStorage.removeItem('aios_role');
  localStorage.removeItem('aios_username');
  showLoginScreen();
});

// View Toggle
document.getElementById('btn-view-eng').addEventListener('click', (e) => {
  appState.currentView = 'engineer';
  document.getElementById('btn-view-eng').classList.add('active');
  document.getElementById('btn-view-exec').classList.remove('active');
  renderActiveState();
});

document.getElementById('btn-view-exec').addEventListener('click', (e) => {
  appState.currentView = 'executive';
  document.getElementById('btn-view-exec').classList.add('active');
  document.getElementById('btn-view-eng').classList.remove('active');
  renderActiveState();
});

// Modal Close controls
document.getElementById('btn-modal-cancel').addEventListener('click', () => {
  document.getElementById('resolve-modal').style.display = 'none';
});

document.getElementById('btn-resolve-outage').addEventListener('click', () => {
  const details = appState.activeIncidentDetails;
  const rootCauseBox = document.getElementById('resolve-root-cause');

  // Pre-fill: top hypothesis + action plan summary so operator can confirm/edit
  if (rootCauseBox && !rootCauseBox.value && details) {
    let prefill = '';
    if (details.hypotheses?.hypotheses?.length) {
      const top = details.hypotheses.hypotheses[0];
      prefill += `[AIOS top hypothesis] ${top.title}\n`;
      if (top.causal_factor) prefill += `Causal factor: ${top.causal_factor}\n`;
      if (top.description) prefill += `${top.description}\n`;
      prefill += '\n';
    }
    if (details.action_plan?.summary) {
      prefill += `[Action plan] ${details.action_plan.summary}`;
    }
    rootCauseBox.value = prefill.trim();
  }

  document.getElementById('resolve-modal').style.display = 'flex';
});

// Resolve Incident Submit
document.getElementById('btn-modal-submit').addEventListener('click', async () => {
  const notes = document.getElementById('resolve-root-cause').value.trim();
  if (!notes) {
    window.showToast("Please write operator resolution notes first.", "warning");
    return;
  }
  
  document.getElementById('resolve-modal').style.display = 'none';
  
  try {
    const res = await apiFetch(`/incident/${appState.activeIncidentId}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ actual_root_cause: notes })
    });
    
    window.showToast(`Incident closed!<br/>Diagnosis accuracy: ${Math.round(res.accuracy_score * 100)}%`, "success");
    
    // Reload Details
    loadIncidentDetails(appState.activeIncidentId);
    refreshHistory();
  } catch (e) {
    window.showToast("Resolution failed: " + e.message, "error");
  }
});

let currentPostmortem = null;

// Export Postmortem preview and download Trigger
document.getElementById('btn-export-postmortem').addEventListener('click', async () => {
  try {
    const res = await apiFetch(`/incident/${appState.activeIncidentId}/export-postmortem`, {
      method: 'POST'
    });
    
    currentPostmortem = res;
    document.getElementById('postmortem-preview-content').textContent = res.markdown;
    document.getElementById('postmortem-preview-modal').style.display = 'flex';
  } catch (e) {
    window.showToast("Export failed: " + e.message, "error");
  }
});

// Close Preview Modal
document.getElementById('btn-postmortem-preview-close').addEventListener('click', () => {
  document.getElementById('postmortem-preview-modal').style.display = 'none';
  currentPostmortem = null;
});

// Download Postmortem from Modal
document.getElementById('btn-postmortem-download').addEventListener('click', () => {
  if (!currentPostmortem) return;
  const blob = new Blob([currentPostmortem.markdown], { type: 'text/markdown;charset=utf-8;' });
  const link = document.createElement("a");
  const url = URL.createObjectURL(blob);
  link.setAttribute("href", url);
  link.setAttribute("download", currentPostmortem.filename);
  link.style.visibility = 'hidden';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  document.getElementById('postmortem-preview-modal').style.display = 'none';
  currentPostmortem = null;
});

// Custom Ingest Modal controls
document.getElementById('btn-custom-alert-modal').addEventListener('click', () => {
  document.getElementById('custom-alert-service').value = 'db-replica-01';
  document.getElementById('custom-alert-severity').value = 'SEV-2';
  document.getElementById('custom-alert-details').value = 'Replication lag exceeded 300 seconds on auth-replica';
  document.getElementById('custom-ingest-modal').style.display = 'flex';
});

document.getElementById('btn-custom-ingest-cancel').addEventListener('click', () => {
  document.getElementById('custom-ingest-modal').style.display = 'none';
});

// Custom Alert Ingest Submit
document.getElementById('btn-custom-ingest-submit').addEventListener('click', async () => {
  const service = document.getElementById('custom-alert-service').value.trim();
  const severity = document.getElementById('custom-alert-severity').value;
  const detailsText = document.getElementById('custom-alert-details').value.trim();

  if (!service || !detailsText) {
    window.showToast("Please fill in both service name and alert details.", "warning");
    return;
  }

  const payloadText = JSON.stringify({
    alert: "Custom operator alert",
    service: service,
    severity: severity,
    details: detailsText
  });
  
  document.getElementById('custom-ingest-modal').style.display = 'none';
  
  ReasoningChain.reset();
  EvidencePanel.render('evidence-panel-container', null, null);
  DecisionPanel.render('decision-panel-container', null, null);
  ObservabilityPanel.render('observability-container', []);
  
  setPipelineStatus('TRIAGING…', 'running');

  try {
    let errorShown = false;
    await apiStream('/ingest', { raw_alert: payloadText }, (eventFrame) => {
      const { event, data } = eventFrame;
      
      if (event === 'pipeline_start') {
        appState.activeIncidentId = data.incident_id;
      } else if (event === 'agent_start') {
        const agentId = ReasoningChain.resolveAgentId(data.agent) || data.agent;
        ReasoningChain.setAgentState(agentId, 'running');
      } else if (event === 'agent_complete') {
        const agentId = ReasoningChain.resolveAgentId(data.agent) || data.agent;
        ReasoningChain.setAgentState(agentId, 'completed', data);
      } else if (event === 'pipeline_complete') {
        setPipelineStatus('COMPLETE', 'success');
        // A9 and A10 only run on Resolve — mark them clearly so users aren't confused
        const a9status = document.getElementById('status-A9_Retrospective');
        const a10status = document.getElementById('status-A10_KnowledgeIngest');
        if (a9status) a9status.textContent = '⏸ Awaiting resolve';
        if (a10status) a10status.textContent = '⏸ Awaiting resolve';
        loadIncidentDetails(data.incident_id);
        refreshHistory();
      } else if (event === 'pipeline_error') {
        errorShown = true;
        setPipelineStatus('FAILED', 'error');
        window.showToast("Analysis failed: " + data.error, "error");
      }
    });
  } catch (e) {
    if (!errorShown) window.showToast("Failed to start alert: " + e.message, "error");
  }
});

// Submit Hint Trigger
document.getElementById('btn-submit-hint').addEventListener('click', async () => {
  const hintVal = document.getElementById('operator-hint-input').value.trim();
  if (!hintVal) {
    window.showToast("Please write a diagnostic hint first.", "warning");
    return;
  }
  
  const incidentId = appState.activeIncidentId;
  if (!incidentId) return;

  document.getElementById('operator-hint-input').value = '';
  ReasoningChain.reset();
  
  setPipelineStatus('RE-EVALUATING…', 'running');

  try {
    let errorShown = false;
    await apiStream(`/incident/${incidentId}/hint`, { operator_hint: hintVal }, (eventFrame) => {
      const { event, data } = eventFrame;
      
      if (event === 'agent_start') {
        const agentId = ReasoningChain.resolveAgentId(data.agent) || data.agent;
        ReasoningChain.setAgentState(agentId, 'running');
      } else if (event === 'agent_complete') {
        const agentId = ReasoningChain.resolveAgentId(data.agent) || data.agent;
        ReasoningChain.setAgentState(agentId, 'completed', data);
      } else if (event === 'pipeline_complete') {
        setPipelineStatus('COMPLETE', 'success');
        // A9 and A10 only run on Resolve — mark them clearly so users aren't confused
        const a9status = document.getElementById('status-A9_Retrospective');
        const a10status = document.getElementById('status-A10_KnowledgeIngest');
        if (a9status) a9status.textContent = '⏸ Awaiting resolve';
        if (a10status) a10status.textContent = '⏸ Awaiting resolve';
        loadIncidentDetails(incidentId);
      } else if (event === 'pipeline_error') {
        errorShown = true;
        setPipelineStatus('RE-RUN FAILED', 'error');
        window.showToast("Re-analysis failed: " + data.error, "error");
      }
    });
  } catch (e) {
    if (!errorShown) window.showToast("Hint endpoint failed: " + e.message, "error");
  }
});

// Text Size Controls
let currentTextSize = 100;
document.getElementById('btn-text-decrease').addEventListener('click', () => {
  if(currentTextSize > 70) currentTextSize -= 10;
  updateTextSize();
});
document.getElementById('btn-text-increase').addEventListener('click', () => {
  if(currentTextSize < 150) currentTextSize += 10;
  updateTextSize();
});
function updateTextSize() {
  document.documentElement.style.fontSize = `${16 * (currentTextSize / 100)}px`;
  document.getElementById('text-size-display').textContent = `${currentTextSize}%`;
}

// Fullscreen AI Log (graceful - button may not exist in new layout)
const _fsBtn = document.getElementById('btn-fullscreen-log');
if (_fsBtn) {
  _fsBtn.addEventListener('click', () => {
    const wrapper = document.getElementById('panel-ai-canvas');
    wrapper.classList.toggle('fullscreen-mode');
  });
}

// Initialize on startup
checkAuth();

// ---- Agent Retry Handler ----
document.addEventListener('agent-retry', async (e) => {
  const { agentId } = e.detail;
  const incidentId = appState.activeIncidentId;
  if (!incidentId) { window.showToast("No active incident selected.", "warning"); return; }

  const POST_RESOLVE_AGENTS = ['A9_Retrospective', 'A10_KnowledgeIngest'];

  if (POST_RESOLVE_AGENTS.includes(agentId)) {
    // Retry just the A9+A10 learning loop using stored root cause
    ReasoningChain.setAgentState('A9_Retrospective', 'running');
    ReasoningChain.setAgentState('A10_KnowledgeIngest', 'running');
    try {
      const res = await apiFetch(`/incident/${incidentId}/retry-learning-loop`, { method: 'POST' });
      ReasoningChain.setAgentState('A9_Retrospective', 'completed', { duration_ms: null });
      ReasoningChain.setAgentState('A10_KnowledgeIngest', 'completed', { duration_ms: null });
      window.showToast(`Learning loop complete! Accuracy: ${Math.round((res.accuracy_score ?? 0) * 100)}%`, 'success');
      loadIncidentDetails(incidentId);
    } catch (err) {
      ReasoningChain.setAgentState('A9_Retrospective', 'failed', { error_message: err.message });
      ReasoningChain.setAgentState('A10_KnowledgeIngest', 'failed', { error_message: err.message });
      window.showToast('Learning loop retry failed: ' + err.message, 'error');
    }
  } else {
    // For pipeline agents (A1–A8): re-run full analysis via the hint endpoint
    window.showToast('Re-running analysis pipeline…', 'info');
    ReasoningChain.reset();
    setPipelineStatus('RE-EVALUATING…', 'running');
    try {
      let errorShown = false;
      await apiStream(`/incident/${incidentId}/hint`, { operator_hint: 'Please re-evaluate this incident.' }, (eventFrame) => {
        const { event, data } = eventFrame;
        if (event === 'agent_start') {
          ReasoningChain.setAgentState(ReasoningChain.resolveAgentId(data.agent) || data.agent, 'running');
        } else if (event === 'agent_complete') {
          ReasoningChain.setAgentState(ReasoningChain.resolveAgentId(data.agent) || data.agent, 'completed', data);
        } else if (event === 'pipeline_complete') {
          setPipelineStatus('COMPLETE', 'success');
          const a9s = document.getElementById('status-A9_Retrospective');
          const a10s = document.getElementById('status-A10_KnowledgeIngest');
          if (a9s) a9s.textContent = '⏸ Awaiting resolve';
          if (a10s) a10s.textContent = '⏸ Awaiting resolve';
          loadIncidentDetails(data.incident_id);
        } else if (event === 'pipeline_error') {
          errorShown = true;
          setPipelineStatus('FAILED', 'error');
          window.showToast('Re-run failed: ' + data.error, 'error');
        }
      });
    } catch (err) {
      if (!errorShown) window.showToast('Re-run failed: ' + err.message, 'error');
      setPipelineStatus('FAILED', 'error');
    }
  }
});

// ---- Agent Trace — inline panel in col-3 (no popup) ----
document.addEventListener('agent-trace-detail', (e) => {
  showAgentTraceInline(e.detail);
});

function showAgentTraceInline(trace) {
  const panel = document.getElementById('agent-trace-inline');
  const titleEl = document.getElementById('agent-trace-inline-title');
  const bodyEl  = document.getElementById('agent-trace-inline-body');
  if (!panel || !titleEl || !bodyEl) return;

  const esc = (v) => String(v ?? '—').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  const pill = (label, value, bgVar, colorVar) =>
    `<span style="display:inline-block;padding:0.15rem 0.45rem;background:${bgVar};color:${colorVar};border-radius:4px;font-size:0.68rem;font-weight:700;">${esc(value)}</span>`;
  const block = (label, value) => value
    ? `<div style="margin-top:0.45rem;"><div style="font-size:0.65rem;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:var(--text-muted);margin-bottom:0.15rem;">${label}</div><div style="color:var(--text-secondary);word-break:break-word;">${esc(value)}</div></div>`
    : '';

  const statusPill = trace.status === 'completed'
    ? pill('', trace.status?.toUpperCase(), 'var(--success-bg)', 'var(--success-text)')
    : pill('', trace.status?.toUpperCase(), 'var(--danger-bg)', 'var(--danger-text)');
  const meta = [
    trace.duration_ms != null && `<span style="font-size:0.68rem;color:var(--text-secondary);">⏱ ${(trace.duration_ms/1000).toFixed(2)}s</span>`,
    trace.tokens_used  && `<span style="font-size:0.68rem;color:var(--text-secondary);">🪙 ${esc(trace.tokens_used)}</span>`,
    trace.model_used   && `<span style="font-size:0.68rem;color:var(--text-secondary);">🤖 ${esc(trace.model_used)}</span>`,
  ].filter(Boolean).join(' · ');

  titleEl.textContent = trace.agent_label || trace.agent_id || 'Agent';
  bodyEl.innerHTML = `
    <div style="display:flex;flex-wrap:wrap;gap:0.35rem;align-items:center;margin-bottom:0.3rem;">
      ${statusPill}
      <span style="font-size:0.68rem;color:var(--text-muted);">${meta}</span>
    </div>
    ${block('Input', trace.input_summary)}
    ${block('Output', trace.output_summary)}
    ${trace.error_message ? block('Error', trace.error_message) : ''}
  `;
  panel.style.display = 'block';
}

document.getElementById('btn-agent-trace-close')?.addEventListener('click', () => {
  document.getElementById('agent-trace-inline').style.display = 'none';
});

// ---- KB Upload Modal ----
document.getElementById('btn-kb-upload-header').addEventListener('click', () => {
  const modal = document.getElementById('kb-upload-modal');
  if (modal) modal.style.display = 'flex';
});

document.getElementById('btn-kb-upload-cancel').addEventListener('click', () => {
  document.getElementById('kb-upload-modal').style.display = 'none';
});

document.getElementById('kb-upload-modal').addEventListener('click', (e) => {
  if (e.target === e.currentTarget) e.currentTarget.style.display = 'none';
});

document.getElementById('btn-kb-upload-submit').addEventListener('click', async () => {
  const id       = document.getElementById('kb-upload-id').value.trim();
  const title    = document.getElementById('kb-upload-title').value.trim();
  const content  = document.getElementById('kb-upload-content').value.trim();
  const category = document.getElementById('kb-upload-category').value;
  const tagsRaw  = document.getElementById('kb-upload-tags').value;
  const tags     = tagsRaw.split(',').map(t => t.trim()).filter(Boolean);
  const statusEl = document.getElementById('kb-upload-status');

  if (!id || !title || !content) {
    window.showToast('Please fill in ID, Title, and Content.', 'warning');
    return;
  }

  statusEl.style.display = 'block';
  statusEl.style.background = 'var(--primary-light)';
  statusEl.style.color = 'var(--primary)';
  statusEl.textContent = '⏳ Uploading and indexing…';

  try {
    await apiFetch('/knowledge/ingest', {
      method: 'POST',
      body: JSON.stringify({ id, title, content, category, tags })
    });
    statusEl.style.background = 'var(--success-bg)';
    statusEl.style.color = 'var(--success-text)';
    statusEl.textContent = '✓ Document uploaded and indexed in Azure AI Search.';
    window.showToast(`KB document "${title}" uploaded successfully.`, 'success');
    setTimeout(() => {
      document.getElementById('kb-upload-modal').style.display = 'none';
      statusEl.style.display = 'none';
    }, 2000);
  } catch (err) {
    statusEl.style.background = 'var(--danger-bg)';
    statusEl.style.color = 'var(--danger-text)';
    statusEl.textContent = `✗ Upload failed: ${err.message}`;
  }
});

// ---- Chat Column Drag-to-Resize ----
(function initChatResizer() {
  const handle = document.getElementById('chat-col-resizer');
  const layout = document.getElementById('layout-wrapper');
  if (!handle || !layout) return;

  // Columns: [explorer, main, canvas, chat]
  // We read the current chat width from the rendered DOM so it works
  // regardless of which breakpoint we're at.
  let startX = 0;
  let startChatW = 0;

  handle.addEventListener('mousedown', (e) => {
    e.preventDefault();
    startX = e.clientX;
    startChatW = document.getElementById('panel-chat').getBoundingClientRect().width;
    handle.classList.add('dragging');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const onMove = (me) => {
      const delta = startX - me.clientX;   // negative = dragging right (shrink)
      const newW = Math.max(240, Math.min(640, startChatW + delta));
      // Update the CSS variable instead of overwriting the whole grid layout
      document.documentElement.style.setProperty('--chat-width', newW + 'px');
    };

    const onUp = () => {
      handle.classList.remove('dragging');
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });
})();

// ---- Draggable Resizers (legacy stub) ----
function initResizers() { /* layout uses CSS grid, no legacy resizers needed */ }

// ── Floating FAB Toggle Logic ───────────────────────────────────────────────
(function initFabToggles() {
  const layout = document.getElementById('layout-wrapper');

  // Helper: sync FAB active state
  function syncFab(fabId, panelClass) {
    const fab = document.getElementById(fabId);
    if (!fab) return;
    const isOpen = layout.classList.contains(panelClass);
    fab.classList.toggle('active', isOpen);
    fab.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  }

  // Explorer FAB
  document.getElementById('fab-explorer')?.addEventListener('click', () => {
    layout.classList.toggle('explorer-open');
    syncFab('fab-explorer', 'explorer-open');
  });

  // Chat FAB
  document.getElementById('fab-chat')?.addEventListener('click', () => {
    layout.classList.toggle('chat-open');
    syncFab('fab-chat', 'chat-open');
  });

  // Legacy in-panel toggle buttons still work
  document.getElementById('btn-toggle-explorer')?.addEventListener('click', () => {
    layout.classList.toggle('explorer-open');
    syncFab('fab-explorer', 'explorer-open');
  });

  // Global helper for ChatInterface.js and other code
  window.toggleChatSidebar = function() {
    layout.classList.toggle('chat-open');
    syncFab('fab-chat', 'chat-open');
  };

  // Expose explorer dot control for pipeline status
  window.setExplorerFabAlert = function(show) {
    const dot = document.getElementById('fab-explorer-dot');
    if (dot) dot.style.display = show ? 'block' : 'none';
  };
  window.setChatFabAlert = function(show) {
    const dot = document.getElementById('fab-chat-dot');
    if (dot) dot.style.display = show ? 'block' : 'none';
  };
})();

// ── Focus Mode: 3-col reasoning workspace (no side panels) ─────────────────
document.getElementById('btn-focus-mode')?.addEventListener('click', () => {
  const layout = document.getElementById('layout-wrapper');
  const btn = document.getElementById('btn-focus-mode');
  const enable = !layout.classList.contains('focus-mode');
  layout.classList.toggle('focus-mode', enable);
  // Close side panels when entering focus mode
  if (enable) {
    layout.classList.remove('explorer-open', 'chat-open');
    document.getElementById('fab-explorer')?.classList.remove('active');
    document.getElementById('fab-chat')?.classList.remove('active');
  }
  btn?.classList.toggle('active', enable);
});

