/**
 * AIOS — Conversational SRE Assistant (production-grade chat widget).
 * Premium light UI: avatars, typing indicator, quick-reply chips,
 * timestamps, animated confidence bar, safe markdown-lite rendering.
 */
import apiFetch, { apiForm } from '../utils/api.js';

const escapeHtml = (value = '') => String(value)
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;');

/** Minimal safe markdown renderer — no raw [N] citations in output */
const formatAnswer = (text = '') => {
  let s = escapeHtml(text);
  s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/`([^`]+?)`/g, '<code style="background:var(--bg-elevated);padding:0.05rem 0.35rem;border-radius:4px;font-family:var(--font-mono);font-size:0.79em;color:var(--text-primary);">$1</code>');
  s = s.replace(/\n/g, '<br>');
  return s;
};

// ── Design tokens ─────────────────────────────────────────────────────────────
const SEV_COLORS = {
  'SEV-1': { bar:'#ef4444', bg:'rgba(239,68,68,0.08)',   text:'#dc2626' },
  'SEV-2': { bar:'#f97316', bg:'rgba(249,115,22,0.08)',  text:'#c2410c' },
  'SEV-3': { bar:'#eab308', bg:'rgba(234,179,8,0.08)',   text:'#a16207' },
  'SEV-4': { bar:'#64748b', bg:'rgba(100,116,139,0.08)', text:'#475569' },
};
const STAT_COLORS = {
  investigating: { bg:'rgba(239,68,68,0.09)',  text:'#dc2626', dot:'#ef4444' },
  open:          { bg:'rgba(249,115,22,0.09)', text:'#c2410c', dot:'#f97316' },
  active:        { bg:'rgba(249,115,22,0.09)', text:'#c2410c', dot:'#f97316' },
  resolved:      { bg:'rgba(22,163,74,0.09)',  text:'#15803d', dot:'#16a34a' },
  closed:        { bg:'rgba(100,116,139,0.09)',text:'#475569', dot:'#94a3b8' },
};
const CAT_ICONS = { runbook:'📋', postmortem:'📝', architecture:'🏗', past_incident:'🔗', web_search:'🌐' };

/** True when the response is a direct DB incident list (not a KB/search answer) */
const isListResponse = (res) =>
  res.confidence === 1.0 &&
  (res.source_breakdown?.kb ?? 0) === 0 &&
  (res.source_breakdown?.web ?? 0) === 0 &&
  Array.isArray(res.related_incidents) && res.related_incidents.length >= 0 &&
  (res.answer || '').includes('incident');

/** Render a structured incident-list data panel */
const renderIncidentPanel = (res) => {
  const list = res.related_incidents || [];
  if (!list.length) {
    return `
      <div style="display:flex;flex-direction:column;align-items:center;padding:1.4rem 1rem;gap:0.4rem;">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" style="color:var(--text-muted);"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
        <div style="font-size:0.84rem;font-weight:600;color:var(--text-primary);">All clear</div>
        <div style="font-size:0.74rem;color:var(--text-muted);">No matching incidents in the database.</div>
      </div>`;
  }
  const match = (res.answer || '').match(/(\d+)\s+([\w /]+)\s+incident/);
  const label = match ? `${match[1]} ${match[2].trim()} incident${parseInt(match[1])!==1?'s':''}` : `${list.length} incident${list.length!==1?'s':''}`;
  const rows = list.map(inc => {
    const sev  = SEV_COLORS[inc.severity]  || SEV_COLORS['SEV-4'];
    const stat = STAT_COLORS[inc.status?.toLowerCase()] || STAT_COLORS['closed'];
    const age  = (() => {
      if (!inc.created_at) return '';
      const mins = Math.floor((Date.now() - new Date(inc.created_at)) / 60000);
      return mins < 120 ? `${mins}m ago` : `${Math.floor(mins/60)}h ago`;
    })();
    return `
      <div style="display:flex;align-items:stretch;border:1px solid var(--border-color);border-radius:8px;overflow:hidden;background:#fff;">
        <div style="width:3.5px;background:${sev.bar};flex-shrink:0;"></div>
        <div style="flex:1;padding:0.55rem 0.75rem;display:flex;align-items:center;justify-content:space-between;gap:0.5rem;flex-wrap:wrap;">
          <div style="display:flex;flex-direction:column;gap:0.12rem;min-width:0;flex:1;">
            <div style="font-size:0.8rem;font-weight:600;color:var(--text-primary);line-height:1.3;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(inc.title)}</div>
            <div style="font-size:0.67rem;color:var(--text-muted);font-family:var(--font-mono);">${escapeHtml(inc.service_name)}</div>
          </div>
          <div style="display:flex;align-items:center;gap:0.35rem;flex-shrink:0;">
            <span style="font-size:0.63rem;font-weight:700;color:${sev.text};background:${sev.bg};padding:0.12rem 0.38rem;border-radius:4px;">${escapeHtml(inc.severity)}</span>
            <span style="display:inline-flex;align-items:center;gap:0.2rem;font-size:0.63rem;font-weight:600;color:${stat.text};background:${stat.bg};padding:0.12rem 0.42rem;border-radius:4px;">
              <span style="width:4.5px;height:4.5px;border-radius:50%;background:${stat.dot};animation:pulse-dot 2s infinite;"></span>${escapeHtml(inc.status)}
            </span>
            <span style="font-size:0.62rem;color:var(--text-muted);font-family:var(--font-mono);">${age}</span>
          </div>
        </div>
      </div>`;
  }).join('');
  return `
    <div>
      <div style="font-size:0.62rem;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.07em;margin-bottom:0.45rem;">${label}</div>
      <div style="display:flex;flex-direction:column;gap:0.3rem;">${rows}</div>
    </div>`;
};

/** Render a KB / incident search answer with source pills and confidence */
const renderSearchAnswer = (res) => {
  const conf   = Math.min(100, Math.round((res.confidence || 0) * 100));
  const cColor = conf >= 70 ? '#16a34a' : conf >= 40 ? '#d97706' : '#dc2626';
  const cLabel = conf >= 70 ? 'High' : conf >= 40 ? 'Moderate' : 'Low';
  const kb = res.source_breakdown?.kb ?? 0;

  const prose = `<div style="font-size:0.84rem;line-height:1.68;color:var(--text-primary);">${formatAnswer(res.answer || '')}</div>`;

  // Source pills — compact, hover to see full title
  let sourcesHtml = '';
  if (res.citations?.length) {
    const pills = res.citations.map(c => {
      const icon = CAT_ICONS[c.category] || '●';
      const label = c.category === 'past_incident' ? 'Incident' : c.category === 'web_search' ? 'Web'
        : c.category.charAt(0).toUpperCase() + c.category.slice(1);
      return `<span title="${escapeHtml(c.title)}" style="display:inline-flex;align-items:center;gap:0.2rem;font-size:0.64rem;color:var(--text-muted);background:var(--bg-elevated);border:1px solid var(--border-color);border-radius:5px;padding:0.1rem 0.38rem;white-space:nowrap;max-width:160px;overflow:hidden;text-overflow:ellipsis;cursor:default;">${icon}&nbsp;<span style="overflow:hidden;text-overflow:ellipsis;">${escapeHtml(c.title)}</span></span>`;
    }).join('');
    sourcesHtml = `<div style="display:flex;flex-wrap:wrap;gap:0.22rem;margin-top:0.75rem;padding-top:0.6rem;border-top:1px solid var(--border-color);">${pills}</div>`;
  }

  // Confidence line
  const confHtml = `
    <div style="display:flex;align-items:center;gap:0.5rem;margin-top:0.45rem;">
      <span style="display:inline-flex;align-items:center;gap:0.22rem;font-size:0.63rem;font-weight:700;color:${cColor};">
        <span style="width:5.5px;height:5.5px;border-radius:50%;background:${cColor};"></span>${conf}% ${cLabel}
      </span>
      ${kb > 0 ? `<span style="font-size:0.62rem;color:var(--text-muted);">${kb} KB source${kb>1?'s':''}</span>` : ''}
    </div>`;

  // Related incidents — borderless compact list
  let relatedHtml = '';
  if (res.related_incidents?.length) {
    const items = res.related_incidents.slice(0, 4).map(inc => {
      const sev = SEV_COLORS[inc.severity] || SEV_COLORS['SEV-4'];
      return `<div style="display:flex;align-items:center;gap:0.45rem;padding:0.28rem 0;">
        <span style="width:3px;height:18px;border-radius:2px;background:${sev.bar};flex-shrink:0;"></span>
        <span style="font-size:0.74rem;color:var(--text-secondary);flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(inc.title)}</span>
        <span style="font-size:0.61rem;font-weight:700;color:${sev.text};flex-shrink:0;">${escapeHtml(inc.severity)}</span>
      </div>`;
    }).join('');
    relatedHtml = `<div style="margin-top:0.7rem;padding-top:0.5rem;border-top:1px solid var(--border-color);">
      <div style="font-size:0.61rem;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.07em;margin-bottom:0.22rem;">Related incidents</div>
      ${items}
    </div>`;
  }

  // Clarifying questions — left-border accent
  let clarHtml = '';
  if (res.clarifying_questions?.length && conf < 55) {
    const qs = res.clarifying_questions.slice(0, 2).map(q =>
      `<div style="font-size:0.73rem;color:var(--text-secondary);line-height:1.4;padding:0.18rem 0;display:flex;gap:0.3rem;"><span style="color:#d97706;flex-shrink:0;">›</span>${escapeHtml(q)}</div>`
    ).join('');
    clarHtml = `<div style="margin-top:0.6rem;padding:0.45rem 0.6rem;border-left:2px solid #f59e0b;background:rgba(245,158,11,0.04);border-radius:0 6px 6px 0;">
      <div style="font-size:0.61rem;font-weight:700;color:#d97706;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.18rem;">Need more context</div>
      ${qs}
    </div>`;
  }

  return prose + sourcesHtml + confHtml + clarHtml + relatedHtml;
};

const nowTime = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

const AI_AVATAR = `<span style="flex-shrink:0;width:30px;height:30px;border-radius:9px;background:var(--brand-gradient);background-size:180% 180%;display:flex;align-items:center;justify-content:center;box-shadow:var(--glow-primary);animation:gradient-shift 6s ease infinite;">
  <svg viewBox="0 0 48 48" width="17" height="17" fill="none"><path d="M24 3.5 6.5 10.5v11.2c0 11.1 7.4 19.4 17.5 22.8 10.1-3.4 17.5-11.7 17.5-22.8V10.5L24 3.5z" fill="rgba(255,255,255,0.2)" stroke="rgba(255,255,255,0.6)" stroke-width="1.6"/><path d="M26.4 13 16.5 26.2h6.6L21 35l10.4-13.6h-6.9L26.4 13z" fill="#fff"/></svg>
