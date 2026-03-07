/* ================================================================
   EISC — Investor AI Chat JS
   Mirrors entrepreneur_chat.js with:
     • Guidance mode  → AI gets investor profile context only
     • Entrepreneur mode → select from connected founders → AI gets
       BOTH investor + entrepreneur (with pitch) context
   ================================================================ */
(function () {
    'use strict';

    // ── State ─────────────────────────────────────────────────────
    let currentMode         = 'guidance';
    let currentSessionId    = null;
    let currentSidebarTab   = 'guidance';
    let selectedEntrepreneur = null; // { email, name, startup_name, image_url }
    let isLoading           = false;

    // ── DOM refs ──────────────────────────────────────────────────
    const messagesArea  = () => document.getElementById('messages-area');
    const textarea      = () => document.getElementById('chat-textarea');
    const sendBtn       = () => document.getElementById('send-btn');
    const welcomeState  = () => document.getElementById('welcome-state');
    const sessionList   = () => document.getElementById('session-list');
    const modeBadge     = () => document.getElementById('mode-badge');
    const modeBadgeText = () => document.getElementById('mode-badge-text');
    const topbarTitle   = () => document.getElementById('topbar-title');
    const stripEl       = () => document.getElementById('selected-entrepreneur-strip');

    // ── Init ──────────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', () => {
        // Check if redirected from interest button with startup_email param
        const urlParams = new URLSearchParams(window.location.search);
        const startupEmail = urlParams.get('startup_email');
        
        if (startupEmail) {
            // Auto-select the startup from the parameter
            autoSelectStartupFromEmail(startupEmail);
        } else {
            loadSessions('guidance');
        }
        
        document.addEventListener('click', handleOutsideClick);
    });
    
    // Auto-select startup from email (when coming from interest button)
    function autoSelectStartupFromEmail(entrepreneurEmail) {
        // Find the entrepreneur button from saved_startups list
        let found = false;
        document.querySelectorAll('.entrepreneur-option').forEach(btn => {
            const btnEmail = btn.getAttribute('data-email');
            if (btnEmail === entrepreneurEmail) {
                // Click this button to select it
                btn.click();
                found = true;
            }
        });
        
        if (!found) {
            // Startup might not be in visible list yet, retry after short delay
            setTimeout(() => {
                document.querySelectorAll('.entrepreneur-option').forEach(btn => {
                    const btnEmail = btn.getAttribute('data-email');
                    if (btnEmail === entrepreneurEmail) {
                        btn.click();
                    }
                });
            }, 300);
        }
    }

    // ── Mode popup toggle ─────────────────────────────────────────
    window.toggleModePopup = function (e) {
        e.stopPropagation();
        const popup   = document.getElementById('mode-popup');
        const plusBtn = document.getElementById('plus-btn');
        const visible = popup.classList.toggle('visible');
        plusBtn.classList.toggle('active', visible);
    };

    function handleOutsideClick(e) {
        const popup   = document.getElementById('mode-popup');
        const plusBtn = document.getElementById('plus-btn');
        if (!popup?.contains(e.target) && e.target !== plusBtn) {
            popup?.classList.remove('visible');
            plusBtn?.classList.remove('active');
        }
    }

    // ── Select mode (guidance) ────────────────────────────────────
    window.selectMode = function (mode) {
        currentMode         = mode;
        selectedEntrepreneur = null;
        currentSessionId    = null;

        // Update popup buttons
        document.getElementById('opt-guidance')?.classList.toggle('active-mode', mode === 'guidance');

        // Deselect all entrepreneur options
        document.querySelectorAll('.entrepreneur-option').forEach(b => b.classList.remove('selected'));

        // Update strip
        renderSelectedStrip();
        updateModeBadge();
        clearMessages();

        // Close popup
        document.getElementById('mode-popup')?.classList.remove('visible');
        document.getElementById('plus-btn')?.classList.remove('active');
    };

    // ── Select entrepreneur ────────────────────────────────────────
    window.selectEntrepreneur = function (email, name, startupName, imageUrl, btnEl) {
        currentMode       = 'entrepreneur';
        selectedEntrepreneur = { email, name, startup_name: startupName, image_url: imageUrl };
        currentSessionId  = null;

        // Reset guidance highlight, highlight this entrepreneur
        document.getElementById('opt-guidance')?.classList.remove('active-mode');
        document.querySelectorAll('.entrepreneur-option').forEach(b => b.classList.remove('selected'));
        btnEl?.classList.add('selected');

        renderSelectedStrip();
        updateModeBadge();
        clearMessages();

        // Close popup
        document.getElementById('mode-popup')?.classList.remove('visible');
        document.getElementById('plus-btn')?.classList.remove('active');

        showToast(`Switched to Startup mode: ${name}`, 'success');
    };

    window.clearSelectedEntrepreneur = function () {
        selectMode('guidance');
    };

    // ── Render selected entrepreneur strip ─────────────────────────
    function renderSelectedStrip() {
        const strip = stripEl();
        if (!strip) return;
        if (!selectedEntrepreneur) {
            strip.style.display = 'none';
            strip.innerHTML = '';
            return;
        }
        const avatarHtml = selectedEntrepreneur.image_url
            ? `<img src="${esc(selectedEntrepreneur.image_url)}" alt="">`
            : selectedEntrepreneur.name[0].toUpperCase();

        strip.style.display = 'flex';
        strip.innerHTML = `
            <div class="strip-avatar">${avatarHtml}</div>
            <span>Startup Mode:</span>
            <strong>${esc(selectedEntrepreneur.startup_name || selectedEntrepreneur.name)}</strong>
            <span style="font-size:0.7rem;color:#b45309;font-weight:500">
                – ${esc(selectedEntrepreneur.name)}
            </span>
            <button class="strip-remove" onclick="clearSelectedEntrepreneur()" title="Switch to Guidance">✕</button>`;
    }

    // ── Update top mode badge ──────────────────────────────────────
    function updateModeBadge() {
        const badge = modeBadge();
        const text  = modeBadgeText();
        const title = topbarTitle();
        if (!badge || !text) return;

        if (currentMode === 'guidance') {
            badge.className = 'chat-mode-badge';
            text.textContent = 'Guidance Mode';
            if (title) title.textContent = 'AI Investment Advisor';
        } else {
            badge.className = 'chat-mode-badge mode-entrepreneur';
            const label = selectedEntrepreneur?.startup_name || selectedEntrepreneur?.name || 'Startup';
            text.textContent = `Startup: ${label}`;
            if (title) title.textContent = 'Startup Analysis Mode';
        }
    }

    // ── Sidebar tab switching ──────────────────────────────────────
    window.switchSidebarTab = function (tab) {
        currentSidebarTab = tab;
        document.getElementById('tab-guidance')?.classList.toggle('active', tab === 'guidance');
        document.getElementById('tab-entrepreneur')?.classList.toggle('active', tab === 'entrepreneur');
        loadSessions(tab);
    };

    // ── Load session list ──────────────────────────────────────────
    async function loadSessions(mode) {
        try {
            const res  = await fetch(`/api/investor/chat/sessions?mode=${mode}`);
            const data = await res.json();
            const list = sessionList();
            if (!list) return;

            if (!data.success || !data.sessions?.length) {
                list.innerHTML = '<div class="sessions-empty">Start a new chat ↗</div>';
                return;
            }

            list.innerHTML = data.sessions.map(s => {
                const pillClass = s.mode === 'guidance' ? 'pill-guidance' : 'pill-entrepreneur';
                const pillLabel = s.mode === 'guidance' ? '🧠 Guidance' : '🚀 Startup';
                const preview   = s.last_message
                    ? esc(s.last_message.substring(0, 50)) + (s.last_message.length > 50 ? '…' : '')
                    : 'No messages yet';
                const timeStr   = s.updated_at ? relTime(s.updated_at) : '';
                const activeClass = s.session_id === currentSessionId ? 'active' : '';

                return `<div class="session-item ${activeClass}" onclick="loadSession('${s.session_id}','${s.mode}','${esc(s.entrepreneur_email||'')}')">
                    <div class="session-title">${esc(s.title || 'Chat')}</div>
                    <div class="session-preview">${preview}</div>
                    <div class="session-meta">
                        <span class="session-mode-pill ${pillClass}">${pillLabel}</span>
                        <span class="session-time">${timeStr}</span>
                        <button class="session-delete-btn" onclick="deleteSession(event,'${s.session_id}')">🗑</button>
                    </div>
                </div>`;
            }).join('');

        } catch (err) {
            console.error('loadSessions error:', err);
        }
    }

    // ── Load existing session ──────────────────────────────────────
    window.loadSession = async function (sessionId, mode, entrepreneurEmail) {
        currentSessionId = sessionId;
        currentMode      = mode;

        if (mode === 'entrepreneur' && entrepreneurEmail) {
            selectedEntrepreneur = { email: entrepreneurEmail, name: entrepreneurEmail, startup_name: '' };
        } else {
            selectedEntrepreneur = null;
        }

        renderSelectedStrip();
        updateModeBadge();
        clearMessages(false);

        try {
            const res  = await fetch(`/api/investor/chat/history?session_id=${sessionId}&mode=${mode}`);
            const data = await res.json();
            if (!data.success) return;

            // Hide welcome
            welcomeState()?.style.setProperty('display', 'none');

            data.messages.forEach(m => appendMessage(m.role, m.content, false));
            scrollBottom();

            // Highlight active
            document.querySelectorAll('.session-item').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.session-item').forEach(el => {
                if (el.getAttribute('onclick')?.includes(sessionId)) el.classList.add('active');
            });
        } catch (err) {
            console.error('loadSession error:', err);
        }
    };

    // ── Start new chat ─────────────────────────────────────────────
    window.startNewChat = function () {
        currentSessionId    = null;
        selectedEntrepreneur = null;
        currentMode         = 'guidance';

        document.getElementById('opt-guidance')?.classList.add('active-mode');
        document.querySelectorAll('.entrepreneur-option').forEach(b => b.classList.remove('selected'));

        renderSelectedStrip();
        updateModeBadge();
        clearMessages();
        textarea()?.focus();
    };

    // ── Quick prompt chips ─────────────────────────────────────────
    window.useQuickPrompt = function (btn) {
        const ta = textarea();
        if (!ta) return;
        ta.value = btn.textContent.trim();
        autoResize(ta);
        ta.focus();
    };

    // ── Send message ───────────────────────────────────────────────
    window.sendMessage = async function () {
        const ta  = textarea();
        const msg = ta?.value.trim();
        if (!msg || isLoading) return;

        // Validate entrepreneur mode requires selection
        if (currentMode === 'entrepreneur' && !selectedEntrepreneur?.email) {
            showToast('Please select a startup founder first (click ＋).', 'error');
            return;
        }

        isLoading = true;
        ta.value  = '';
        autoResize(ta);
        sendBtn()?.setAttribute('disabled', 'true');

        // Hide welcome, show user message
        welcomeState()?.style.setProperty('display', 'none');
        appendMessage('user', msg, true);
        showTyping();
        scrollBottom();

        try {
            const res  = await fetch('/api/investor/chat/send', {
                method : 'POST',
                headers: { 'Content-Type': 'application/json' },
                body   : JSON.stringify({
                    mode               : currentMode,
                    message            : msg,
                    session_id         : currentSessionId || '',
                    entrepreneur_email : selectedEntrepreneur?.email || '',
                }),
            });
            const data = await res.json();

            removeTyping();

            if (data.success) {
                currentSessionId = data.session_id;
                appendMessage('assistant', data.reply, true);
                loadSessions(currentSidebarTab);
            } else {
                appendMessage('assistant', `⚠️ ${data.message || 'Something went wrong.'}`, true);
                showToast(data.message || 'AI error', 'error');
            }
        } catch (err) {
            removeTyping();
            appendMessage('assistant', '⚠️ Network error. Please try again.', true);
        } finally {
            isLoading = false;
            sendBtn()?.removeAttribute('disabled');
            scrollBottom();
            ta.focus();
        }
    };

    // ── Keyboard handler ───────────────────────────────────────────
    window.handleKey = function (e) {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    };

    // ── Auto-resize textarea ───────────────────────────────────────
    window.autoResize = function (el) {
        el.style.height = 'auto';
        el.style.height = Math.min(el.scrollHeight, 120) + 'px';
    };

    // ── Delete session ─────────────────────────────────────────────
    window.deleteSession = async function (e, sessionId) {
        e.stopPropagation();
        if (!confirm('Delete this chat?')) return;
        try {
            await fetch('/api/investor/chat/session/delete', {
                method : 'POST',
                headers: { 'Content-Type': 'application/json' },
                body   : JSON.stringify({ session_id: sessionId }),
            });
            if (currentSessionId === sessionId) {
                currentSessionId = null;
                clearMessages();
            }
            loadSessions(currentSidebarTab);
        } catch {
            showToast('Delete failed.', 'error');
        }
    };

    // ── Append message bubble ──────────────────────────────────────
    function appendMessage(role, content, animate) {
        const area     = messagesArea();
        if (!area) return;
        const isUser   = role === 'user';
        const now      = new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});

        const avatarHtml = isUser
            ? (INV_PROFILE_IMAGE
                ? `<img src="${esc(INV_PROFILE_IMAGE)}" alt="">`
                : esc(INV_USERNAME[0]?.toUpperCase() || 'I'))
            : '🤖';

        const row = document.createElement('div');
        row.className = `msg-row ${role}`;
        if (animate) row.style.animation = 'fadeUp 0.25s ease';

        row.innerHTML = `
            <div class="msg-avatar ${isUser ? 'user-av' : 'ai-av'}">${avatarHtml}</div>
            <div>
                <div class="msg-bubble">${renderMarkdown(content)}</div>
                <div class="msg-time">${now}</div>
            </div>`;
        area.appendChild(row);
    }

    function showTyping() {
        const area = messagesArea();
        if (!area) return;
        const el = document.createElement('div');
        el.className = 'typing-indicator';
        el.id        = 'typing-indicator';
        el.innerHTML = `<div class="msg-avatar ai-av">🤖</div>
            <div class="typing-dots">
                <span></span><span></span><span></span>
            </div>`;
        area.appendChild(el);
    }

    function removeTyping() {
        document.getElementById('typing-indicator')?.remove();
    }

    function clearMessages(showWelcome = true) {
        const area = messagesArea();
        if (!area) return;
        // Remove everything except welcome-state
        Array.from(area.children).forEach(child => {
            if (child.id !== 'welcome-state') child.remove();
        });
        const ws = welcomeState();
        if (ws) ws.style.display = showWelcome ? '' : 'none';
    }

    function scrollBottom() {
        const area = messagesArea();
        if (area) area.scrollTop = area.scrollHeight;
    }

    // ── Simple markdown renderer ───────────────────────────────────
    function renderMarkdown(text) {
        return text
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/^#{1,3} (.+)$/gm, '<strong>$1</strong>')
            .replace(/^[-•] (.+)$/gm, '• $1')
            .replace(/\n/g, '<br>');
    }

    // ── Relative time ──────────────────────────────────────────────
    function relTime(str) {
        try {
            const diff = Math.floor((Date.now() - new Date(str)) / 1000);
            if (diff < 60)     return 'just now';
            if (diff < 3600)   return `${Math.floor(diff/60)}m ago`;
            if (diff < 86400)  return `${Math.floor(diff/3600)}h ago`;
            return `${Math.floor(diff/86400)}d ago`;
        } catch { return ''; }
    }

    function esc(s) {
        return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
    }

    console.log('✅ investor_chat.js loaded');
})();