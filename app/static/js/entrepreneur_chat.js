// ═══════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════
let currentMode       = 'guidance';
let currentSessionId  = null;
let currentInvestorEmail = null;
let currentInvestorName  = null;
let isLoading         = false;
let sidebarTab        = 'guidance';

// ═══════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
    loadSessions('guidance');
    document.addEventListener('click', (e) => {
        if (!e.target.closest('#plus-btn') && !e.target.closest('#mode-popup')) {
            closeModePopup();
        }
    });
});

// ═══════════════════════════════════════════════
// SIDEBAR TABS
// ═══════════════════════════════════════════════
function switchSidebarTab(mode) {
    sidebarTab = mode;
    document.getElementById('tab-guidance').classList.toggle('active', mode === 'guidance');
    document.getElementById('tab-intermediary').classList.toggle('active', mode === 'intermediary');
    loadSessions(mode);
}

async function loadSessions(mode) {
    try {
        const res  = await fetch(`/api/chat/sessions?mode=${mode}`);
        const data = await res.json();
        renderSessions(data.sessions || []);
    } catch {
        renderSessions([]);
    }
}

function renderSessions(sessions) {
    const el = document.getElementById('session-list');
    if (!sessions.length) {
        el.innerHTML = '<div class="sessions-empty">No conversations yet.<br>Start a new chat ↗</div>';
        return;
    }
    el.innerHTML = sessions.map(s => `
        <div class="session-item ${s.session_id === currentSessionId ? 'active' : ''}"
             onclick="loadSession('${s.session_id}', '${s.mode}', '${s.investor_email || ''}')">
            <div class="session-title">${escHtml(s.title || 'Chat')}</div>
            <div class="session-preview">${escHtml((s.last_message || '').substring(0, 55))}${(s.last_message||'').length>55?'…':''}</div>
            <button class="session-delete" onclick="deleteSession(event,'${s.session_id}')">✕</button>
        </div>
    `).join('');
}

// ═══════════════════════════════════════════════
// LOAD EXISTING SESSION
// ═══════════════════════════════════════════════
async function loadSession(sessionId, mode, investorEmail) {
    currentSessionId     = sessionId;
    currentMode          = mode;
    currentInvestorEmail = investorEmail || null;

    updateModeUI();
    clearMessages();
    document.getElementById('welcome-state').style.display = 'none';

    // Mark active in sidebar
    document.querySelectorAll('.session-item').forEach(el => el.classList.remove('active'));
    event?.currentTarget?.classList.add('active');

    try {
        const res  = await fetch(`/api/chat/history?session_id=${sessionId}&mode=${mode}`);
        const data = await res.json();
        (data.messages || []).forEach(m => appendBubble(m.role, m.content));
        scrollBottom();
    } catch {
        showToast('Failed to load conversation.', 'error');
    }
}

// ═══════════════════════════════════════════════
// NEW CHAT
// ═══════════════════════════════════════════════
function startNewChat() {
    currentSessionId     = null;
    currentInvestorEmail = null;
    clearMessages();
    document.getElementById('welcome-state').style.display = 'flex';
    updateQuickPrompts();
    document.querySelectorAll('.session-item').forEach(el => el.classList.remove('active'));
}

// ═══════════════════════════════════════════════
// MODE & INVESTOR SELECTION
// ═══════════════════════════════════════════════
function toggleModePopup(e) {
    e.stopPropagation();
    document.getElementById('mode-popup').classList.toggle('show');
}
function closeModePopup() {
    document.getElementById('mode-popup').classList.remove('show');
}

function selectMode(mode) {
    currentMode          = mode;
    currentInvestorEmail = null;
    currentInvestorName  = null;

    document.getElementById('opt-guidance').classList.toggle('active-mode', mode === 'guidance');
    document.querySelectorAll('.investor-option').forEach(el => el.classList.remove('selected'));

    updateModeUI();
    closeModePopup();
    startNewChat();
}

function selectInvestor(email, name, el) {
    currentMode          = 'intermediary';
    currentInvestorEmail = email;
    currentInvestorName  = name;

    document.getElementById('opt-guidance').classList.remove('active-mode');
    document.querySelectorAll('.investor-option').forEach(e => e.classList.remove('selected'));
    el.classList.add('selected');

    updateModeUI();
    closeModePopup();
    startNewChat();
}

