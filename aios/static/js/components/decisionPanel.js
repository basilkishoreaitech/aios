/**
 * Renders the Right Panel: Mitigation Action items with human-in-the-loop validation.
 */
import apiFetch from '../utils/api.js';

/** Build an SVG-backed radial blast-radius card. */
function buildBlastRadiusCard(risk, serviceName) {
  if (!risk || !risk.blast_radius) return '';
  const br = risk.blast_radius;
  const level = (risk.overall_risk_level || 'medium').toLowerCase();
  const COLORS = { critical: '#ef4444', high: '#f97316', medium: '#eab308', low: '#22c55e' };
  const BKGS   = { critical: 'rgba(239,68,68,0.07)', high: 'rgba(249,115,22,0.07)', medium: 'rgba(234,179,8,0.07)', low: 'rgba(34,197,94,0.07)' };
  const c = COLORS[level] || COLORS.medium;
  const bg = BKGS[level] || BKGS.medium;
  const DL_COLORS = { none: '#22c55e', potential: '#eab308', verified: '#ef4444' };
  const dlColor = DL_COLORS[(br.estimated_data_loss || 'none').toLowerCase()] || '#22c55e';

  const services = br.impacted_services || [];
  const n = services.length;

  // Build SVG lines + HTML node chips using polar math
  let svgLines = `
    <circle cx="50" cy="50" r="40" fill="none" stroke="${c}" stroke-width="0.4" stroke-opacity="0.18" stroke-dasharray="3 3"/>
    <circle cx="50" cy="50" r="26" fill="none" stroke="${c}" stroke-width="0.4" stroke-opacity="0.25" stroke-dasharray="3 3"/>
    <circle cx="50" cy="50" r="13" fill="${bg}" stroke="${c}" stroke-width="1.8"/>
  `;
  let chips = '';
  services.forEach((svc, i) => {
    const angle = (n === 1 ? 0 : (i / n) * 2 * Math.PI) - Math.PI / 2;
    const R = 38;
    const px = 50 + R * Math.cos(angle);
    const py = 50 + R * Math.sin(angle);
    svgLines += `<line x1="50%" y1="50%" x2="${px}%" y2="${py}%" stroke="${c}" stroke-width="0.8" stroke-opacity="0.35" stroke-dasharray="3 2"/>`;
    chips += `<div style="position:absolute;left:${px}%;top:${py}%;transform:translate(-50%,-50%);padding:0.14rem 0.38rem;background:${bg};border:1px solid ${c};border-radius:4px;font-size:0.58rem;font-weight:700;color:${c};white-space:nowrap;max-width:72px;overflow:hidden;text-overflow:ellipsis;text-align:center;" title="${svc}">${svc}</div>`;
  });

  return `
    <div class="pop-in" style="position:relative;margin-bottom:1rem;padding:0.8rem;border:1px solid ${c};border-radius:var(--radius-md);background:${bg};overflow:hidden;">
      <!-- Radar ping rings (decorative) -->
      <div style="position:absolute;left:50%;top:50%;width:300%;height:300%;border-radius:50%;border:1.5px solid ${c};opacity:0.07;pointer-events:none;animation:radar-ping 2.8s ease-out infinite;"></div>
      <div style="position:absolute;left:50%;top:50%;width:300%;height:300%;border-radius:50%;border:1.5px solid ${c};opacity:0.05;pointer-events:none;animation:radar-ping 2.8s ease-out 1.4s infinite;"></div>

      <!-- Title row -->
      <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.6rem;position:relative;z-index:1;">
        <span style="width:8px;height:8px;border-radius:50%;background:${c};animation:pulse-dot 0.9s ease-in-out alternate infinite;flex-shrink:0;"></span>
        <strong style="font-size:0.73rem;color:${c};text-transform:uppercase;letter-spacing:0.05em;">${level} · Blast Radius</strong>
        ${br.user_facing_impact ? `<span style="margin-left:auto;font-size:0.62rem;padding:0.1rem 0.4rem;border:1px solid ${c};border-radius:4px;color:${c};font-weight:700;white-space:nowrap;">👥 USER-FACING</span>` : ''}
      </div>

      <!-- Radial diagram -->
      <div style="position:relative;height:120px;z-index:1;margin-bottom:0.55rem;">
        <svg style="position:absolute;inset:0;width:100%;height:100%;" viewBox="0 0 100 100" preserveAspectRatio="none">
          ${svgLines}
        </svg>
        <!-- Center label -->
        <div style="position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:48px;text-align:center;font-size:0.56rem;font-weight:800;color:${c};line-height:1.15;z-index:2;word-break:break-all;">${serviceName || 'Source'}</div>
        <!-- Service chips -->
        ${chips}
      </div>

      <!-- Stat badges -->
      <div style="display:flex;flex-wrap:wrap;gap:0.3rem;position:relative;z-index:1;">
        <span style="padding:0.14rem 0.45rem;border-radius:4px;background:rgba(255,255,255,0.04);border:1px solid var(--border-color);font-size:0.65rem;font-weight:600;color:var(--text-secondary);">Downstream: <strong style="color:${c};">${(br.downstream_impact_rating||'—').toUpperCase()}</strong></span>
        <span style="padding:0.14rem 0.45rem;border-radius:4px;background:rgba(255,255,255,0.04);border:1px solid var(--border-color);font-size:0.65rem;font-weight:600;color:var(--text-secondary);">Data Loss: <strong style="color:${dlColor};">${(br.estimated_data_loss||'none').toUpperCase()}</strong></span>
        <span style="padding:0.14rem 0.45rem;border-radius:4px;background:rgba(255,255,255,0.04);border:1px solid var(--border-color);font-size:0.65rem;font-weight:600;color:var(--text-secondary);">${n} svc${n !== 1 ? 's' : ''} impacted</span>
      </div>

      ${risk.business_impact_summary ? `<div style="margin-top:0.45rem;font-size:0.7rem;color:var(--text-secondary);line-height:1.4;position:relative;z-index:1;">${risk.business_impact_summary}</div>` : ''}
      ${risk.mitigation_risk_factors?.length ? `<div style="margin-top:0.4rem;position:relative;z-index:1;">${risk.mitigation_risk_factors.map(f => `<div style="font-size:0.68rem;color:var(--text-secondary);padding-left:0.55rem;border-left:2px solid ${c};margin-bottom:0.12rem;line-height:1.35;">⚠ ${f}</div>`).join('')}</div>` : ''}
    </div>
  `;
}

