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
const SIDEBAR_COLLAPSED_STORAGE_KEY = 'mediax-agent-bank-sidebar-collapsed-v1';
const PRIMARY_ACCESS_TOKEN_STORAGE_KEY = 'mediax-agent-bank-access-token';
const ACCESS_TOKEN_STORAGE_KEYS = [
  PRIMARY_ACCESS_TOKEN_STORAGE_KEY,
  'access_token',
  'auth_token',
  'token',
  'mediax_access_token',
  'mediax-auth-token',
];
const AUTH_DEMO_LOGIN_ENDPOINT = '/api/v1/auth/demo-login';
const AUTH_ME_ENDPOINT = '/api/v1/auth/me';
const ORCHESTRATOR_CHAT_ENDPOINT = '/api/v1/orchestrator/chat';
const DOMAIN_LABELS = {
  general: 'Agent Planner',
  credit: 'Agent Credit',
  compliance: 'Agent Compliance',
  operations: 'Agent Operations',
};

let activeChatStorageKey = '';
let state = createInitialChatState();

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

function createInitialChatState() {
  const firstSession = createSessionObject();
  firstSession.active = true;
  return {
    sessions: [firstSession],
    isProcessing: false,
    activeSourceId: null,
  };
}

function loadChatState(storageKey) {
  if (!storageKey) return createInitialChatState();

  let sourceKey = storageKey;
  try {
    let raw = localStorage.getItem(storageKey);
    if (!raw) {
      sourceKey = CHAT_STORAGE_KEY;
      raw = localStorage.getItem(sourceKey);
    }
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
        if (sourceKey !== storageKey) {
          localStorage.setItem(storageKey, JSON.stringify({ sessions }));
          localStorage.removeItem(sourceKey);
        }
        return { sessions, isProcessing: false, activeSourceId: null };
      }
    }
  } catch (_error) {
    localStorage.removeItem(sourceKey);
  }

  return createInitialChatState();
}

