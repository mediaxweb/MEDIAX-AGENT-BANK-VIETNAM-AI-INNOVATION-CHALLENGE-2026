/**
 * MediaX Agent Bank — app.js
 * Full state machine: runStep 0→4, agent trace, source overlay
 */
'use strict';

// ============================================================
// SVG Icons (inline)
// ============================================================
const ICON = {
  sparkles: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/><path d="M5 3v4"/><path d="M19 17v4"/><path d="M3 5h4"/><path d="M17 19h4"/></svg>`,
  sparkles24: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/><path d="M5 3v4"/><path d="M19 17v4"/><path d="M3 5h4"/><path d="M17 19h4"/></svg>`,
  loader: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>`,
  compass: `<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/></svg>`,
  check: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`,
  checkCircle: `<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`,
  alert: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
  shield: `<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></svg>`,
  users: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`,
  file: `<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`,
  plus: `<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>`,
  msg: `<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`,
  trash: `<svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>`,
  arrowUp: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>`,
  x: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`,
  book: `<svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>`,
  graph: `<svg xmlns="http://www.w3.org/2000/svg" width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>`,
  fileUp: `<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><line x1="9" y1="15" x2="12" y2="12"/><line x1="15" y1="15" x2="12" y2="12"/></svg>`,
  search: `<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>`,
  doc: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>`,
};

// ============================================================
// State
// ============================================================
const CHAT_STORAGE_KEY = 'mediax-agent-bank-chat-state-v1';
const ORCHESTRATOR_CHAT_ENDPOINT = '/api/v1/orchestrator/chat';
const DOMAIN_LABELS = {
  credit: 'Tín dụng',
  compliance: 'Tuân thủ',
  operations: 'Vận hành',
};

let state = loadChatState();

