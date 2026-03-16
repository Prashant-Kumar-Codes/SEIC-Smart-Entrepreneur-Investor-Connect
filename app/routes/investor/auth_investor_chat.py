"""
EISC — Investor AI Chat Blueprint
Route prefix: /dashboard/investor/ai-chat  (page)
API prefix:   /api/investor/chat/...

Two modes:
  guidance       → AI gets INVESTOR profile only
  intermediate   → User selects saved startup → AI gets BOTH
                   investor profile + startup profile + pitch content
"""
from ..extensions import *
import json

investor_chat_auth = Blueprint('investor_chat_auth', '__name__')


# ─────────────────────────────────────────────────────────────────────
# GEMINI CLIENT  (re-uses same helper pattern as entrepreneur chat)
# ─────────────────────────────────────────────────────────────────────
_gemini_client = None

def get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        import os
        from google import genai
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            raise RuntimeError('GEMINI_API_KEY not set in environment variables.')
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


# =====================================================================
# PAGE
# =====================================================================

@investor_chat_auth.route('/dashboard/investor/ai-chat')
def investor_chat_page():
    if 'user_id' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('login_signup_auth.login_signup'))

    email = session.get('user_email')
    print(f"💎 Investor AI Chat → {email}")

    mycon  = get_db_connection()
    cursor = mycon.cursor(cursor_factory=RealDictCursor)

    # ── Investor full profile (for AI context + sidebar) ──────────
    cursor.execute("""
        SELECT
            ld.email, ld.username,
            ip.full_name, ip.firm_name, ip.profile_image_url,
            ip.investment_focus, ip.geography, ip.bio,
            ip.investor_type, ip.total_investments, ip.startups_connected,
            ip.location, ip.years_of_experience, ip.current_position,
            ipp.preferred_sectors, ipp.investment_stage,
            ipp.min_ticket_size, ipp.max_ticket_size,
            ipp.investment_thesis, ipp.portfolio_highlights,
            ipp.available_funds, ipp.investment_utilization_pct
        FROM login_data ld
        LEFT JOIN investor_profiles ip ON ld.email = ip.email
        LEFT JOIN investor_portfolio_profile ipp ON ld.email = ipp.email
        WHERE ld.email = %s
    """, (email,))
    profile = cursor.fetchone()

    # ── Saved startups (for selector popup in intermediate mode) ──
    # Fetch startups that investor has saved
    cursor.execute("""
        SELECT DISTINCT
            ep.email              AS entrepreneur_email,
            ld.username           AS entrepreneur_name,
            ep.startup_name,
            ep.profile_image_url,
            ep.industry,
            ep.stage,
            ep.funding_required
        FROM entrepreneur_profile ep
        JOIN login_data ld ON ep.email = ld.email
        WHERE ep.email IN (
            SELECT entrepreneur_email FROM saved_startups
            WHERE investor_email = %s
        )
        ORDER BY ep.startup_name
        LIMIT 30
    """, (email,))
    saved_startups = cursor.fetchall() or []

    cursor.close(); mycon.close()

    return render_template(
        'auth/investor/investor_ai_chat.html',
        active_nav              = 'ai',
        profile                 = profile,
        saved_startups          = saved_startups,
        unread_msgs             = get_unread_count(email),
        unread_notifs           = get_notification_count(email),
    )


# =====================================================================
# LIST SESSIONS
# =====================================================================

@investor_chat_auth.route('/api/investor/chat/sessions', methods=['GET'])
def investor_list_sessions():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    email = session.get('user_email')
    mode  = request.args.get('mode', 'guidance')

    try:
        mycon  = get_db_connection()
        cursor = mycon.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT
                s.session_id,
                s.mode,
                s.entrepreneur_email,
                s.title,
                s.created_at,
                s.updated_at,
                (SELECT content FROM inv_chat_messages
                 WHERE session_id = s.session_id
                 ORDER BY created_at DESC LIMIT 1) AS last_message
            FROM inv_chat_sessions s
            WHERE s.investor_email = %s
              AND s.mode = %s
            ORDER BY s.updated_at DESC
            LIMIT 20
        """, (email, mode))
        sessions = cursor.fetchall() or []
        cursor.close(); mycon.close()

        for s in sessions:
            for k in ('created_at', 'updated_at'):
                if s.get(k):
                    s[k] = s[k].strftime('%Y-%m-%d %H:%M:%S')

        return jsonify({'success': True, 'sessions': sessions}), 200

    except Exception as e:
        print(f"❌ Investor list sessions: {e}")
        return jsonify({'success': False, 'message': 'Failed to load sessions.'}), 500


# =====================================================================
# GET HISTORY
# =====================================================================

@investor_chat_auth.route('/api/investor/chat/history', methods=['GET'])
def investor_chat_history():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    email      = session.get('user_email')
    session_id = request.args.get('session_id', '').strip()
    mode       = request.args.get('mode', 'guidance')

    if not session_id:
        return jsonify({'success': True, 'messages': []}), 200

    try:
        mycon  = get_db_connection()
        cursor = mycon.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT role, content, created_at
            FROM inv_chat_messages
            WHERE session_id    = %s
              AND investor_email = %s
              AND mode           = %s
            ORDER BY created_at ASC
            LIMIT 60
        """, (session_id, email, mode))
        messages = cursor.fetchall() or []
        cursor.close(); mycon.close()

        for m in messages:
            if m.get('created_at'):
                m['created_at'] = m['created_at'].strftime('%Y-%m-%d %H:%M:%S')

        return jsonify({'success': True, 'messages': messages}), 200

    except Exception as e:
        print(f"❌ Investor chat history: {e}")
        return jsonify({'success': False, 'message': 'Failed to load history.'}), 500


