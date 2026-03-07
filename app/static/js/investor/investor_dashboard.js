/* ================================================================
   INVESTOR DASHBOARD — investor_dashboard.js
   Mirrors the entrepreneur dashboard.js pattern
================================================================ */

(function () {
    'use strict';

    // ── Modal helpers ──────────────────────────────────────────────
    function openModal(id)  { const el = document.getElementById(id); if (el) el.classList.add('open'); }
    function closeModal(id) { const el = document.getElementById(id); if (el) el.classList.remove('open'); }

    // Close modal on overlay click or [data-close-modal] buttons
    document.addEventListener('click', function (e) {
        // data-close-modal button
        const closeBtn = e.target.closest('[data-close-modal]');
        if (closeBtn) {
            closeModal(closeBtn.dataset.closeModal);
            return;
        }
        // Click on overlay backdrop itself
        if (e.target.classList.contains('modal-overlay')) {
            e.target.classList.remove('open');
        }
    });

    // Escape key closes any open modal
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal-overlay.open')
                .forEach(el => el.classList.remove('open'));
        }
    });

    // ── Express Interest ───────────────────────────────────────────
    window.expressInterest = async function (entrepreneurEmail, btn) {
        if (!entrepreneurEmail) return;

        const original = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = 'Sending…';

        try {
            const res  = await fetch('/api/investor/interests/express', {
                method : 'POST',
                headers: { 'Content-Type': 'application/json' },
                body   : JSON.stringify({ entrepreneur_email: entrepreneurEmail }),
            });
            const data = await res.json();

            if (data.success) {
                btn.innerHTML = '✓ Interested';
                btn.classList.add('pending');
                showToast('Interest expressed! Opening AI Chat...', 'success');
                
                // Redirect to AI chat with the interested startup pre-selected
                setTimeout(() => {
                    window.location.href = `/dashboard/investor/ai-chat?startup_email=${encodeURIComponent(entrepreneurEmail)}`;
                }, 800);
            } else {
                btn.disabled = false;
                btn.innerHTML = original;
                showToast(data.message || 'Failed. Please try again.', 'error');
            }
        } catch {
            btn.disabled = false;
            btn.innerHTML = original;
            showToast('Network error. Please try again.', 'error');
        }
    };

    // Edit Profile form listener was removed to prevent conflicts with investor_profile.js

    // ── Expose globals (needed by inline onclick handlers) ─────────
    window.openModal  = openModal;
    window.closeModal = closeModal;

    // ── Tab switching ──────────────────────────────────────────────
    window.switchTab = function (tabName) {
        // Update tab buttons
        document.querySelectorAll('.people-tab').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tabName);
        });
        // Show/hide panels
        document.querySelectorAll('.tab-panel').forEach(panel => {
            panel.classList.toggle('active', panel.id === `tab-${tabName}`);
        });
    };

    // ── People search filter ───────────────────────────────────────
    window.filterCards = function (type) {
        const inputId = type === 'ent' ? 'searchEntrepreneurs' : 'searchInvestors';
        const gridId  = type === 'ent' ? 'entGrid' : 'invGrid';
        const cls     = type === 'ent' ? '.ent-card' : '.inv-card';

        const q    = (document.getElementById(inputId)?.value || '').toLowerCase().trim();
        const grid = document.getElementById(gridId);
        if (!grid) return;

        grid.querySelectorAll(cls).forEach(card => {
            const haystack = (card.dataset.search || '').toLowerCase();
            card.style.display = (!q || haystack.includes(q)) ? '' : 'none';
        });
    };

    // showToast is also defined inline in the HTML (same as entrepreneur),
    // but we re-expose here in case the inline block hasn't run yet.
    if (!window.showToast) {
        window.showToast = function (msg, type) {
            const t = document.createElement('div');
            t.className = `toast ${type || 'default'}`;
            const icons = {
                success: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="width:15px;height:15px;flex-shrink:0"><polyline points="20 6 9 17 4 12"/></svg>`,
                error:   `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="width:15px;height:15px;flex-shrink:0"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/></svg>`,
                default: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="width:15px;height:15px;flex-shrink:0"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/></svg>`
            };
            t.innerHTML = (icons[type] || icons.default) + `<span>${msg}</span>`;
            const container = document.getElementById('toastContainer');
            if (container) container.appendChild(t);
            setTimeout(() => {
                t.classList.add('removing');
                t.addEventListener('animationend', () => t.remove());
            }, 3200);
        };
    }

})();