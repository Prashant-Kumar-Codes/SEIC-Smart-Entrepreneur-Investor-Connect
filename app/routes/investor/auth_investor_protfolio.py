from ..extensions import *
from ...models.ai_matchmaking import async_trigger_on_investor_portfolio_save
from ...models.ai_investor_scoring import compute_and_save_investor_profile_score

investor_portfolio_auth = Blueprint('investor_portfolio_auth', '__name__')


# ─────────────────────────────────────────────────────────────────────
# PORTFOLIO PAGE
# ─────────────────────────────────────────────────────────────────────

@investor_portfolio_auth.route('/dashboard/investor/portfolio')
def investor_portfolio_page():
    if 'user_id' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('login_signup_auth.login_signup'))

    email = session.get('user_email')
    print(f"💼 Investor Portfolio → {email}")

    mycon  = get_db_connection()
    cursor = mycon.cursor(dictionary=True)

    # ── 1. Investor base profile (sidebar + topbar avatar) ────
    cursor.execute("""
        SELECT
            ld.email,
            ld.username,
            ip.full_name,
            ip.firm_name,
            ip.profile_image_url,
            ip.investment_focus,
            ip.investor_type,
            ip.geography,
            ip.total_investments,
            ip.startups_connected,
            ip.is_premium,
            ip.is_verified_investor
        FROM login_data ld
        LEFT JOIN investor_profiles ip ON ld.email = ip.email
        WHERE ld.email = %s
    """, (email,))
    profile = cursor.fetchone() or {}

    # ── 2. Investor portfolio profile (all 14 editable fields) ─
    #       Reads from investor_portfolio_profile table.
    #       Returns an empty dict with all keys = None if row
    #       doesn't exist yet (new user — first visit).
    cursor.execute("""
        SELECT
            investment_thesis,
            deal_criteria,
            portfolio_highlights,
            sector_expertise,
            dd_framework,
            value_add,
            exit_strategy,
            co_investment,
            preferred_sectors,
            investment_stage,
            min_ticket_size,
            max_ticket_size,
            available_funds,
            investment_utilization_pct
        FROM investor_portfolio_profile
        WHERE email = %s
    """, (email,))
    row = cursor.fetchone()

    # If no row yet, provide a dict of None values so the template renders cleanly
    portfolio = row if row else {
        'investment_thesis'    : None,
        'deal_criteria'        : None,
        'portfolio_highlights' : None,
        'sector_expertise'     : None,
        'dd_framework'         : None,
        'value_add'            : None,
        'exit_strategy'        : None,
        'co_investment'        : None,
        'preferred_sectors'    : None,
        'investment_stage'     : None,
        'min_ticket_size'      : None,
        'max_ticket_size'      : None,
        'available_funds'      : None,
        'investment_utilization_pct': None,
    }

    # ── 3. Deal pipeline (latest 5) ───────────────────────────
    try:
        cursor.execute("""
            SELECT
                d.deal_id,
                d.deal_stage,
                d.deal_value,
                d.equity_offered,
                d.updated_at,
                ep.startup_name,
                ep.profile_image_url,
                ld2.username AS entrepreneur_username
            FROM deals d
            LEFT JOIN entrepreneur_profile ep ON d.entrepreneur_email = ep.email
            LEFT JOIN login_data ld2 ON d.entrepreneur_email = ld2.email
            WHERE d.investor_email = %s
            ORDER BY d.updated_at DESC
            LIMIT 5
        """, (email,))
        deals = cursor.fetchall() or []
    except Exception as e:
        print(f"⚠️  Deals query error: {e}")
        deals = []

    # ── 4. Recent interests (latest 5) ────────────────────────
    try:
        cursor.execute("""
            SELECT
                ii.interest_id,
                ii.status,
                ii.created_at,
                ii.entrepreneur_email,
                ep.startup_name,
                ep.profile_image_url,
                ep.industry,
                ep.stage,
                ld2.username AS entrepreneur_username
            FROM investor_interests ii
            LEFT JOIN entrepreneur_profile ep ON ii.entrepreneur_email = ep.email
            LEFT JOIN login_data ld2 ON ii.entrepreneur_email = ld2.email
            WHERE ii.investor_email = %s
            ORDER BY ii.created_at DESC
            LIMIT 5
        """, (email,))
        interests = cursor.fetchall() or []
    except Exception as e:
        print(f"⚠️  Interests query error: {e}")
        interests = []

    # ── 5. Portfolio investments (latest 6) ───────────────────
    try:
        cursor.execute("""
            SELECT
                investment_id,
                startup_name,
                investment_amount,
                equity_percentage,
                investment_date,
                sector,
                status
            FROM investor_portfolio
            WHERE investor_email = %s
            ORDER BY investment_date DESC
            LIMIT 6
        """, (email,))
        portfolio_companies = cursor.fetchall() or []
    except Exception as e:
        print(f"⚠️  Portfolio companies query error: {e}")
        portfolio_companies = []

    # ── 6. Aggregate stats ─────────────────────────────────────
    try:
        cursor.execute(
            "SELECT COUNT(*) AS cnt FROM investor_portfolio WHERE investor_email = %s",
            (email,))
        total_investments = (cursor.fetchone() or {}).get('cnt', 0)

        cursor.execute(
            "SELECT COUNT(*) AS cnt FROM investor_portfolio WHERE investor_email = %s AND status = 'active'",
            (email,))
        active_count = (cursor.fetchone() or {}).get('cnt', 0)

        cursor.execute(
            "SELECT COUNT(*) AS cnt FROM investor_interests WHERE investor_email = %s",
            (email,))
        interests_sent = (cursor.fetchone() or {}).get('cnt', 0)

        cursor.execute("""
            SELECT COUNT(*) AS cnt FROM deals
            WHERE investor_email = %s
              AND deal_stage NOT IN ('closed')
        """, (email,))
        deals_in_pipeline = (cursor.fetchone() or {}).get('cnt', 0)

    except Exception as e:
        print(f"⚠️  Stats query error: {e}")
        total_investments = active_count = interests_sent = deals_in_pipeline = 0

    cursor.close()
    mycon.close()

    stats = {
        'total_investments' : total_investments,
        'active_count'      : active_count,
        'interests_sent'    : interests_sent,
        'deals_in_pipeline' : deals_in_pipeline,
    }

    return render_template(
        'auth/investor/investor_portfolio.html',
        active_nav          = 'portfolio',
        profile             = profile,
        portfolio           = portfolio,
        deals               = deals,
        interests           = interests,
        portfolio_companies = portfolio_companies,
        stats               = stats,
        unread_msgs         = get_unread_count(email),
        unread_notifs       = get_notification_count(email),
    )


