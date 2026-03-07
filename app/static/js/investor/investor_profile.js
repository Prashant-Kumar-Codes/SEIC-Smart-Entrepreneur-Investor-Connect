/* ================================================================
   EISC — Investor My Profile JS
   ================================================================ */
(function () {
    'use strict';

    // ── Tab switching ──────────────────────────────────────────
    document.querySelectorAll('.edit-tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            document.querySelectorAll('.edit-tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.edit-tab-panel').forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(`tab-${tab}`)?.classList.add('active');
        });
    });

    // Open modal on a specific tab (called from section "Edit" buttons)
    window.openEditTab = function(tabName) {
        openModal('editProfileModal');
        // Slight delay so modal is rendered before switching tab
        setTimeout(() => {
            document.querySelectorAll('.edit-tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.edit-tab-panel').forEach(p => p.classList.remove('active'));
            const btn = document.querySelector(`.edit-tab-btn[data-tab="${tabName}"]`);
            const panel = document.getElementById(`tab-${tabName}`);
            if (btn)   btn.classList.add('active');
            if (panel) panel.classList.add('active');
        }, 60);
    };

    // ── Bio char count ─────────────────────────────────────────
    const bioTextarea = document.getElementById('ep_bio');
    const bioCount    = document.getElementById('bioCharCount');
    if (bioTextarea && bioCount) {
        const update = () => {
            const len = bioTextarea.value.length;
            bioCount.textContent = `${len} / 600`;
            bioCount.style.color = len > 550 ? '#ef4444' : 'var(--text-muted)';
        };
        update();
        bioTextarea.addEventListener('input', update);
    }

    // ── Avatar preview ─────────────────────────────────────────
    window.previewAvatar = function(input) {
        if (!input.files || !input.files[0]) return;
        const reader = new FileReader();
        reader.onload = (e) => {
            const preview = document.getElementById('modalAvatarPreview');
            if (preview) {
                preview.innerHTML = `<img src="${e.target.result}" style="width:100%;height:100%;object-fit:cover;border-radius:50%">`;
            }
        };
        reader.readAsDataURL(input.files[0]);
    };

    // ── Format INR helper ──────────────────────────────────────
    function fmtINR(val) {
        if (!val) return '—';
        const n = parseFloat(val);
        if (isNaN(n)) return '—';
        if (n >= 10_000_000) return `₹${(n / 10_000_000).toFixed(1)} Cr`;
        if (n >= 100_000)    return `₹${(n / 100_000).toFixed(1)} L`;
        return `₹${n.toLocaleString('en-IN')}`;
    }

    // ── Form submit ────────────────────────────────────────────
    const form = document.getElementById('editInvestorProfileForm');
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn  = document.getElementById('investorSaveBtn');
            const orig = btn.textContent;
            btn.disabled = true; btn.textContent = 'Saving…';

            const payload = {
                full_name:            v('ep_full_name'),
                investor_type:        v('ep_investor_type'),
                bio:                  v('ep_bio'),
                location:             v('ep_location'),
                geography:            v('ep_geography'),
                current_position:     v('ep_current_position'),
                firm_name:            v('ep_firm_name'),
                years_of_experience:  v('ep_years_exp'),
                education:            v('ep_education'),
                previous_roles:       v('ep_previous_roles'),
                investment_focus:     v('ep_investment_focus'),
                preferred_sectors:    v('ep_preferred_sectors'),
                investment_stage:     v('ep_investment_stage'),
                min_ticket_size:      v('ep_min_ticket'),
                max_ticket_size:      v('ep_max_ticket'),
                investment_thesis:    v('ep_investment_thesis'),
                portfolio_highlights: v('ep_portfolio_highlights'),
                available_funds:      v('ep_available_funds'),
                investment_utilization_pct: v('ep_deployment_pct'),
                website_url:          v('ep_website'),
                linkedin_url:         v('ep_linkedin'),
                twitter_url:          v('ep_twitter'),
                crunchbase_url:       v('ep_crunchbase'),
            };

            try {
                const res  = await fetch('/api/investor/profile/edit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();

                if (data.success) {
                    showToast('Profile saved!', 'success');
                    closeModal('editProfileModal');
                    updateDisplay(payload);
                } else {
                    showToast(data.message || 'Save failed.', 'error');
                }
            } catch {
                showToast('Network error. Please try again.', 'error');
            } finally {
                btn.disabled = false; btn.textContent = orig;
            }
        });
    }

    // ── Live DOM update after save ─────────────────────────────
    function updateDisplay(p) {

        // Name
        setText('displayName', p.full_name);

        // Role badge
        if (p.investor_type) {
            const badge = document.getElementById('displayRoleBadge');
            if (badge) badge.childNodes[badge.childNodes.length - 1].textContent = ' ' + p.investor_type;
        }

        // Tagline
        const taglineEl = document.getElementById('displayTagline');
        if (taglineEl && (p.firm_name || p.current_position)) {
            const pos  = p.current_position ? `<strong>${esc(p.current_position)}</strong> at ` : '';
            const firm = p.firm_name ? `<strong>${esc(p.firm_name)}</strong>` : '';
            const foc  = p.investment_focus ? ` · ${esc(p.investment_focus)}` : '';
            taglineEl.innerHTML = pos + firm + foc;
        }

        // Location
        setText('displayLocation', p.location);

        // Bio
        const bioEl = document.getElementById('displayBio');
        if (bioEl) {
            if (p.bio) { bioEl.textContent = p.bio; bioEl.className = 'profile-bio-text'; }
            else        { bioEl.className = 'profile-bio-empty'; }
        }

        // Background section
        setTextWithEmpty('dispPosition',     p.current_position);
        setTextWithEmpty('dispFirmName',     p.firm_name);
        setTextWithEmpty('dispYearsExp',     p.years_of_experience ? p.years_of_experience + '+ years' : '');
        setTextWithEmpty('dispEducation',    p.education);

        const prevRolesEl = document.getElementById('dispPreviousRoles');
        if (prevRolesEl) {
            if (p.previous_roles) {
                prevRolesEl.innerHTML = `<div class="profile-info-label" style="margin-bottom:8px">Previous Roles</div><p class="profile-bio-text" style="font-size:0.84rem">${esc(p.previous_roles)}</p>`;
            } else {
                prevRolesEl.innerHTML = `<p class="profile-bio-empty" style="font-size:0.84rem">Add previous roles and operator experience to build founder trust.</p>`;
            }
        }

        // Investment prefs
        setTextWithEmpty('dispInvestorType', p.investor_type);
        setTextWithEmpty('dispStage',        p.investment_stage);
        setTextWithEmpty('dispMinTicket',    p.min_ticket_size ? '₹' + Number(p.min_ticket_size).toLocaleString('en-IN') : '');
        setTextWithEmpty('dispMaxTicket',    p.max_ticket_size ? '₹' + Number(p.max_ticket_size).toLocaleString('en-IN') : '');
        setTextWithEmpty('dispGeography',    p.geography);
        setTextWithEmpty('dispSectors',      p.preferred_sectors);

        // Investment thesis
        const thesisEl = document.getElementById('dispThesis');
        if (thesisEl) {
            thesisEl.textContent = p.investment_thesis || '';
            thesisEl.className   = p.investment_thesis ? 'profile-bio-text' : 'profile-bio-empty';
        }

        // Portfolio highlights
        const portEl = document.getElementById('dispPortfolio');
        if (portEl) {
            portEl.textContent = p.portfolio_highlights || '';
            portEl.className   = p.portfolio_highlights ? 'profile-bio-text' : 'profile-bio-empty';
        }

        // Ticket card
        const minCardEl  = document.getElementById('dispMinTicketCard');
        const maxCardEl  = document.getElementById('dispMaxTicketCard');
        const stageCardEl = document.getElementById('dispStageCard');
        if (minCardEl)   minCardEl.textContent   = fmtINR(p.min_ticket_size);
        if (maxCardEl)   maxCardEl.textContent   = fmtINR(p.max_ticket_size);
        if (stageCardEl && p.investment_stage) {
            // Keep the SVG, just update the text node
            const lastChild = stageCardEl.lastChild;
            if (lastChild && lastChild.nodeType === 3) lastChild.textContent = ' ' + p.investment_stage;
        }

        // Social links — rebuild
        rebuildSocialLinks(p);
    }

    function rebuildSocialLinks(p) {
        const container = document.getElementById('displaySocial');
        if (!container) return;

        const links = [
            { url: p.website_url,    name: 'Website / Fund', iconClass: 'icon-web',        svgPath: '<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>' },
            { url: p.linkedin_url,   name: 'LinkedIn',       iconClass: 'icon-linkedin',   svgPath: '<path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect x="2" y="9" width="4" height="12"/><circle cx="4" cy="4" r="2"/>', fill: true },
            { url: p.twitter_url,    name: 'Twitter / X',    iconClass: 'icon-twitter',    svgPath: '<path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>', fill: true },
            { url: p.crunchbase_url, name: 'Crunchbase',     iconClass: 'icon-crunchbase', svgPath: '<path d="M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0zM9 8.25H7.5v7.5H9v-3h1.5a3 3 0 0 0 0-6H9v1.5zm1.5 3H9v-1.5h1.5a1.5 1.5 0 0 1 0 3z"/>', fill: true },
        ];

        const hasAny = links.some(l => l.url);
        if (!hasAny) {
            container.innerHTML = `<p class="profile-bio-empty">Add your website, LinkedIn and Crunchbase to build credibility.</p>`;
            return;
        }

        container.innerHTML = links
            .filter(l => l.url)
            .map(l => {
                const fillAttr = l.fill ? 'fill="currentColor"' : `fill="none" stroke="currentColor" stroke-width="2"`;
                const urlShort = l.url.replace(/^https?:\/\//, '').substring(0, 40);
                return `<a class="social-link-item" href="${esc(l.url)}" target="_blank">
                    <div class="social-link-icon ${l.iconClass}">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" ${fillAttr}>${l.svgPath}</svg>
                    </div>
                    <div class="social-link-text">
                        <div class="social-link-name">${l.name}</div>
                        <div class="social-link-url">${esc(urlShort)}…</div>
                    </div>
                    <div class="social-link-arrow">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
                    </div>
                </a>`;
            }).join('');
    }

    // ── Copy profile link ──────────────────────────────────────
    window.copyProfileLink = function() {
        const name = document.getElementById('displayName')?.textContent?.trim() || '';
        const url  = `${window.location.origin}/investor/profile/${encodeURIComponent(name)}`;
        navigator.clipboard.writeText(url)
            .then(() => showToast('Profile link copied!', 'success'))
            .catch(() => showToast('Copy failed — try manually.', 'error'));
    };

    // ── Helpers ────────────────────────────────────────────────
    function v(id) {
        const el = document.getElementById(id);
        return el ? el.value.trim() : '';
    }
    function setText(id, val) {
        const el = document.getElementById(id);
        if (el && val) el.textContent = val;
    }
    function setTextWithEmpty(id, val) {
        const el = document.getElementById(id);
        if (!el) return;
        if (val) { el.textContent = val; el.classList.remove('empty'); }
        else      { el.textContent = 'Not specified'; el.classList.add('empty'); }
    }
    function esc(s) {
        return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    console.log('✅ investor_profile.js loaded');
})();