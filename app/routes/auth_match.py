"""
EISC — Match Routes Blueprint
Serves:
  GET  /dashboard/investor/matches        → investor sees matched startups
  GET  /dashboard/entrepreneur/matches    → entrepreneur sees matched investors
  POST /api/matches/recompute             → manual cache refresh (AJAX)
  POST /api/matches/express-interest      → investor expresses interest from match card
"""
from .extensions import *
from app.models.ai_matchmaking import (
    get_cached_investor_matches,
    get_cached_entrepreneur_matches,
    compute_matches_for_investor,
    compute_matches_for_entrepreneur,
    score_to_label,
)

match_auth = Blueprint('match_auth', '__name__')


# ─────────────────────────────────────────────────────────────────────
# INVESTOR MATCH PAGE — "Startup Matches"
# ─────────────────────────────────────────────────────────────────────

@match_auth.route('/dashboard/investor/matches')
def investor_matches():
    if 'user_id' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('login_signup_auth.login_signup'))

    email = session.get('user_email')
    print(f"🤝 Investor Matches → {email}")

    mycon  = get_db_connection()
    cursor = mycon.cursor(dictionary=True)

    # ── Investor profile (sidebar) ─────────────────────────────
    cursor.execute("""
        SELECT
            ld.email, ld.username,
            ip.full_name, ip.firm_name, ip.profile_image_url,
            ip.investment_focus, ip.total_investments, ip.startups_connected,
            ipp.investment_thesis, ipp.deal_criteria, ipp.portfolio_highlights,
            ipp.sector_expertise, ipp.preferred_sectors, ipp.investment_stage,
            ipp.min_ticket_size, ipp.max_ticket_size,
            ipp.available_funds, ipp.investment_utilization_pct
        FROM login_data ld
        LEFT JOIN investor_profiles ip ON ld.email = ip.email
        LEFT JOIN investor_portfolio_profile ipp ON ld.email = ipp.email
        WHERE ld.email = %s
    """, (email,))
    profile = cursor.fetchone()
    cursor.close()

    # ── Get / compute matches ──────────────────────────────────
    matches = get_cached_investor_matches(email, mycon, limit=20)

    # Attach score metadata to each match
    for m in matches:
        m['score_meta'] = score_to_label(float(m.get('score', 0)))

    # Check if investor has completed their portfolio (not just embeddings)
    # Portfolio is complete if they have at least one of: thesis, deal criteria, sectors, stage, or ticket size
    has_portfolio = profile and (
        profile.get('investment_thesis') or 
        profile.get('deal_criteria') or
        profile.get('preferred_sectors') or 
        profile.get('investment_stage') or
        profile.get('min_ticket_size')
    )
    
    print(f"📊 Investor Portfolio Check: {email}")
    if profile:
        print(f"  - Investment Thesis: {bool(profile.get('investment_thesis'))}")
        print(f"  - Deal Criteria: {bool(profile.get('deal_criteria'))}")
        print(f"  - Preferred Sectors: {bool(profile.get('preferred_sectors'))}")
        print(f"  - Investment Stage: {bool(profile.get('investment_stage'))}")
        print(f"  - Min Ticket Size: {bool(profile.get('min_ticket_size'))}")
        print(f"  - Has Portfolio: {has_portfolio}")
    else:
        print(f"  - No profile found!")
        has_portfolio = False
    
    mycon.close()

    return render_template(
        'auth/investor/investor_matches.html',
        active_nav    = 'matches',
        profile       = profile,
        matches       = matches,
        has_embedding = has_portfolio,
        unread_msgs   = get_unread_count(email),
        unread_notifs = get_notification_count(email),
    )


# ─────────────────────────────────────────────────────────────────────
# ENTREPRENEUR MATCH PAGE — "Investor Matches"
# ─────────────────────────────────────────────────────────────────────