# ─────────────────────────────────────────────────────────────────────
# AI ENHANCE  — POST /api/investor/portfolio/enhance
# ─────────────────────────────────────────────────────────────────────

@investor_portfolio_auth.route('/api/investor/portfolio/enhance', methods=['POST'])
def enhance_portfolio_section():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    email = session.get('user_email')
    data  = request.get_json(silent=True) or {}

    section_name = (data.get('section') or '').strip()
    content      = (data.get('content') or '').strip()
    firm_name    = (data.get('firm_name') or '').strip()
    full_name    = (data.get('full_name') or '').strip()

    if not content:
        return jsonify({'success': False, 'message': 'No content to enhance.'}), 400
    if not section_name:
        return jsonify({'success': False, 'message': 'Section name missing.'}), 400

    # Build investor context string for the AI prompt
    inv_context = ''
    if full_name and firm_name:
        inv_context = f" for {full_name} at {firm_name}"
    elif full_name:
        inv_context = f" for {full_name}"
    elif firm_name:
        inv_context = f" for {firm_name}"

    system_prompt = (
        "You are a world-class investor relations and communications expert who has "
        "helped top-tier VCs, family offices, and angel investors craft compelling "
        "investor profiles that attract the best deal flow. "
        "You write clear, authoritative, and specific content that builds trust with "
        "founders and clearly communicates investment conviction. "
        "Avoid buzzwords and generic language. Be direct, credible, and precise. "
        "Return ONLY the enhanced content — no preamble, no explanation, "
        "no surrounding quotes."
    )

    user_prompt = (
        f"Enhance the following '{section_name}' section of an investor profile"
        f"{inv_context}. "
        f"Keep all the same core facts but make it sharper, more credible, and "
        f"compelling to high-quality founders evaluating you as a potential investor. "
        f"Match the original length roughly (±20%). Use a confident, professional tone. "
        f"Be specific — vague investor content loses founder trust.\n\n"
        f"Original content:\n{content}"
    )

    try:
        client = get_gemini_client()

        response = client.models.generate_content(
            model    = "gemini-2.5-flash",
            contents = user_prompt,
            config   = types.GenerateContentConfig(
                system_instruction = system_prompt,
                max_output_tokens  = 800,
                temperature        = 0.38,
            )
        )

        enhanced = (response.text or '').strip()
        if not enhanced:
            return jsonify({'success': False, 'message': 'AI returned empty response.'}), 500

        print(f"✅ Section '{section_name}' enhanced for {email}")
        return jsonify({'success': True, 'enhanced': enhanced}), 200

    except Exception as e:
        err_str = str(e).lower()
        print(f"❌ Portfolio AI enhance error: {e}")
        import traceback; traceback.print_exc()

        if any(x in err_str for x in ['api key', 'authentication', '401']):
            msg = 'AI service configuration error. Contact support.'
        elif any(x in err_str for x in ['quota', 'rate limit', '429']):
            msg = 'AI rate limit reached. Please wait a moment and try again.'
        elif any(x in err_str for x in ['blocked', 'safety', 'harm']):
            msg = 'Request blocked by AI safety filters. Try different wording.'
        else:
            msg = 'AI enhancement failed. Please try again.'

        return jsonify({'success': False, 'message': msg}), 500


