/**
 * Renders the Observability Panel: execution traces, token consumption, and model selection.
 */
const ObservabilityPanel = {
  render(containerId, traces) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!traces || traces.length === 0) {
      container.innerHTML = `<div style="font-size: 0.8rem; color: var(--text-muted); text-align: center;">No agent traces captured yet.</div>`;
      return;
    }

    let html = `
      <div class="fade-in" style="overflow-x: auto;">
        <table style="width: 100%; border-collapse: collapse; font-size: 0.75rem; text-align: left;">
          <thead>
            <tr style="border-bottom: 2px solid var(--border-color); color: var(--text-secondary); font-weight: 600;">
              <th style="padding: 0.4rem;">Agent</th>
              <th style="padding: 0.4rem;">Status</th>
              <th style="padding: 0.4rem;">Model</th>
              <th style="padding: 0.4rem; text-align: right;">Time</th>
              <th style="padding: 0.4rem; text-align: right;">Tokens</th>
              <th style="padding: 0.4rem; text-align: center;">Audit</th>
            </tr>
          </thead>
          <tbody>
    `;

    let totalTokens = 0;
    let totalTime = 0;

    traces.forEach(t => {
      totalTokens += t.tokens_used || 0;
      totalTime += t.duration_ms || 0;
      
      const statusColor = t.status.startsWith('completed') ? 'var(--success)' : (t.status === 'running' ? 'var(--primary)' : 'var(--danger)');
      const timeVal = t.duration_ms ? `${(t.duration_ms / 1000).toFixed(2)}s` : 'N/A';
      const hasPayload = t.input_summary || t.output_summary;
      const inspectId = `audit-${t.agent_name.replace(/[^a-zA-Z0-9]/g, '-')}`;
      
      const auditButton = hasPayload 
        ? `<button onclick="const row = document.getElementById('${inspectId}'); row.style.display = row.style.display === 'none' ? 'table-row' : 'none';" style="padding: 0.1rem 0.35rem; background: var(--primary-light); color: var(--primary); border: 1px solid var(--primary); border-radius: 3px; font-size: 0.65rem; font-weight: 600; cursor: pointer;">Inspect</button>`
        : `<span style="color: var(--text-muted);">None</span>`;
      
      html += `
        <tr style="border-bottom: 1px solid var(--border-color);">
          <td style="padding: 0.4rem; font-weight: 600; color: var(--text-primary);">${t.agent_name}</td>
          <td style="padding: 0.4rem; color: ${statusColor}; font-weight: 500;">${t.status.toUpperCase()}</td>
          <td style="padding: 0.4rem; font-family: monospace; color: var(--text-secondary);">${t.model_used || 'system'}</td>
          <td style="padding: 0.4rem; text-align: right; font-family: monospace;">${timeVal}</td>
          <td style="padding: 0.4rem; text-align: right; font-family: monospace;">${t.tokens_used || 0}</td>
          <td style="padding: 0.4rem; text-align: center;">${auditButton}</td>
        </tr>
      `;

      if (hasPayload) {
        html += `
          <tr id="${inspectId}" style="display: none; background: rgba(8, 12, 24, 0.85); border-bottom: 1px solid var(--border-color);">
            <td colspan="6" style="padding: 0.75rem;">
              <div style="display: flex; flex-direction: column; gap: 0.5rem; max-height: 250px; overflow-y: auto;">
                ${t.input_summary ? `
                  <div>
                    <strong style="font-size: 0.65rem; color: var(--text-muted); text-transform: uppercase; display: block; margin-bottom: 0.2rem; letter-spacing: 0.05em;">📥 Agent Input Payload:</strong>
                    <pre style="margin: 0; padding: 0.75rem; background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255,255,255,0.08); border-left: 2px solid var(--primary); border-radius: 4px; font-family: monospace; font-size: 0.75rem; white-space: pre-wrap; overflow-x: auto; color: var(--text-primary); text-shadow: 0 0 5px rgba(255,255,255,0.1);">${t.input_summary}</pre>
                  </div>
                ` : ''}
                ${t.output_summary ? `
                  <div>
                    <strong style="font-size: 0.65rem; color: var(--text-muted); text-transform: uppercase; display: block; margin-bottom: 0.2rem; letter-spacing: 0.05em;">📤 Agent Output Summary / Reasoning:</strong>
                    <pre style="margin: 0; padding: 0.75rem; background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255,255,255,0.08); border-left: 2px solid var(--success); border-radius: 4px; font-family: monospace; font-size: 0.75rem; white-space: pre-wrap; overflow-x: auto; color: var(--success-text); text-shadow: 0 0 8px rgba(52, 211, 153, 0.2);">${t.output_summary}</pre>
                  </div>
                ` : ''}
              </div>
            </td>
          </tr>
        `;
      }
    });

    html += `
          </tbody>
          <tfoot>
            <tr style="font-weight: 700; border-top: 2px solid var(--border-color); background: rgba(255, 255, 255, 0.05);">
              <td style="padding: 0.4rem; color: var(--text-primary);" colspan="3">Total Pipeline Consumption</td>
              <td style="padding: 0.4rem; text-align: right; font-family: monospace;">${(totalTime / 1000).toFixed(2)}s</td>
              <td style="padding: 0.4rem; text-align: right; font-family: monospace;">${totalTokens}</td>
              <td style="padding: 0.4rem;"></td>
            </tr>
          </tfoot>
        </table>
      </div>
    `;

    container.innerHTML = html;
  }
};

export default ObservabilityPanel;
