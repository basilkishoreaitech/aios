/**
 * Renders a historic incident explorer with filters and compact operational metrics.
 */
import apiFetch from '../utils/api.js';

const escapeHtml = (value = '') => String(value)
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/\"/g, '&quot;')
  .replace(/'/g, '&#39;');

const IncidentExplorer = {
  state: {
    incidents: [],
    selectedId: null,
    filters: {
      search: '',
      service_name: '',
      severity: '',
      status: ''
    }
  },

  async render(containerId, onIncidentSelected) {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = `
      <div style="display:flex; flex-direction:column; gap:0.9rem; min-height:0; height:100%;">
        <div style="display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:0.6rem;">
          <div style="padding:0.75rem; border:1px solid var(--border-color); border-radius:8px; background:rgba(255,255,255,0.04);">
            <div style="font-size:0.68rem; text-transform:uppercase; letter-spacing:0.08em; color:var(--text-muted); margin-bottom:0.2rem;">Visible Incidents</div>
            <div id="incident-explorer-count" style="font-size:1.2rem; font-weight:700; color:var(--text-primary);">0</div>
          </div>
          <div style="padding:0.75rem; border:1px solid var(--border-color); border-radius:8px; background:rgba(255,255,255,0.04);">
            <div style="font-size:0.68rem; text-transform:uppercase; letter-spacing:0.08em; color:var(--text-muted); margin-bottom:0.2rem;">Resolved Rate</div>
            <div id="incident-explorer-resolved-rate" style="font-size:1.2rem; font-weight:700; color:var(--text-primary);">0%</div>
          </div>
        </div>
        <div style="display:grid; grid-template-columns:1.3fr 1fr 1fr 1fr auto; gap:0.45rem; align-items:end;">
          <div>
            <label style="display:block; font-size:0.68rem; color:var(--text-secondary); margin-bottom:0.2rem;">Search</label>
            <input id="incident-explorer-search" type="text" placeholder="payment latency, jwks, db pool..." style="width:100%; padding:0.55rem; border:1px solid var(--border-color); border-radius:6px; background:var(--bg-color); color:var(--text-primary);" />
          </div>
          <div>
            <label style="display:block; font-size:0.68rem; color:var(--text-secondary); margin-bottom:0.2rem;">Service</label>
            <input id="incident-explorer-service" type="text" placeholder="auth-service" style="width:100%; padding:0.55rem; border:1px solid var(--border-color); border-radius:6px; background:var(--bg-color); color:var(--text-primary);" />
          </div>
          <div>
            <label style="display:block; font-size:0.68rem; color:var(--text-secondary); margin-bottom:0.2rem;">Severity</label>
            <select id="incident-explorer-severity" style="width:100%; padding:0.55rem; border:1px solid var(--border-color); border-radius:6px; background:var(--bg-color); color:var(--text-primary);">
              <option value="">All</option>
              <option value="SEV-1">SEV-1</option>
              <option value="SEV-2">SEV-2</option>
              <option value="SEV-3">SEV-3</option>
            </select>
          </div>
          <div>
            <label style="display:block; font-size:0.68rem; color:var(--text-secondary); margin-bottom:0.2rem;">Status</label>
            <select id="incident-explorer-status" style="width:100%; padding:0.55rem; border:1px solid var(--border-color); border-radius:6px; background:var(--bg-color); color:var(--text-primary);">
              <option value="">All</option>
              <option value="investigating">Investigating</option>
              <option value="resolved">Resolved</option>
            </select>
          </div>
          <button id="incident-explorer-refresh" style="padding:0.6rem 0.9rem; background:var(--primary); color:#fff; border:none; border-radius:6px; font-weight:600; cursor:pointer;">Refresh</button>
        </div>
        <div id="incident-explorer-list" style="display:flex; flex-direction:column; gap:0.5rem; min-height:240px; max-height:420px; overflow:auto; padding-right:0.25rem;"></div>
      </div>
    `;

    const bindAndLoad = async () => {
      const filters = {
        search: document.getElementById('incident-explorer-search').value.trim(),
        service_name: document.getElementById('incident-explorer-service').value.trim(),
        severity: document.getElementById('incident-explorer-severity').value,
        status: document.getElementById('incident-explorer-status').value
      };
      this.state.filters = filters;
      await this.loadIncidents(onIncidentSelected);
    };

    ['incident-explorer-search', 'incident-explorer-service'].forEach((id) => {
      document.getElementById(id).addEventListener('keydown', (event) => {
        if (event.key === 'Enter') bindAndLoad();
      });
    });
    document.getElementById('incident-explorer-severity').addEventListener('change', bindAndLoad);
    document.getElementById('incident-explorer-status').addEventListener('change', bindAndLoad);
    document.getElementById('incident-explorer-refresh').addEventListener('click', bindAndLoad);

    await this.loadIncidents(onIncidentSelected);
  },

  async loadIncidents(onIncidentSelected) {
    const list = document.getElementById('incident-explorer-list');
    if (!list) return;

    list.innerHTML = `<div style="font-size:0.82rem; color:var(--text-muted); text-align:center; padding:1rem;">Loading historic incidents...</div>`;

    const params = new URLSearchParams();
    Object.entries(this.state.filters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    params.set('limit', '50');

    try {
      const incidents = await apiFetch(`/incidents?${params.toString()}`);
      this.state.incidents = incidents || [];
      this.renderList(onIncidentSelected);
    } catch (error) {
      list.innerHTML = `<div style="font-size:0.82rem; color:var(--danger); text-align:center; padding:1rem;">Failed to load incidents: ${escapeHtml(error.message)}</div>`;
    }
  },

  renderList(onIncidentSelected) {
    const list = document.getElementById('incident-explorer-list');
    if (!list) return;

    const incidents = this.state.incidents;
    const resolvedCount = incidents.filter((incident) => incident.status === 'resolved').length;
    document.getElementById('incident-explorer-count').textContent = String(incidents.length);
    document.getElementById('incident-explorer-resolved-rate').textContent = incidents.length ? `${Math.round((resolvedCount / incidents.length) * 100)}%` : '0%';

    if (!incidents.length) {
      list.innerHTML = `<div style="font-size:0.82rem; color:var(--text-muted); text-align:center; padding:1rem;">No incidents matched the current filters.</div>`;
      return;
    }

    list.innerHTML = incidents.map((incident) => {
      const selected = incident.id === this.state.selectedId;
      const statusStyles = incident.status === 'resolved'
        ? 'background:var(--success-bg); color:var(--success-text);'
        : 'background:var(--danger-bg); color:var(--danger-text);';
      const createdAt = new Date(incident.created_at);
      return `
        <button class="incident-explorer-item" data-incident-id="${incident.id}" style="text-align:left; width:100%; padding:0.8rem; border-radius:8px; border:1px solid ${selected ? 'var(--primary)' : 'var(--border-color)'}; background:${selected ? 'rgba(56, 189, 248, 0.08)' : 'rgba(255,255,255,0.04)'}; cursor:pointer; transition:background 0.2s ease, border-color 0.2s ease;">
          <div style="display:flex; justify-content:space-between; gap:0.5rem; align-items:flex-start; margin-bottom:0.35rem;">
            <div style="font-size:0.86rem; font-weight:700; color:var(--text-primary); line-height:1.3;">${escapeHtml(incident.title || 'Untitled incident')}</div>
            <span style="padding:0.15rem 0.35rem; border-radius:999px; font-size:0.64rem; font-weight:700; ${statusStyles}">${escapeHtml((incident.status || 'unknown').toUpperCase())}</span>
          </div>
          <div style="font-size:0.72rem; color:var(--text-secondary); margin-bottom:0.45rem;">${escapeHtml(incident.service_name || 'unknown-service')} • ${escapeHtml(incident.severity || 'n/a')} • ${createdAt.toLocaleDateString()} ${createdAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
          <div style="display:flex; gap:0.45rem; flex-wrap:wrap; font-size:0.68rem; color:var(--text-muted);">
            <span style="padding:0.12rem 0.35rem; border-radius:999px; border:1px solid var(--border-color);">Accuracy: ${incident.accuracy_score != null ? `${Math.round(incident.accuracy_score * 100)}%` : 'n/a'}</span>
            <span style="padding:0.12rem 0.35rem; border-radius:999px; border:1px solid var(--border-color);">Duration: ${incident.pipeline_duration_ms ? `${incident.pipeline_duration_ms}ms` : 'n/a'}</span>
          </div>
        </button>
      `;
    }).join('');

    list.querySelectorAll('.incident-explorer-item').forEach((element) => {
      element.addEventListener('click', () => {
        const incidentId = element.getAttribute('data-incident-id');
        this.state.selectedId = incidentId;
        if (onIncidentSelected) onIncidentSelected(incidentId);
        this.renderList(onIncidentSelected);
      });
    });
  },

  setSelectedIncident(incidentId) {
    this.state.selectedId = incidentId;
  }
};

export default IncidentExplorer;
