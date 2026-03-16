
from ..extensions import *
# use the matchmaking module for embedding tasks instead of the older
# ai_embedding_engine; the async trigger manages its own DB connection.
from ...models.ai_matchmaking import async_trigger_on_investor_portfolio_save
from ...models.ai_investor_scoring import compute_and_save_investor_profile_score

investor_my_profile_auth = Blueprint('investor_my_profile_auth', '__name__')

@investor_my_profile_auth.route('/dashboard/investor/profile')
@investor_my_profile_auth.route('/investor/profile/<string:investor_email>')
def investor_my_profile(investor_email=None):
    """Investor profile page. If investor_email is provided the logged‑in user
    (entrepreneur or investor) sees another investor's profile; otherwise
    they view their own."""
    if 'user_id' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('login_signup_auth.login_signup'))

    session_email = session.get('user_email')
    email = investor_email or session_email
    viewing_self = (email == session_email)
    print(f"[PROFILE] Investor Profile -> {email} (self? {viewing_self})")

    mycon  = get_db_connection()
    cursor = mycon.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT
            ld.email,
            ld.username,
            ld.created_at,
            ld.authorized,
            ip.firm_name,
            ip.bio,
            ip.investment_focus,
            ip.location,
            ip.website_url,
            ip.profile_image_url,
            ip.linkedin_url,
            ip.twitter_url,
            ip.full_name,
            ip.geography,
            ip.investor_type,
            ip.current_position,
            ip.years_of_experience,
            ip.education,
            ip.previous_roles,
            ip.crunchbase_url,
            ip.investor_rating,
            ip.is_premium,
            ip.is_verified_investor,
            ipp.preferred_sectors,
            ipp.investment_stage,
            ipp.investment_thesis,
            ipp.portfolio_highlights,
            ipp.min_ticket_size,
            ipp.max_ticket_size,
            ipp.available_funds,
            ipp.investment_utilization_pct
        FROM login_data ld
        LEFT JOIN investor_profiles ip ON ld.email = ip.email
        LEFT JOIN investor_portfolio_profile ipp ON ld.email = ipp.email
        WHERE ld.email = %s
    """, (email,))
    profile = cursor.fetchone()
    portfolio = profile  # Same row contains both profile and portfolio data
    cursor.close(); mycon.close()

    # auto-create row only when viewing self
    if viewing_self and profile and profile.get('firm_name') is None:
        try:
            mycon  = get_db_connection()
            cursor = mycon.cursor()
            cursor.execute("""
                INSERT INTO investor_profiles (email)
                VALUES (%s)
                ON CONFLICT DO NOTHING
            """, (email,))
            mycon.commit()
            cursor.close(); mycon.close()
        except Exception as e:
            print(f"[WARNING] Auto-create investor_profiles row: {e}")

    # ── Completeness score (out of 8 fields) ──────────────────
    checks = [
        profile and profile.get('profile_image_url'),
        profile and profile.get('full_name'),
        profile and profile.get('bio'),
        profile and profile.get('investor_type'),
        profile and profile.get('firm_name'),
        profile and profile.get('investment_focus'),
        profile and profile.get('linkedin_url'),
        profile and profile.get('location'),
    ]
    profile_completeness = round(
        (sum(bool(c) for c in checks) / len(checks)) * 100
    )

    return render_template(
        'auth/investor/investor_profile.html',
        active_nav           = 'profile',
        profile              = profile,
        portfolio            = portfolio,
        profile_completeness = profile_completeness,
        is_self              = viewing_self,
        user_authorized      = session.get('user_authorized', 'not_authorized'),  # NEW: Pass auth status
        unread_msgs          = get_unread_count(session_email),
        unread_notifs        = get_notification_count(session_email),
    )


# =====================================================================
# INVESTOR PROFILE EDIT API
# =====================================================================

@investor_my_profile_auth.route('/api/investor/profile/edit', methods=['POST'])
def edit_investor_profile():
    """Save all investor profile fields from the multi-tab modal."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    email = session.get('user_email')
    data  = request.get_json()

    # Sanitise numeric fields
    def _num(key, cast=float):
        try:
            val = data.get(key)
            return cast(val) if val else None
        except (ValueError, TypeError):
            return None

    min_ticket  = _num('min_ticket_size')
    max_ticket  = _num('max_ticket_size')
    avail_funds = _num('available_funds')
    utilization = _num('investment_utilization_pct')
    years_exp   = _num('years_of_experience', int)

    # Validate ticket sizes
    if min_ticket and max_ticket and min_ticket > max_ticket:
        return jsonify({
            'success': False,
            'message': 'Min ticket size cannot be greater than max ticket size.'
        }), 400

    try:
        mycon  = get_db_connection()
        cursor = mycon.cursor()
        
        # Update investor_profiles with basic profile info
        cursor.execute("""
            INSERT INTO investor_profiles (
                email,
                full_name, bio, investor_type, location, geography,
                current_position, firm_name,
                years_of_experience, education, previous_roles,
                investment_focus,
                website_url, linkedin_url, twitter_url, crunchbase_url
            ) VALUES (
                %s,
                %s, %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                %s,
                %s, %s, %s, %s
            )
            ON CONFLICT (email) DO UPDATE SET
                full_name                  = EXCLUDED.full_name,
                bio                        = EXCLUDED.bio,
                investor_type              = EXCLUDED.investor_type,
                location                   = EXCLUDED.location,
                geography                  = EXCLUDED.geography,
                current_position           = EXCLUDED.current_position,
                firm_name                  = EXCLUDED.firm_name,
                years_of_experience        = EXCLUDED.years_of_experience,
                education                  = EXCLUDED.education,
                previous_roles             = EXCLUDED.previous_roles,
                investment_focus           = EXCLUDED.investment_focus,
                website_url                = EXCLUDED.website_url,
                linkedin_url               = EXCLUDED.linkedin_url,
                twitter_url                = EXCLUDED.twitter_url,
                crunchbase_url             = EXCLUDED.crunchbase_url
        """, (
            email,
            data.get('full_name','').strip()         or None,
            data.get('bio','').strip()               or None,
            data.get('investor_type','').strip()     or None,
            data.get('location','').strip()          or None,
            data.get('geography','').strip()         or None,
            data.get('current_position','').strip()  or None,
            data.get('firm_name','').strip()         or None,
            years_exp,
            data.get('education','').strip()         or None,
            data.get('previous_roles','').strip()    or None,
            data.get('investment_focus','').strip()  or None,
            data.get('website_url','').strip()       or None,
            data.get('linkedin_url','').strip()      or None,
            data.get('twitter_url','').strip()       or None,
            data.get('crunchbase_url','').strip()    or None,
        ))
        flash('Updated profile','success')
        
        # Update investor_portfolio_profile with portfolio-specific info
        cursor.execute("""
            INSERT INTO investor_portfolio_profile (
                email,
                preferred_sectors, investment_stage,
                investment_thesis, portfolio_highlights,
                min_ticket_size, max_ticket_size,
                available_funds, investment_utilization_pct
            ) VALUES (
                %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s
            )
            ON CONFLICT (email) DO UPDATE SET
                preferred_sectors          = EXCLUDED.preferred_sectors,
                investment_stage           = EXCLUDED.investment_stage,
                investment_thesis          = EXCLUDED.investment_thesis,
                portfolio_highlights       = EXCLUDED.portfolio_highlights,
                min_ticket_size            = EXCLUDED.min_ticket_size,
                max_ticket_size            = EXCLUDED.max_ticket_size,
                available_funds            = EXCLUDED.available_funds,
                investment_utilization_pct = EXCLUDED.investment_utilization_pct
        """, (
            email,
            data.get('preferred_sectors','').strip() or None,
            data.get('investment_stage','').strip()  or None,
            data.get('investment_thesis','').strip()    or None,
            data.get('portfolio_highlights','').strip() or None,
            min_ticket,
            max_ticket,
            avail_funds,
            utilization,
        ))
        

        mycon.commit()
        cursor.close(); mycon.close()

        print(f"[OK] Investor profile updated: {email}")

        # Async embedding – load fresh rows and hand off to matcher
        try:
            conn2 = get_db_connection()
            cur2 = conn2.cursor(cursor_factory=RealDictCursor)
            cur2.execute("SELECT * FROM investor_profiles WHERE email = %s", (email,))
            investor_profile = cur2.fetchone() or {}
            cur2.execute("SELECT * FROM investor_portfolio_profile WHERE email = %s", (email,))
            investor_portfolio = cur2.fetchone() or {}
            cur2.close(); conn2.close()

            async_trigger_on_investor_portfolio_save(
                email, investor_profile, investor_portfolio)
        except Exception as embed_err:
            print(f"⚠️ Investor embedding queue error: {embed_err}")

        # Trigger profile scoring
        try:
            new_con = get_db_connection()
            compute_and_save_investor_profile_score(email, new_con)
            new_con.close()
            print(f"✅ Profile score updated for {email}")
        except Exception as scoring_err:
            import traceback
            print(f"⚠️ Warning: Could not update investor profile score for {email}: {scoring_err}")
            print(f"   Traceback: {traceback.format_exc()}")
            # Don't fail the entire request if scoring fails

        return jsonify({'success': True}), 200

    except Exception as e:
        print(f"❌ Investor profile edit error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': 'Profile update failed. Please try again.'}), 500
