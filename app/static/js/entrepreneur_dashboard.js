// --- AI Startup Summary Toggle Logic ---
window.showInvestorList = async function() {
    const btn = document.getElementById('btn-investors');
    if (btn) btn.classList.add('active');
    const b2 = document.getElementById('btn-entrepreneurs');
    if (b2) b2.classList.remove('active');
    
    const c1 = document.getElementById('investor-list-container');
    if (c1) c1.style.display = '';
    const c2 = document.getElementById('entrepreneur-list-container');
    if (c2) c2.style.display = 'none';

    try {
        const res = await fetch('/api/dashboard/all_investors');
        const data = await res.json();
        if (data.success) renderInvestorList(data.investors);
        window._allInvestorsLoaded = true;
    } catch(e) { console.warn("Failed to load investors", e); }
};

window.showEntrepreneurList = async function() {
    const b1 = document.getElementById('btn-investors');
    if (b1) b1.classList.remove('active');
    const b2 = document.getElementById('btn-entrepreneurs');
    if (b2) b2.classList.add('active');

    const c1 = document.getElementById('investor-list-container');
    if (c1) c1.style.display = 'none';
    const c2 = document.getElementById('entrepreneur-list-container');
    if (c2) c2.style.display = '';

    try {
        const res = await fetch('/api/dashboard/all_entrepreneurs');
        const data = await res.json();
        if (data.success) renderEntrepreneurList(data.entrepreneurs);
        window._allEntrepreneursLoaded = true;
    } catch(e) { console.warn("Failed to load entrepreneurs", e); }
};

// Attach event listeners for toggle buttons after DOM is loaded
// and show investors by default

document.addEventListener('DOMContentLoaded', () => {
    const btnInvestors = document.getElementById('btn-investors');
    const btnEntrepreneurs = document.getElementById('btn-entrepreneurs');
    if (btnInvestors) btnInvestors.addEventListener('click', showInvestorList);
    if (btnEntrepreneurs) btnEntrepreneurs.addEventListener('click', showEntrepreneurList);
    showInvestorList();
});

function renderInvestorList(investors) {
    const container = document.getElementById('investor-list-container');
    container.innerHTML = '';
    if (!investors.length) {
        container.innerHTML = '<div class="empty-state">No investors found.</div>';
        return;
    }
    investors.forEach(inv => {
        const row = document.createElement('div');
        row.className = 'investor-row clickable';
        row.onclick = () => showToast('Click "View Profile" to open investor profile.', 'default');
        row.innerHTML = `
            <div class="investor-avatar">
                ${inv.profile_image_url ? `<img src="${inv.profile_image_url}" alt="${inv.username}">` : `<div class="investor-avatar-placeholder">${inv.username ? inv.username[0].toUpperCase() : 'I'}</div>`}
            </div>
            <div class="investor-info">
                <div class="investor-name">${inv.username}</div>
                <div class="investor-meta">${inv.firm_name || 'Investor'}${inv.investment_focus ? ' | ' + inv.investment_focus : ''}</div>
            </div>
            <div class="investor-actions">
                <span class="status-badge badge-potential">Score: ${inv.match_score !== null ? (inv.match_score * 100).toFixed(0) : '--'}</span>
                <button class="view-profile-btn">View Profile</button>
            </div>
        `;
        container.appendChild(row);
        // wire the View Profile button to open the investor profile page
        const vp = row.querySelector('.view-profile-btn');
        if (vp) {
            vp.addEventListener('click', (e) => {
                e.stopPropagation();
                if (inv.email) {
                    window.location.href = `/investor/profile/${encodeURIComponent(inv.email)}`;
                } else {
                    showToast('Investor email not available.', 'error');
                }
            });
        }
    });
}