# ─────────────────────────────────────────────────────────────────────
# SAVE PORTFOLIO — POST /api/investor/portfolio/save
# ─────────────────────────────────────────────────────────────────────

@investor_portfolio_auth.route('/api/investor/portfolio/save', methods=['POST'])
def save_portfolio():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    email = session.get('user_email')
    data  = request.get_json(silent=True) or {}

    # ── Clean helpers ──────────────────────────────────────────
    def clean_str(key):
        """Strip text, return None if empty."""
        val = data.get(key)
        if val is None:
            return None
        val = str(val).strip()
        return val if val else None

    def clean_decimal(key):
        """Parse float, return None if absent/invalid/negative."""
        val = data.get(key)
        if val is None or val == '':
            return None
        try:
            f = float(val)
            return f if f >= 0 else None
        except (ValueError, TypeError):
            return None

    def clean_pct(key):
        """Parse float 0–100, clamp, return None if absent/invalid."""
        val = clean_decimal(key)
        if val is None:
            return None
        return min(max(val, 0.0), 100.0)

    try:
        mycon  = get_db_connection()
        cursor = mycon.cursor()

        cursor.execute("""
            INSERT INTO investor_portfolio_profile (
                email,
                investment_thesis,
                deal_criteria,
                portfolio_highlights,
                sector_expertise,
                dd_framework,
                value_add,
                exit_strategy,
                co_investment,
                preferred_sectors,
                investment_stage,
                min_ticket_size,
                max_ticket_size,
                available_funds,
                investment_utilization_pct
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (email) DO UPDATE SET
                investment_thesis    = EXCLUDED.investment_thesis,
                deal_criteria        = EXCLUDED.deal_criteria,
                portfolio_highlights = EXCLUDED.portfolio_highlights,
                sector_expertise     = EXCLUDED.sector_expertise,
                dd_framework         = EXCLUDED.dd_framework,
                value_add            = EXCLUDED.value_add,
                exit_strategy        = EXCLUDED.exit_strategy,
                co_investment        = EXCLUDED.co_investment,
                preferred_sectors    = EXCLUDED.preferred_sectors,
                investment_stage     = EXCLUDED.investment_stage,
                min_ticket_size      = EXCLUDED.min_ticket_size,
                max_ticket_size      = EXCLUDED.max_ticket_size,
                available_funds      = EXCLUDED.available_funds,
                investment_utilization_pct = EXCLUDED.investment_utilization_pct,
                updated_at           = NOW()
        """, (
            email,
            clean_str('investment_thesis'),
            clean_str('deal_criteria'),
            clean_str('portfolio_highlights'),
            clean_str('sector_expertise'),
            clean_str('dd_framework'),
            clean_str('value_add'),
            clean_str('exit_strategy'),
            clean_str('co_investment'),
            clean_str('preferred_sectors'),
            clean_str('investment_stage'),
            clean_decimal('min_ticket_size'),
            clean_decimal('max_ticket_size'),
            clean_decimal('available_funds'),
            clean_pct('investment_utilization_pct'),
        ))


        mycon.commit()
        cursor.close()
        mycon.close()

        print(f"✅ Portfolio profile saved for {email}")

        # Async embedding: load updated profile/portfolio rows and hand off
        try:
            conn2 = get_db_connection()
            cur2 = conn2.cursor(dictionary=True)
            cur2.execute("SELECT * FROM investor_profiles WHERE email = %s", (email,))
            investor_profile = cur2.fetchone() or {}
            cur2.execute("SELECT * FROM investor_portfolio_profile WHERE email = %s", (email,))
            investor_portfolio = cur2.fetchone() or {}
            cur2.close(); conn2.close()

            async_trigger_on_investor_portfolio_save(
                email, investor_profile, investor_portfolio)
        except Exception as embed_err:
            print(f"⚠️ Investor embedding queue error: {embed_err}")

        # Trigger AI scoring update for the profile
        try:
            score_con = get_db_connection()
            compute_and_save_investor_profile_score(email, score_con)
            score_con.close()
            print(f"✅ Portfolio AI score updated for {email}")
        except Exception as score_err:
            import traceback
            print(f"⚠️ Warning: Could not update investor portfolio score for {email}: {score_err}")
            print(f"   Traceback: {traceback.format_exc()}")
            # Fail gracefully, still returning success for the actual save operation

        return jsonify({'success': True}), 200

    except Exception as e:
        print(f"❌ Save portfolio error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': 'Failed to save. Please try again.'}), 500