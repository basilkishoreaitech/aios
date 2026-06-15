/**
 * Renders the Executive Mode Overlay view.
 */
const ExecutiveView = {
  render(containerId, executiveData) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!executiveData) {
      container.innerHTML = `<div class="text-secondary" style="text-align: center; padding-top: 4rem;">Waiting for executive summary reports...</div>`;
      return;
    }

    // Try to parse if it is double encoded string
    let data = executiveData;
    if (typeof executiveData === 'string') {
      try {
        data = JSON.parse(executiveData);
      } catch (e) {}
    }

    const html = `
      <div class="fade-in" style="padding: 1.5rem; background: #ffffff; border-radius: var(--radius-md); box-shadow: var(--shadow-sm);">
        <div style="font-family: var(--font-display); font-size: 1.4rem; font-weight: 700; color: var(--primary); margin-bottom: 1rem; border-bottom: 2px solid var(--border-color); padding-bottom: 0.5rem;">
          💼 Operations Dashboard — Executive View
        </div>
        
        <div style="margin-bottom: 1.5rem;">
          <h4 style="font-size: 0.9rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.5rem;">Status Summary</h4>
          <p style="font-size: 1.1rem; font-weight: 500; color: var(--text-primary);">${data.status_summary || 'N/A'}</p>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.5rem;">
          <div style="padding: 1rem; background: var(--bg-color); border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
            <h5 style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 0.25rem;">Business Impact</h5>
            <p style="font-size: 0.9rem; font-weight: 600; color: var(--danger-text);">${data.business_impact || 'No impact recorded.'}</p>
          </div>
          <div style="padding: 1rem; background: var(--bg-color); border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
            <h5 style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 0.25rem;">Est. Resolution Time</h5>
            <p style="font-size: 0.9rem; font-weight: 600; color: var(--success-text);">${data.estimated_resolution_time || 'N/A'}</p>
          </div>
        </div>

        <div style="margin-bottom: 1rem;">
          <h4 style="font-size: 0.9rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.5rem;">On-Call Escalation Roster</h4>
          <p style="font-size: 0.9rem; font-weight: 500;">Responding SREs: <strong style="color:var(--primary);">${data.oncall_assigned || 'On-Call Pool'}</strong></p>
        </div>
      </div>
    `;

    container.innerHTML = html;
  }
};

export default ExecutiveView;