function renderEntrepreneurList(entrepreneurs) {
    const container = document.getElementById('entrepreneur-list-container');
    container.innerHTML = '';
    if (!entrepreneurs.length) {
        container.innerHTML = '<div class="empty-state">No entrepreneurs found.</div>';
        return;
    }
    entrepreneurs.forEach(ent => {
        const row = document.createElement('div');
        row.className = 'investor-row clickable';
        row.onclick = () => showToast('Click "View Pitch" to open entrepreneur profile.', 'default');
        row.innerHTML = `
            <div class="investor-avatar">
                ${ent.profile_image_url ? `<img src="${ent.profile_image_url}" alt="${ent.username}">` : `<div class="investor-avatar-placeholder">${ent.username ? ent.username[0].toUpperCase() : 'E'}</div>`}
            </div>
            <div class="investor-info">
                <div class="investor-name">${ent.username}</div>
                <div class="investor-meta">${ent.startup_name || ''}${ent.industry ? ' | ' + ent.industry : ''}</div>
            </div>
            <div class="investor-actions">
                <span class="status-badge badge-potential">Profile Score: ${ent.profile_score !== null ? ent.profile_score : '--'}</span>
                <button class="view-profile-btn">View Pitch</button>
            </div>
        `;
        container.appendChild(row);
        // wire the View Pitch button to open the entrepreneur profile page
        const vp2 = row.querySelector('.view-profile-btn');
        if (vp2) {
            vp2.addEventListener('click', (e) => {
                e.stopPropagation();
                if (ent.email) {
                    window.location.href = `/entrepreneur/profile/${encodeURIComponent(ent.email)}`;
                } else {
                    showToast('Entrepreneur email not available.', 'error');
                }
            });
        }
    });
}

// Auto-load investors on page load
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('btn-investors')) {
        showInvestorList();
    }
});
/* ================================================================
   EISC Platform — Shared Dashboard JS (home + feed)
   ================================================================ */