# =====================================================================
# SEND MESSAGE  — core AI call
# =====================================================================

@investor_chat_auth.route('/api/investor/chat/send', methods=['POST'])
def investor_send_message():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    email = session.get('user_email')
    data  = request.get_json()

    mode                 = data.get('mode', 'guidance')            # guidance | intermediate
    user_message         = data.get('message', '').strip()
    session_id           = data.get('session_id', '').strip()
    entrepreneur_email   = data.get('entrepreneur_email', '').strip()

    if not user_message:
        return jsonify({'success': False, 'message': 'Empty message.'}), 400

    # Intermediate mode requires a selected startup founder
    if mode == 'intermediate' and not entrepreneur_email:
        return jsonify({'success': False, 'message': 'Please select a startup founder first.'}), 400

    try:
        from google.genai import types

        mycon  = get_db_connection()
        cursor = mycon.cursor(cursor_factory=RealDictCursor)

        # ── Load investor profile ──────────────────────────────────
        cursor.execute("""
            SELECT
                ld.email, ld.username,
                ip.full_name, ip.firm_name, ip.bio, ip.investor_type,
                ip.investment_focus, ip.geography,
                ip.location, ip.years_of_experience, ip.current_position,
                ip.total_investments,
                ipp.preferred_sectors, ipp.investment_stage,
                ipp.min_ticket_size, ipp.max_ticket_size,
                ipp.investment_thesis, ipp.portfolio_highlights,
                ipp.available_funds
            FROM login_data ld
            LEFT JOIN investor_profiles ip ON ld.email = ip.email
            LEFT JOIN investor_portfolio_profile ipp ON ld.email = ipp.email
            WHERE ld.email = %s
        """, (email,))
        investor = cursor.fetchone() or {}

        # ── Create session if new ──────────────────────────────────
        if not session_id:
            import uuid
            session_id = uuid.uuid4().hex
            title      = _inv_session_title(mode, user_message, investor, entrepreneur_email)
            cursor.execute("""
                INSERT INTO inv_chat_sessions
                    (session_id, investor_email, mode, entrepreneur_email, title)
                VALUES (%s, %s, %s, %s, %s)
            """, (session_id, email, mode,
                  entrepreneur_email or None, title))
            mycon.commit()

        # ── Load recent history (last 16 rows = 8 exchanges) ──────
        cursor.execute("""
            SELECT role, content
            FROM inv_chat_messages
            WHERE session_id = %s
            ORDER BY created_at DESC
            LIMIT 16
        """, (session_id,))
        recent = list(reversed(cursor.fetchall()))

        # ── Build prompt based on mode ─────────────────────────────
        if mode == 'guidance':
            system_prompt, contents = _build_investor_guidance_prompt(
                investor, recent, user_message
            )
        else:
            # Load entrepreneur profile + pitch
            cursor.execute("""
                SELECT
                    ld.email, ld.username,
                    ep.startup_name, ep.bio, ep.industry, ep.stage,
                    ep.location, ep.team_size, ep.founded_year,
                    ep.funding_amount, ep.funding_currency, ep.funding_required,
                    ep.use_of_funds, ep.focus_areas
                FROM login_data ld
                LEFT JOIN entrepreneur_profile ep ON ld.email = ep.email
                WHERE ld.email = %s
            """, (entrepreneur_email,))
            entrepreneur = cursor.fetchone() or {}

            cursor.execute("""
                SELECT problem, solution, market, business_model,
                       traction, team, financials, the_ask
                FROM pitch_content
                WHERE email = %s
            """, (entrepreneur_email,))
            pitch = cursor.fetchone() or {}

            system_prompt, contents = _build_startup_analysis_prompt(
                investor, entrepreneur, pitch, recent, user_message
            )

        # ── Call Gemini ────────────────────────────────────────────
        client   = get_gemini_client()
        response = client.models.generate_content(
            model   = "gemini-2.5-flash",
            contents= contents,
            config  = types.GenerateContentConfig(
                system_instruction = system_prompt,
                max_output_tokens  = 3000,
                temperature        = 0.42,
            )
        )

        ai_reply = response.text.strip()
        if not ai_reply:
            raise ValueError("Empty AI response from Gemini")

        # ── Persist both turns ─────────────────────────────────────
        cursor.execute("""
            INSERT INTO inv_chat_messages
                (session_id, investor_email, mode, role, content)
            VALUES (%s, %s, %s, 'user', %s)
        """, (session_id, email, mode, user_message))

        cursor.execute("""
            INSERT INTO inv_chat_messages
                (session_id, investor_email, mode, role, content)
            VALUES (%s, %s, %s, 'assistant', %s)
        """, (session_id, email, mode, ai_reply))

        cursor.execute("""
            UPDATE inv_chat_sessions
            SET updated_at = NOW()
            WHERE session_id = %s
        """, (session_id,))

        mycon.commit()
        cursor.close(); mycon.close()

        print(f"✅ Investor AI chat [{mode}] for {email} — session {session_id[:8]}")
        return jsonify({
            'success'   : True,
            'reply'     : ai_reply,
            'session_id': session_id,
        }), 200

    except Exception as e:
        err = str(e).lower()
        print(f"❌ Investor chat send error: {e}")
        import traceback; traceback.print_exc()

        if any(x in err for x in ['api key', 'authentication', '401']):
            msg = 'AI service configuration error. Contact admin.'
        elif any(x in err for x in ['quota', 'rate limit', '429']):
            msg = 'AI rate limit reached. Please try again shortly.'
        elif any(x in err for x in ['blocked', 'safety']):
            msg = 'Request blocked by AI safety filters.'
        else:
            msg = 'AI is unavailable right now. Please try again.'

        return jsonify({'success': False, 'message': msg}), 500


