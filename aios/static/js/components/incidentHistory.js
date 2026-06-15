/**
 * Renders the incident history list side bar.
 */
import apiFetch from '../utils/api.js';

const IncidentHistory = {
  async render(containerId, onIncidentSelected) {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = `<div style="font-size:0.8rem; color:var(--text-muted); text-align:center;">Loading past incidents...</div>`;

    try {
      const incidents = await apiFetch('/incidents');
      
      if (!incidents || incidents.length === 0) {
        container.innerHTML = `<div style="font-size: 0.8rem; color: var(--text-muted); text-align: center; padding: 1rem;">No incidents logged.</div>`;
        return;
      }

      let html = '<div style="display:flex; flex-direction:column; gap:0.5rem; padding-right:0.25rem;">';
      incidents.forEach(inc => {
        const dateStr = new Date(inc.created_at).toLocaleDateString();
        const timeStr = new Date(inc.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const isResolved = inc.status === 'resolved';
        const statusBadge = isResolved ? 'background:var(--success-bg); color:var(--success-text);' : 'background:var(--danger-bg); color:var(--danger-text);';
        
        html += `
          <div class="history-item fade-in" style="cursor:pointer; padding: 0.6rem; background:rgba(255, 255, 255, 0.05); border: 1px solid var(--border-color); border-radius: 4px; transition: transform 0.15s ease;"
               onclick="window.selectIncident('${inc.id}')" onmouseover="this.style.transform='translateX(2px)'" onmouseout="this.style.transform='none'">
            <div style="display:flex; justify-content:space-between; font-size: 0.7rem; color:var(--text-muted); font-weight:600; margin-bottom:0.2rem;">
              <span>${dateStr} ${timeStr}</span>
              <span style="padding:0.1rem 0.3rem; border-radius:3px; font-size:0.6rem; ${statusBadge}">${inc.status.toUpperCase()}</span>
            </div>
            <div style="font-weight: 600; font-size: 0.8rem; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
              ${inc.title}
            </div>
            <div style="font-size:0.7rem; color: var(--text-secondary);">
              Service: <strong>${inc.service_name}</strong> | Severity: <strong>${inc.severity}</strong>
            </div>
          </div>
        `;
      });
      html += '</div>';

      container.innerHTML = html;

      // Attach selection handler to window
      window.selectIncident = (id) => {
        if (onIncidentSelected) onIncidentSelected(id);
      };

    } catch (e) {
      container.innerHTML = `<div style="font-size:0.8rem; color:var(--danger); text-align:center;">Failed loading: ${e.message}</div>`;
    }
  }
};

export default IncidentHistory;