</span>`;


const ChatInterface = {
  render(containerId, permanent = false) {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = `
      <!-- Header -->
      <div class="chat-inner-header" style="background: var(--brand-gradient); background-size:180% 180%; animation:gradient-shift 8s ease infinite; padding: 0.95rem 1.1rem; color: #fff; display: flex; justify-content: space-between; align-items: center; border-radius: var(--radius-lg) var(--radius-lg) 0 0;">
        <div style="display:flex; align-items:center; gap:0.65rem;" class="chat-hidden-when-collapsed">
          <span style="width:38px;height:38px;border-radius:11px;background:rgba(255,255,255,0.18);display:flex;align-items:center;justify-content:center;backdrop-filter:blur(4px);">
            <svg viewBox="0 0 48 48" width="22" height="22" fill="none"><path d="M24 3.5 6.5 10.5v11.2c0 11.1 7.4 19.4 17.5 22.8 10.1-3.4 17.5-11.7 17.5-22.8V10.5L24 3.5z" fill="rgba(255,255,255,0.25)" stroke="rgba(255,255,255,0.7)" stroke-width="1.6"/><path d="M26.4 13 16.5 26.2h6.6L21 35l10.4-13.6h-6.9L26.4 13z" fill="#fff"/></svg>
          </span>
          <div>
            <div style="font-size:0.98rem; font-weight:700; font-family:var(--font-display); line-height:1.1;">AIOS Assistant</div>
            <div style="font-size:0.7rem; opacity:0.92; display:flex; align-items:center; gap:0.35rem; margin-top:2px;">
              <span class="live-dot" style="background:#86efac;"></span> Online · ready
            </div>
          </div>
        </div>
        <div style="display:flex; gap:0.25rem;">
          <button id="btn-toggle-chat" title="Toggle Sidebar" style="background: rgba(255,255,255,0.15); border: none; color: #fff; cursor: pointer; width:30px;height:30px;border-radius:8px;display:flex;align-items:center;justify-content:center;transition:background 0.2s;">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="15" y1="3" x2="15" y2="21"></line></svg>
          </button>
          <button id="btn-close-chat" title="Close" class="chat-hidden-when-collapsed" style="background: rgba(255,255,255,0.15); border: none; color: #fff; cursor: pointer; width:30px;height:30px;border-radius:8px;display:flex;align-items:center;justify-content:center;transition:background 0.2s;">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
          </button>
        </div>
      </div>

      <!-- Conversation -->
      <div id="chat-history-container" style="flex-grow: 1; padding: 1.1rem; overflow-y: auto; background: var(--bg-color); display: flex; flex-direction: column; gap: 0.9rem;"></div>

      <!-- Composer -->
      <div style="padding: 0.85rem 1rem 1rem; background: #fff; border-top: 1px solid var(--border-color); border-radius: 0 0 var(--radius-lg) var(--radius-lg);">
        <div style="display: flex; gap: 0.5rem; align-items:flex-end;">
          <textarea id="chat-query-input" rows="1" placeholder="Ask anything about your incidents…"
                 style="flex-grow: 1; padding: 0.6rem 0.8rem; border-radius: 12px; font-size: 0.85rem; resize:none; max-height:120px; line-height:1.4;"></textarea>
          <button id="btn-chat-submit" class="ripple" style="flex-shrink:0; width:42px; height:42px; background: var(--brand-gradient); background-size:180% 180%; color: #fff; border: none; border-radius: 12px; cursor: pointer; display: flex; align-items: center; justify-content: center; box-shadow:var(--glow-primary); transition:transform 0.15s ease;">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
          </button>
        </div>
      </div>
    `;

    const closeBtn = document.getElementById('btn-close-chat');
    const input = document.getElementById('chat-query-input');
    const submitBtn = document.getElementById('btn-chat-submit');
    const historyBox = document.getElementById('chat-history-container');

    let greeted = false;

    // ---- Bubble builders -------------------------------------------------
    const scrollDown = () => { historyBox.scrollTop = historyBox.scrollHeight; };

    const addUserBubble = (text, fileName) => {
      const wrap = document.createElement('div');
      wrap.className = 'msg-enter';
      wrap.style.cssText = 'align-self:flex-end; max-width:86%; display:flex; flex-direction:column; align-items:flex-end; gap:0.2rem;';
      wrap.innerHTML = `
        <div style="background: var(--brand-gradient); color:#fff; padding:0.7rem 0.85rem; border-radius:16px 16px 4px 16px; font-size:0.85rem; line-height:1.45; box-shadow:var(--shadow-sm);">
          <div>${escapeHtml(text)}</div>
          ${fileName ? `<div style="margin-top:0.3rem; font-size:0.7rem; opacity:0.85;">📎 ${escapeHtml(fileName)}</div>` : ''}
        </div>
        <span style="font-size:0.62rem; color:var(--text-muted);">${nowTime()}</span>`;
      historyBox.appendChild(wrap);
      scrollDown();
    };

    const addTyping = () => {
      const el = document.createElement('div');
      el.className = 'msg-enter';
      el.style.cssText = 'align-self:flex-start; max-width:86%; display:flex; gap:0.55rem; align-items:flex-end;';
      el.innerHTML = `${AI_AVATAR}
        <div style="background:#fff; border:1px solid var(--border-color); padding:0.75rem 0.9rem; border-radius:16px 16px 16px 4px; box-shadow:var(--shadow-sm);">
          <span class="typing-dots"><span></span><span></span><span></span></span>
        </div>`;
      historyBox.appendChild(el);
      scrollDown();
      return el;
    };

    const addAiBubble = (innerHtml) => {
      const wrap = document.createElement('div');
      wrap.className = 'msg-enter';
      wrap.style.cssText = 'align-self:flex-start; max-width:92%; display:flex; gap:0.5rem; align-items:flex-start;';
      wrap.innerHTML = `
        <div style="margin-top:2px;">${AI_AVATAR}</div>
        <div style="display:flex; flex-direction:column; gap:0.18rem; min-width:0; flex:1;">
          <div style="background:#fff; border:1px solid var(--border-color); padding:0.85rem 1rem; border-radius:4px 16px 16px 16px; font-size:0.85rem; box-shadow:0 1px 4px rgba(0,0,0,0.05); color:var(--text-primary);">
            ${innerHtml}
          </div>
          <span style="font-size:0.61rem; color:var(--text-muted); padding-left:0.25rem;">${nowTime()}</span>
        </div>`;
      historyBox.appendChild(wrap);
      scrollDown();
      return wrap;
    };

    const greet = () => {
      if (greeted) return;
      greeted = true;
      addAiBubble(`<div style="line-height:1.55;">👋 Hi, I'm <strong>AIOS</strong> — your Agentic Intelligence Operations assistant. Ask me to show open incidents, diagnose an alert, explain a root cause, or walk through a runbook.</div>`);
    };

    // ---- FAB / window toggle (floating mode only) -----------------------
    const chatWindow = document.getElementById('chat-window');
    const fab = document.getElementById('chat-fab');
    const toggleBtn = document.getElementById('btn-toggle-chat');

    if (toggleBtn) {
      toggleBtn.addEventListener('click', () => {
        if (window.toggleChatSidebar) window.toggleChatSidebar();
      });
    }

    if (!permanent && fab && chatWindow) {
      fab.addEventListener('click', () => {
        const opening = chatWindow.style.display !== 'flex';
        chatWindow.style.display = opening ? 'flex' : 'none';
        if (opening) { greet(); setTimeout(() => input.focus(), 80); }
      });
      closeBtn.addEventListener('click', () => { chatWindow.style.display = 'none'; });
    } else {
      // Permanent panel — hide close button, auto-greet
      if (closeBtn) closeBtn.style.display = 'none';
      setTimeout(() => { greet(); input.focus(); }, 120);
    }

    // ---- Composer behaviour ---------------------------------------------
    input.addEventListener('input', () => {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 120) + 'px';
    });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); runQuery(); }
    });

    // Button ripple
    submitBtn.addEventListener('click', (e) => {
      const wave = document.createElement('span');
      wave.className = 'ripple-wave';
      const rect = submitBtn.getBoundingClientRect();
      const size = Math.max(rect.width, rect.height);
      wave.style.width = wave.style.height = size + 'px';
      wave.style.left = (e.clientX - rect.left - size / 2) + 'px';
      wave.style.top = (e.clientY - rect.top - size / 2) + 'px';
      submitBtn.appendChild(wave);
      setTimeout(() => wave.remove(), 600);
    });

    // ---- Query flow ------------------------------------------------------
    const runQuery = async () => {
      const q = input.value.trim();
      if (!q) return;

      const filters = {};

      addUserBubble(q);
      input.value = '';
      input.style.height = 'auto';

      const typingEl = addTyping();

      try {
        const res = await apiFetch('/query', { method: 'POST', body: JSON.stringify({ question: q, filters }) });

        typingEl.remove();

        // Route to the correct renderer
        const innerHtml = isListResponse(res)
          ? renderIncidentPanel(res)
          : renderSearchAnswer(res);

        addAiBubble(innerHtml);

      } catch (e) {
        typingEl.remove();
        addAiBubble(`<div style="color:var(--danger-text);">⚠️ I couldn't complete that request: ${escapeHtml(e.message)}</div>`);
      }
      scrollDown();
    };

    submitBtn.addEventListener('click', runQuery);

    // In floating mode, if window is already visible on render, greet immediately.
    const _cw = document.getElementById('chat-window');
    if (!permanent && _cw && _cw.style.display === 'flex') greet();
  }
};

export default ChatInterface;
