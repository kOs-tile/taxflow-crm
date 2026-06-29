/**
 * TaxFlow CRM — Frontend Application
 * Vanilla JS: API client, auth, routing, UI components, SSE
 */

// ─── Config ────────────────────────────────────────────────────────
const API_BASE = '/api';

// ─── State ─────────────────────────────────────────────────────────
const State = {
  token: localStorage.getItem('taxflow_token'),
  user: JSON.parse(localStorage.getItem('taxflow_user') || 'null'),
  currentClientId: null,
  sseSource: null,
  unreadCounts: {},
  conversationHistory: [],
};

// ─── Auth Helpers ───────────────────────────────────────────────────
function isAuthenticated() {
  return !!State.token;
}

function getAuthHeaders() {
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${State.token}`,
  };
}

function saveAuth(token, user) {
  State.token = token;
  State.user = user;
  localStorage.setItem('taxflow_token', token);
  localStorage.setItem('taxflow_user', JSON.stringify(user));
}

function clearAuth() {
  State.token = null;
  State.user = null;
  localStorage.removeItem('taxflow_token');
  localStorage.removeItem('taxflow_user');
}

function logout() {
  clearAuth();
  window.location.href = '/login';
}

// ─── API Client ─────────────────────────────────────────────────────
async function api(method, path, body = null, options = {}) {
  const url = `${API_BASE}${path}`;
  const config = {
    method,
    headers: getAuthHeaders(),
    ...options,
  };
  if (body && method !== 'GET') {
    config.body = JSON.stringify(body);
  }

  const res = await fetch(url, config);

  if (res.status === 401) {
    clearAuth();
    window.location.href = '/login';
    return null;
  }

  if (res.status === 204) return null;

  const data = await res.json().catch(() => null);

  if (!res.ok) {
    const msg = data?.detail || `HTTP ${res.status}`;
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  }

  return data;
}

const API = {
  get: (path) => api('GET', path),
  post: (path, body) => api('POST', path, body),
  patch: (path, body) => api('PATCH', path, body),
  delete: (path) => api('DELETE', path),

  // Auth
  login: (email, password) =>
    api('POST', '/auth/login', { email, password }),

  // Dashboard
  dashboard: () => api('GET', '/dashboard'),
  stats: () => api('GET', '/dashboard/stats'),

  // Clients
  clients: (params = '') => api('GET', `/clients${params}`),
  client: (id) => api('GET', `/clients/${id}`),
  createClient: (data) => api('POST', '/clients', data),
  updateClient: (id, data) => api('PATCH', `/clients/${id}`, data),
  deleteClient: (id) => api('DELETE', `/clients/${id}`),
  clientSummary: (id) => api('GET', `/clients/${id}/summary`),

  // Documents
  documents: (clientId, year = '') =>
    api('GET', `/documents/client/${clientId}${year ? `?tax_year=${year}` : ''}`),
  docStats: (clientId) => api('GET', `/documents/client/${clientId}/stats`),
  initDocs: (clientId) => api('POST', `/documents/client/${clientId}/initialize`),
  updateDoc: (docId, data) => api('PATCH', `/documents/${docId}`, data),
  missingDocs: (clientId) => api('GET', `/documents/client/${clientId}/missing`),

  // Deadlines
  deadlines: (clientId) => api('GET', `/deadlines/client/${clientId}`),
  upcomingDeadlines: (days = 14) => api('GET', `/deadlines/upcoming?days=${days}`),
  createDeadline: (data) => api('POST', '/deadlines', data),
  updateDeadline: (id, data) => api('PATCH', `/deadlines/${id}`, data),
  autoDeadlines: (clientId) => api('POST', `/deadlines/client/${clientId}/auto-generate`),

  // Messages
  threads: () => api('GET', '/messages/threads'),
  messages: (clientId) => api('GET', `/messages/client/${clientId}`),
  sendMessage: (clientId, content) =>
    api('POST', `/messages/client/${clientId}/send`, { client_id: clientId, content }),
  markRead: (clientId) => api('POST', `/messages/client/${clientId}/read`),

  // Tasks
  tasks: (clientId) => api('GET', `/tasks/client/${clientId}`),
  createTask: (data) => api('POST', '/tasks', data),
  updateTask: (id, data) => api('PATCH', `/tasks/${id}`, data),
  completeTask: (id) => api('POST', `/tasks/${id}/complete`),

  // AI Assistant
  chat: (clientId, message, history) =>
    api('POST', '/assistant/chat', {
      client_id: clientId || null,
      message,
      conversation_history: history || [],
    }),
  prompts: (clientId) =>
    api('GET', `/assistant/prompts${clientId ? `?client_id=${clientId}` : ''}`),

  // Users
  users: () => api('GET', '/users'),
};

// ─── Toast Notifications ────────────────────────────────────────────
function showToast(message, type = 'default', duration = 3500) {
  let wrap = document.getElementById('toast-wrap');
  if (!wrap) {
    wrap = document.createElement('div');
    wrap.id = 'toast-wrap';
    wrap.className = 'toast-wrap';
    document.body.appendChild(wrap);
  }

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  wrap.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(8px)';
    toast.style.transition = 'opacity 0.3s, transform 0.3s';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// ─── Modal System ───────────────────────────────────────────────────
function openModal(modalId) {
  const overlay = document.getElementById(modalId);
  if (overlay) overlay.classList.add('open');
}

function closeModal(modalId) {
  const overlay = document.getElementById(modalId);
  if (overlay) overlay.classList.remove('open');
}

function setupModalClose() {
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.classList.remove('open');
    });
  });
  document.querySelectorAll('[data-close-modal]').forEach(btn => {
    btn.addEventListener('click', () => {
      const modal = btn.closest('.modal-overlay');
      if (modal) modal.classList.remove('open');
    });
  });
}

// ─── Sidebar Active State ───────────────────────────────────────────
function setActiveNav() {
  const path = window.location.pathname;
  document.querySelectorAll('.nav-item').forEach(item => {
    const href = item.getAttribute('href');
    if (!href) return;
    const isActive = path === href || (href !== '/' && path.startsWith(href));
    item.classList.toggle('active', isActive);
  });
}

// ─── User Display ───────────────────────────────────────────────────
function renderSidebarUser() {
  const nameEl = document.getElementById('sidebar-user-name');
  const roleEl = document.getElementById('sidebar-user-role');
  const avatarEl = document.getElementById('sidebar-avatar');

  if (State.user) {
    if (nameEl) nameEl.textContent = State.user.full_name || State.user.email;
    if (roleEl) roleEl.textContent = State.user.role || 'preparer';
    if (avatarEl) {
      const initials = (State.user.full_name || 'U')
        .split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
      avatarEl.textContent = initials;
    }
  }
}

// ─── Date Helpers ───────────────────────────────────────────────────
function formatDate(dateStr) {
  if (!dateStr) return '—';
  try {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric'
    });
  } catch { return dateStr; }
}

function formatDateTime(dateStr) {
  if (!dateStr) return '—';
  try {
    return new Date(dateStr).toLocaleString('en-US', {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  } catch { return dateStr; }
}

function timeAgo(dateStr) {
  if (!dateStr) return '';
  const now = new Date();
  const then = new Date(dateStr);
  const diffMs = now - then;
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return formatDate(dateStr);
}

function daysUntil(dateStr) {
  if (!dateStr) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const due = new Date(dateStr);
  due.setHours(0, 0, 0, 0);
  return Math.round((due - today) / (1000 * 60 * 60 * 24));
}

// ─── Badge Helpers ──────────────────────────────────────────────────
function docStatusBadge(status) {
  const map = {
    awaiting: ['status-awaiting', 'Awaiting'],
    received: ['status-received', 'Received'],
    reviewed: ['status-reviewed', 'Reviewed'],
    not_applicable: ['status-na badge-gray', 'N/A'],
  };
  const [cls, label] = map[status] || ['badge-gray', status];
  return `<span class="badge ${cls}">${label}</span>`;
}

function deadlineStatusBadge(status) {
  const map = {
    upcoming: ['status-upcoming', 'Upcoming'],
    completed: ['status-completed', 'Completed'],
    missed: ['status-missed', 'Missed'],
    extended: ['status-extended', 'Extended'],
    in_progress: ['badge-blue', 'In Progress'],
  };
  const [cls, label] = map[status] || ['badge-gray', status];
  return `<span class="badge ${cls}">${label}</span>`;
}

function entityBadge(type) {
  const map = {
    individual: 'badge-blue',
    llc: 'badge-green',
    s_corp: 'badge-yellow',
    c_corp: 'badge-yellow',
    partnership: 'badge-gray',
    sole_proprietor: 'badge-gray',
    nonprofit: 'badge-green',
  };
  return `<span class="badge ${map[type] || 'badge-gray'}">${type.replace(/_/g, ' ').toUpperCase()}</span>`;
}

function completionBar(pct) {
  const level = pct >= 80 ? 'high' : pct >= 40 ? 'medium' : 'low';
  return `
    <div style="min-width:80px">
      <div style="display:flex;align-items:center;gap:6px">
        <div class="progress-bar-wrap" style="flex:1">
          <div class="progress-bar ${level}" style="width:${pct}%"></div>
        </div>
        <span class="text-sm text-muted">${pct.toFixed(0)}%</span>
      </div>
    </div>`;
}

// ─── SSE (Real-time messages) ───────────────────────────────────────
function connectSSE(clientId) {
  if (State.sseSource) {
    State.sseSource.close();
  }
  const url = `${API_BASE}/messages/client/${clientId}/stream`;
  const source = new EventSource(url + `?token=${State.token}`);
  State.sseSource = source;

  source.addEventListener('new_message', (e) => {
    const msg = JSON.parse(e.data);
    // Update unread badge if not on this client's page
    if (!window.location.pathname.includes(`/clients/${clientId}`)) {
      State.unreadCounts[clientId] = (State.unreadCounts[clientId] || 0) + 1;
      updateUnreadBadge();
    }
    // If message thread is open, append message
    const thread = document.getElementById('message-thread');
    if (thread && msg.sender_role === 'client') {
      appendMessageToThread(msg);
    }
  });

  source.addEventListener('heartbeat', () => {});
  source.onerror = () => {
    setTimeout(() => connectSSE(clientId), 5000);
  };
}

function updateUnreadBadge() {
  const total = Object.values(State.unreadCounts).reduce((a, b) => a + b, 0);
  const badge = document.getElementById('msg-badge');
  if (badge) {
    badge.textContent = total;
    badge.style.display = total > 0 ? 'inline-flex' : 'none';
  }
}

// ─── Message Thread Rendering ────────────────────────────────────────
function renderMessage(msg) {
  const isStaff = msg.sender_role === 'staff';
  const name = msg.sender_name || (isStaff ? 'Staff' : 'Client');
  return `
    <div class="message-wrap ${isStaff ? 'staff-wrap' : 'client-wrap'}"
         style="display:flex;flex-direction:column;align-items:${isStaff ? 'flex-end' : 'flex-start'}">
      <div class="message-bubble ${msg.sender_role}">${escapeHtml(msg.content)}</div>
      <div class="message-meta ${msg.sender_role}">${name} · ${timeAgo(msg.created_at)}</div>
    </div>`;
}

function appendMessageToThread(msg) {
  const thread = document.getElementById('message-thread');
  if (!thread) return;
  thread.insertAdjacentHTML('beforeend', renderMessage(msg));
  thread.scrollTop = thread.scrollHeight;
}

// ─── Document Checklist Rendering ───────────────────────────────────
function renderDocChecklist(docs, container) {
  if (!docs.length) {
    container.innerHTML = `<div class="empty-state">
      <div class="empty-state-icon">📋</div>
      <div class="empty-state-title">No documents tracked yet</div>
      <div class="empty-state-sub">Click "Initialize Checklist" to add standard documents</div>
    </div>`;
    return;
  }

  const statusOrder = { awaiting: 0, received: 1, reviewed: 2, not_applicable: 3 };
  docs.sort((a, b) => (statusOrder[a.status] || 0) - (statusOrder[b.status] || 0));

  container.innerHTML = `<ul class="doc-list">
    ${docs.map(doc => `
      <li class="doc-item" data-doc-id="${doc.id}">
        <div class="doc-icon ${getDocColor(doc.status)}">
          ${getDocIcon(doc.status)}
        </div>
        <div class="doc-name">${doc.doc_type}</div>
        <div class="doc-actions">
          ${docStatusBadge(doc.status)}
          <div class="doc-status-select" style="margin-left:8px">
            <select class="form-control" style="padding:4px 8px;font-size:12px;width:auto"
                    onchange="updateDocStatus(${doc.id}, this.value)">
              <option value="awaiting" ${doc.status==='awaiting'?'selected':''}>Awaiting</option>
              <option value="received" ${doc.status==='received'?'selected':''}>Received</option>
              <option value="reviewed" ${doc.status==='reviewed'?'selected':''}>Reviewed</option>
              <option value="not_applicable" ${doc.status==='not_applicable'?'selected':''}>N/A</option>
            </select>
          </div>
        </div>
      </li>`).join('')}
  </ul>`;
}

function getDocIcon(status) {
  return { awaiting: '⏳', received: '📄', reviewed: '✅', not_applicable: '—' }[status] || '📄';
}

function getDocColor(status) {
  return {
    awaiting: 'style="background:var(--yellow-light)"',
    received: 'style="background:var(--blue-light)"',
    reviewed: 'style="background:var(--green-light)"',
    not_applicable: 'style="background:#F1F5F9"',
  }[status] || '';
}

async function updateDocStatus(docId, status) {
  try {
    await API.updateDoc(docId, { status });
    showToast('Document status updated', 'success');
    // Refresh if on client detail page
    if (typeof refreshDocSection === 'function') refreshDocSection();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

// ─── AI Assistant Logic ──────────────────────────────────────────────
async function sendAIMessage(message, clientId = null) {
  const messagesEl = document.getElementById('ai-messages');
  if (!messagesEl) return;

  // Append user message
  messagesEl.insertAdjacentHTML('beforeend', `
    <div class="ai-message" style="flex-direction:row-reverse">
      <div class="ai-avatar user">${(State.user?.full_name || 'U')[0].toUpperCase()}</div>
      <div class="ai-bubble user">${escapeHtml(message)}</div>
    </div>`);

  // Loading indicator
  const loadingId = 'ai-loading-' + Date.now();
  messagesEl.insertAdjacentHTML('beforeend', `
    <div id="${loadingId}" class="ai-message">
      <div class="ai-avatar assistant">🤖</div>
      <div class="ai-loading">
        <div class="ai-loading-dot"></div>
        <div class="ai-loading-dot"></div>
        <div class="ai-loading-dot"></div>
      </div>
    </div>`);
  messagesEl.scrollTop = messagesEl.scrollHeight;

  try {
    State.conversationHistory.push({ role: 'user', content: message });
    const res = await API.chat(clientId, message, State.conversationHistory.slice(-8));

    // Remove loading
    document.getElementById(loadingId)?.remove();

    State.conversationHistory.push({ role: 'assistant', content: res.reply });

    messagesEl.insertAdjacentHTML('beforeend', `
      <div class="ai-message">
        <div class="ai-avatar assistant">🤖</div>
        <div class="ai-bubble assistant">${escapeHtml(res.reply)}</div>
      </div>`);

    // Show suggested actions
    if (res.suggested_actions?.length) {
      const actionsHtml = res.suggested_actions.map(a =>
        `<button class="prompt-chip" onclick="handleSuggestedAction('${escapeHtml(a)}')">${a}</button>`
      ).join('');
      messagesEl.insertAdjacentHTML('beforeend', `
        <div style="padding:4px 0;display:flex;flex-wrap:wrap;gap:6px">${actionsHtml}</div>`);
    }

    messagesEl.scrollTop = messagesEl.scrollHeight;
  } catch (e) {
    document.getElementById(loadingId)?.remove();
    messagesEl.insertAdjacentHTML('beforeend', `
      <div class="ai-message">
        <div class="ai-avatar assistant">🤖</div>
        <div class="ai-bubble assistant" style="border-color:var(--red);color:var(--red-text)">
          ${e.message === 'AI assistant not configured. Set OPENAI_API_KEY or DEEPSEEK_API_KEY in .env'
            ? '⚠️ AI not configured. Add your OpenAI or DeepSeek API key to .env to enable the assistant.'
            : `Error: ${escapeHtml(e.message)}`}
        </div>
      </div>`);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }
}

function handleSuggestedAction(action) {
  const input = document.getElementById('ai-input');
  if (input) {
    input.value = action;
    input.focus();
  }
}

// ─── Security ───────────────────────────────────────────────────────
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// ─── Entity Type Label ───────────────────────────────────────────────
function entityLabel(type) {
  const map = {
    individual: 'Individual',
    llc: 'LLC',
    s_corp: 'S-Corp',
    c_corp: 'C-Corp',
    partnership: 'Partnership',
    sole_proprietor: 'Sole Proprietor',
    nonprofit: 'Nonprofit',
  };
  return map[type] || type;
}

// ─── Deadline urgency color ──────────────────────────────────────────
function deadlineUrgencyClass(days) {
  if (days === null || days === undefined) return '';
  if (days < 0) return 'badge-red';
  if (days <= 7) return 'badge-red';
  if (days <= 30) return 'badge-yellow';
  return 'badge-blue';
}

// ─── Init ────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Auth guard (skip for login and portal pages)
  const publicPages = ['/login', '/portal'];
  const isPublic = publicPages.some(p => window.location.pathname.startsWith(p));

  if (!isPublic && !isAuthenticated()) {
    window.location.href = '/login';
    return;
  }

  setActiveNav();
  renderSidebarUser();
  setupModalClose();

  // Logout button
  document.getElementById('btn-logout')?.addEventListener('click', logout);

  // Page-specific init
  if (typeof initPage === 'function') {
    initPage();
  }
});
