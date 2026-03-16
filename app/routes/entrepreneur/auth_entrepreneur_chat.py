from ..extensions import *
import json

entrepreneur_chat_auth = Blueprint('entrepreneur_chat_auth', '__name__')


# =====================================================================
# CHAT PAGE
# =====================================================================

@entrepreneur_chat_auth.route('/dashboard/entrepreneur/ai-chat')
def chat_page():
    if 'user_id' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('login_signup_auth.login_signup'))

    email = session.get('user_email')
    print(f"💬 AI Chat → {email}")

    mycon  = get_db_connection()
    cursor = mycon.cursor(cursor_factory=RealDictCursor)

    # Profile (for sidebar + AI context)
    cursor.execute("""
        SELECT ld.email, ld.username,
               ep.startup_name, ep.profile_image_url,
               ep.total_pitches, ep.investors_connected, ep.profile_views,
               ep.funding_required, ep.funding_progress_pct,
               ep.stage, ep.industry, ep.location, ep.bio,
               ep.focus_areas, ep.funding_amount, ep.funding_currency,
               ep.use_of_funds, ep.team_size, ep.founded_year
        FROM login_data ld
        LEFT JOIN entrepreneur_profile ep ON ld.email = ep.email
        WHERE ld.email = %s
    """, (email,))
    profile = cursor.fetchone()

    # Pitch content (for AI context)
    cursor.execute("SELECT * FROM pitch_content WHERE email = %s", (email,))
    pitch = cursor.fetchone() or {}

    # Saved investors (for selector in intermediary mode)
    cursor.execute("""
        SELECT DISTINCT
            ip.email            AS investor_email,
            ip.full_name        AS investor_name,
            ip.firm_name,
            ip.profile_image_url,
            ipp.preferred_sectors,
            ipp.investment_stage,
            ipp.min_ticket_size,
            ipp.max_ticket_size,
            ip.geography,
            ipp.investment_thesis,
            ipp.portfolio_highlights
        FROM investor_profiles ip
        LEFT JOIN investor_portfolio_profile ipp ON ip.email = ipp.email
        JOIN login_data ld ON ip.email = ld.email
        WHERE ip.email IN (
            SELECT investor_email FROM saved_investors
            WHERE entrepreneur_email = %s
        )
        ORDER BY ip.firm_name
        LIMIT 20
    """, (email,))
    saved_investors = cursor.fetchall() or []

    cursor.close(); mycon.close()

    return render_template(
        'auth/entrepreneur/entrepreneur_ai_chat.html',
        profile              = profile,
        pitch                = pitch,
        saved_investors      = saved_investors,
        unread_msgs          = get_unread_count(email),
        unread_notifs        = get_notification_count(email),
    )


# =====================================================================
# GET CHAT HISTORY  (for a given session_id)
# =====================================================================

@entrepreneur_chat_auth.route('/api/chat/history', methods=['GET'])
def get_chat_history():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    email      = session.get('user_email')
    session_id = request.args.get('session_id', '').strip()
    mode       = request.args.get('mode', 'guidance')        # guidance | intermediary

    if not session_id:
        return jsonify({'success': True, 'messages': []}), 200

    try:
        mycon  = get_db_connection()
        cursor = mycon.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT role, content, created_at
            FROM ai_chat_messages
            WHERE session_id = %s
              AND entrepreneur_email = %s
              AND mode = %s
            ORDER BY created_at ASC
            LIMIT 60
        """, (session_id, email, mode))
        messages = cursor.fetchall()
        cursor.close(); mycon.close()

        # Serialize datetimes
        for m in messages:
            m['created_at'] = m['created_at'].strftime('%Y-%m-%d %H:%M:%S') if m.get('created_at') else None

        return jsonify({'success': True, 'messages': messages}), 200

    except Exception as e:
        print(f"❌ Chat history error: {e}")
        return jsonify({'success': False, 'message': 'Failed to load history.'}), 500


# =====================================================================
# LIST CHAT SESSIONS
# =====================================================================

@entrepreneur_chat_auth.route('/api/chat/sessions', methods=['GET'])
def list_sessions():
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
                s.investor_email,
                s.title,
                s.created_at,
                s.updated_at,
                (SELECT content FROM ai_chat_messages
                 WHERE session_id = s.session_id
                 ORDER BY created_at DESC LIMIT 1) AS last_message
            FROM ai_chat_sessions s
            WHERE s.entrepreneur_email = %s
              AND s.mode = %s
            ORDER BY s.updated_at DESC
            LIMIT 20
        """, (email, mode))
        sessions = cursor.fetchall()
        cursor.close(); mycon.close()

        for s in sessions:
            for k in ('created_at', 'updated_at'):
                if s.get(k):
                    s[k] = s[k].strftime('%Y-%m-%d %H:%M:%S')

        return jsonify({'success': True, 'sessions': sessions}), 200

    except Exception as e:
        print(f"❌ List sessions error: {e}")
        return jsonify({'success': False, 'message': 'Failed.'}), 500