function updateModeUI() {
    const badgeText = document.getElementById('mode-badge-text');
    const topTitle  = document.getElementById('topbar-title');
    const textarea  = document.getElementById('chat-textarea');
    const badge     = document.getElementById('mode-badge');

    if (currentMode === 'guidance') {
        badgeText.textContent = 'Guidance Mode';
        topTitle.textContent  = 'AI Startup Advisor';
        textarea.placeholder  = 'Ask your AI advisor anything…';
        badge.style.background = '#6c63ff22';
        badge.style.borderColor = '#6c63ff44';
        badge.querySelector('.dot').style.background = '#6c63ff';
    } else {
        const name = currentInvestorName || 'Investor';
        badgeText.textContent = 'Investor Mode';
        topTitle.textContent  = `Talking about: ${name}`;
        textarea.placeholder  = `Ask how to approach ${name}…`;
        badge.style.background = '#0ea5e922';
        badge.style.borderColor = '#0ea5e944';
        badge.querySelector('.dot').style.background = '#0ea5e9';
    }
    updateQuickPrompts();
}

function updateQuickPrompts() {
    const qp = document.getElementById('quick-prompts');
    if (!qp) return;
    if (currentMode === 'guidance') {
        qp.innerHTML = `
            <button class="quick-chip" onclick="useQuickPrompt(this)">Review my pitch deck</button>
            <button class="quick-chip" onclick="useQuickPrompt(this)">What investors should I target?</button>
            <button class="quick-chip" onclick="useQuickPrompt(this)">How do I improve my traction story?</button>
            <button class="quick-chip" onclick="useQuickPrompt(this)">Prepare me for due diligence</button>
            <button class="quick-chip" onclick="useQuickPrompt(this)">What's a realistic valuation for my stage?</button>
        `;
    } else {
        const name = currentInvestorName || 'this investor';
        qp.innerHTML = `
            <button class="quick-chip" onclick="useQuickPrompt(this)">Are we a good fit for ${name}?</button>
            <button class="quick-chip" onclick="useQuickPrompt(this)">What will ${name} likely ask me?</button>
            <button class="quick-chip" onclick="useQuickPrompt(this)">How should I open the conversation?</button>
            <button class="quick-chip" onclick="useQuickPrompt(this)">What are our alignment gaps?</button>
        `;
    }
}

function useQuickPrompt(btn) {
    const ta = document.getElementById('chat-textarea');
    ta.value = btn.textContent.trim();
    autoResize(ta);
    ta.focus();
}

// ═══════════════════════════════════════════════
// SEND MESSAGE
// ═══════════════════════════════════════════════
async function sendMessage() {
    if (isLoading) return;
    const ta  = document.getElementById('chat-textarea');
    const msg = ta.value.trim();
    if (!msg) return;

    if (currentMode === 'intermediary' && !currentInvestorEmail) {
        showToast('Please select an investor first using the + button.', 'warning');
        return;
    }

    // Hide welcome
    document.getElementById('welcome-state').style.display = 'none';

    ta.value = '';
    autoResize(ta);

    appendBubble('user', msg);
    showTyping();
    setLoading(true);

    try {
        const res  = await fetch('/api/chat/send', {
            method : 'POST',
            headers: { 'Content-Type': 'application/json' },
            body   : JSON.stringify({
                mode           : currentMode,
                message        : msg,
                session_id     : currentSessionId || '',
                investor_email : currentInvestorEmail || '',
            }),
        });
        const data = await res.json();

        hideTyping();
        setLoading(false);

        if (data.success) {
            if (!currentSessionId) {
                currentSessionId = data.session_id;
                loadSessions(currentMode);
            }
            appendBubble('assistant', data.reply);
            scrollBottom();
        } else {
            showToast(data.message || 'AI error. Please retry.', 'error');
        }
    } catch {
        hideTyping();
        setLoading(false);
        showToast('Network error. Please check your connection.', 'error');
    }
}

function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
}