@match_auth.route('/dashboard/entrepreneur/matches')
def entrepreneur_matches():
    if 'user_id' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('login_signup_auth.login_signup'))

    email = session.get('user_email')
    print(f"🤝 Entrepreneur Matches → {email}")

    mycon  = get_db_connection()
    cursor = mycon.cursor(dictionary=True)

    # ── Entrepreneur profile (sidebar) ────────────────────────
    cursor.execute("""
        SELECT
            ld.email, ld.username,
            ep.startup_name, ep.profile_image_url,
            ep.total_pitches, ep.investors_connected,
            ep.profile_views, ep.funding_required,
            ep.funding_progress_pct,
            pc.problem, pc.solution, pc.market, pc.business_model,
            pc.traction, pc.team, pc.financials, pc.the_ask
        FROM login_data ld
        LEFT JOIN entrepreneur_profile ep ON ld.email = ep.email
        LEFT JOIN pitch_content pc ON ld.email = pc.email
        WHERE ld.email = %s
    """, (email,))
    profile = cursor.fetchone()
    cursor.close()

    # ── Get / compute matches ──────────────────────────────────
    matches = get_cached_entrepreneur_matches(email, mycon, limit=20)

    # filter out any non-dict rows (shouldn't happen but guard against broken data)
    matches = [m for m in matches if isinstance(m, dict)]
    for m in matches:
        # ensure score_meta always exists to avoid template errors
        try:
            m['score_meta'] = score_to_label(float(m.get('score', 0)))
        except Exception:
            m['score_meta'] = score_to_label(0.0)

    # only show matches with score >= 0.30 (30%)
    original_count = len(matches)
    matches = [m for m in matches if float(m.get('score', 0)) >= 0.3]
    print(f"    - filtered {original_count} → {len(matches)} by score threshold")

    # Check if entrepreneur has completed their pitch deck (not just embeddings)
    # Pitch is complete if they have at least 3+ fields filled in
    has_pitch = profile and sum(bool(profile.get(field)) for field in [
        'problem', 'solution', 'market', 'business_model', 
        'traction', 'team', 'financials', 'the_ask'
    ]) >= 3
    
    print(f"📊 Entrepreneur Pitch Deck Check: {email}")
    if profile:
        pitch_fields = {
            'problem': bool(profile.get('problem')),
            'solution': bool(profile.get('solution')),
            'market': bool(profile.get('market')),
            'business_model': bool(profile.get('business_model')),
            'traction': bool(profile.get('traction')),
            'team': bool(profile.get('team')),
            'financials': bool(profile.get('financials')),
            'the_ask': bool(profile.get('the_ask'))
        }
        filled_count = sum(pitch_fields.values())
        print(f"  - Pitch Fields Filled: {filled_count}/8")
        for field, filled in pitch_fields.items():
            print(f"    • {field}: {filled}")
        print(f"  - Has Pitch (≥3): {has_pitch}")
    else:
        print(f"  - No profile found!")
        has_pitch = False
    
    mycon.close()

    return render_template(
        'auth/entrepreneur/entrepreneur_matches.html',
        active_nav    = 'matches',
        profile       = profile,
        matches       = matches,
        has_embedding = has_pitch,
        unread_msgs   = get_unread_count(email),
        unread_notifs = get_notification_count(email),
    )


# ─────────────────────────────────────────────────────────────────────
# API: Manual Recompute (AJAX button on page)
# ─────────────────────────────────────────────────────────────────────

@match_auth.route('/api/matches/recompute', methods=['POST'])
def recompute_matches():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    email = session.get('user_email')
    role  = session.get('role', '').lower()   # 'investor' | 'entrepreneur'

    print(f"🔄 Manual recompute: {role} {email}")
    mycon = get_db_connection()

    try:
        if role == 'investor':
            count = compute_matches_for_investor(email, mycon)
        elif role == 'entrepreneur':
            count = compute_matches_for_entrepreneur(email, mycon)
        else:
            return jsonify({'success': False, 'message': 'Unknown role.'}), 400

        mycon.close()
        return jsonify({'success': True, 'matches_found': count}), 200

    except Exception as e:
        print(f"❌ Recompute error: {e}")
        import traceback; traceback.print_exc()
        mycon.close()
        return jsonify({'success': False, 'message': 'Recompute failed. Try again.'}), 500


# ─────────────────────────────────────────────────────────────────────
# API: Express Interest (investor → startup, from match card)
# ─────────────────────────────────────────────────────────────────────