# =====================================================================
# SEND MESSAGE  (core AI call)
# =====================================================================

@entrepreneur_chat_auth.route('/api/chat/send', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    email = session.get('user_email')
    data  = request.get_json()

    mode           = data.get('mode', 'guidance')          # guidance | intermediary
    user_message   = data.get('message', '').strip()
    session_id     = data.get('session_id', '').strip()
    investor_email = data.get('investor_email', '').strip() # only for intermediary mode

    if not user_message:
        return jsonify({'success': False, 'message': 'Empty message.'}), 400

    try:
        mycon  = get_db_connection()
        cursor = mycon.cursor(cursor_factory=RealDictCursor)

        # ── Load entrepreneur profile & pitch ──────────────────────────
        cursor.execute("""
            SELECT ld.email, ld.username,
                   ep.startup_name, ep.stage, ep.industry, ep.location,
                   ep.bio, ep.focus_areas, ep.funding_amount,
                   ep.funding_currency, ep.use_of_funds, ep.team_size,
                   ep.founded_year, ep.funding_required
            FROM login_data ld
            LEFT JOIN entrepreneur_profile ep ON ld.email = ep.email
            WHERE ld.email = %s
        """, (email,))
        profile = cursor.fetchone() or {}

        cursor.execute("SELECT * FROM pitch_content WHERE email = %s", (email,))
        pitch = cursor.fetchone() or {}

        # ── Create session if new ──────────────────────────────────────
        if not session_id:
            import uuid
            session_id = uuid.uuid4().hex

            title = _make_session_title(mode, user_message, profile, investor_email)

            cursor.execute("""
                INSERT INTO ai_chat_sessions
                    (session_id, entrepreneur_email, mode, investor_email, title)
                VALUES (%s, %s, %s, %s, %s)
            """, (session_id, email, mode, investor_email or None, title))
            mycon.commit()

        # ── Load recent history (last 8 exchanges = 16 rows) ──────────
        cursor.execute("""
            SELECT role, content FROM ai_chat_messages
            WHERE session_id = %s
            ORDER BY created_at DESC
            LIMIT 16
        """, (session_id,))
        recent = list(reversed(cursor.fetchall()))   # oldest first

        # ── Build Gemini conversation ──────────────────────────────────
        if mode == 'guidance':
            system_prompt, contents = _build_guidance_prompt(
                profile, pitch, recent, user_message
            )
        else:
            # Load investor profile
            cursor.execute("""
                SELECT ip.full_name, ip.firm_name, ip.geography, ip.bio,
                       ipp.preferred_sectors, ipp.investment_stage,
                       ipp.min_ticket_size, ipp.max_ticket_size,
                       ipp.investment_thesis, ipp.portfolio_highlights
                FROM investor_profiles ip
                LEFT JOIN investor_portfolio_profile ipp ON ip.email = ipp.email
                WHERE ip.email = %s
            """, (investor_email,))
            investor = cursor.fetchone() or {}

            system_prompt, contents = _build_intermediary_prompt(
                profile, pitch, investor, recent, user_message
            )

        # ── Call Gemini ────────────────────────────────────────────────
        client   = get_gemini_client()
        response = client.models.generate_content(
            model   = "gemini-2.5-flash",
            contents= contents,
            config  = types.GenerateContentConfig(
                system_instruction = system_prompt,
                max_output_tokens  = 3000,
                temperature        = 0.45,
            )
        )

        ai_reply = response.text.strip()
        if not ai_reply:
            raise ValueError("Empty AI response")

        # ── Persist both turns ─────────────────────────────────────────
        cursor.execute("""
            INSERT INTO ai_chat_messages (session_id, entrepreneur_email, mode, role, content)
            VALUES (%s,%s,%s,'user',%s)
        """, (session_id, email, mode, user_message))

        cursor.execute("""
            INSERT INTO ai_chat_messages (session_id, entrepreneur_email, mode, role, content)
            VALUES (%s,%s,%s,'assistant',%s)
        """, (session_id, email, mode, ai_reply))

        # Update session timestamp
        cursor.execute("""
            UPDATE ai_chat_sessions SET updated_at = NOW() WHERE session_id = %s
        """, (session_id,))

        mycon.commit()
        cursor.close(); mycon.close()

        print(f"✅ AI chat [{mode}] for {email} — session {session_id[:8]}")
        return jsonify({
            'success'    : True,
            'reply'      : ai_reply,
            'session_id' : session_id,
        }), 200

    except Exception as e:
        error_msg = str(e).lower()
        print(f"❌ Chat send error: {e}")
        import traceback; traceback.print_exc()

        if any(x in error_msg for x in ["api key", "authentication", "401"]):
            msg = "AI service configuration error."
        elif any(x in error_msg for x in ["quota", "rate limit", "429"]):
            msg = "AI rate limit reached. Please try again shortly."
        elif any(x in error_msg for x in ["blocked", "safety"]):
            msg = "Request blocked by AI safety filters."
        else:
            msg = "AI is unavailable right now. Please try again."

        return jsonify({'success': False, 'message': msg}), 500


# =====================================================================
# DELETE SESSION
# =====================================================================

@entrepreneur_chat_auth.route('/api/chat/session/delete', methods=['POST'])
def delete_session():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    email      = session.get('user_email')
    data       = request.get_json()
    session_id = data.get('session_id', '').strip()

    if not session_id:
        return jsonify({'success': False, 'message': 'No session_id.'}), 400

    try:
        mycon  = get_db_connection()
        cursor = mycon.cursor()
        cursor.execute("""
            DELETE FROM ai_chat_sessions
            WHERE session_id = %s AND entrepreneur_email = %s
        """, (session_id, email))
        mycon.commit()
        cursor.close(); mycon.close()
        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"❌ Delete session error: {e}")
        return jsonify({'success': False, 'message': 'Failed.'}), 500