function persistChatState() {
  if (!activeChatStorageKey) return;
  try {
    localStorage.setItem(
      activeChatStorageKey,
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
  return DOMAIN_LABELS[domain] || 'Agent';
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

function citationDisplayFileName(fileName) {
  return String(fileName || 'Nguồn không tên').replace(/^[0-9a-f]{32}_/i, '');
}

function formatAnswerText(value) {
  return escapeHtml(value).replace(/\n/g, '<br>');
}

function formatAssistantAnswer(value) {
  const text = String(value ?? '');
  if (!window.marked || !window.DOMPurify) return formatAnswerText(text);
  return window.DOMPurify.sanitize(
    window.marked.parse(text, { breaks: true, gfm: true }),
    { FORBID_TAGS: ['img'] }
  );
}

async function readApiJson(response) {
  try {
    return await response.json();
  } catch (_error) {
    return null;
  }
}

function apiErrorMessage(data, fallbackStatus) {
  if (!data) return `HTTP ${fallbackStatus}`;
  if (typeof data.detail === 'string') return data.detail;
  if (Array.isArray(data.detail)) return data.detail.map(item => item.msg || item.type || 'Lỗi dữ liệu').join(', ');
  if (typeof data.message === 'string') return data.message;
  return `HTTP ${fallbackStatus}`;
}

function getStoredAccessToken() {
  try {
    for (const key of ACCESS_TOKEN_STORAGE_KEYS) {
      const raw = localStorage.getItem(key);
      if (!raw) continue;

      const normalized = raw.trim();
      if (!normalized) continue;
      if (normalized.startsWith('{')) {
        try {
          const parsed = JSON.parse(normalized);
          const nestedToken = parsed.access_token || parsed.accessToken || parsed.token;
          if (nestedToken) return String(nestedToken).replace(/^Bearer\s+/i, '').trim();
        } catch (_error) {
          continue;
        }
      }
      return normalized.replace(/^Bearer\s+/i, '').trim();
    }
  } catch (_error) {
    return '';
  }
  return '';
}

function storeAccessToken(token) {
  const normalizedToken = String(token || '').replace(/^Bearer\s+/i, '').trim();
  if (!normalizedToken) return;
  localStorage.setItem(PRIMARY_ACCESS_TOKEN_STORAGE_KEY, normalizedToken);
}

function clearAccessToken() {
  ACCESS_TOKEN_STORAGE_KEYS.forEach(key => localStorage.removeItem(key));
}

function buildKnowledgeBaseHeaders(headers = {}) {
  const token = getStoredAccessToken();
  if (!token) return headers;
  return { ...headers, Authorization: `Bearer ${token}` };
}

function localizeAgentActionText(value) {
  return String(value ?? '')
    .replace(/Đội chuyên gia AI/g, 'MediaX AI Agent Bank')
    .replace(/Chưa xác định miền xử lý/g, 'Chưa xác định Agent phù hợp')
    .replace(/(?:[Mm]iền|Chuyên gia)\s+Tín dụng/g, 'Agent Credit')
    .replace(/(?:[Mm]iền|Chuyên gia)\s+(?:Chính sách|Tuân thủ)/g, 'Agent Compliance')
    .replace(/(?:[Mm]iền|Chuyên gia)\s+Vận hành/g, 'Agent Operations')
    .replace(/Bộ điều phối/g, 'Agent Planner')
    .replace(/\b[Cc]huyên gia\b/g, 'Agent')
    .replace(/Giao diện QA/g, 'Giao diện hỏi đáp')
    .replace(/Orchestrator Agent/g, 'Agent Planner')
    .replace(/Orchestrator/g, 'Agent Planner')
    .replace(/MCP\s*\/\s*RAG/g, 'Kho tri thức')
    .replace(/Trace:/g, 'Mã theo dõi:')
    .replace(/Đã gửi câu hỏi tới API \/api\/v1\/orchestrator\/chat\./g, 'Đã gửi câu hỏi tới dịch vụ hỏi đáp.')
    .replace(/Tín dụng Agent/g, 'Agent Credit')
    .replace(/Chính sách Agent/g, 'Agent Compliance')
    .replace(/Tuân thủ Agent/g, 'Agent Compliance')
    .replace(/Vận hành Agent/g, 'Agent Operations');
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
  if (status === 'pending') return '';
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
             : card.status === 'pending' ? ''
             : ICON.alert;
  const iconHtml = icon ? `${icon} ` : '';
  return `<span class="agent-card-status ${cls}">${iconHtml}${localizeAgentActionText(card.statusText)}</span>`;
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
        <h3 class="chat-empty-title">Bắt đầu cuộc trò chuyện với MediaX AI Agent Bank</h3>
        <p class="chat-empty-desc">Nhập câu hỏi nghiệp vụ để Agent Planner chuyển đến Agent phù hợp.</p>
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
            <div class="msg-bubble-error">${formatAnswerText(localizeAgentActionText(msg.text))}</div>
          </div>
        </div>
      `;
    } else {
      const sources = (msg.sources || [])
        .map(sourceId => session.sourcesById[sourceId])
        .filter(Boolean);
      const sourceLinks = sources.map(source => {
        const page = source.page ? ` · trang ${escapeHtml(source.page)}` : '';
        const label = `${escapeHtml(citationDisplayFileName(source.file_name || source.source_id))}${page}`;
        return `<button class="qa-source-link" data-source-id="${escapeHtml(source.source_id)}">${ICON.file}<span class="qa-source-label">${label}</span></button>`;
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
            <div class="msg-author">MediaX AI Agent Bank</div>
            <div class="msg-bubble-ai">${formatAssistantAnswer(msg.text)}</div>
            <div class="msg-meta">
              <span class="msg-meta-reliability">${ICON.shield}&nbsp;${statusText}</span>
              <span class="msg-meta-agents">${ICON.users}&nbsp;${domain}</span>
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
          MediaX AI Agent Bank đang phân tích dữ liệu...
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
    const from = localizeAgentActionText(card.from);
    const to = localizeAgentActionText(card.to);
    const msg = localizeAgentActionText(card.msg);
    const div = document.createElement('div');
    div.className = 'agent-card';
    div.style.animationDelay = '0ms';
    div.innerHTML = `
      <div class="agent-card-route">
        <div class="agent-card-agents">
          <span>${escapeHtml(from)}</span>
          <span class="arrow">→</span>
          <span>${escapeHtml(to)}</span>
        </div>
        <span class="agent-card-time">${escapeHtml(card.time)}</span>
      </div>
      <div class="agent-card-msg">${escapeHtml(msg)}</div>
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
      from: 'Giao diện hỏi đáp',
      to: 'Agent Planner',
      time: nowLabel(),
      msg: 'Đã gửi câu hỏi tới dịch vụ hỏi đáp.',
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
      headers: buildKnowledgeBaseHeaders({
        Accept: 'application/json',
        'Content-Type': 'application/json',
      }),
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
    if (data.domain === 'general') {
      session.traceEvents.push({
        from: 'Agent Planner',
        to: 'Giao diện hỏi đáp',
        time: nowLabel(),
        msg: data.trace_id
          ? `Chưa xác định Agent phù hợp. Mã theo dõi: ${data.trace_id}`
          : 'Chưa xác định Agent phù hợp.',
        status: 'warning',
        statusText: 'Cần làm rõ',
      });
    } else {
      session.traceEvents.push(
        {
          from: 'Agent Planner',
          to: domainLabel(data.domain),
          time: nowLabel(),
          msg: `Đã chọn ${domainLabel(data.domain)} để xử lý câu hỏi.`,
          status: 'done',
          statusText: 'Đã điều phối',
        },
        {
          from: domainLabel(data.domain),
          to: 'Kho tri thức',
          time: nowLabel(),
          msg: data.insufficient_information
            ? 'Tài liệu hiện có chưa đủ thông tin để trả lời chắc chắn.'
            : `Đã truy xuất ${sourceIds.length} nguồn từ kho tri thức.`,
          status: data.insufficient_information ? 'warning' : 'done',
          statusText: data.insufficient_information ? 'Thiếu dữ liệu' : 'Có nguồn',
        },
        {
          from: 'Agent Planner',
          to: 'Giao diện hỏi đáp',
          time: nowLabel(),
          msg: data.trace_id ? `Đã trả lời. Mã theo dõi: ${data.trace_id}` : 'Đã trả lời.',
          status: data.insufficient_information ? 'warning' : 'done',
          statusText: data.insufficient_information ? 'Cần kiểm tra' : 'Hoàn thành',
        }
      );
    }

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
      : 'Không thể kết nối tới Agent Planner.';
    session.traceEvents[0] = {
      ...session.traceEvents[0],
      status: 'error',
      statusText: 'Thất bại',
    };
    session.traceEvents.push({
      from: 'Agent Planner',
      to: 'Giao diện hỏi đáp',
      time: nowLabel(),
      msg: errorMessage,
      status: 'error',
      statusText: 'Lỗi',
    });
    session.messages.push({
      kind: 'error',
      text: `Không thể lấy câu trả lời từ Agent Planner. ${errorMessage}`,
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

function setSidebarCollapsed(collapsed) {
  document.body.classList.toggle('sidebar-collapsed', collapsed);

  const toggle = document.getElementById('sidebar-toggle');
  if (!toggle) return;

  toggle.innerHTML = collapsed ? '&#x203A;' : '&#x2039;';
  toggle.title = collapsed ? 'Mở rộng' : 'Thu gọn';
  toggle.setAttribute('aria-label', collapsed ? 'Mở rộng menu' : 'Thu gọn menu');
  toggle.setAttribute('aria-expanded', String(!collapsed));

  try {
    localStorage.setItem(SIDEBAR_COLLAPSED_STORAGE_KEY, collapsed ? '1' : '0');
  } catch (_error) {
    // Sidebar collapse still works when browser storage is unavailable.
  }
}

function initSidebarToggle() {
  const toggle = document.getElementById('sidebar-toggle');
  if (!toggle) return;

  let collapsed = false;
  try {
    collapsed = localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY) === '1';
  } catch (_error) {
    collapsed = false;
  }

  setSidebarCollapsed(collapsed);
  toggle.addEventListener('click', () => {
    setSidebarCollapsed(!document.body.classList.contains('sidebar-collapsed'));
  });
}

// ============================================================
// Authentication
// ============================================================
function updateAuthenticatedUser(user) {
  if (!user) return;
  const displayName = user.full_name || user.email || 'Người dùng';
  const role = user.email || 'Đã đăng nhập';
  const initials = displayName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map(part => part[0])
    .join('')
    .toUpperCase() || 'ND';

  const nameEl = document.querySelector('.user-name');
  const roleEl = document.querySelector('.user-role');
  const avatarEl = document.querySelector('.user-avatar');
  if (nameEl) nameEl.textContent = displayName;
  if (roleEl) roleEl.textContent = role;
  if (avatarEl) avatarEl.textContent = initials.slice(0, 2);
}

function loadAuthenticatedChatState(user) {
  const userId = String(user && user.id || '').trim();
  if (!userId) return;

  const storageKey = `${CHAT_STORAGE_KEY}:${userId}`;
  if (storageKey === activeChatStorageKey) return;
  activeChatStorageKey = storageKey;
  state = loadChatState(storageKey);
  renderSessions();
  renderChat();
  renderTrace();
  updateComposerState();
}

function unlockApp(user = null) {
  document.body.classList.remove('auth-locked');
  if (user) {
    updateAuthenticatedUser(user);
    loadAuthenticatedChatState(user);
  }
  ensureDefaultDocumentsLoaded();
}

function lockApp() {
  document.body.classList.add('auth-locked');
  activeChatStorageKey = '';
  state = createInitialChatState();
  const error = document.getElementById('auth-error');
  if (error) error.textContent = '';
}

async function fetchCurrentUser() {
  const token = getStoredAccessToken();
  if (!token) return null;

  const response = await fetch(AUTH_ME_ENDPOINT, {
    method: 'GET',
    headers: buildKnowledgeBaseHeaders({ Accept: 'application/json' }),
    credentials: 'include',
  });
  const data = await readApiJson(response);
  if (!response.ok) {
    const error = new Error(apiErrorMessage(data, response.status));
    error.status = response.status;
    throw error;
  }
  return data;
}

async function loginWithDemoAccount(accountNumber) {
  const response = await fetch(`${AUTH_DEMO_LOGIN_ENDPOINT}/${accountNumber}`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
    },
    credentials: 'include',
  });
  const data = await readApiJson(response);
  if (!response.ok) throw new Error(apiErrorMessage(data, response.status));
  if (!data || !data.access_token) throw new Error('Không nhận được access token.');
  storeAccessToken(data.access_token);
  return data;
}

function initAuthModule() {
  const token = getStoredAccessToken();
  if (token) {
    unlockApp();
    fetchCurrentUser().then(unlockApp).catch(error => {
      if (error.status === 401 || error.status === 403) {
        clearAccessToken();
        lockApp();
      }
    });
  } else {
    lockApp();
  }

  const demoButtons = document.querySelectorAll('[data-demo-account]');
  demoButtons.forEach(button => {
    button.addEventListener('click', async () => {
      const error = document.getElementById('auth-error');
      if (error) error.textContent = '';
      demoButtons.forEach(item => { item.disabled = true; });
      try {
        await loginWithDemoAccount(button.dataset.demoAccount);
        let user = null;
        try {
          user = await fetchCurrentUser();
        } catch (_error) {
          // Token is already stored; the UI can continue even if profile lookup fails.
        }
        unlockApp(user);
      } catch (submitError) {
        if (error) error.textContent = submitError.message || 'Không thể xác thực.';
      } finally {
        demoButtons.forEach(item => { item.disabled = false; });
      }
    });
  });

  const logout = document.getElementById('btn-logout');
  if (logout) {
    logout.addEventListener('click', () => {
      clearAccessToken();
      lockApp();
    });
  }
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

  document.getElementById('source-header-filename').textContent = citationDisplayFileName(data.file_name);
  document.getElementById('source-meta-category').textContent  = domainLabel(data.domain);
  document.getElementById('source-meta-folder').textContent    = data.source_id || sourceId;
  document.getElementById('source-meta-updated').textContent   = data.page || '—';
  document.getElementById('source-excerpt').textContent        = data.excerpt || 'Không có đoạn trích.';

  const agentsList = document.getElementById('source-agents-list');
  agentsList.innerHTML = `
    <div class="source-agent-item">${ICON.checkCircle}<span>${escapeHtml(domainLabel(data.domain))}</span></div>
    <div class="source-agent-item">${ICON.checkCircle}<span>Kho tri thức</span></div>
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
    pageSubtitle.textContent = 'Truy vấn dữ liệu và phân tích nghiệp vụ với sự trợ giúp từ MediaX AI Agent Bank';
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
  initAuthModule();

  // Initial render
  renderSessions();
  renderChat();
  renderTrace();
  updateComposerState();
  initSidebarToggle();

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
// DOCUMENTS MODULE
// ============================================================

const KNOWLEDGE_BASE_FILES_ENDPOINT = '/api/v1/knowledge-base/files';
const KNOWLEDGE_BASE_PROCESS_ENDPOINT = '/api/v1/knowledge-base/process-document';
const DOCUMENT_AGENT_SCOPES = {
  credit: {
    id: 'credit',
    name: DOMAIN_LABELS.credit,
    userId: '6a5b187063aaa5e0510f2da1',
  },
  compliance: {
    id: 'compliance',
    name: DOMAIN_LABELS.compliance,
    userId: '6a5b187063aaa5e0510f2da2',
  },
  operations: {
    id: 'operations',
    name: DOMAIN_LABELS.operations,
    userId: '6a5b187163aaa5e0510f2da3',
  },
};
const DEFAULT_DOCUMENT_AGENT_ID = 'credit';

const STATUS_LABELS = {
  ready: 'Sẵn sàng',
  processing: 'Đang xử lý',
  failed: 'Cần kiểm tra',
  deleted: 'Đã xoá',
};
const UPLOAD_STAGES = ['Chờ tải lên', 'Đang tải lên', 'Đang lập chỉ mục', 'Sẵn sàng'];
let docState = {
  selectedAgentId: DEFAULT_DOCUMENT_AGENT_ID,
  documents: [],
  query: '',
  pageSize: 10,
  currentPage: 1,
  isLoading: false,
  hasLoaded: false,
  loadError: null,
  uploadItems: [],
  isUploading: false,
};

// --- SVG icons for table ---
const ICON_PDF  = `<svg class="doc-icon-pdf"  xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`;
const ICON_FILE_EMPTY = `<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`;
const ICON_FILE_UPLOAD = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`;

function getDocIcon() {
  return ICON_PDF;
}

function getDocumentAgent(agentId = docState.selectedAgentId) {
  return DOCUMENT_AGENT_SCOPES[agentId] || null;
}

function setSelectedDocumentAgent(agentId) {
  docState.selectedAgentId = agentId;
  document.querySelectorAll('.agent-scope-card').forEach(card => {
    card.classList.toggle('active', card.dataset.agentId === agentId);
  });
  updateDocumentsScopeLabel();
}

function updateDocumentsScopeLabel() {
  const label = document.getElementById('docs-current-scope');
  if (!label) return;
  const agent = getDocumentAgent();
  if (!agent) {
    label.textContent = 'Chọn Agent để xem kho tri thức';
    return;
  }
  if (docState.isLoading) {
    label.textContent = `Đang tải danh sách của ${agent.name}`;
    return;
  }
  if (docState.loadError) {
    label.textContent = `Không tải được danh sách của ${agent.name}`;
    return;
  }
  if (docState.hasLoaded) {
    label.textContent = `${agent.name} · ${docState.documents.length} tài liệu`;
    return;
  }
  label.textContent = `${agent.name} · Chưa tải danh sách`;
}

function normalizeDocumentRecord(item) {
  const fileName = item.file_name || item.file_path || 'Tài liệu không tên';
  const ext = String(fileName).split('.').pop().toLowerCase();
  const rawStatus = String(item.index_status || 'indexed').toLowerCase();
  const status = rawStatus === 'indexed'
    ? 'ready'
    : rawStatus === 'indexing'
      ? 'processing'
      : rawStatus === 'deleted'
        ? 'deleted'
        : rawStatus === 'failed'
          ? 'failed'
          : 'processing';

  return {
    name: fileName,
    ext,
    status,
    statusText: STATUS_LABELS[status] || rawStatus,
    pageCount: Number(item.page_count || 0),
    chunkCount: Number(item.chunk_count || 0),
    lastError: item.last_error || '',
  };
}

function formatFileSize(bytes) {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${bytes} B`;
}

function makeUploadItem(file, { failed = false, error = null, canRetry = true } = {}) {
  return {
    id: makeLocalId(),
    name: file.name,
    size: formatFileSize(file.size),
    file,
    stageIndex: failed ? 2 : 0,
    status: failed ? 'failed' : 'queued',
    failed,
    error,
    canRetry,
  };
}

// ---- Render Table ----
function renderDocTable() {
  const tbody        = document.getElementById('doc-tbody');
  const countLabel   = document.getElementById('doc-count-label');
  const paginationEl = document.getElementById('pagination-controls');
  if (!tbody) return;

  updateDocumentsScopeLabel();

  // Filter by query (locale-aware, case-insensitive)
  const q = docState.query.trim().toLowerCase();
  const records = Array.isArray(docState.documents) ? docState.documents : [];
  const filtered = q ? records.filter(r => r.name.toLowerCase().includes(q)) : records;

  const pageSize    = docState.pageSize;
  const totalPages  = Math.max(1, Math.ceil(filtered.length / pageSize));
  const page        = Math.min(docState.currentPage, totalPages);
  docState.currentPage = page;

  const start   = (page - 1) * pageSize;
  const pageRows = filtered.slice(start, start + pageSize);

  if (countLabel) {
    countLabel.textContent = '';
  }
  if (paginationEl) {
    paginationEl.innerHTML = '';
  }

  // Table rows
  tbody.innerHTML = '';
  tbody.classList.toggle(
    'doc-tbody-empty',
    filtered.length === 0 || docState.isLoading || Boolean(docState.loadError) || !docState.hasLoaded
  );

  const renderEmptyRow = ({ title, desc, error = false, button = null }) => {
    const emptyRow = document.createElement('tr');
    emptyRow.innerHTML = `
      <td colspan="4" style="padding:0;border:none;">
        <div class="doc-empty-state">
          ${docState.isLoading ? `<span class="spinning">${ICON.loader}</span>` : ICON_FILE_EMPTY}
          <div class="doc-empty-title">${escapeHtml(title)}</div>
          ${desc ? `<div class="doc-empty-desc${error ? ' error' : ''}">${escapeHtml(desc)}</div>` : ''}
          ${button ? `<button class="btn-clear-search" id="${button.id}">${escapeHtml(button.label)}</button>` : ''}
        </div>
      </td>
    `;
    tbody.appendChild(emptyRow);
    if (button && button.onClick) {
      const btn = document.getElementById(button.id);
      if (btn) btn.addEventListener('click', button.onClick);
    }
  };

  if (!docState.selectedAgentId) {
    renderEmptyRow({
      title: 'Chưa chọn Agent',
      desc: 'Bấm Danh sách trên một Agent để xem kho tài liệu.',
    });
    return;
  }

  if (docState.isLoading) {
    renderEmptyRow({
      title: 'Đang tải danh sách tài liệu',
      desc: 'Hệ thống đang đọc kho tri thức đã chọn.',
    });
    return;
  }

  if (docState.loadError) {
    renderEmptyRow({
      title: 'Không thể tải danh sách tài liệu',
      desc: docState.loadError,
      error: true,
      button: {
        id: 'btn-reload-documents',
        label: 'Tải lại',
        onClick: () => loadDocumentsForAgent(docState.selectedAgentId),
      },
    });
    return;
  }

  if (!docState.hasLoaded) {
    renderEmptyRow({
      title: 'Danh sách chưa được tải',
      desc: 'Bấm Danh sách để đọc tài liệu của Agent đã chọn.',
    });
    return;
  }

  if (filtered.length === 0) {
    renderEmptyRow({
      title: q ? 'Không tìm thấy tài liệu phù hợp' : 'Chưa có tài liệu',
      desc: q ? 'Thử thay đổi từ khóa tìm kiếm.' : 'Upload tài liệu để lập chỉ mục cho Agent này.',
      button: q ? {
        id: 'btn-clear-search',
        label: 'Xóa tìm kiếm',
        onClick: () => {
          docState.query = '';
          document.getElementById('doc-search').value = '';
          docState.currentPage = 1;
          renderDocTable();
        },
      } : null,
    });
    return;
  }

  if (countLabel) {
    const endIdx = Math.min(start + pageSize, filtered.length);
    countLabel.innerHTML = `Hiển thị <strong>${start + 1}–${endIdx}</strong> trong tổng số <strong>${filtered.length}</strong> tài liệu`;
  }

  pageRows.forEach(rec => {
    const tr = document.createElement('tr');
    const statusTitle = rec.lastError ? ` title="${escapeHtml(rec.lastError)}"` : '';
    tr.innerHTML = `
      <td><div class="doc-filename">${getDocIcon()}<span>${escapeHtml(rec.name)}</span></div></td>
      <td>${rec.pageCount || '-'}</td>
      <td>${rec.chunkCount || '-'}</td>
      <td><span class="doc-badge ${rec.status}"${statusTitle}>${escapeHtml(rec.statusText)}</span></td>
    `;
    tbody.appendChild(tr);
  });

  // Pagination (only if totalPages > 1)
  if (paginationEl && totalPages > 1) {
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

async function loadDocumentsForAgent(agentId, { silent = false } = {}) {
  const agent = getDocumentAgent(agentId);
  if (!agent) return;

  setSelectedDocumentAgent(agent.id);
  docState.isLoading = !silent;
  docState.loadError = null;
  docState.hasLoaded = true;
  if (!silent) renderDocTable();

  try {
    const url = new URL(KNOWLEDGE_BASE_FILES_ENDPOINT, window.location.origin);
    url.searchParams.set('user_id', agent.userId);
    const response = await fetch(`${url.pathname}${url.search}`, {
      method: 'GET',
      headers: buildKnowledgeBaseHeaders({ Accept: 'application/json' }),
      credentials: 'include',
    });
    const data = await readApiJson(response);
    if (!response.ok) throw new Error(apiErrorMessage(data, response.status));

    const files = Array.isArray(data && data.files) ? data.files : [];
    docState.documents = files.map(normalizeDocumentRecord);
    docState.currentPage = 1;
  } catch (error) {
    docState.documents = [];
    docState.loadError = error.message || 'Không thể tải danh sách tài liệu.';
  } finally {
    docState.isLoading = false;
    renderDocTable();
  }
}

// ---- Upload Modal ----
function openUploadModal(agentId) {
  const agent = getDocumentAgent(agentId);
  if (!agent) return;

  setSelectedDocumentAgent(agent.id);
  docState.uploadItems = [];
  docState.isUploading = false;
  const title = document.getElementById('modal-title');
  const subtitle = document.getElementById('modal-subtitle');
  const footerNote = document.getElementById('modal-footer-note');
  if (title) title.textContent = `Tải tài liệu cho ${agent.name}`;
  if (subtitle) subtitle.textContent = 'Thêm PDF vào kho tri thức của Agent đã chọn.';
  if (footerNote) footerNote.textContent = `Tài liệu sẽ được lập chỉ mục vào kho của ${agent.name}.`;
  renderUploadQueue();
  document.getElementById('upload-modal').classList.add('open');
  document.getElementById('btn-start-processing').disabled = true;
}

function closeUploadModal() {
  document.getElementById('upload-modal').classList.remove('open');
}

function renderUploadQueue() {
  const queue = document.getElementById('upload-queue');
  const startBtn = document.getElementById('btn-start-processing');
  if (!queue) return;

  queue.innerHTML = '';
  if (docState.uploadItems.length === 0) {
    queue.innerHTML = `
      <div class="doc-empty-state" style="padding:18px 12px;">
        ${ICON_FILE_EMPTY}
        <div class="doc-empty-title">Chưa chọn tệp</div>
        <div class="doc-empty-desc">Chọn một hoặc nhiều PDF để tải lên.</div>
      </div>
    `;
    if (startBtn) startBtn.disabled = true;
    return;
  }

  docState.uploadItems.forEach((item, idx) => {
    const article = document.createElement('article');
    article.className = 'upload-file';

    const currentStage = UPLOAD_STAGES[item.stageIndex] || UPLOAD_STAGES[0];
    const stageLabel   = item.failed ? `<span class="stage-label failed">Lỗi tại: ${currentStage}</span>`
                       : item.stageIndex === UPLOAD_STAGES.length - 1
                         ? `<span class="stage-label done">${UPLOAD_STAGES[UPLOAD_STAGES.length - 1]}</span>`
                         : `<span class="stage-label${item.status === 'uploading' ? ' active' : ''}">${currentStage}</span>`;

    // Stage dots
    const dotsHtml = UPLOAD_STAGES.map((_, si) => {
      let cls = '';
      if (item.failed && si === item.stageIndex) cls = 'failed';
      else if (si < item.stageIndex) cls = 'done';
      else if (si === item.stageIndex && item.status === 'uploading' && !item.failed) cls = 'active';
      return `<div class="stage-dot ${cls}"></div>`;
    }).join('');

    article.innerHTML = `
      <div class="upload-file-row">
        <div class="upload-file-icon">${ICON_FILE_UPLOAD}</div>
        <div class="upload-file-info">
          <strong class="upload-file-name">${escapeHtml(item.name)}</strong>
          <span class="upload-file-meta">${escapeHtml(item.size)}</span>
        </div>
      </div>
      <div class="upload-stage-bar">
        ${dotsHtml}
        ${stageLabel}
      </div>
      ${item.failed ? `
        <div class="upload-error">
          <span>${escapeHtml(item.error || 'Không thể tải tệp')}</span>
          ${item.canRetry === false ? '' : `<button class="btn-retry" data-idx="${idx}">Thử lại</button>`}
        </div>
      ` : ''}
    `;
    queue.appendChild(article);
  });

  // Retry handlers
  queue.querySelectorAll('.btn-retry').forEach(btn => {
    btn.addEventListener('click', () => {
      const idx = parseInt(btn.dataset.idx);
      if (!docState.uploadItems[idx] || docState.isUploading) return;
      docState.uploadItems[idx].failed = false;
      docState.uploadItems[idx].error  = null;
      docState.uploadItems[idx].stageIndex = 0;
      docState.uploadItems[idx].status = 'queued';
      renderUploadQueue();
    });
  });

  const hasPendingUpload = docState.uploadItems.some(item => item.file && item.status !== 'done' && item.canRetry !== false);
  if (startBtn) startBtn.disabled = docState.isUploading || !hasPendingUpload;
}

async function uploadKnowledgeBaseFile(agent, item) {
  const formData = new FormData();
  formData.append('file', item.file, item.file.name);
  formData.append('user_id', agent.userId);

  const response = await fetch(KNOWLEDGE_BASE_PROCESS_ENDPOINT, {
    method: 'POST',
    headers: buildKnowledgeBaseHeaders({ Accept: 'application/json' }),
    credentials: 'include',
    body: formData,
  });
  const data = await readApiJson(response);
  if (!response.ok) throw new Error(apiErrorMessage(data, response.status));
  return data;
}

async function processUploadQueue() {
  const agent = getDocumentAgent();
  if (!agent || docState.isUploading) return;

  const uploadItems = docState.uploadItems.filter(item => item.file && item.status !== 'done' && item.canRetry !== false);
  if (uploadItems.length === 0) return;

  docState.isUploading = true;
  renderUploadQueue();

  let successCount = 0;
  for (const item of uploadItems) {
    item.status = 'uploading';
    item.failed = false;
    item.error = null;
    item.stageIndex = 1;
    renderUploadQueue();

    try {
      await uploadKnowledgeBaseFile(agent, item);
      item.stageIndex = UPLOAD_STAGES.length - 1;
      item.status = 'done';
      successCount++;
    } catch (error) {
      item.stageIndex = 2;
      item.status = 'failed';
      item.failed = true;
      item.error = error.message || 'Không thể tải tài liệu lên.';
    }
    renderUploadQueue();
  }

  docState.isUploading = false;
  renderUploadQueue();
  if (successCount > 0) {
    await loadDocumentsForAgent(agent.id, { silent: true });
  }
}

// ---- Drag & Drop ----
function setupDropzone() {
  const dropzone  = document.getElementById('upload-dropzone');
  const fileInput = document.getElementById('file-input');
  if (!dropzone || !fileInput) return;

  dropzone.addEventListener('click', () => fileInput.click());
  const addFiles = files => {
    Array.from(files).forEach(file => {
      const ext = file.name.split('.').pop().toLowerCase();
      if (ext !== 'pdf') {
        docState.uploadItems.push(makeUploadItem(file, {
          failed: true,
          error: 'Chỉ hỗ trợ tệp PDF.',
          canRetry: false,
        }));
        return;
      }
      docState.uploadItems.push(makeUploadItem(file));
    });
    renderUploadQueue();
  };

  fileInput.addEventListener('change', () => {
    addFiles(fileInput.files);
    fileInput.value = '';
  });

  dropzone.addEventListener('dragover',  e => { e.preventDefault(); dropzone.classList.add('drag-over'); });
  dropzone.addEventListener('dragleave', e => { dropzone.classList.remove('drag-over'); });
  dropzone.addEventListener('drop',      e => {
    e.preventDefault(); dropzone.classList.remove('drag-over');
    addFiles(e.dataTransfer.files);
  });
}

// ---- Bootstrap Documents ----
function ensureDefaultDocumentsLoaded() {
  const agentId = docState.selectedAgentId || DEFAULT_DOCUMENT_AGENT_ID;
  if (!docState.selectedAgentId) {
    setSelectedDocumentAgent(agentId);
  } else {
    setSelectedDocumentAgent(docState.selectedAgentId);
  }
  if (!getStoredAccessToken()) {
    renderDocTable();
    return;
  }
  if (docState.isLoading || (docState.hasLoaded && !docState.loadError)) return;
  loadDocumentsForAgent(agentId);
}

function initDocumentsModule() {
  ensureDefaultDocumentsLoaded();

  document.querySelectorAll('[data-doc-action]').forEach(btn => {
    btn.addEventListener('click', () => {
      const agentId = btn.dataset.agentId;
      const action = btn.dataset.docAction;
      if (action === 'list') {
        loadDocumentsForAgent(agentId);
      } else if (action === 'upload') {
        openUploadModal(agentId);
      }
    });
  });

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
      processUploadQueue();
    });
  }

  setupDropzone();
}