(function () {
    'use strict';

    // ── Modal helpers ──────────────────────────────────────────
    window.openModal  = function(id) { const el = document.getElementById(id); if (el) el.classList.add('open'); };
    window.closeModal = function(id) { const el = document.getElementById(id); if (el) el.classList.remove('open'); };

    // Close modals on overlay backdrop click
    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeModal(overlay.id);
        });
    });

    // Close buttons [data-close-modal]
    document.querySelectorAll('[data-close-modal]').forEach(btn => {
        btn.addEventListener('click', () => closeModal(btn.dataset.closeModal));
    });

    // Escape key closes all modals
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal-overlay.open').forEach(el => el.classList.remove('open'));
        }
    });

    // ── Toast ──────────────────────────────────────────────────
    window.showToast = function(msg, type = 'default') {
        const container = document.getElementById('toastContainer');
        if (!container) return;

        const t = document.createElement('div');
        t.className = `toast ${type}`;

        const icons = {
            success: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="width:15px;height:15px;flex-shrink:0"><polyline points="20 6 9 17 4 12"/></svg>`,
            error:   `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="width:15px;height:15px;flex-shrink:0"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/></svg>`,
            default: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="width:15px;height:15px;flex-shrink:0"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/></svg>`
        };

        t.innerHTML = (icons[type] || icons.default) + `<span>${msg}</span>`;
        container.appendChild(t);
        setTimeout(() => {
            t.classList.add('removing');
            t.addEventListener('animationend', () => t.remove(), { once: true });
        }, 3200);
    };

    // ── Edit Profile form ─────────────────────────────────────
    const editProfileBtn  = document.getElementById('editProfileBtn');
    if (editProfileBtn) {
        editProfileBtn.addEventListener('click', () => openModal('editProfileModal'));
    }

    const editProfileForm = document.getElementById('editProfileForm');
    if (editProfileForm) {
        editProfileForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = editProfileForm.querySelector('.btn-submit');
            const orig = btn.textContent;
            btn.disabled = true; btn.textContent = 'Saving…';

            const payload = {
                startup_name: document.getElementById('ep_startup_name')?.value.trim(),
                bio:          document.getElementById('ep_bio')?.value.trim(),
                industry:     document.getElementById('ep_industry')?.value.trim(),
                location:     document.getElementById('ep_location')?.value.trim(),
                website_url:  document.getElementById('ep_website')?.value.trim(),
                linkedin_url: document.getElementById('ep_linkedin')?.value.trim(),
                twitter_url:  document.getElementById('ep_twitter')?.value.trim(),
            };

            try {
                const res  = await fetch('/api/profile/edit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (data.success) {
                    showToast('Profile updated!', 'success');
                    closeModal('editProfileModal');
                    // Update sidebar display
                    const startupEl = document.getElementById('sidebarStartup');
                    const bioEl     = document.getElementById('sidebarBio');
                    if (startupEl && payload.startup_name) startupEl.textContent = payload.startup_name;
                    if (bioEl     && payload.bio)          bioEl.textContent     = payload.bio.slice(0, 100) + (payload.bio.length > 100 ? '…' : '');
                } else {
                    showToast(data.message || 'Update failed.', 'error');
                }
            } catch {
                showToast('Network error.', 'error');
            } finally {
                btn.disabled = false; btn.textContent = orig;
            }
        });
    }

    // ── Create Post ───────────────────────────────────────────
    const createInput = document.getElementById('createPostInput');
    if (createInput) createInput.addEventListener('click', () => openModal('createPostModal'));

    document.querySelectorAll('.create-action-btn[data-open-modal]').forEach(btn => {
        btn.addEventListener('click', () => openModal(btn.dataset.openModal));
    });

    const createPostForm = document.getElementById('createPostForm');
    if (createPostForm) {
        createPostForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn  = createPostForm.querySelector('.btn-submit');
            const orig = btn.textContent;
            btn.disabled = true; btn.textContent = 'Posting…';

            const payload = {
                title:            document.getElementById('cp_title')?.value.trim(),
                description:      document.getElementById('cp_description')?.value.trim(),
                industry_tag:     document.getElementById('cp_industry')?.value.trim(),
                pitch_deck_url:   document.getElementById('cp_deck_url')?.value.trim(),
                video_url:        document.getElementById('cp_video_url')?.value.trim(),
            };

            if (!payload.title || !payload.description) {
                showToast('Title and description required.', 'error');
                btn.disabled = false; btn.textContent = orig;
                return;
            }

            try {
                const res  = await fetch('/api/posts/create', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (data.success) {
                    showToast('Pitch posted!', 'success');
                    closeModal('createPostModal');
                    createPostForm.reset();
                    prependPostToFeed(payload, data.post_id);
                } else {
                    showToast(data.message || 'Post failed.', 'error');
                }
            } catch {
                showToast('Network error.', 'error');
            } finally {
                btn.disabled = false; btn.textContent = orig;
            }
        });
    }

    // Optimistically prepend a new card to the feed
    function prependPostToFeed(post, postId) {
        const feed = document.getElementById('pitchFeed');
        if (!feed) return;

        const username  = document.querySelector('.topbar-avatar')?.title || 'You';
        const startup   = document.getElementById('sidebarStartup')?.textContent || '';
        const initials  = username.charAt(0).toUpperCase();
        const html = `
        <div class="card pitch-card" data-post-id="${postId || ''}" style="animation: fadeUp 0.4s ease both;">
            <div class="pitch-header">
                <div class="pitch-avatar">${initials}</div>
                <div class="pitch-author">
                    <div class="pitch-author-name">${esc(username)}</div>
                    <div class="pitch-author-meta">
                        ${startup ? esc(startup) + '<span class="dot"> · </span>' : ''}
                        <span>just now</span>
                    </div>
                </div>
                <button class="pitch-more-btn">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
                        <circle cx="12" cy="5" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="19" r="1.5"/>
                    </svg>
                </button>
            </div>
            <div class="pitch-tags">
                <span class="pitch-tag tag-stage">${stageLabel[post.stage] || post.stage}</span>
                ${post.industry_tag ? `<span class="pitch-tag tag-industry">${esc(post.industry_tag)}</span>` : ''}
                ${fundingStr ? `<span class="pitch-tag tag-funding">🎯 ${esc(fundingStr)}</span>` : ''}
            </div>
            <div class="pitch-title">${esc(post.title)}</div>
            <div class="pitch-desc clamped">${esc(post.description)}</div>
            <div class="pitch-stats-row">
                <span class="pitch-stat"><strong>0</strong> interested</span>
                <span class="pitch-stat"><strong>0</strong> saves</span>
                <span class="pitch-stat"><strong>0</strong> comments</span>
            </div>
            <div class="pitch-actions">
                <button class="pitch-action-btn" data-action="interested">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:15px;height:15px">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
                    </svg> Interested
                </button>
                <button class="pitch-action-btn" data-action="view">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:15px;height:15px">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
                    </svg> View Details
                </button>
                <button class="pitch-action-btn" data-action="save">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:15px;height:15px">
                        <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
                    </svg> Save
                </button>
                <button class="pitch-action-btn" data-action="comment">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:15px;height:15px">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                    </svg> Comment
                </button>
            </div>
        </div>`;

        feed.insertAdjacentHTML('afterbegin', html);
        bindPostActions(feed.firstElementChild);
    }

    // ── Bind pitch action buttons ─────────────────────────────
    function bindPostActions(card) {
        const postId = card.dataset.postId;
        card.querySelectorAll('.pitch-action-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const action = btn.dataset.action;
                if (action === 'comment' || action === 'view') {
                    showToast(`${action === 'comment' ? 'Comments' : 'Full pitch view'} coming soon!`, 'default');
                    return;
                }
                if (!postId) { btn.classList.toggle('active'); return; }
                btn.disabled = true;
                fetch(`/api/posts/${postId}/interact`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ type: action })
                })
                .then(r => r.json())
                .then(d => { if (d.success) btn.classList.add('active'); })
                .catch(() => showToast('Action failed.', 'error'))
                .finally(() => { btn.disabled = false; });
            });
        });
    }

    // Bind all existing feed cards
    document.querySelectorAll('.pitch-card[data-post-id]').forEach(bindPostActions);

    // ── Message thread click ──────────────────────────────────
    document.querySelectorAll('.msg-item').forEach(item => {
        item.addEventListener('click', () => {
            const name = item.querySelector('.msg-name')?.textContent;
            const email = item.dataset.partnerEmail;
            item.classList.remove('unread');
            item.querySelector('.msg-unread-dot')?.remove();
            showToast(`Opening chat with ${name || 'user'}…`, 'default');
            if (email) {
                fetch('/api/messages/read', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ partner_email: email })
                }).catch(() => {});
            }
        });
    });

    // ── Message search ────────────────────────────────────────
    const msgSearch = document.getElementById('msgSearch');
    if (msgSearch) {
        msgSearch.addEventListener('input', () => {
            const q = msgSearch.value.toLowerCase();
            document.querySelectorAll('.msg-item').forEach(item => {
                const name = item.querySelector('.msg-name')?.textContent.toLowerCase() || '';
                const prev = item.querySelector('.msg-preview')?.textContent.toLowerCase() || '';
                item.style.display = (name.includes(q) || prev.includes(q)) ? '' : 'none';
            });
        });
    }

    // ── Profile dropdown (topbar avatar) ─────────────────────
    const profileDropdown = document.getElementById('profileDropdown');
    const avatarEl        = document.querySelector('.topbar-avatar');
    if (profileDropdown && avatarEl) {
        avatarEl.addEventListener('click', (e) => {
            e.stopPropagation();
            profileDropdown.classList.toggle('open');
        });
        document.addEventListener('click', () => profileDropdown.classList.remove('open'));
    }

    // ── Schedule Meeting Form ───────────────────────────────────
    const scheduleMeetingForm = document.getElementById('scheduleMeetingForm');
    if (scheduleMeetingForm) {
        scheduleMeetingForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const investor_email = document.getElementById('meetInvestor').value;
            const meeting_type = document.getElementById('meetType').value;
            const datetime_local = document.getElementById('meetDate').value;
            
            if (!investor_email || !meeting_type || !datetime_local) {
                showToast('Please fill in all fields', 'error');
                return;
            }
            
            // Convert datetime-local format (2024-01-15T10:30) to MySQL format (2024-01-15 10:30:00)
            const scheduled_at = datetime_local.replace('T', ' ') + ':00';
            
            try {
                const res = await fetch('/api/meetings/schedule', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        investor_email,
                        meeting_type,
                        scheduled_at
                    })
                });
                const data = await res.json();
                
                if (data.success) {
                    showToast('Meeting scheduled successfully!', 'success');
                    closeModal('scheduleMeetingModal');
                    scheduleMeetingForm.reset();
                    // Reload to show updated meetings
                    setTimeout(() => location.reload(), 1500);
                } else {
                    showToast(data.message || 'Failed to schedule meeting', 'error');
                }
            } catch (err) {
                console.error(err);
                showToast('Network error', 'error');
            }
        });
    }

    // ── HTML escape helper ─────────────────────────────────────
    function esc(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g,'&amp;').replace(/</g,'&lt;')
            .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    console.log('🚀 EISC Dashboard JS loaded');
})();