@match_auth.route('/api/matches/express-interest', methods=['POST'])
def express_interest():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    investor_email     = session.get('user_email')
    data               = request.get_json()
    entrepreneur_email = data.get('entrepreneur_email', '').strip()
    message            = data.get('message', '').strip()

    if not entrepreneur_email:
        return jsonify({'success': False, 'message': 'No entrepreneur specified.'}), 400

    try:
        mycon  = get_db_connection()
        cursor = mycon.cursor()
        cursor.execute("""
            INSERT INTO investor_interests
                (investor_email, entrepreneur_email, status, message)
            VALUES (%s, %s, 'pending', %s)
            ON CONFLICT (investor_email, entrepreneur_email) DO UPDATE SET
                status  = 'pending',
                message = EXCLUDED.message
        """, (investor_email, entrepreneur_email, message or None))

        # Optionally notify the entrepreneur
        cursor.execute("""
            INSERT INTO notifications
                (email, type, title, body, related_user_email)
            VALUES (%s, 'investor_interested',
                    'New investor interest!',
                    'An investor has expressed interest in your startup.',
                    %s)
        """, (entrepreneur_email, investor_email))

        mycon.commit()
        cursor.close()
        mycon.close()
        return jsonify({'success': True}), 200

    except Exception as e:
        print(f"❌ express_interest error: {e}")
        return jsonify({'success': False, 'message': 'Failed. Try again.'}), 500


# ─────────────────────────────────────────────────────────────────────
# API: Save Startup (investor bookmarks from match card)
# ─────────────────────────────────────────────────────────────────────

@match_auth.route('/api/matches/save-startup', methods=['POST'])
def save_startup():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    investor_email     = session.get('user_email')
    data               = request.get_json()
    entrepreneur_email = data.get('entrepreneur_email', '').strip()

    if not entrepreneur_email:
        return jsonify({'success': False, 'message': 'No entrepreneur specified.'}), 400

    try:
        mycon  = get_db_connection()
        cursor = mycon.cursor()
        cursor.execute("""
            INSERT INTO saved_startups (investor_email, entrepreneur_email)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, (investor_email, entrepreneur_email))
        mycon.commit()
        cursor.close()
        mycon.close()
        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"❌ save_startup error: {e}")
        return jsonify({'success': False, 'message': 'Failed.'}), 500


# ─────────────────────────────────────────────────────────────────────
# API: Request Connection (entrepreneur → investor)
# ─────────────────────────────────────────────────────────────────────

@match_auth.route('/api/matches/request-connection', methods=['POST'])
def request_connection():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    entrepreneur_email = session.get('user_email')
    data               = request.get_json()
    investor_email     = data.get('investor_email', '').strip()

    if not investor_email:
        return jsonify({'success': False, 'message': 'No investor specified.'}), 400

    try:
        mycon  = get_db_connection()
        cursor = mycon.cursor()

        # Insert connection request (entrepreneur → investor)
        cursor.execute("""
            INSERT INTO connections
                (entrepreneur_email, investor_email, status, requested_by)
            VALUES (%s, %s, 'pending', %s)
            ON CONFLICT (entrepreneur_email, investor_email) DO UPDATE SET
                status       = 'pending',
                requested_by = EXCLUDED.requested_by
        """, (entrepreneur_email, investor_email, entrepreneur_email))

        # Notify the investor
        cursor.execute("""
            INSERT INTO notifications
                (email, type, title, body, related_user_email)
            VALUES (%s, 'connection_request',
                    'New connection request',
                    'An entrepreneur wants to connect with you.',
                    %s)
        """, (investor_email, entrepreneur_email))

        mycon.commit()
        cursor.close()
        mycon.close()
        return jsonify({'success': True}), 200

    except Exception as e:
        print(f"❌ request_connection error: {e}")
        return jsonify({'success': False, 'message': 'Failed. Try again.'}), 500


# ─────────────────────────────────────────────────────────────────────
# API: Save Investor (entrepreneur bookmarks from match card)
# ─────────────────────────────────────────────────────────────────────

@match_auth.route('/api/matches/save-investor', methods=['POST'])
def save_investor():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    entrepreneur_email = session.get('user_email')
    data               = request.get_json()
    investor_email     = data.get('investor_email', '').strip()

    if not investor_email:
        return jsonify({'success': False, 'message': 'No investor specified.'}), 400

    try:
        mycon  = get_db_connection()
        cursor = mycon.cursor()
        cursor.execute("""
            INSERT INTO saved_investors (entrepreneur_email, investor_email)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, (entrepreneur_email, investor_email))
        mycon.commit()
        cursor.close()
        mycon.close()
        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"❌ save_investor error: {e}")
        return jsonify({'success': False, 'message': 'Failed.'}), 500