# =====================================================================
# INTERNAL HELPERS
# =====================================================================

def _make_session_title(mode, first_message, profile, investor_email):
    startup = profile.get('startup_name') or 'Startup'
    if mode == 'guidance':
        snippet = first_message[:40] + ('…' if len(first_message) > 40 else '')
        return f"Guidance: {snippet}"
    else:
        return f"Investor Talk: {investor_email[:20] if investor_email else 'Unknown'}"


def _profile_summary(profile, pitch):
    """Compact text block describing the entrepreneur for AI context."""
    p = profile or {}
    pc = pitch or {}
    lines = [
        f"Startup: {p.get('startup_name','N/A')}",
        f"Founder: {p.get('username','N/A')}",
        f"Industry: {p.get('industry','N/A')}",
        f"Stage: {p.get('stage','N/A')}",
        f"Location: {p.get('location','N/A')}",
        f"Team Size: {p.get('team_size','N/A')}",
        f"Founded: {p.get('founded_year','N/A')}",
        f"Funding Ask: {p.get('funding_currency','INR')} {p.get('funding_amount','N/A')}",
        f"Use of Funds: {p.get('use_of_funds','N/A')}",
        f"Bio: {p.get('bio','N/A')}",
        "",
        "Pitch Summary:",
        f"  Problem: {pc.get('problem','N/A')}",
        f"  Solution: {pc.get('solution','N/A')}",
        f"  Market: {pc.get('market','N/A')}",
        f"  Business Model: {pc.get('business_model','N/A')}",
        f"  Traction: {pc.get('traction','N/A')}",
        f"  The Ask: {pc.get('the_ask','N/A')}",
    ]
    return "\n".join(lines)


def _history_to_gemini(recent):
    """Convert DB rows → Gemini contents list."""
    contents = []
    for row in recent:
        role = "user" if row['role'] == 'user' else "model"
        contents.append({"role": role, "parts": [{"text": row['content']}]})
    return contents


def _build_guidance_prompt(profile, pitch, recent, user_message):
    system_prompt = (
        "You are an elite startup fundraising advisor with 20+ years of experience "
        "helping founders raise capital from top VCs and angel investors. "
        "You have deep knowledge of pitch strategy, investor psychology, term sheets, "
        "valuation, and go-to-market positioning. "
        "Give actionable, specific, and direct advice — never generic. "
        "Reference the entrepreneur's actual startup details whenever relevant. "
        "Format your responses cleanly with line breaks. Use bullet points for lists."
        "Keep it precise and do not proivde extra details. Only answer questions regarding investor and entrepreneur"
        "\n\n"
        "ENTREPRENEUR CONTEXT:\n"
        f"{_profile_summary(profile, pitch)} word limit for answer is 300"
    )

    contents = _history_to_gemini(recent)
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    return system_prompt, contents


def _build_intermediary_prompt(profile, pitch, investor, recent, user_message):
    inv = investor or {}
    system_prompt = (
        "You are an AI investment intermediary helping an entrepreneur navigate a potential "
        "investor relationship. You have full context on both sides. "
        "Help the entrepreneur craft the best possible communication strategy, "
        "understand the investor's perspective, identify alignment/gaps, "
        "and prepare for tough investor questions. "
        "Be direct, strategic, and supportive. Reference both profiles when relevant."
        "\n\n"
        "ENTREPRENEUR PROFILE:\n"
        f"{_profile_summary(profile, pitch)}"
        "\n\n"
        "INVESTOR PROFILE:\n"
        f"Name: {inv.get('full_name','N/A')}\n"
        f"Firm: {inv.get('firm_name','N/A')}\n"
        f"Focus Sectors: {inv.get('preferred_sectors','N/A')}\n"
        f"Investment Stage: {inv.get('investment_stage','N/A')}\n"
        f"Ticket Size: {inv.get('min_ticket_size','N/A')} – {inv.get('max_ticket_size','N/A')}\n"
        f"Geography: {inv.get('geography','N/A')}\n"
        f"Thesis: {inv.get('investment_thesis','N/A')}\n"
        f"Portfolio: {inv.get('portfolio_highlights','N/A')}\n"
    )

    contents = _history_to_gemini(recent)
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    return system_prompt, contents