# =====================================================================
# DELETE SESSION
# =====================================================================

@investor_chat_auth.route('/api/investor/chat/session/delete', methods=['POST'])
def investor_delete_session():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    email      = session.get('user_email')
    data       = request.get_json()
    session_id = data.get('session_id', '').strip()

    if not session_id:
        return jsonify({'success': False, 'message': 'No session_id provided.'}), 400

    try:
        mycon  = get_db_connection()
        cursor = mycon.cursor()
        cursor.execute("""
            DELETE FROM inv_chat_sessions
            WHERE session_id = %s AND investor_email = %s
        """, (session_id, email))
        mycon.commit()
        cursor.close(); mycon.close()
        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"❌ Investor delete session: {e}")
        return jsonify({'success': False, 'message': 'Delete failed.'}), 500


# =====================================================================
# INTERNAL HELPERS
# =====================================================================

def _inv_session_title(mode, first_message, investor, entrepreneur_email):
    """Generate a session title for the sidebar."""
    if mode == 'guidance':
        snippet = first_message[:42] + ('…' if len(first_message) > 42 else '')
        return f"Guidance: {snippet}"
    else:
        return f"Startup Analysis: {(entrepreneur_email or 'Unknown')[:24]}"


def _investor_summary(investor):
    """Compact text block describing the investor for AI context."""
    inv = investor or {}
    lines = [
        f"Name: {inv.get('full_name') or inv.get('username', 'N/A')}",
        f"Type: {inv.get('investor_type', 'N/A')}",
        f"Firm/Fund: {inv.get('firm_name', 'N/A')}",
        f"Current Role: {inv.get('current_position', 'N/A')}",
        f"Experience: {inv.get('years_of_experience', 'N/A')} years",
        f"Location: {inv.get('location', 'N/A')}",
        f"Geography of Investment: {inv.get('geography', 'N/A')}",
        f"Investment Focus: {inv.get('investment_focus', 'N/A')}",
        f"Preferred Sectors: {inv.get('preferred_sectors', 'N/A')}",
        f"Investment Stage: {inv.get('investment_stage', 'N/A')}",
        f"Ticket Size: {inv.get('min_ticket_size', 'N/A')} – {inv.get('max_ticket_size', 'N/A')}",
        f"Available Funds: {inv.get('available_funds', 'N/A')}",
        f"Total Investments Made: {inv.get('total_investments', 'N/A')}",
        f"Bio: {inv.get('bio', 'N/A')}",
        f"Investment Thesis: {inv.get('investment_thesis', 'N/A')}",
        f"Portfolio Highlights: {inv.get('portfolio_highlights', 'N/A')}",
    ]
    return "\n".join(lines)


