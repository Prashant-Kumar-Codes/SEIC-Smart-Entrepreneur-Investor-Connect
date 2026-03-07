/* ================================================================
   EISC — My Profile Page JS
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
            const panel = document.getElementById(`tab-${tab}`);
            if (panel) panel.classList.add('active');
        });
    });

    // ── Bio char count ─────────────────────────────────────────
    const bioTextarea = document.getElementById('ep_bio');
    const bioCount    = document.getElementById('bioCharCount');
    if (bioTextarea && bioCount) {
        const updateBioCount = () => {
            const len = bioTextarea.value.length;
            bioCount.textContent = `${len} / 500`;
            bioCount.style.color = len > 450 ? '#ef4444' : 'var(--text-muted)';
        };
        updateBioCount();
        bioTextarea.addEventListener('input', updateBioCount);
    }

    // ── Avatar preview ─────────────────────────────────────────
    window.previewAvatar = function(input) {
        if (!input.files || !input.files[0]) return;
        const file   = input.files[0];
        const reader = new FileReader();
        reader.onload = (e) => {
            // Modal preview
            const preview = document.getElementById('modalAvatarPreview');
            if (preview) {
                preview.innerHTML = `<img src="${e.target.result}" alt="Avatar preview" style="width:100%;height:100%;object-fit:cover;border-radius:50%">`;
            }
        };
        reader.readAsDataURL(file);
    };

    // ── Edit Profile Form submit ────────────────────────────────
    const form = document.getElementById('editProfileForm');
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn  = document.getElementById('profileSaveBtn');
            const orig = btn.textContent;
            
            // Visual feedback: Start saving
            btn.disabled = true; 
            btn.textContent = 'Saving...';
            showToast('Saving your profile changes...', 'default');

            // Collect form values
            const payload = {
                username:          document.getElementById('ep_username')?.value.trim()        || '',
                bio:               document.getElementById('ep_bio')?.value.trim()              || '',
                location:          document.getElementById('ep_location')?.value.trim()         || '',
                focus_areas:       document.getElementById('ep_focus')?.value.trim()            || '',
                startup_name:      document.getElementById('ep_startup_name')?.value.trim()     || '',
                industry:          document.getElementById('ep_industry')?.value.trim()          || '',
                stage:             document.getElementById('ep_stage')?.value                    || '',
                founded_year:      document.getElementById('ep_founded')?.value                  || '',
                team_size:         document.getElementById('ep_team_size')?.value               || '',
                funding_amount:    document.getElementById('ep_funding_amount')?.value          || '',
                funding_currency:  document.getElementById('ep_funding_currency')?.value        || 'INR',
                use_of_funds:      document.getElementById('ep_use_of_funds')?.value.trim()    || '',
                funding_progress_pct: document.getElementById('ep_progress')?.value            || '',
                website_url:       document.getElementById('ep_website')?.value.trim()          || '',
                linkedin_url:      document.getElementById('ep_linkedin')?.value.trim()         || '',
                twitter_url:       document.getElementById('ep_twitter')?.value.trim()          || '',
                pitch_deck_url:    document.getElementById('ep_deck_url')?.value.trim()        || '',
                demo_url:          document.getElementById('ep_demo_url')?.value.trim()        || '',
                video_pitch_url:   document.getElementById('ep_video_pitch')?.value.trim()     || '',
            };

            try {
                const res  = await fetch('/api/profile/edit/full', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (data.success) {
                    showToast('Profile updated successfully!', 'success');
                    closeModal('editProfileModal');
                    updateProfileDisplay(payload);
                } else {
                    showToast(data.message || 'Failed to save changes.', 'error');
                }
            } catch (err) {
                console.error('Save error:', err);
                showToast('Network error while saving.', 'error');
            } finally {
                btn.disabled = false; 
                btn.textContent = orig;
            }
        });
    }

    // ── Update displayed profile live after save ───────────────
    function updateProfileDisplay(p) {
        // Name
        const nameEl = document.getElementById('displayName');
        if (nameEl && p.username) nameEl.textContent = p.username;

        // Tagline
        const taglineEl = document.getElementById('displayTagline');
        if (taglineEl) {
            if (p.startup_name) {
                taglineEl.innerHTML = `Founder & CEO at <strong>${esc(p.startup_name)}</strong>${p.industry ? ' · ' + esc(p.industry) : ''}`;
            }
        }

        // Bio
        const bioEl = document.getElementById('displayBio');
        if (bioEl) {
            if (p.bio) {
                bioEl.textContent = p.bio;
                bioEl.className = 'profile-bio-text';
            } else {
                bioEl.textContent = 'Add a compelling bio…';
                bioEl.className = 'profile-bio-empty';
            }
        }

        // Startup detail fields
        const fieldMap = {
            'dispStartupName': p.startup_name,
            'dispIndustry':    p.industry,
            'dispStage':       p.stage ? p.stage.replace(/-/g,' ').replace(/\b\w/g, c => c.toUpperCase()) : '',
            'dispLocation':    p.location,
            'dispFounded':     p.founded_year,
            'dispTeam':        p.team_size,
        };
        for (const [id, val] of Object.entries(fieldMap)) {
            const el = document.getElementById(id);
            if (!el) continue;
            if (val) { el.textContent = val; el.classList.remove('empty'); }
            else      { el.textContent = 'Not specified'; el.classList.add('empty'); }
        }

        // Location in meta
        const locEl = document.getElementById('displayLocation');
        if (locEl && p.location) locEl.textContent = p.location;

        // Funding
        if (p.funding_amount) {
            const sym = { INR: '₹', USD: '$', EUR: '€', GBP: '£' }[p.funding_currency] || '';
            const formatted = sym + Number(p.funding_amount).toLocaleString('en-IN');
            const amtEl = document.getElementById('dispFundingAmt');
            if (amtEl) amtEl.textContent = formatted;
        }
        const pctEl   = document.getElementById('dispFundingPct');
        const fillEl  = document.getElementById('fundingFill');
        const uofEl   = document.getElementById('dispUseOfFunds');
        if (pctEl  && p.funding_progress_pct) pctEl.textContent  = p.funding_progress_pct + '%';
        if (fillEl && p.funding_progress_pct) fillEl.style.width = p.funding_progress_pct + '%';
        if (uofEl  && p.use_of_funds)         uofEl.textContent  = p.use_of_funds;

        // Focus tags
        const tagsEl = document.getElementById('displayTags');
        if (tagsEl && p.focus_areas) {
            tagsEl.innerHTML = p.focus_areas.split(',')
                .map(t => t.trim()).filter(Boolean)
                .map(t => `<span class="profile-skill-tag">${esc(t)}</span>`)
                .join('');
        }

        showToast('Profile updated!', 'success');
    }

    // ── Copy profile link ──────────────────────────────────────
    window.copyProfileLink = function() {
        const url = window.location.origin + '/profile/' + encodeURIComponent(document.getElementById('displayName')?.textContent || '');
        navigator.clipboard.writeText(url).then(() => {
            showToast('Profile link copied!', 'success');
        }).catch(() => {
            showToast('Copy failed — try manually.', 'error');
        });
    };

    // ── Helper ────────────────────────────────────────────────
    function esc(s) {
        return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    console.log('✅ my_profile.js loaded');
})();