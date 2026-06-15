/**
 * Renders the Evidence & Context Panel — user-friendly terminology throughout.
 */
const FRIENDLY_CAT = {
  runbook: '📋 Procedure Guide',
  postmortem: '📝 Past Incident Report',
  architecture: '🏗 Architecture Reference',
};

const truncate = (str = '', len = 160) => str.length > len ? str.slice(0, len).trimEnd() + '…' : str;

const EvidencePanel = {
  render(containerId, evidenceBundle, contextData) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!evidenceBundle && !contextData) {
      container.innerHTML = `<div style="text-align:center;padding:3rem 1rem;color:var(--text-muted);">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="opacity:0.4;animation:iconPulse 2s infinite;margin-bottom:0.75rem;"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
        <div style="font-size:0.8rem;">Waiting for alert data…</div>
      </div>`;
      return;
    }

    let html = '';

    // 1. Relevant Knowledge & Guides
    html += `<div class="evidence-section fade-in">`;
    html += `<h4 class="section-title">🔍 Relevant Knowledge & Guides</h4>`;
    if (evidenceBundle?.kb_citations?.length) {
      evidenceBundle.kb_citations.forEach(cit => {
        const matchPct = Math.min(100, Math.round(cit.relevance * 100));
        const catLabel = FRIENDLY_CAT[cit.category] || cit.category;
        const barColor = matchPct >= 70 ? '#16a34a' : matchPct >= 40 ? '#d97706' : '#6b7280';
        html += `
          <div style="padding:0.65rem 0.75rem;border:1px solid var(--border-color);border-radius:var(--radius-sm);background:var(--card-bg-alt);margin-bottom:0.5rem;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.28rem;gap:0.5rem;">
              <span style="font-size:0.67rem;font-weight:700;color:var(--text-muted);background:var(--border-color);border-radius:4px;padding:0.05rem 0.35rem;">${catLabel}</span>
              <span style="font-size:0.64rem;font-weight:700;color:${barColor};flex-shrink:0;">${matchPct}% match</span>
            </div>
            <div style="font-size:0.78rem;font-weight:700;color:var(--text-primary);line-height:1.35;margin-bottom:0.3rem;">${cit.title}</div>
            <div style="font-size:0.72rem;color:var(--text-secondary);line-height:1.45;">${truncate(cit.content_snippet)}</div>
            <div style="height:3px;background:var(--border-color);border-radius:999px;margin-top:0.45rem;overflow:hidden;"><div style="height:100%;width:${matchPct}%;background:${barColor};border-radius:999px;transition:width 0.6s ease;"></div></div>
          </div>
        `;
      });
    } else {
      html += `<div style="font-size:0.78rem;color:var(--text-muted);padding:0.5rem 0;">No matching guides found in the knowledge base.</div>`;
    }
    html += `</div>`;

    // 2. Web search results
    if (evidenceBundle?.web_citations?.length) {
      html += `<div class="evidence-section fade-in" style="margin-top:1.25rem;">`;
      html += `<h4 class="section-title">🌐 Additional Online References</h4>`;
      evidenceBundle.web_citations.forEach(web => {
        html += `
          <div style="padding:0.55rem 0.7rem;border:1px solid var(--border-color);border-left:3px solid var(--primary);border-radius:var(--radius-sm);background:var(--card-bg-alt);margin-bottom:0.45rem;">
            <div style="font-size:0.77rem;font-weight:600;margin-bottom:0.2rem;"><a href="${web.url}" target="_blank" rel="noopener noreferrer" style="text-decoration:none;color:var(--primary);">${web.title}</a></div>
            <div style="font-size:0.7rem;color:var(--text-secondary);line-height:1.4;">${truncate(web.snippet, 140)}</div>
          </div>
        `;
      });
      html += `</div>`;
    }

    // 3. Operational context — user-friendly labels
    html += `<div class="evidence-section fade-in" style="margin-top:1.25rem;">`;
    html += `<h4 class="section-title">⏱ Recent Activity & Context</h4>`;

    if (contextData) {
      let hasContent = false;

      if (contextData.deployments?.length) {
        hasContent = true;
        html += `<div style="font-size:0.68rem;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em;margin-bottom:0.3rem;">Recent Deployments</div>`;
        contextData.deployments.forEach(d => {
          html += `
            <div style="display:flex;gap:0.5rem;align-items:flex-start;padding:0.45rem 0.6rem;background:var(--card-bg-alt);border:1px solid var(--border-color);border-radius:6px;margin-bottom:0.3rem;">
              <span style="font-size:0.9rem;flex-shrink:0;">🚀</span>
              <div>
                <div style="font-size:0.75rem;font-weight:700;color:var(--text-primary);">${d.service_name} — v${d.version}</div>
                <div style="font-size:0.7rem;color:var(--text-secondary);">Deployed by ${d.deployed_by} · ${d.details || ''}</div>
              </div>
            </div>
          `;
        });
      }

      if (contextData.teams_messages?.length) {
        hasContent = true;
        html += `<div style="font-size:0.68rem;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.04em;margin-top:0.65rem;margin-bottom:0.3rem;">Team Chat Activity</div>`;
        contextData.teams_messages.forEach(m => {
          html += `
            <div style="padding:0.45rem 0.6rem;background:var(--card-bg-alt);border:1px solid var(--border-color);border-radius:6px;margin-bottom:0.3rem;">
              <div style="font-size:0.71rem;font-weight:700;color:var(--text-primary);">${m.author} <span style="font-weight:400;color:var(--text-muted);">in ${m.channel}</span></div>
              <div style="font-size:0.72rem;color:var(--text-secondary);margin-top:0.15rem;font-style:italic;">"${truncate(m.content, 120)}"</div>
            </div>
          `;
        });
      }

      if (!hasContent) {
        html += `<div style="font-size:0.78rem;color:var(--text-muted);padding:0.5rem 0;">No recent activity recorded for this alert.</div>`;
      }
    } else {
      html += `<div style="font-size:0.78rem;color:var(--text-muted);padding:0.5rem 0;">No context data available.</div>`;
    }
    html += `</div>`;

    container.innerHTML = html;
  }
};
export default EvidencePanel;
