/* ================================================================
   EISC — Pitch Deck Page JS
   AI Enhancement via /api/pitch/enhance (Flask → Anthropic API)
   ================================================================ */
(function () {
    'use strict';

    const SECTIONS = ['problem','solution','market','business','traction','team','financials','ask'];
    const FIELD_MAP = {
        problem: 'field-problem', solution: 'field-solution',
        market: 'field-market', business: 'field-business_model',
        traction: 'field-traction', team: 'field-team',
        financials: 'field-financials', ask: 'field-the_ask'
    };

    // ── Section accordion toggle ───────────────────────────────
    window.toggleSection = function(id) {
        const el = document.getElementById(`sec-${id}`);
        if (!el) return;
        const isOpen = el.classList.contains('open');
        // Close all
        SECTIONS.forEach(s => document.getElementById(`sec-${s}`)?.classList.remove('open'));
        // Open clicked if was closed
        if (!isOpen) el.classList.add('open');
    };

    // ── Word / char count ──────────────────────────────────────
    window.updateWordCount = function(secId, textarea) {
        const text  = textarea.value.trim();
        const words = text ? text.split(/\s+/).length : 0;
        const chars = textarea.value.length;

        const wcEl = document.getElementById(`wc-${secId}`);
        const ccEl = document.getElementById(`cc-${secId}`);
        if (wcEl) wcEl.textContent = `${words} word${words !== 1 ? 's' : ''}`;
        if (ccEl) ccEl.textContent = `${chars} characters`;

        updateCompleteness();
    };

    // Run on load
    SECTIONS.forEach(id => {
        const fieldId = FIELD_MAP[id];
        const ta = document.getElementById(fieldId);
        if (ta && ta.value.trim()) {
            updateWordCount(id, ta);
        }
    });

    // ── Pitch Completeness Ring ────────────────────────────────
    function updateCompleteness() {
        let filled = 0;
        SECTIONS.forEach(id => {
            const fieldId = FIELD_MAP[id];
            const ta = document.getElementById(fieldId);
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

        const pct     = Math.round((filled / SECTIONS.length) * 100);
        const ringEl  = document.getElementById('strengthRing');
        const pctEl   = document.getElementById('strengthPct');
        const circum  = 2 * Math.PI * 30; // r=30

        if (pctEl)  pctEl.textContent = `${pct}%`;
        if (ringEl) ringEl.style.strokeDashoffset = circum - (circum * pct / 100);

        // Color ring by strength
        if (ringEl) {
            if (pct < 40)       ringEl.style.stroke = '#ef4444';
            else if (pct < 70)  ringEl.style.stroke = '#f59e0b';
            else                ringEl.style.stroke = '#0d9488';
        }
    }

    // Initialise ring
    updateCompleteness();

    // ── Single section AI enhance ──────────────────────────────
    window.enhanceSection = async function(secId, fieldKey, sectionName) {
        const fieldId  = FIELD_MAP[secId];
        const textarea = document.getElementById(fieldId);
        const btn      = document.getElementById(`ai-btn-${secId}`);
        const resultBox = document.getElementById(`ai-result-${secId}`);

        if (!textarea || !textarea.value.trim()) {
            showToast(`Write something in "${sectionName}" first.`, 'error');
            return;
        }

        // Show thinking state
        btn.disabled  = true;
        btn.innerHTML = `<span style="display:flex;align-items:center;gap:5px">
            <span class="ai-thinking-dots">
                <span></span><span></span><span></span>
            </span> Enhancing…</span>`;

        resultBox.classList.remove('visible');
        resultBox.style.display = 'block';
        resultBox.classList.add('visible');
        document.getElementById(`ai-text-${secId}`).textContent = '';
        resultBox.querySelector('.ai-result-header').style.display = 'none';
        resultBox.innerHTML = `
            <div class="ai-thinking" style="margin-top:0;">
                <span>✨ AI is crafting a stronger version…</span>
                <div class="ai-thinking-dots"><span></span><span></span><span></span></div>
            </div>`;

        try {
            const res = await fetch('/api/pitch/enhance', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    section: sectionName,
                    content: textarea.value.trim(),
                    startup_name: getStartupContext()
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
                            <button class="ai-accept-btn" onclick="acceptAiResult('${secId}', '${fieldKey}')">Use This</button>
                            <button class="ai-dismiss-btn" onclick="dismissAiResult('${secId}')">Dismiss</button>
                        </div>
                    </div>
                    <div class="ai-result-text" id="ai-text-${secId}">${esc(data.enhanced)}</div>`;
            } else {
                resultBox.innerHTML = `<div style="font-size:0.82rem;color:#ef4444">${data.message || 'AI enhancement failed. Try again.'}</div>`;
            }
        } catch (err) {
            resultBox.innerHTML = `<div style="font-size:0.82rem;color:#ef4444">Network error. Please try again.</div>`;
        } finally {
            btn.disabled = false;
            btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" style="width:12px;height:12px"><path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"/></svg> ✨ Enhance with AI`;
        }
    };

    // ── Accept AI result → replace textarea ───────────────────
    window.acceptAiResult = function(secId, fieldKey) {
        const fieldId  = FIELD_MAP[secId];
        const textarea = document.getElementById(fieldId);
        const textEl   = document.getElementById(`ai-text-${secId}`);
        if (textarea && textEl) {
            textarea.value = textEl.textContent;
            updateWordCount(secId, textarea);
            dismissAiResult(secId);
            showToast('AI version applied!', 'success');
        }
    };

    window.dismissAiResult = function(secId) {
        const box = document.getElementById(`ai-result-${secId}`);
        if (box) { box.classList.remove('visible'); box.style.display = 'none'; }
    };

    // ── Enhance ALL sections ───────────────────────────────────
    window.enhanceAllSections = async function() {
        const btn  = document.getElementById('globalAiBtn');
        const orig = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = `<span style="display:flex;align-items:center;gap:7px">
            <span class="ai-thinking-dots"><span></span><span></span><span></span></span>
            Enhancing All…</span>`;

        const sectionLabels = {
            problem: 'Problem', solution: 'Solution', market: 'Market Opportunity',
            business: 'Business Model', traction: 'Traction', team: 'Team',
            financials: 'Financials', ask: 'The Ask'
        };

        for (const secId of SECTIONS) {
            const fieldId  = FIELD_MAP[secId];
            const textarea = document.getElementById(fieldId);
            if (!textarea || !textarea.value.trim()) continue;

            // Open this section
            SECTIONS.forEach(s => document.getElementById(`sec-${s}`)?.classList.remove('open'));
            document.getElementById(`sec-${secId}`)?.classList.add('open');

            await enhanceSection(secId, FIELD_MAP[secId].replace('field-',''), sectionLabels[secId]);
            await new Promise(r => setTimeout(r, 400)); // brief pause between calls
        }

        btn.disabled = false;
        btn.innerHTML = orig;
        showToast('All sections enhanced!', 'success');
    };

    // ── Save pitch ─────────────────────────────────────────────
    window.savePitch = async function() {
        const btn  = document.getElementById('savePitchBtn');
        const orig = btn.innerHTML;
        btn.disabled = true;
        btn.textContent = 'Saving…';

        const payload = {};
        for (const [secId, fieldId] of Object.entries(FIELD_MAP)) {
            const ta = document.getElementById(fieldId);
            if (ta) payload[fieldId.replace('field-','')] = ta.value.trim();
        }

        // Add video URL
        const videoUrl = document.getElementById('videoUrlInput')?.value.trim();
        if (videoUrl) payload.video_pitch_url = videoUrl;

        try {
            const res  = await fetch('/api/pitch/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (data.success) {
                showToast('Pitch saved!', 'success');
                updateCompleteness();
            } else {
                showToast(data.message || 'Save failed.', 'error');
            }
        } catch {
            showToast('Network error.', 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = orig;
        }
    };

    // ── Save Deck URL ──────────────────────────────────────────
    window.saveDeckUrl = async function() {
        const url = document.getElementById('deckUrlInput')?.value.trim();
        if (!url) { showToast('Please enter a deck URL first.', 'error'); return; }

        try {
            const res  = await fetch('/api/pitch/deck-url', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pitch_deck_url: url })
            });
            const data = await res.json();
            if (data.success) showToast('Deck link saved!', 'success');
            else showToast(data.message || 'Failed.', 'error');
        } catch {
            showToast('Network error.', 'error');
        }
    };

    // ── Video Drag & Drop ──────────────────────────────────────
    window.handleDragOver = function(e) {
        e.preventDefault();
        document.getElementById('videoDropZone')?.classList.add('drag-over');
    };
    window.handleDragLeave = function() {
        document.getElementById('videoDropZone')?.classList.remove('drag-over');
    };
    window.handleDrop = function(e) {
        e.preventDefault();
        document.getElementById('videoDropZone')?.classList.remove('drag-over');
        const file = e.dataTransfer.files[0];
        if (file && file.type.startsWith('video/')) processVideoFile(file);
        else showToast('Please drop a video file.', 'error');
    };

    window.handleVideoUpload = function(input) {
        if (input.files && input.files[0]) processVideoFile(input.files[0]);
    };

    function processVideoFile(file) {
        const MAX = 200 * 1024 * 1024; // 200MB
        if (file.size > MAX) { showToast('Video too large (max 200MB).', 'error'); return; }

        // Simulate upload progress (replace with real fetch FormData upload)
        const progressWrap = document.getElementById('uploadProgress');
        const progressFill = document.getElementById('uploadFill');
        const progressText = document.getElementById('uploadText');
        const dropZone     = document.getElementById('videoDropZone');
        const previewWrap  = document.getElementById('videoPreviewWrap');
        const preview      = document.getElementById('videoPreview');
        const fileName     = document.getElementById('videoFileName');

        dropZone.style.display = 'none';
        progressWrap.classList.add('visible');

        let pct = 0;
        const interval = setInterval(() => {
            pct += Math.random() * 15;
            if (pct >= 100) {
                pct = 100;
                clearInterval(interval);

                // Show preview
                progressWrap.classList.remove('visible');
                previewWrap.classList.add('visible');

                const objectUrl = URL.createObjectURL(file);
                preview.src = objectUrl;
                fileName.textContent = file.name;
                showToast('Video uploaded!', 'success');

                // In production: upload via FormData to /api/pitch/video-upload
                uploadVideoToServer(file);
            }
            progressFill.style.width = pct + '%';
            progressText.textContent = `Uploading… ${Math.round(pct)}%`;
        }, 150);
    }

    async function uploadVideoToServer(file) {
        const formData = new FormData();
        formData.append('video', file);
        try {
            const res = await fetch('/api/pitch/video-upload', { method: 'POST', body: formData });
            const data = await res.json();
            if (data.success && data.video_url) {
                // Store the URL in the URL input for reference
                const urlInput = document.getElementById('videoUrlInput');
                if (urlInput) urlInput.value = data.video_url;
            }
        } catch { /* local preview still shown */ }
    }

    window.removeVideo = function() {
        const previewWrap = document.getElementById('videoPreviewWrap');
        const dropZone    = document.getElementById('videoDropZone');
        const preview     = document.getElementById('videoPreview');
        const fileInput   = document.getElementById('videoFileInput');

        if (preview.src) { URL.revokeObjectURL(preview.src); preview.src = ''; }
        previewWrap.classList.remove('visible');
        dropZone.style.display = '';
        if (fileInput) fileInput.value = '';
        showToast('Video removed.', 'default');
    };

    // ── Validate video URL ─────────────────────────────────────
    window.validateVideoUrl = function(input) {
        const val = input.value.trim();
        const isValid = !val || /^https?:\/\//.test(val);
        input.style.borderColor = isValid ? '' : '#ef4444';
    };

    // ── Startup context for AI ─────────────────────────────────
    function getStartupContext() {
        // Try to get from the sidebar if on feed/home, or from a meta tag
        return document.querySelector('meta[name="startup-name"]')?.content
            || document.getElementById('sidebarStartup')?.textContent?.trim()
            || '';
    }

    // ── Helper ────────────────────────────────────────────────
    function esc(s) {
        return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    console.log('✅ pitch_deck.js loaded');
})();