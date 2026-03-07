/* ================================================================
   EISC — AI Matches Page JS  (shared by investor + entrepreneur)
   Handles:
     • toggleAlgoPanel()          — show/hide how-it-works panel
     • recomputeMatches()         — call /api/matches/recompute
     • expressInterest()          — investor → startup (POST)
     • saveStartup()              — investor bookmarks startup
     • requestConnection()        — entrepreneur → investor (POST)
     • saveInvestor()             — entrepreneur bookmarks investor
   ================================================================ */
(function () {
    'use strict';

    // ── Algorithm panel toggle ─────────────────────────────────
    window.toggleAlgoPanel = function () {
        const panel = document.getElementById('algoPanel');
        if (!panel) return;
        panel.classList.toggle('open');
    };

    // ── Recompute matches (manual refresh) ────────────────────
    window.recomputeMatches = async function () {
        const btn  = document.getElementById('refreshBtn');
        if (!btn) return;

        const origHTML = btn.innerHTML;
        btn.disabled   = true;
        btn.innerHTML  = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg> Computing…`;

        try {
            const res  = await fetch(MATCH_RECOMPUTE_URL || '/api/matches/recompute', {
                method : 'POST',
                headers: { 'Content-Type': 'application/json' },
            });
            const data = await res.json();

            if (data.success) {
                showToast(
                    `✅ Matches refreshed — ${data.matches_found} result${data.matches_found !== 1 ? 's' : ''} found.`,
                    'success'
                );
                // Reload page after short delay to show new results
                setTimeout(() => window.location.reload(), 1200);
            } else {
                showToast(data.message || 'Recompute failed. Try again.', 'error');
                btn.disabled  = false;
                btn.innerHTML = origHTML;
            }
        } catch {
            showToast('Network error. Please try again.', 'error');
            btn.disabled  = false;
            btn.innerHTML = origHTML;
        }
    };

    // ── Express Interest (investor → startup) ─────────────────
    window.expressInterest = async function (entrepreneurEmail, btnIndex) {
        const btn = document.getElementById(`interest-btn-${btnIndex}`);
        if (!btn || btn.disabled) return;

        const origHTML    = btn.innerHTML;
        btn.disabled      = true;
        btn.innerHTML     = `<span style="display:flex;align-items:center;gap:5px">
            <span class="ai-spinner"></span> Sending…</span>`;

        try {
            const res  = await fetch('/api/matches/express-interest', {
                method : 'POST',
                headers: { 'Content-Type': 'application/json' },
                body   : JSON.stringify({ entrepreneur_email: entrepreneurEmail }),
            });
            const data = await res.json();

            if (data.success) {
                // Mark as sent permanently
                btn.classList.add('btn-sent');
                btn.innerHTML = `✓ Interest Sent`;
                showToast('Interest expressed! The founder will be notified.', 'success');
            } else {
                showToast(data.message || 'Failed. Please try again.', 'error');
                btn.disabled  = false;
                btn.innerHTML = origHTML;
            }
        } catch {
            showToast('Network error. Please try again.', 'error');
            btn.disabled  = false;
            btn.innerHTML = origHTML;
        }
    };

    // ── Save Startup (investor bookmarks) ─────────────────────
    window.saveStartup = async function (entrepreneurEmail, btnEl) {
        if (btnEl.classList.contains('saved')) {
            showToast('Already saved.', 'default');
            return;
        }

        try {
            const res  = await fetch('/api/matches/save-startup', {
                method : 'POST',
                headers: { 'Content-Type': 'application/json' },
                body   : JSON.stringify({ entrepreneur_email: entrepreneurEmail }),
            });
            const data = await res.json();

            if (data.success) {
                btnEl.classList.add('saved');
                // Fill the bookmark icon
                const svg = btnEl.querySelector('svg');
                if (svg) svg.setAttribute('fill', 'currentColor');
                showToast('Startup saved to your list!', 'success');
            } else {
                showToast(data.message || 'Save failed.', 'error');
            }
        } catch {
            showToast('Network error.', 'error');
        }
    };

    // ── Request Connection (entrepreneur → investor) ───────────
    window.requestConnection = async function (investorEmail, btnIndex) {
        const btn = document.getElementById(`connect-btn-${btnIndex}`);
        if (!btn || btn.disabled) return;

        const origHTML = btn.innerHTML;
        btn.disabled   = true;
        btn.innerHTML  = `<span style="display:flex;align-items:center;gap:5px"><span class="ai-spinner"></span> Sending…</span>`;

        try {
            const res  = await fetch('/api/matches/request-connection', {
                method : 'POST',
                headers: { 'Content-Type': 'application/json' },
                body   : JSON.stringify({ investor_email: investorEmail }),
            });
            const data = await res.json();

            if (data.success) {
                btn.classList.add('btn-sent');
                btn.innerHTML = `✓ Request Sent`;
                showToast('Connection request sent! The investor will be notified.', 'success');
            } else {
                showToast(data.message || 'Failed. Please try again.', 'error');
                btn.disabled  = false;
                btn.innerHTML = origHTML;
            }
        } catch {
            showToast('Network error. Please try again.', 'error');
            btn.disabled  = false;
            btn.innerHTML = origHTML;
        }
    };

    // ── Save Investor (entrepreneur bookmarks) ─────────────────
    window.saveInvestor = async function (investorEmail, btnEl) {
        if (btnEl.classList.contains('saved')) {
            showToast('Already saved.', 'default');
            return;
        }

        try {
            const res  = await fetch('/api/matches/save-investor', {
                method : 'POST',
                headers: { 'Content-Type': 'application/json' },
                body   : JSON.stringify({ investor_email: investorEmail }),
            });
            const data = await res.json();

            if (data.success) {
                btnEl.classList.add('saved');
                const svg = btnEl.querySelector('svg');
                if (svg) svg.setAttribute('fill', 'currentColor');
                showToast('Investor saved to your list!', 'success');
            } else {
                showToast(data.message || 'Save failed.', 'error');
            }
        } catch {
            showToast('Network error.', 'error');
        }
    };

    // ── Animate score bars on load ─────────────────────────────
    document.addEventListener('DOMContentLoaded', () => {
        // Score bars start at 0, animate to actual width via CSS transition
        // The width is already set inline; CSS transition handles the animation
        // We just need to ensure the bars are visible after a short delay
        setTimeout(() => {
            document.querySelectorAll('.match-score-bar').forEach(bar => {
                // Force a repaint to trigger the CSS transition
                bar.style.opacity = '1';
            });
        }, 200);
    });

    // ── Investment Modal Functions ─────────────────────────────
    let currentInvestmentEmail = '';

    window.openInvestModal = function (entrepreneurEmail, startupName) {
        currentInvestmentEmail = entrepreneurEmail;
        document.getElementById('investStartupName').textContent = startupName || 'Selected Startup';
        document.getElementById('investAmount').value = '';
        document.getElementById('investEquity').value = '';
        document.getElementById('investNotes').value = '';
        
        const modal = document.getElementById('investModal');
        if (modal) {
            modal.classList.add('active');
            modal.style.display = 'flex';
        }
    };

    window.closeModal = function (modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('active');
            modal.style.display = 'none';
        }
    };

    window.submitInvestment = async function () {
        const amount = parseFloat(document.getElementById('investAmount').value);
        const equity = parseFloat(document.getElementById('investEquity').value) || null;
        const notes = document.getElementById('investNotes').value.trim();

        if (!amount || amount <= 0) {
            showToast('Please enter a valid investment amount', 'error');
            return;
        }

        if (!currentInvestmentEmail) {
            showToast('Error: Startup not selected', 'error');
            return;
        }

        try {
            const res = await fetch('/api/investor/investments/propose', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    entrepreneur_email: currentInvestmentEmail,
                    investment_amount: amount,
                    equity_percentage: equity,
                    notes: notes
                })
            });

            const data = await res.json();

            if (data.success) {
                showToast('✅ Investment proposal sent to founder!', 'success');
                closeModal('investModal');
            } else {
                showToast(data.message || 'Failed to submit proposal', 'error');
            }
        } catch (error) {
            showToast('Network error. Please try again.', 'error');
            console.error(error);
        }
    };

    console.log('✅ matches.js loaded');
})();