// ═══════════════════════════════════════════════
// DELETE SESSION
// ═══════════════════════════════════════════════
async function deleteSession(e, sessionId) {
    e.stopPropagation();
    if (!confirm('Delete this conversation?')) return;

    await fetch('/api/chat/session/delete', {
        method : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body   : JSON.stringify({ session_id: sessionId }),
    });

    if (currentSessionId === sessionId) startNewChat();
    loadSessions(sidebarTab);
}

// ═══════════════════════════════════════════════
// DOM HELPERS
// ═══════════════════════════════════════════════
let typingEl = null;

function appendBubble(role, content) {
    const area = document.getElementById('messages-area');
    const isAI = (role === 'assistant' || role === 'model');

    const avatarHtml = isAI
        ? `<div class="msg-avatar ai-avatar">🤖</div>`
        : `<div class="msg-avatar user-avatar">${
              PROFILE_IMAGE
                ? `<img src="${PROFILE_IMAGE}" alt="">`
                : `<span style="color:#a89cff;font-size:14px;font-weight:700;">${USERNAME.charAt(0).toUpperCase()}</span>`
          }</div>`;

    const div = document.createElement('div');
    div.className = `msg-row ${isAI ? 'ai' : 'user'}`;
    div.innerHTML = `
        ${avatarHtml}
        <div class="msg-bubble">${renderMarkdown(content)}</div>
    `;
    area.appendChild(div);
    scrollBottom();
}

function showTyping() {
    const area = document.getElementById('messages-area');
    typingEl = document.createElement('div');
    typingEl.className = 'typing-indicator';
    typingEl.innerHTML = `
        <div class="msg-avatar ai-avatar">🤖</div>
        <div class="typing-dots"><span></span><span></span><span></span></div>
    `;
    area.appendChild(typingEl);
    scrollBottom();
}

function hideTyping() {
    if (typingEl) { typingEl.remove(); typingEl = null; }
}

function clearMessages() {
    const area = document.getElementById('messages-area');
    // Remove everything except welcome-state
    [...area.children].forEach(el => {
        if (el.id !== 'welcome-state') el.remove();
    });
}

function scrollBottom() {
    const area = document.getElementById('messages-area');
    area.scrollTop = area.scrollHeight;
}

function setLoading(val) {
    isLoading = val;
    document.getElementById('send-btn').disabled = val;
}

function autoResize(ta) {
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 160) + 'px';
}

// ═══════════════════════════════════════════════
// LIGHTWEIGHT MARKDOWN RENDERER
// ═══════════════════════════════════════════════
function renderMarkdown(text) {
    return text
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        // Bold **text**
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        // Italic *text*
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        // Headers ### ## #
        .replace(/^### (.+)$/gm, '<strong style="font-size:14px;color:#e2e8f0;">$1</strong>')
        .replace(/^## (.+)$/gm, '<strong style="font-size:15px;color:#e2e8f0;">$1</strong>')
        .replace(/^# (.+)$/gm, '<strong style="font-size:16px;color:#e2e8f0;">$1</strong>')
        // Bullet points
        .replace(/^[\-\*] (.+)$/gm, '<li>$1</li>')
        .replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>')
        // Numbered lists
        .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
        // Line breaks → <br> (keep double newlines as paragraph breaks)
        .replace(/\n\n/g, '</p><p style="margin:0 0 8px;">')
        .replace(/\n/g, '<br>')
        // Wrap in paragraph
        .replace(/^(.+)$/, '<p style="margin:0;">$1</p>');
}

function escHtml(str) {
    return String(str)
        .replace(/&/g,'&amp;').replace(/</g,'&lt;')
        .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ═══════════════════════════════════════════════
// EXPOSE TO GLOBAL SCOPE
// Required because base.html loads scripts with defer,
// making functions unavailable to inline onclick handlers.
// ═══════════════════════════════════════════════
window.startNewChat       = startNewChat;
window.switchSidebarTab   = switchSidebarTab;
window.loadSession        = loadSession;
window.deleteSession      = deleteSession;
window.toggleModePopup    = toggleModePopup;
window.selectMode         = selectMode;
window.selectInvestor     = selectInvestor;
window.useQuickPrompt     = useQuickPrompt;
window.sendMessage        = sendMessage;
window.handleKey          = handleKey;
window.autoResize         = autoResize;
window.showToast          = showToast;