function makeLocalId() {
  if (window.crypto && typeof window.crypto.randomUUID === 'function') {
    return window.crypto.randomUUID();
  }
  return `local-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function createSessionObject(name = 'Phiên hỏi đáp mới') {
  return {
    id: makeLocalId(),
    serverSessionId: null,
    name,
    active: false,
    messages: [],
    traceEvents: [],
    sourcesById: {},
  };
}

function loadChatState() {
  try {
    const raw = localStorage.getItem(CHAT_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed.sessions) && parsed.sessions.length > 0) {
        const sessions = parsed.sessions.map(session => ({
          id: session.id || makeLocalId(),
          serverSessionId: session.serverSessionId || null,
          name: session.name || 'Phiên hỏi đáp',
          active: Boolean(session.active),
          messages: Array.isArray(session.messages) ? session.messages : [],
          traceEvents: Array.isArray(session.traceEvents) ? session.traceEvents : [],
          sourcesById: session.sourcesById || {},
        }));
        if (!sessions.some(session => session.active)) sessions[0].active = true;
        return { sessions, isProcessing: false, activeSourceId: null };
      }
    }
  } catch (_error) {
    localStorage.removeItem(CHAT_STORAGE_KEY);
  }

  const firstSession = createSessionObject();
  firstSession.active = true;
  return {
    sessions: [firstSession],
    isProcessing: false,
    activeSourceId: null,
  };
}

function persistChatState() {
  try {
    localStorage.setItem(
      CHAT_STORAGE_KEY,
      JSON.stringify({ sessions: state.sessions })
    );
  } catch (_error) {
    // Browser storage can be full or disabled; chat still works in memory.
  }
}

function getActiveSession() {
  let session = state.sessions.find(item => item.active);
  if (!session) {
    session = state.sessions[0] || createSessionObject();
    session.active = true;
    if (!state.sessions.length) state.sessions.push(session);
  }
  return session;
}

function domainLabel(domain) {
  return DOMAIN_LABELS[domain] || 'Chuyên gia';
}

function nowLabel() {
  return new Date().toLocaleTimeString('vi-VN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatAnswerText(value) {
  return escapeHtml(value).replace(/\n/g, '<br>');
}

function shortQuestionName(question) {
  const normalized = question.replace(/\s+/g, ' ').trim();
  if (!normalized) return 'Phiên hỏi đáp';
  return normalized.length > 34 ? `${normalized.slice(0, 31)}...` : normalized;
}

// ============================================================
// Render helpers
// ============================================================
function getBadgeCount(label) {
  const len = state.sessions.length;
  return `<span class="badge badge-info">&bull; ${len}</span>`;
}

function getStatusIcon(status) {
  if (status === 'done')    return ICON.check;
  if (status === 'pending') return `<span class="spinning">${ICON.loader}</span>`;
  if (status === 'warning') return ICON.alert;
  if (status === 'error')   return ICON.alert;
  return '';
}
function getStatusEl(card) {
  const cls = card.status === 'done' ? 'status-done'
            : card.status === 'pending' ? 'status-pending'
            : card.status === 'error' ? 'status-error'
            : 'status-warning';
  const icon = card.status === 'done'    ? ICON.check
             : card.status === 'pending' ? `<span class="spinning">${ICON.loader}</span>`
             : ICON.alert;
  return `<span class="agent-card-status ${cls}">${icon} ${card.statusText}</span>`;
}

function traceCountLabel(step) {
  return step ? `${step} lượt` : '';
}

// ============================================================
// Render Sessions Panel
// ============================================================
function renderSessions() {
  const list  = document.getElementById('session-list');
  const badge = document.getElementById('session-badge');
  if (!list) return;

  badge.innerHTML = `<span class="badge badge-info">&bull; ${state.sessions.length}</span>`;
  list.innerHTML = '';
  state.sessions.forEach(s => {
    const div = document.createElement('div');
    div.className = 'session-item' + (s.active ? ' active' : '');
    div.dataset.id = s.id;
    div.innerHTML = `
      <span class="session-item-icon">${ICON.msg}</span>
      <span class="session-item-name" title="${escapeHtml(s.name)}">${escapeHtml(s.name)}</span>
      <button class="btn-delete-session" data-id="${s.id}" title="Xoá phiên">
        ${ICON.trash}
      </button>
    `;
    div.addEventListener('click', (e) => {
      if (e.target.closest('.btn-delete-session')) return;
      activateSession(s.id);
    });
    div.querySelector('.btn-delete-session').addEventListener('click', (e) => {
      e.stopPropagation();
      deleteSession(s.id);
    });
    list.appendChild(div);
  });
}

function activateSession(id) {
  if (state.isProcessing) return;
  state.sessions = state.sessions.map(s => ({ ...s, active: s.id === id }));
  persistChatState();
  renderSessions();
  renderChat();
  renderTrace();
}

function deleteSession(id) {
  if (state.isProcessing && getActiveSession().id === id) return;
  state.sessions = state.sessions.filter(s => s.id !== id);
  if (state.sessions.length === 0) {
    const session = createSessionObject();
    session.active = true;
    state.sessions.push(session);
  } else if (!state.sessions.find(s => s.active)) {
    state.sessions[0].active = true;
  }
  persistChatState();
  renderSessions();
  renderChat();
  renderTrace();
}

function createNewSession() {
  if (state.isProcessing) return;
  const newS = createSessionObject();
  newS.active = true;
  state.sessions = state.sessions.map(s => ({ ...s, active: false }));
  state.sessions.unshift(newS);
  persistChatState();
  renderSessions();
  renderChat();
  renderTrace();
}

// ============================================================
// Render Chat Panel
// ============================================================
function renderChatHeader() {
  const badge = document.getElementById('chat-badge');
  if (!badge) return;
  const session = getActiveSession();
  if (session.messages.length === 0) {
    badge.innerHTML = `<span class="badge badge-success">&bull; Phiên mới</span>`;
  } else {
    const cnt = session.messages.filter(m => m.kind === 'user').length;
    badge.innerHTML = `<span class="badge badge-neutral">${cnt} lượt</span>`;
  }
}

function renderChat() {
  const container = document.getElementById('chat-messages');
  if (!container) return;
  const session = getActiveSession();
  renderChatHeader();

  container.innerHTML = '';

  // Empty state
  if (session.messages.length === 0 && !state.isProcessing) {
    container.innerHTML = `
      <div class="chat-empty">
        <div class="chat-empty-icon">${ICON.sparkles24}</div>
        <h3 class="chat-empty-title">Bắt đầu cuộc trò chuyện với Đội chuyên gia</h3>
        <p class="chat-empty-desc">Nhập câu hỏi nghiệp vụ để Orchestrator điều phối đến chuyên gia phù hợp.</p>
      </div>
    `;
    return;
  }

  // Messages
  session.messages.forEach(msg => {
    const div = document.createElement('div');
    div.className = 'fade-slide-up';
    if (msg.kind === 'user') {
      div.innerHTML = `
        <div class="msg-row user-row">
          <div class="msg-avatar user">ND</div>
          <div class="msg-body">
            <div class="msg-author">Bạn</div>
            <div class="msg-bubble-user">${formatAnswerText(msg.text)}</div>
          </div>
        </div>
      `;
    } else if (msg.kind === 'error') {
      div.innerHTML = `
        <div class="msg-row">
          <div class="msg-avatar ai">${ICON.alert}</div>
          <div class="msg-body">
            <div class="msg-author">Hệ thống</div>
            <div class="msg-bubble-error">${formatAnswerText(msg.text)}</div>
          </div>
        </div>
      `;
    } else {
      const sources = (msg.sources || [])
        .map(sourceId => session.sourcesById[sourceId])
        .filter(Boolean);
      const sourceLinks = sources.map(source => {
        const page = source.page ? ` · trang ${escapeHtml(source.page)}` : '';
        const label = `${escapeHtml(source.file_name || source.source_id)}${page}`;
        return `<button class="qa-source-link" data-source-id="${escapeHtml(source.source_id)}">${ICON.file}&nbsp;${label}</button>`;
      }).join('');
      const sourceCount = sources.length;
      const domain = domainLabel(msg.domain);
      const statusText = msg.insufficientInformation
        ? 'Chưa đủ thông tin'
        : `${sourceCount} nguồn trích dẫn`;
      div.innerHTML = `
        <div class="msg-row">
          <div class="msg-avatar ai">${ICON.sparkles}</div>
          <div class="msg-body">
            <div class="msg-author">Đội chuyên gia AI</div>
            <div class="msg-bubble-ai">${formatAnswerText(msg.text)}</div>
            <div class="msg-meta">
              <span class="msg-meta-reliability">${ICON.shield}&nbsp;${statusText}</span>
              <span class="msg-meta-agents">${ICON.users}&nbsp;Miền ${domain}</span>
            </div>
            <div class="msg-sources" ${sourceCount ? '' : 'style="display:none;"'}>
              <div class="msg-sources-label">Nguồn trích dẫn</div>
              <div class="msg-sources-links">
                ${sourceLinks}
              </div>
            </div>
          </div>
        </div>
      `;
      div.querySelectorAll('.qa-source-link').forEach(btn => {
        btn.addEventListener('click', () => openSourceOverlay(btn.dataset.sourceId));
      });
    }
    container.appendChild(div);
  });

  // Loading
  if (state.isProcessing) {
    const loadDiv = document.createElement('div');
    loadDiv.id = 'loading-msg';
    loadDiv.className = 'msg-loading fade-slide-up';
    loadDiv.innerHTML = `
      <div class="msg-avatar ai"><span class="spinning">${ICON.loader}</span></div>
      <div class="loading-body">
        <div class="loading-title">
          <span class="spinning" style="color:var(--purple)">${ICON.loader}</span>
          Đội chuyên gia AI đang phân tích dữ liệu...
        </div>
        <div class="skeleton-line" style="width:100%;"></div>
        <div class="skeleton-line"></div>
      </div>
    `;
    container.appendChild(loadDiv);
  }

  // Scroll to bottom
  setTimeout(() => { container.scrollTop = container.scrollHeight; }, 0);
}

// ============================================================
// Render Trace Panel
// ============================================================
function renderTrace() {
  const emptyEl = document.getElementById('trace-empty');
  const listEl  = document.getElementById('trace-list');
  const headerBadge = document.getElementById('trace-badge');
  if (!emptyEl || !listEl) return;
  const session = getActiveSession();
  const events = session.traceEvents || [];

  if (events.length === 0) {
    emptyEl.style.display = 'flex';
    listEl.style.display  = 'none';
    if (headerBadge) headerBadge.innerHTML = '';
    return;
  }

  emptyEl.style.display = 'none';
  listEl.style.display  = 'flex';
  if (headerBadge) {
    headerBadge.innerHTML = `<span class="badge badge-neutral">${traceCountLabel(events.length)}</span>`;
  }

  listEl.innerHTML = '';
  events.forEach(card => {
    const div = document.createElement('div');
    div.className = 'agent-card';
    div.style.animationDelay = '0ms';
    div.innerHTML = `
      <div class="agent-card-route">
        <div class="agent-card-agents">
          <span>${escapeHtml(card.from)}</span>
          <span class="arrow">→</span>
          <span>${escapeHtml(card.to)}</span>
        </div>
        <span class="agent-card-time">${escapeHtml(card.time)}</span>
      </div>
      <div class="agent-card-msg">${escapeHtml(card.msg)}</div>
      ${getStatusEl(card)}
    `;
    listEl.appendChild(div);
  });
  setTimeout(() => { listEl.scrollTop = listEl.scrollHeight; }, 50);
}

// ============================================================
// Send Message — State Machine
// ============================================================
async function sendMessage(text) {
  text = (text || document.getElementById('composer-input').value).trim();
  if (!text || state.isProcessing) return;

  document.getElementById('composer-input').value = '';
  autoResizeTextarea(document.getElementById('composer-input'));

  const session = getActiveSession();
  if (session.messages.filter(message => message.kind === 'user').length === 0) {
    session.name = shortQuestionName(text);
  }

  session.messages.push({ kind: 'user', text });
  session.traceEvents = [
    {
      from: 'Giao diện QA',
      to: 'Orchestrator',
      time: nowLabel(),
      msg: 'Đã gửi câu hỏi tới API /api/v1/orchestrator/chat.',
      status: 'pending',
      statusText: 'Đang gửi',
    },
  ];
  state.isProcessing = true;
  persistChatState();

  renderSessions();
  renderChat();
  renderChatHeader();
  renderTrace();
  updateComposerState();

  try {
    const payload = { message: text };
    if (session.serverSessionId) payload.session_id = session.serverSessionId;

    const response = await fetch(ORCHESTRATOR_CHAT_ENDPOINT, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    let data = null;
    try {
      data = await response.json();
    } catch (_error) {
      data = null;
    }

    if (!response.ok) {
      const detail = data && data.detail ? data.detail : `HTTP ${response.status}`;
      throw new Error(detail);
    }

    const sources = Array.isArray(data.sources) ? data.sources : [];
    const sourceIds = [];
    sources.forEach((source, index) => {
      const sourceId = String(source.source_id || `source-${Date.now()}-${index}`);
      session.sourcesById[sourceId] = {
        source_id: sourceId,
        file_name: source.file_name || 'Nguồn không tên',
        page: source.page || null,
        excerpt: source.excerpt || '',
        domain: data.domain || null,
      };
      sourceIds.push(sourceId);
    });

    session.serverSessionId = data.session_id || session.serverSessionId;
    session.traceEvents[0] = {
      ...session.traceEvents[0],
      status: 'done',
      statusText: 'Đã gửi',
    };
    session.traceEvents.push(
      {
        from: 'Orchestrator',
        to: `${domainLabel(data.domain)} Agent`,
        time: nowLabel(),
        msg: `Đã chọn miền ${domainLabel(data.domain)} để xử lý câu hỏi.`,
        status: 'done',
        statusText: 'Đã điều phối',
      },
      {
        from: `${domainLabel(data.domain)} Agent`,
        to: 'MCP / RAG',
        time: nowLabel(),
        msg: data.insufficient_information
          ? 'Tài liệu hiện có chưa đủ thông tin để trả lời chắc chắn.'
          : `Đã truy xuất ${sourceIds.length} nguồn từ kho tri thức.`,
        status: data.insufficient_information ? 'warning' : 'done',
        statusText: data.insufficient_information ? 'Thiếu dữ liệu' : 'Có nguồn',
      },
      {
        from: 'Orchestrator',
        to: 'Giao diện QA',
        time: nowLabel(),
        msg: data.trace_id ? `Đã trả lời. Trace: ${data.trace_id}` : 'Đã trả lời.',
        status: data.insufficient_information ? 'warning' : 'done',
        statusText: data.insufficient_information ? 'Cần kiểm tra' : 'Hoàn thành',
      }
    );

    session.messages.push({
      kind: 'answer',
      text: data.answer || 'Không có nội dung trả lời.',
      domain: data.domain,
      traceId: data.trace_id,
      insufficientInformation: Boolean(data.insufficient_information),
      sources: sourceIds,
    });
  } catch (error) {
    const errorMessage = error && error.message
      ? error.message
      : 'Không thể kết nối tới Orchestrator Agent.';
    session.traceEvents[0] = {
      ...session.traceEvents[0],
      status: 'error',
      statusText: 'Thất bại',
    };
    session.traceEvents.push({
      from: 'Orchestrator',
      to: 'Giao diện QA',
      time: nowLabel(),
      msg: errorMessage,
      status: 'error',
      statusText: 'Lỗi',
    });
    session.messages.push({
      kind: 'error',
      text: `Không thể lấy câu trả lời từ Orchestrator Agent. ${errorMessage}`,
    });
  } finally {
    state.isProcessing = false;
    persistChatState();
    renderTrace();
    renderChat();
    renderChatHeader();
    renderSessions();
    updateComposerState();
  }
}

function updateComposerState() {
  const input = document.getElementById('composer-input');
  const btn   = document.getElementById('btn-send');
  if (!input || !btn) return;
  input.disabled = state.isProcessing;
  btn.disabled   = state.isProcessing;
}

// ============================================================
// Auto-resize textarea
// ============================================================
function autoResizeTextarea(el) {
  el.style.height = 'auto';
  el.style.height = el.scrollHeight + 'px';
}

// ============================================================
// Source Overlay
// ============================================================
function openSourceOverlay(sourceId) {
  const session = getActiveSession();
  const data = session.sourcesById[sourceId];
  if (!data) return;
  state.activeSourceId = sourceId;

  document.getElementById('source-header-filename').textContent = data.file_name || 'Nguồn không tên';
  document.getElementById('source-meta-category').textContent  = domainLabel(data.domain);
  document.getElementById('source-meta-folder').textContent    = data.source_id || sourceId;
  document.getElementById('source-meta-updated').textContent   = data.page || '—';
  document.getElementById('source-excerpt').textContent        = data.excerpt || 'Không có đoạn trích.';

  const agentsList = document.getElementById('source-agents-list');
  agentsList.innerHTML = `
    <div class="source-agent-item">${ICON.checkCircle}<span>${escapeHtml(domainLabel(data.domain))} Agent</span></div>
    <div class="source-agent-item">${ICON.checkCircle}<span>MCP / RAG</span></div>
  `;

  document.getElementById('overlay-backdrop').classList.add('open');
  document.getElementById('source-panel').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeSourceOverlay() {
  document.getElementById('overlay-backdrop').classList.remove('open');
  document.getElementById('source-panel').classList.remove('open');
  document.body.style.overflow = '';
  state.activeSourceId = null;
}

// ============================================================
// Page Navigation (QA ↔ Documents)
// ============================================================
function switchPage(page) {
  const navQa   = document.getElementById('nav-qa');
  const navDocs = document.getElementById('nav-docs');
  const qaView  = document.getElementById('qa-view');
  const docsView= document.getElementById('documents-view');
  const pageTitle    = document.getElementById('page-title');
  const pageSubtitle = document.getElementById('page-subtitle');

  if (page === 'qa') {
    navQa.classList.add('active'); navDocs.classList.remove('active');
    qaView.classList.add('active'); docsView.classList.remove('active');
    pageTitle.textContent    = 'Hỏi đáp AI';
    pageSubtitle.textContent = 'Truy vấn dữ liệu và phân tích nghiệp vụ với sự trợ giúp từ Đội chuyên gia AI';
    history.pushState(null, '', '#qa');
  } else {
    navDocs.classList.add('active'); navQa.classList.remove('active');
    docsView.classList.add('active'); qaView.classList.remove('active');
    pageTitle.textContent    = 'Kho tài liệu';
    pageSubtitle.textContent = 'Quản lý dữ liệu và tri thức nghiệp vụ của hệ thống';
    history.pushState(null, '', '#documents');
  }
}

// ============================================================
// Bootstrap
// ============================================================
document.addEventListener('DOMContentLoaded', () => {

  // Initial render
  renderSessions();
  renderChat();
  renderTrace();
  updateComposerState();

  // Initial page from hash
  const hash = window.location.hash;
  switchPage(hash === '#documents' ? 'documents' : 'qa');

  // Nav
  document.getElementById('nav-qa')  .addEventListener('click', () => switchPage('qa'));
  document.getElementById('nav-docs').addEventListener('click', () => switchPage('documents'));

  // New session
  document.getElementById('btn-new-session').addEventListener('click', createNewSession);

  // Composer: Enter to send, Shift+Enter for newline
  const composerInput = document.getElementById('composer-input');
  composerInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
  composerInput.addEventListener('input', () => autoResizeTextarea(composerInput));

  // Send button
  document.getElementById('btn-send').addEventListener('click', () => sendMessage());

  // Source overlay: backdrop & close button
  document.getElementById('overlay-backdrop').addEventListener('click', closeSourceOverlay);
  document.getElementById('btn-close-source').addEventListener('click', closeSourceOverlay);

  // ----------------------------------------------------------------
  // Documents Module Init
  // ----------------------------------------------------------------
  initDocumentsModule();
});

// ============================================================
// DOCUMENTS MODULE — Full spec implementation
// ============================================================

// --- Data ---
const DOCUMENT_RECORDS = [
  { name: 'Quy trình cấp tín dụng 2026.pdf',       date: '15/07/2026', size: '4,8 MB', status: 'ready',      ext: 'pdf' },
  { name: 'Chính sách chấm điểm tín dụng.pdf',     date: '08/07/2026', size: '3,6 MB', status: 'ready',      ext: 'pdf' },
  { name: 'Báo cáo CIC khách hàng.pdf',             date: '14/07/2026', size: '1,7 MB', status: 'ready',      ext: 'pdf' },
  { name: 'Quy định tài sản bảo đảm.pdf',           date: '12/07/2026', size: '2,1 MB', status: 'ready',      ext: 'pdf' },
  { name: 'Danh mục kiểm tra KYC.pdf',              date: '10/07/2026', size: '860 KB', status: 'ready',      ext: 'pdf' },
  { name: 'Danh mục hồ sơ vay doanh nghiệp.docx',  date: '09/07/2026', size: '540 KB', status: 'processing', ext: 'docx' },
  { name: 'Biểu phí tín dụng doanh nghiệp.pdf',    date: '01/07/2026', size: '1,2 MB', status: 'ready',      ext: 'pdf' },
  { name: 'Chính sách tín dụng 2024.pdf',           date: '22/12/2024', size: '5,4 MB', status: 'expired',    ext: 'pdf' },
];

const STATUS_LABELS = { ready: 'Sẵn sàng', processing: 'Đang xử lý', expired: 'Hết hiệu lực' };

// --- Upload demo files ---
const DEMO_UPLOAD_ITEMS = [
  { id: 'u1', name: 'Hồ sơ đề nghị cấp tín dụng.pdf',  size: '2,4 MB', stageIndex: 0, failed: false, error: null },
  { id: 'u2', name: 'Danh mục tài sản bảo đảm.docx',    size: '840 KB', stageIndex: 0, failed: false, error: null },
  { id: 'u3', name: 'Sao kê giao dịch lỗi.xlsx',        size: '1,1 MB', stageIndex: 0, failed: false, error: null },
];
const UPLOAD_STAGES = ['Đang tải', 'Đang phân loại', 'Đang lập chỉ mục', 'Sẵn sàng'];

// --- Documents state ---
let docState = {
  query: '',
  pageSize: 10,
  currentPage: 1,
  uploadItems: DEMO_UPLOAD_ITEMS.map(x => ({ ...x })),
  stageInterval: null,
  processingStarted: false,
};

// --- SVG icons for table ---
const ICON_PDF  = `<svg class="doc-icon-pdf"  xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`;
const ICON_DOCX = `<svg class="doc-icon-docx" xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`;
const ICON_XLSX = `<svg class="doc-icon-xlsx" xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`;
const ICON_FILE_EMPTY = `<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`;
const ICON_FILE_UPLOAD = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`;

function getDocIcon(ext) {
  if (ext === 'docx') return ICON_DOCX;
  if (ext === 'xlsx') return ICON_XLSX;
  return ICON_PDF;
}

// ---- Render Table ----
function renderDocTable() {
  const tbody        = document.getElementById('doc-tbody');
  const countLabel   = document.getElementById('doc-count-label');
  const paginationEl = document.getElementById('pagination-controls');
  if (!tbody) return;

  // Filter by query (locale-aware, case-insensitive)
  const q = docState.query.trim().toLowerCase();
  const filtered = q
    ? DOCUMENT_RECORDS.filter(r => r.name.toLowerCase().includes(q))
    : DOCUMENT_RECORDS;

  const pageSize    = docState.pageSize;
  const totalPages  = Math.max(1, Math.ceil(filtered.length / pageSize));
  const page        = Math.min(docState.currentPage, totalPages);
  docState.currentPage = page;

  const start   = (page - 1) * pageSize;
  const pageRows = filtered.slice(start, start + pageSize);

  // Count label
  if (filtered.length === 0) {
    countLabel.textContent = '';
  } else {
    const endIdx = Math.min(start + pageSize, filtered.length);
    countLabel.innerHTML = `Hiển thị <strong>${start + 1}–${endIdx}</strong> trong tổng số <strong>${filtered.length}</strong> tài liệu`;
  }

  // Table rows
  tbody.innerHTML = '';

  if (pageRows.length === 0) {
    // Empty state
    const emptyRow = document.createElement('tr');
    emptyRow.innerHTML = `
      <td colspan="4" style="padding:0;border:none;">
        <div class="doc-empty-state">
          ${ICON_FILE_EMPTY}
          <div class="doc-empty-title">Không tìm thấy tài liệu phù hợp</div>
          <div class="doc-empty-desc">Thử thay đổi từ khóa tìm kiếm.</div>
          <button class="btn-clear-search" id="btn-clear-search">Xóa tìm kiếm</button>
        </div>
      </td>
    `;
    tbody.appendChild(emptyRow);
    document.getElementById('btn-clear-search').addEventListener('click', () => {
      docState.query = '';
      document.getElementById('doc-search').value = '';
      docState.currentPage = 1;
      renderDocTable();
    });
  } else {
    pageRows.forEach(rec => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><div class="doc-filename">${getDocIcon(rec.ext)}<span>${rec.name}</span></div></td>
        <td>${rec.date}</td>
        <td>${rec.size}</td>
        <td><span class="doc-badge ${rec.status}">${STATUS_LABELS[rec.status]}</span></td>
      `;
      tbody.appendChild(tr);
    });
  }

  // Pagination (only if totalPages > 1)
  paginationEl.innerHTML = '';
  if (totalPages > 1) {
    const prevBtn = document.createElement('button');
    prevBtn.className = 'pager-btn';
    prevBtn.textContent = 'Trang trước';
    prevBtn.disabled = (page === 1);
    prevBtn.addEventListener('click', () => { docState.currentPage--; renderDocTable(); });
    paginationEl.appendChild(prevBtn);

    for (let i = 1; i <= totalPages; i++) {
      const numBtn = document.createElement('button');
      numBtn.className = 'pager-num' + (i === page ? ' active' : '');
      numBtn.textContent = i;
      numBtn.addEventListener('click', () => { docState.currentPage = i; renderDocTable(); });
      paginationEl.appendChild(numBtn);
    }

    const nextBtn = document.createElement('button');
    nextBtn.className = 'pager-btn';
    nextBtn.textContent = 'Trang sau';
    nextBtn.disabled = (page === totalPages);
    nextBtn.addEventListener('click', () => { docState.currentPage++; renderDocTable(); });
    paginationEl.appendChild(nextBtn);
  }
}

// ---- Upload Modal ----
function openUploadModal() {
  docState.uploadItems = DEMO_UPLOAD_ITEMS.map(x => ({ ...x, stageIndex: 0, failed: false, error: null }));
  docState.processingStarted = false;
  if (docState.stageInterval) { clearInterval(docState.stageInterval); docState.stageInterval = null; }
  renderUploadQueue();
  document.getElementById('upload-modal').classList.add('open');
  document.getElementById('btn-start-processing').disabled = (docState.uploadItems.length === 0);
}

function closeUploadModal() {
  document.getElementById('upload-modal').classList.remove('open');
  if (docState.stageInterval) { clearInterval(docState.stageInterval); docState.stageInterval = null; }
}

function renderUploadQueue() {
  const queue = document.getElementById('upload-queue');
  const startBtn = document.getElementById('btn-start-processing');
  if (!queue) return;

  queue.innerHTML = '';
  docState.uploadItems.forEach((item, idx) => {
    const article = document.createElement('article');
    article.className = 'upload-file';

    const currentStage = item.failed ? UPLOAD_STAGES[item.stageIndex] : UPLOAD_STAGES[item.stageIndex];
    const stageLabel   = item.failed ? `<span class="stage-label failed">Lỗi tại: ${currentStage}</span>`
                       : item.stageIndex === UPLOAD_STAGES.length - 1
                         ? `<span class="stage-label done">${UPLOAD_STAGES[UPLOAD_STAGES.length - 1]}</span>`
                         : `<span class="stage-label${docState.processingStarted ? ' active' : ''}">${currentStage}</span>`;

    // Stage dots
    const dotsHtml = UPLOAD_STAGES.map((_, si) => {
      let cls = '';
      if (item.failed && si === item.stageIndex) cls = 'failed';
      else if (si < item.stageIndex) cls = 'done';
      else if (si === item.stageIndex && docState.processingStarted && !item.failed) cls = 'active';
      return `<div class="stage-dot ${cls}"></div>`;
    }).join('');

    article.innerHTML = `
      <div class="upload-file-row">
        <div class="upload-file-icon">${ICON_FILE_UPLOAD}</div>
        <div class="upload-file-info">
          <strong class="upload-file-name">${item.name}</strong>
          <span class="upload-file-meta">${item.size}</span>
        </div>
      </div>
      <div class="upload-stage-bar">
        ${dotsHtml}
        ${stageLabel}
      </div>
      ${item.failed ? `
        <div class="upload-error">
          <span>${item.error}</span>
          <button class="btn-retry" data-idx="${idx}">Thử lại</button>
        </div>
      ` : ''}
    `;
    queue.appendChild(article);
  });

  // Retry handlers
  queue.querySelectorAll('.btn-retry').forEach(btn => {
    btn.addEventListener('click', () => {
      const idx = parseInt(btn.dataset.idx);
      docState.uploadItems[idx].failed = false;
      docState.uploadItems[idx].error  = null;
      docState.uploadItems[idx].stageIndex = 0;
      renderUploadQueue();
      if (docState.processingStarted && !docState.stageInterval) startStageInterval();
    });
  });

  if (startBtn) startBtn.disabled = (docState.uploadItems.length === 0);
}

function startStageInterval() {
  docState.processingStarted = true;
  docState.stageInterval = setInterval(() => {
    let anyActive = false;
    docState.uploadItems.forEach((item, idx) => {
      if (item.failed) return;
      if (item.stageIndex < UPLOAD_STAGES.length - 1) {
        // Simulate failure for item index 2 at stage 2
        if (idx === 2 && item.stageIndex === 2) {
          item.failed = true;
          item.error  = 'Tệp bị gián đoạn khi lập chỉ mục';
        } else {
          item.stageIndex++;
        }
        anyActive = true;
      }
    });
    renderUploadQueue();
    if (!anyActive) {
      clearInterval(docState.stageInterval);
      docState.stageInterval = null;
    }
  }, 650);
}

// ---- Drag & Drop ----
function setupDropzone() {
  const dropzone  = document.getElementById('upload-dropzone');
  const fileInput = document.getElementById('file-input');
  if (!dropzone || !fileInput) return;

  dropzone.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', () => {
    Array.from(fileInput.files).forEach(f => {
      const ext = f.name.split('.').pop().toLowerCase();
      docState.uploadItems.push({
        id: 'f' + Date.now() + Math.random(),
        name: f.name,
        size: f.size > 1024 * 1024 ? `${(f.size / 1024 / 1024).toFixed(1)} MB` : `${Math.round(f.size / 1024)} KB`,
        stageIndex: 0, failed: false, error: null,
      });
    });
    fileInput.value = '';
    renderUploadQueue();
  });

  dropzone.addEventListener('dragover',  e => { e.preventDefault(); dropzone.classList.add('drag-over'); });
  dropzone.addEventListener('dragleave', e => { dropzone.classList.remove('drag-over'); });
  dropzone.addEventListener('drop',      e => {
    e.preventDefault(); dropzone.classList.remove('drag-over');
    Array.from(e.dataTransfer.files).forEach(f => {
      docState.uploadItems.push({
        id: 'f' + Date.now() + Math.random(),
        name: f.name,
        size: f.size > 1024 * 1024 ? `${(f.size / 1024 / 1024).toFixed(1)} MB` : `${Math.round(f.size / 1024)} KB`,
        stageIndex: 0, failed: false, error: null,
      });
    });
    renderUploadQueue();
  });
}

// ---- Bootstrap Documents ----
function initDocumentsModule() {
  renderDocTable();

  // Search — real-time, reset to page 1
  const searchInput = document.getElementById('doc-search');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      docState.query = searchInput.value;
      docState.currentPage = 1;
      renderDocTable();
    });
  }

  // Page size selector
  const pageSizeSelect = document.getElementById('page-size-select');
  if (pageSizeSelect) {
    pageSizeSelect.addEventListener('change', () => {
      docState.pageSize = parseInt(pageSizeSelect.value);
      docState.currentPage = 1;
      renderDocTable();
    });
  }

  // Upload modal
  const btnUpload = document.getElementById('btn-upload-docs');
  if (btnUpload) btnUpload.addEventListener('click', openUploadModal);

  const btnModalClose  = document.getElementById('btn-modal-close');
  const btnModalCancel = document.getElementById('btn-modal-cancel');
  const modalBackdrop  = document.getElementById('modal-backdrop');
  if (btnModalClose)  btnModalClose.addEventListener('click', closeUploadModal);
  if (btnModalCancel) btnModalCancel.addEventListener('click', closeUploadModal);
  if (modalBackdrop)  modalBackdrop.addEventListener('click', closeUploadModal);

  // Escape key closes modal
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && document.getElementById('upload-modal').classList.contains('open')) {
      closeUploadModal();
    }
  });

  // Start processing button
  const btnStart = document.getElementById('btn-start-processing');
  if (btnStart) {
    btnStart.addEventListener('click', () => {
      if (docState.uploadItems.length > 0 && !docState.stageInterval) {
        startStageInterval();
      }
    });
  }

  setupDropzone();
}
