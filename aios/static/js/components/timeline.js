/**
 * Renders the Incident Timeline Bar.
 */
const Timeline = {
  render(containerId, createdAt, resolvedAt) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const startStr = createdAt ? new Date(createdAt).toLocaleTimeString() : 'Intake';
    const endStr = resolvedAt ? new Date(resolvedAt).toLocaleTimeString() : 'Active Outage';
    
    let percent = 100;
    let color = 'var(--danger)';
    if (resolvedAt) {
      percent = 100;
      color = 'var(--success)';
    }

    container.innerHTML = `
      <div style="margin-top: 1rem; padding: 0.75rem 0.25rem;">
        <div style="display:flex; justify-content:space-between; font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 0.25rem; font-weight:600;">
          <span>🕒 Start: ${startStr}</span>
          <span>🔧 Status: ${resolvedAt ? 'RESOLVED' : 'Triage In Progress'}</span>
          <span>🏁 End: ${endStr}</span>
        </div>
        <div style="width: 100%; height: 6px; background: var(--border-color); border-radius: 3px; overflow: hidden;">
          <div style="width: ${percent}%; height: 100%; background: ${color}; transition: width 0.3s ease;"></div>
        </div>
      </div>
    `;
  }
};

export default Timeline;
