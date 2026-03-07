/* ================================================================
   EISC — Investor Portfolio Page JS
   AI Enhancement via /api/investor/portfolio/enhance (Gemini)
   Mirrors entrepreneur_pitch_deck.js pattern exactly.
   ================================================================ */
(function () {
    'use strict';

    const SECTIONS = [
        'thesis', 'criteria', 'highlights',
        'sectors', 'dd', 'valueadd', 'exit', 'coinvest'
    ];

    // Map section-id → textarea field id
    const FIELD_MAP = {
        thesis    : 'field-investment_thesis',
        criteria  : 'field-deal_criteria',
        highlights: 'field-portfolio_highlights',
        sectors   : 'field-sector_expertise',
        dd        : 'field-dd_framework',
        valueadd  : 'field-value_add',
        exit      : 'field-exit_strategy',
        coinvest  : 'field-co_investment',
    };

    // Section labels for AI context
    const SECTION_LABELS = {
        thesis    : 'Investment Thesis',
        criteria  : 'Deal Criteria',
        highlights: 'Portfolio Highlights',
        sectors   : 'Sector Expertise',
        dd        : 'Due Diligence Framework',
        valueadd  : 'Value Add',
        exit      : 'Exit Strategy',
        coinvest  : 'Co-Investment',
    };

    // ── Section accordion toggle ───────────────────────────────
    window.toggleSection = function (id) {
        const el = document.getElementById(`sec-${id}`);
        if (!el) return;
        const isOpen = el.classList.contains('open');
        SECTIONS.forEach(s => document.getElementById(`sec-${s}`)?.classList.remove('open'));
        if (!isOpen) el.classList.add('open');
    };

    // ── Word / char count ──────────────────────────────────────
    window.updateWordCount = function (secId, textarea) {
        const text  = textarea.value.trim();
        const words = text ? text.split(/\s+/).length : 0;
        const chars = textarea.value.length;

        const wcEl = document.getElementById(`wc-${secId}`);
        const ccEl = document.getElementById(`cc-${secId}`);
        if (wcEl) wcEl.textContent = `${words} word${words !== 1 ? 's' : ''}`;
        if (ccEl) ccEl.textContent = `${chars} characters`;

        updateStrength();
    };

    // Initialise counts on page load
    SECTIONS.forEach(id => {
        const ta = document.getElementById(FIELD_MAP[id]);
        if (ta && ta.value.trim()) updateWordCount(id, ta);
    });

    // ── Profile Strength Ring ──────────────────────────────────
    function updateStrength() {
        let filled = 0;

        SECTIONS.forEach(id => {
            const ta = document.getElementById(FIELD_MAP[id]);
            const hasContent = ta && ta.value.trim().length > 30;

            const checkEl = document.getElementById(`check-${id}`);
            if (checkEl) {
                const svg = checkEl.querySelector('svg');
                if (hasContent) {
                    svg.innerHTML = '<polyline points="20 6 9 17 4 12"/>';
                    svg.setAttribute('class', 'check-done');
                    svg.setAttribute('stroke-width', '2.5');
                    filled++;
                } else {
                    svg.innerHTML = '<circle cx="12" cy="12" r="10"/>';
                    svg.setAttribute('class', 'check-todo');
                    svg.setAttribute('stroke-width', '2');
                }
            }
        });

        const pct    = Math.round((filled / SECTIONS.length) * 100);
        const ringEl = document.getElementById('strengthRing');
        const pctEl  = document.getElementById('strengthPct');
        const circum = 2 * Math.PI * 30; // r=30

        if (pctEl)  pctEl.textContent = `${pct}%`;
        if (ringEl) {
            ringEl.style.strokeDashoffset = circum - (circum * pct / 100);
            if (pct < 40)       ringEl.style.stroke = '#ef4444';
            else if (pct < 70)  ringEl.style.stroke = '#f59e0b';
            else                ringEl.style.stroke = '#0d9488';
        }
    }

    // Initialise ring
    updateStrength();

    // ── Single section AI enhance ──────────────────────────────
    window.enhanceSection = async function (secId, fieldKey, sectionName) {
        const textarea   = document.getElementById(FIELD_MAP[secId]);
        const btn        = document.getElementById(`ai-btn-${secId}`);
        const resultBox  = document.getElementById(`ai-result-${secId}`);

        if (!textarea || !textarea.value.trim()) {
            showToast(`Write something in "${sectionName}" first.`, 'error');
            return;
        }

        // Show thinking state
        btn.disabled  = true;
        btn.innerHTML = `<span style="display:flex;align-items:center;gap:5px">
            <span class="ai-thinking-dots"><span></span><span></span><span></span></span>
            Enhancing…</span>`;

        resultBox.style.display = 'block';
        resultBox.classList.add('visible');
        resultBox.innerHTML = `
            <div class="ai-thinking" style="margin-top:0">
                <span>✨ AI is crafting a stronger version…</span>
                <div class="ai-thinking-dots"><span></span><span></span><span></span></div>
            </div>`;

        try {
            const res  = await fetch('/api/investor/portfolio/enhance', {
                method : 'POST',
                headers: { 'Content-Type': 'application/json' },
                body   : JSON.stringify({
                    section   : sectionName,
                    content   : textarea.value.trim(),
                    firm_name : typeof INV_FIRM_NAME !== 'undefined' ? INV_FIRM_NAME : '',
                    full_name : typeof INV_FULL_NAME !== 'undefined' ? INV_FULL_NAME : '',
                })
            });
            const data = await res.json();

            if (data.success && data.enhanced) {
                resultBox.innerHTML = `
                    <div class="ai-result-header">
                        <div class="ai-result-label">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" style="width:14px;height:14px">
                                <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"/>
                            </svg>
                            AI Enhanced Version
                        </div>
                        <div class="ai-result-actions">
                            <button class="ai-accept-btn" onclick="acceptAiResult('${secId}','${fieldKey}')">Use This</button>
                            <button class="ai-dismiss-btn" onclick="dismissAiResult('${secId}')">Dismiss</button>
                        </div>
                    </div>
                    <div class="ai-result-text" id="ai-text-${secId}">${esc(data.enhanced)}</div>`;
            } else {
                resultBox.innerHTML = `<div style="padding:12px;font-size:0.82rem;color:#ef4444;background:#fef2f2">
                    ${data.message || 'AI enhancement failed. Try again.'}</div>`;
            }
        } catch {
            resultBox.innerHTML = `<div style="padding:12px;font-size:0.82rem;color:#ef4444;background:#fef2f2">
                Network error. Please try again.</div>`;
        } finally {
            btn.disabled = false;
            btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" style="width:11px;height:11px"><path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"/></svg> ✨ Enhance with AI`;
        }
    };

    // ── Accept AI result → replace textarea ───────────────────
    window.acceptAiResult = function (secId, fieldKey) {
        const ta     = document.getElementById(FIELD_MAP[secId]);
        const textEl = document.getElementById(`ai-text-${secId}`);
        if (ta && textEl) {
            ta.value = textEl.textContent;
            updateWordCount(secId, ta);
            dismissAiResult(secId);
            showToast('AI version applied!', 'success');
        }
    };

    window.dismissAiResult = function (secId) {
        const box = document.getElementById(`ai-result-${secId}`);
        if (box) { box.classList.remove('visible'); box.style.display = 'none'; }
    };

    // ── Enhance ALL sections ───────────────────────────────────
    window.enhanceAllSections = async function () {
        const btn  = document.getElementById('globalAiBtn');
        const orig = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = `<span style="display:flex;align-items:center;gap:6px">
            <span class="ai-thinking-dots" style="display:flex;gap:3px">
                <span style="width:5px;height:5px;background:#fff;border-radius:50%;animation:bounce 0.8s ease-in-out infinite"></span>
                <span style="width:5px;height:5px;background:#fff;border-radius:50%;animation:bounce 0.8s ease-in-out infinite;animation-delay:0.16s"></span>
                <span style="width:5px;height:5px;background:#fff;border-radius:50%;animation:bounce 0.8s ease-in-out infinite;animation-delay:0.32s"></span>
            </span> Enhancing All…</span>`;

        let count = 0;
        for (const secId of SECTIONS) {
            const ta = document.getElementById(FIELD_MAP[secId]);
            if (!ta || !ta.value.trim()) continue;

            // Open this section for visual feedback
            SECTIONS.forEach(s => document.getElementById(`sec-${s}`)?.classList.remove('open'));
            document.getElementById(`sec-${secId}`)?.classList.add('open');

            await enhanceSection(secId, FIELD_MAP[secId].replace('field-', ''), SECTION_LABELS[secId]);
            count++;
            await new Promise(r => setTimeout(r, 450));
        }

        btn.disabled  = false;
        btn.innerHTML = orig;
        showToast(count > 0 ? `${count} section${count > 1 ? 's' : ''} enhanced!` : 'No content to enhance yet.', count > 0 ? 'success' : 'error');
    };

    // ── Save portfolio ─────────────────────────────────────────
    window.savePortfolio = async function () {
        const btn  = document.getElementById('savePortfolioBtn');
        const orig = btn.innerHTML;
        btn.disabled    = true;
        btn.textContent = 'Saving…';

        const payload = {};
        
        // Save text sections
        for (const [secId, fieldId] of Object.entries(FIELD_MAP)) {
            const ta = document.getElementById(fieldId);
            if (ta) payload[fieldId.replace('field-', '')] = ta.value.trim();
        }

        // Save investment parameters
        const paramFields = [
            'preferred_sectors',
            'investment_stage',
            'min_ticket_size',
            'max_ticket_size',
            'available_funds',
            'capital_deployed_pct'
        ];
        paramFields.forEach(field => {
            const el = document.getElementById(`param-${field}`);
            if (el) {
                const val = el.value.trim();
                payload[field] = val ? val : '';
            }
        });

        try {
            const res  = await fetch('/api/investor/portfolio/save', {
                method : 'POST',
                headers: { 'Content-Type': 'application/json' },
                body   : JSON.stringify(payload)
            });
            const data = await res.json();
            if (data.success) {
                showToast('Portfolio profile saved!', 'success');
                updateStrength();
            } else {
                showToast(data.message || 'Save failed.', 'error');
            }
        } catch {
            showToast('Network error.', 'error');
        } finally {
            btn.disabled  = false;
            btn.innerHTML = orig;
        }
    };

    // ── Format ticket size hints ────────────────────────────────
    window.formatTicketHint = function (input, hintId) {
        const val = input.value.trim();
        const hint = document.getElementById(hintId);
        if (!hint) return;
        
        if (!val) {
            hint.textContent = '';
            return;
        }
        
        try {
            const num = parseInt(val);
            const formatted = new Intl.NumberFormat('en-IN', {
                style: 'currency',
                currency: 'INR',
                minimumFractionDigits: 0,
                maximumFractionDigits: 0
            }).format(num);
            hint.textContent = formatted;
        } catch {
            hint.textContent = '';
        }
    };

    // ── Helper ─────────────────────────────────────────────────
    function esc(s) {
        return String(s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    console.log('✅ investor_portfolio.js loaded');
})();