def _entrepreneur_summary(entrepreneur, pitch):
    """Compact text block describing the entrepreneur + pitch for AI context."""
    ent = entrepreneur or {}
    pc  = pitch or {}
    lines = [
        f"Founder: {ent.get('username', 'N/A')}",
        f"Startup: {ent.get('startup_name', 'N/A')}",
        f"Industry: {ent.get('industry', 'N/A')}",
        f"Stage: {ent.get('stage', 'N/A')}",
        f"Location: {ent.get('location', 'N/A')}",
        f"Team Size: {ent.get('team_size', 'N/A')}",
        f"Founded: {ent.get('founded_year', 'N/A')}",
        f"Funding Ask: {ent.get('funding_currency','INR')} {ent.get('funding_amount','N/A')} ({ent.get('funding_required','N/A')})",
        f"Use of Funds: {ent.get('use_of_funds', 'N/A')}",
        f"Focus Areas: {ent.get('focus_areas', 'N/A')}",
        f"Bio: {ent.get('bio', 'N/A')}",
        "",
        "── Pitch Deck ──",
        f"Problem:        {pc.get('problem', 'N/A')}",
        f"Solution:       {pc.get('solution', 'N/A')}",
        f"Market:         {pc.get('market', 'N/A')}",
        f"Business Model: {pc.get('business_model', 'N/A')}",
        f"Traction:       {pc.get('traction', 'N/A')}",
        f"Team:           {pc.get('team', 'N/A')}",
        f"Financials:     {pc.get('financials', 'N/A')}",
        f"The Ask:        {pc.get('the_ask', 'N/A')}",
    ]
    return "\n".join(lines)


def _history_to_gemini(recent):
    """Convert DB rows → Gemini contents list (oldest first)."""
    contents = []
    for row in recent:
        role = "user" if row['role'] == 'user' else "model"
        contents.append({"role": role, "parts": [{"text": row['content']}]})
    return contents


def _build_investor_guidance_prompt(investor, recent, user_message):
    """
    Guidance mode: AI advisor that knows the investor's thesis,
    portfolio, and preferences — helps with deal evaluation, DD,
    term sheets, market research, etc.
    """
    system_prompt = (
        "You are an elite investment advisor with 25+ years of experience across "
        "venture capital, angel investing, and private equity. You have deep expertise "
        "in deal sourcing, due diligence, valuation, term sheets, portfolio management, "
        "and market analysis across all major sectors. "
        "You know this investor's profile, thesis, and portfolio intimately. "
        "Give direct, specific, actionable advice. Reference the investor's actual "
        "preferences and thesis when relevant. "
        "Format responses cleanly with line breaks. Use bullet points for lists. "
        "Be the kind of advisor that a top-tier investor would actually pay for.\n\n"
        "INVESTOR PROFILE:\n"
        f"{_investor_summary(investor)}"
    )

    contents = _history_to_gemini(recent)
    contents.append({"role": "user", "parts": [{"text": user_message}]})
    return system_prompt, contents


def _build_startup_analysis_prompt(investor, entrepreneur, pitch, recent, user_message):
    """
    Entrepreneur/Startup mode: AI has full context on BOTH the investor
    and the selected entrepreneur + their pitch deck. Helps the investor
    evaluate fit, prepare questions, assess risk, structure the deal.
    """
    system_prompt = (
        "You are an AI investment analysis assistant with full context on both "
        "the investor and the startup being evaluated. You help the investor:\n"
        "  • Assess strategic and financial fit between their thesis and the startup\n"
        "  • Identify strengths, weaknesses, red flags, and opportunities in the pitch\n"
        "  • Prepare smart due diligence questions specific to this startup\n"
        "  • Think through valuation and deal structuring\n"
        "  • Craft effective communication strategy for the relationship\n\n"
        "Be analytical, balanced, and direct. Reference both profiles specifically. "
        "Highlight mismatches (stage, ticket, sector) honestly but constructively. "
        "Format responses cleanly. Use bullet points where helpful.\n\n"
        "══ INVESTOR PROFILE ══\n"
        f"{_investor_summary(investor)}"
        "\n\n"
        "══ STARTUP / ENTREPRENEUR PROFILE ══\n"
        f"{_entrepreneur_summary(entrepreneur, pitch)}"
    )

    contents = _history_to_gemini(recent)
    contents.append({"role": "user", "parts": [{"text": user_message}]})
    return system_prompt, contents