const DecisionPanel = {
  render(containerId, actionPlan, incidentId, onActionExecuted, convergenceScore = null, accuracyScore = null, status = null, riskAssessment = null, serviceName = '', actionsStatus = []) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!actionPlan) {
      container.innerHTML = `<div class="text-secondary" style="text-align: center; padding-top: 4rem;">Waiting for action recommendations...</div>`;
      return;
    }

    // Build a quick lookup: step_id → { status, approved_by }
    // IDs in DB are prefixed with incident_id; step_id field holds the original "step_N" value
    const statusMap = {};
    (actionsStatus || []).forEach(a => {
      statusMap[a.id] = a;
      if (a.step_id) statusMap[a.step_id] = a;
    });

    let html = '';

    // Blast Radius chart — shown first when risk data available
    html += buildBlastRadiusCard(riskAssessment, serviceName);

    // A9 Retrospective — prominent self-scored diagnosis accuracy (shown once resolved)
    if (accuracyScore !== null && accuracyScore !== undefined) {
      const pct = Math.round(accuracyScore * 100);
      let scoreColor = 'var(--success)';
      let verdict = 'Accurate diagnosis';
      if (accuracyScore < 0.5) { scoreColor = 'var(--danger)'; verdict = 'Diagnosis missed root cause'; }
      else if (accuracyScore < 0.8) { scoreColor = 'var(--warning)'; verdict = 'Partially correct'; }

      html += `
        <div class="pop-in" style="margin-bottom: 1rem; padding: 0.9rem 1rem; border-radius: var(--radius-md); border: 1px solid ${scoreColor}; background: linear-gradient(135deg, rgba(37,99,235,0.06), rgba(6,182,212,0.06)); display: flex; align-items: center; gap: 0.9rem;">
          <div style="position: relative; width: 56px; height: 56px; flex-shrink: 0;">
            <svg viewBox="0 0 56 56" style="width:56px; height:56px; transform: rotate(-90deg);">
              <circle cx="28" cy="28" r="24" fill="none" stroke="var(--border-color)" stroke-width="5"/>
              <circle cx="28" cy="28" r="24" fill="none" stroke="${scoreColor}" stroke-width="5" stroke-linecap="round"
                stroke-dasharray="${(pct / 100) * 150.8} 150.8"/>
            </svg>
            <span style="position:absolute; inset:0; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:0.85rem; color:${scoreColor};">${pct}%</span>
          </div>
          <div style="flex-grow:1;">
            <div style="font-size:0.7rem; font-weight:700; letter-spacing:0.04em; text-transform:uppercase; color:var(--text-muted);">A9 · Self-Scored Diagnosis Accuracy</div>
            <div style="font-size:0.92rem; font-weight:700; color:var(--text-primary); margin-top:0.1rem;">${verdict}</div>
            <div style="font-size:0.72rem; color:var(--text-secondary); margin-top:0.1rem;">The system graded its own diagnosis against the operator-confirmed root cause.</div>
          </div>
        </div>
      `;
    }

    // Summary with Convergence Indicator
    let convergenceHtml = '';
    if (convergenceScore !== null) {
      const percentage = Math.round(convergenceScore * 100);
      let dotColor = 'var(--success)';
      if (convergenceScore < 0.5) dotColor = 'var(--danger)';
      else if (convergenceScore < 0.75) dotColor = 'var(--warning)';
      
      convergenceHtml = `
        <div style="display: inline-flex; align-items: center; gap: 0.3rem; font-size: 0.75rem; font-weight: 600; padding: 0.2rem 0.5rem; background: rgba(255, 255, 255, 0.05); border: 1px solid var(--border-color); border-radius: 12px; white-space: nowrap;">
          <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: ${dotColor};"></span>
          <span>${percentage}% Convergence</span>
        </div>
      `;
    }
    
    html += `
      <div class="fade-in" style="margin-bottom: 1rem; padding: 0.75rem; background: var(--primary-light); border-radius: var(--radius-sm); font-size: 0.85rem; display: flex; justify-content: space-between; align-items: center; gap: 0.5rem;">
        <div style="flex-grow: 1;"><strong>Summary Strategy</strong>: ${actionPlan.summary}</div>
        ${convergenceHtml}
      </div>
    `;

    // Actions
    if (actionPlan.mitigation_steps && actionPlan.mitigation_steps.length > 0) {
      actionPlan.mitigation_steps.forEach(step => {
        const isAuto = step.risk_tag === 'auto_approve';
        const badgeColor = step.risk_level === 'low' ? 'low' : (step.risk_level === 'medium' ? 'medium' : 'high');
        
        html += `
          <div class="action-card fade-in" id="action-card-${step.id}">
            <div class="action-header">
              <span class="risk-badge ${badgeColor}">${step.risk_level} Risk</span>
              <span style="font-size: 0.75rem; font-weight: 600; color: var(--text-secondary);">${step.risk_tag.toUpperCase()}</span>
            </div>
            <div class="action-title">${step.action}</div>
            <div class="action-rationale"><strong>Why:</strong> ${step.rationale}</div>
            <div style="font-size: 0.75rem; font-family: monospace; padding: 0.4rem; background: rgba(255, 255, 255, 0.05); border-radius: 4px; margin-bottom: 0.75rem;">
              <strong>Check:</strong> ${step.verification_check}
            </div>
            
            <div id="btn-gate-${step.id}">
              ${isAuto ? `
                <div style="font-size:0.75rem; color: var(--success); font-weight:600; display:flex; align-items:center; gap:0.25rem;">
                  <span>⚡</span> Auto-Approved (No action required)
                </div>
              ` : (() => {
                const dbAction = statusMap[step.id];
                if (dbAction && dbAction.status === 'executed') {
                  return `<span style="font-size:0.8rem; color:var(--success); font-weight:600;">✅ Executed by ${dbAction.approved_by || 'operator'}</span>`;
                } else if (dbAction && dbAction.status === 'rejected') {
                  return `<span style="font-size:0.8rem; color:var(--danger); font-weight:600;">❌ Rejected by ${dbAction.approved_by || 'operator'}</span>`;
                } else {
                  return `
                    <div style="display:flex; gap: 0.5rem;">
                      <button class="btn-action approve" onclick="window.approveAction('${incidentId}', '${step.id}')">Approve Execution</button>
                      <button class="btn-action" style="background: var(--border-color); color: var(--text-primary);" onclick="window.rejectAction('${incidentId}', '${step.id}')">Reject</button>
                    </div>
                  `;
                }
              })()}
            </div>
          </div>
        `;
      });
    } else {
      html += `<div style="font-size:0.85rem; color: var(--text-secondary);">No actions recommended by planner.</div>`;
    }

    container.innerHTML = html;

    // Attach global window handlers so the inline onclick triggers work
    window.approveAction = async (incId, stepId) => {
      const card = document.getElementById(`btn-gate-${stepId}`);
      if (card) card.innerHTML = `<span style="font-size:0.8rem; color:var(--text-muted);">Executing SRE payload...</span>`;
      
      try {
        const res = await apiFetch(`/action/${stepId}/approve`, {
          method: 'POST',
          body: JSON.stringify({ incident_id: incId, decision: 'approve' })
        });
        if (card) card.innerHTML = `<span style="font-size:0.8rem; color:var(--success); font-weight:600;">✅ Executed by ${res.operator}</span>`;
        if (onActionExecuted) onActionExecuted();
      } catch (e) {
        alert(e.message);
        // Reset
        this.render(containerId, actionPlan, incidentId, onActionExecuted);
      }
    };

    window.rejectAction = async (incId, stepId) => {
      const card = document.getElementById(`btn-gate-${stepId}`);
      if (card) card.innerHTML = `<span style="font-size:0.8rem; color:var(--text-muted);">Rejecting SRE payload...</span>`;
      
      try {
        const res = await apiFetch(`/action/${stepId}/approve`, {
          method: 'POST',
          body: JSON.stringify({ incident_id: incId, decision: 'reject' })
        });
        if (card) card.innerHTML = `<span style="font-size:0.8rem; color:var(--danger); font-weight:600;">❌ Rejected by ${res.operator}</span>`;
        if (onActionExecuted) onActionExecuted();
      } catch (e) {
        alert(e.message);
        this.render(containerId, actionPlan, incidentId, onActionExecuted);
      }
    };
  }
};

export default DecisionPanel;
