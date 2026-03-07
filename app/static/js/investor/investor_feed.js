/* ================================================================
   EISC Platform — Investor Feed JS
   ================================================================ */

(function () {
    'use strict';

    // ── Toast ──────────────────────────────────────────────────
    const toastContainer = document.getElementById('toastContainer');

    function showToast(msg, type = 'default') {
        const t = document.createElement('div');
        t.className = `toast ${type}`;

        const icon = {
            success: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`,
            error:   `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
            default: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`
        }[type] || '';

        t.innerHTML = `${icon}<span>${msg}</span>`;
        if(toastContainer) toastContainer.appendChild(t);

        setTimeout(() => {
            t.classList.add('removing');
            t.addEventListener('animationend', () => t.remove());
        }, 3000);
    }

    // ── Modal helpers ──────────────────────────────────────────
    function openModal(overlayId) {
        const el = document.getElementById(overlayId);
        if (el) el.classList.add('open');
    }
    function closeModal(overlayId) {
        const el = document.getElementById(overlayId);
        if (el) el.classList.remove('open');
    }

    // Close modal on overlay backdrop click
    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeModal(overlay.id);
        });
    });

    // Close buttons
    document.querySelectorAll('[data-close-modal]').forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.dataset.closeModal;
            closeModal(target);
        });
    });

    // ── Create Post ───────────────────────────────────────────
    const createInput = document.getElementById('createPostInput');
    if (createInput) {
        createInput.addEventListener('click', () => openModal('createPostModal'));
    }

    // Action buttons in create box also open modal
    document.querySelectorAll('.create-action-btn[data-open-modal]').forEach(btn => {
        btn.addEventListener('click', () => openModal('createPostModal'));
    });

    const createPostForm = document.getElementById('createPostForm');
    if (createPostForm) {
        createPostForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = createPostForm.querySelector('.btn-submit');
            btn.disabled = true;
            btn.textContent = 'Posting…';

            const payload = {
                title:            document.getElementById('cp_title').value.trim(),
                description:      document.getElementById('cp_description').value.trim(),
                industry_tag:     document.getElementById('cp_industry').value.trim(),
                pitch_deck_url:   '',
                video_url:        ''
            };

            if (!payload.title || !payload.description) {
                showToast('Title and description are required.', 'error');
                btn.disabled = false;
                btn.textContent = 'Post';
                return;
            }

            try {
                const res = await fetch('/api/posts/create', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (data.success) {
                    showToast('Post created successfully!', 'success');
                    closeModal('createPostModal');
                    createPostForm.reset();
                    // Prepend a new card to feed (optimistic)
                    prependPostToFeed(payload);
                } else {
                    showToast(data.message || 'Failed to post.', 'error');
                }
            } catch (err) {
                showToast('Network error. Please try again.', 'error');
            } finally {
                btn.disabled = false;
                btn.textContent = 'Post';
            }
        });
    }

    function prependPostToFeed(post) {
        const feed = document.getElementById('pitchFeed');
        if (!feed) return;

        const username = document.querySelector('.topbar-avatar')?.title || 'You';
        const initials = username.charAt(0).toUpperCase();

        const html = `
            <div class="card pitch-card new-card" style="animation: fadeInDown 0.4s ease;">
                <div class="pitch-header">
                    <div class="pitch-avatar">${initials}</div>
                    <div class="pitch-author">
                        <div class="pitch-author-name">${escHtml(username)}</div>
                        <div class="pitch-author-meta">
                            <span>just now</span>
                        </div>
                    </div>
                </div>
                <div class="pitch-tags">
                    ${post.industry_tag ? `<span class="pitch-tag tag-industry">${escHtml(post.industry_tag)}</span>` : ''}
                </div>
                <div class="pitch-title">${escHtml(post.title)}</div>
                <div class="pitch-desc clamped">${escHtml(post.description)}</div>
                <div class="pitch-stats-row">
                    <span class="pitch-stat"><strong>0</strong> interested</span>
                    <span class="pitch-stat"><strong>0</strong> saves</span>
                    <span class="pitch-stat"><strong>0</strong> comments</span>
                </div>
                <div class="pitch-actions">
                    ${actionBtns()}
                </div>
            </div>`;

        feed.insertAdjacentHTML('afterbegin', html);
        bindPostActions(feed.firstElementChild);
    }

    function actionBtns() {
        return `
            <button class="pitch-action-btn" data-action="interested">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                Interested
            </button>
            <button class="pitch-action-btn" data-action="view">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                View Details
            </button>
            <button class="pitch-action-btn" data-action="save">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>
                Save
            </button>
            <button class="pitch-action-btn" data-action="comment">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                Comment
            </button>`;
    }

    // ── Post Action Buttons (Interested, Save, etc.) ──────────
    function bindPostActions(card) {
        const postId = card.dataset.postId;
        card.querySelectorAll('.pitch-action-btn').forEach(btn => {
            btn.addEventListener('click', () => handlePostAction(btn, postId));
        });
    }

    function handlePostAction(btn, postId) {
        const action = btn.dataset.action;

        if (action === 'comment') {
            showToast('Comment feature coming soon!', 'default');
            return;
        }
        if (action === 'view') {
            showToast('Full pitch view coming soon!', 'default');
            return;
        }

        if (!postId) {
            // Optimistic toggle
            btn.classList.toggle('active');
            return;
        }

        btn.disabled = true;
        fetch(`/api/posts/${postId}/interact`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: action })
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) btn.classList.add('active');
        })
        .catch(() => showToast('Action failed.', 'error'))
        .finally(() => { btn.disabled = false; });
    }

    // Bind existing feed cards
    document.querySelectorAll('.pitch-card[data-post-id]').forEach(card => {
        bindPostActions(card);
    });

    // ── Inject fadeInDown animation ──────────────────────────
    const style = document.createElement('style');
    style.textContent = `
        @keyframes fadeInDown {
            from { opacity: 0; transform: translateY(-16px); }
            to   { opacity: 1; transform: translateY(0); }
        }
    `;
    document.head.appendChild(style);

    // ── Helper: escape HTML ───────────────────────────────────
    function escHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    console.log('🚀 EISC Investor Feed JS initialized');
})();
