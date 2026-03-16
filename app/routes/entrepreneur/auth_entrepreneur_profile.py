from ..extensions import *
import os
from ...models.ai_entrepreneur_scoring import compute_and_save_entrepreneur_profile_score

entrepreneur_profile_auth = Blueprint('entrepreneur_profile_auth', __name__)


@entrepreneur_profile_auth.route('/dashboard/entrepreneur/profile')
def entrepreneur_profile():
    if 'user_id' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('login_signup_auth.login_signup'))

    email = session.get('user_email')
    print(f"👤 My Profile → {email}")

    mycon  = get_db_connection()
    cursor = mycon.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT
            ld.email, ld.username, ld.created_at,
            ep.startup_name, ep.bio, ep.industry, ep.location,
            ep.website_url, ep.linkedin_url, ep.twitter_url,
            ep.profile_image_url,
            ep.profile_views, ep.investors_connected, ep.total_pitches,
            ep.profile_score, ep.funding_required, ep.funding_progress_pct,
            ep.funding_amount, ep.funding_currency, ep.use_of_funds,
            ep.stage, ep.founded_year, ep.team_size, ep.focus_areas,
            ep.pitch_deck_url, ep.demo_url, ep.video_pitch_url,
            ep.is_premium, ep.is_verified_profile
        FROM login_data ld
        LEFT JOIN entrepreneur_profile ep ON ld.email = ep.email
        WHERE ld.email = %s
    """, (email,))
    profile = cursor.fetchone()
    cursor.close(); mycon.close()

    # Calculate completeness score (out of 8 fields)
    checks = [
        profile and profile.get('profile_image_url'),
        profile and profile.get('bio'),
        profile and profile.get('startup_name'),
        profile and profile.get('industry'),
        profile and profile.get('location'),
        profile and profile.get('funding_amount'),
        profile and profile.get('linkedin_url'),
        profile and profile.get('website_url'),
    ]
    profile_completeness = round((sum(bool(c) for c in checks) / len(checks)) * 100)

    from datetime import datetime
    return render_template(
        'auth/entrepreneur/entrepreneur_profile.html',
        profile              = profile,
        profile_completeness = profile_completeness,
        unread_msgs          = get_unread_count(email),
        unread_notifs        = get_notification_count(email),
        now_year             = datetime.now().year,
    )


# =====================================================================
# FULL PROFILE EDIT  (covers all tabs)
# =====================================================================

@entrepreneur_profile_auth.route('/api/profile/edit/full', methods=['POST'])
def edit_profile_full():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    email = session.get('user_email')
    data  = request.get_json()

    # Build funding_required display string
    funding_required = None
    if data.get('funding_amount'):
        sym = {'INR': '₹', 'USD': '$', 'EUR': '€', 'GBP': '£'}.get(
            data.get('funding_currency', 'INR'), '₹')
        try:
            amt = float(data['funding_amount'])
            if amt >= 10_000_000:
                funding_required = f"{sym}{amt/10_000_000:.1f} Cr"
            elif amt >= 100_000:
                funding_required = f"{sym}{amt/100_000:.1f} L"
            else:
                funding_required = f"{sym}{int(amt):,}"
        except Exception:
            funding_required = data.get('funding_amount')

    try:
        mycon  = get_db_connection()
        cursor = mycon.cursor()
        
        # ✅ FIX 1: Update username in login_data table
        username = data.get('username', '').strip()
        if username:
            cursor.execute("""
                UPDATE login_data 
                SET username = %s 
                WHERE email = %s
            """, (username, email))
            print(f"✅ Updated username to: {username}")
        
        # ✅ FIX 2: Update entrepreneur_profile table
        cursor.execute("""
            INSERT INTO entrepreneur_profile (
                email, startup_name, bio, industry, location,
                website_url, linkedin_url, twitter_url,
                stage, founded_year, team_size, focus_areas,
                funding_amount, funding_currency, use_of_funds,
                funding_progress_pct, funding_required,
                pitch_deck_url, demo_url, video_pitch_url
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (email) DO UPDATE SET
                startup_name        = EXCLUDED.startup_name,
                bio                 = EXCLUDED.bio,
                industry            = EXCLUDED.industry,
                location            = EXCLUDED.location,
                website_url         = EXCLUDED.website_url,
                linkedin_url        = EXCLUDED.linkedin_url,
                twitter_url         = EXCLUDED.twitter_url,
                stage               = EXCLUDED.stage,
                founded_year        = EXCLUDED.founded_year,
                team_size           = EXCLUDED.team_size,
                focus_areas         = EXCLUDED.focus_areas,
                funding_amount      = EXCLUDED.funding_amount,
                funding_currency    = EXCLUDED.funding_currency,
                use_of_funds        = EXCLUDED.use_of_funds,
                funding_progress_pct= EXCLUDED.funding_progress_pct,
                funding_required    = EXCLUDED.funding_required,
                pitch_deck_url      = EXCLUDED.pitch_deck_url,
                demo_url            = EXCLUDED.demo_url,
                video_pitch_url     = EXCLUDED.video_pitch_url
        """, (
            email,
            data.get('startup_name','').strip()  or None,
            data.get('bio','').strip()            or None,
            data.get('industry','').strip()       or None,
            data.get('location','').strip()       or None,
            data.get('website_url','').strip()    or None,
            data.get('linkedin_url','').strip()   or None,
            data.get('twitter_url','').strip()    or None,
            data.get('stage')                     or None,
            data.get('founded_year')              or None,
            data.get('team_size','').strip()      or None,
            data.get('focus_areas','').strip()    or None,
            data.get('funding_amount')            or None,
            data.get('funding_currency','INR'),
            data.get('use_of_funds','').strip()   or None,
            data.get('funding_progress_pct')      or None,
            funding_required,
            data.get('pitch_deck_url','').strip() or None,
            data.get('demo_url','').strip()       or None,
            data.get('video_pitch_url','').strip() or None,
        ))
        mycon.commit()
        cursor.close(); mycon.close()
        print(f"✅ Full profile updated: {email}")
        
        # Trigger profile scoring (async-like, continue even if it fails)
        try:
            new_con = get_db_connection()
            result = compute_and_save_entrepreneur_profile_score(email, new_con)
            new_con.close()
            if result:
                print(f"✅ Profile score updated for {email}")
            else:
                print(f"⚠️ Profile score update was skipped or failed for {email}")
        except Exception as scoring_err:
            import traceback
            print(f"⚠️ Warning: Could not update profile score for {email}: {scoring_err}")
            print(f"   Traceback: {traceback.format_exc()}")
            # Don't fail the entire request if scoring fails
        
        return jsonify({'success': True}), 200

    except Exception as e:
        print(f"❌ Full profile edit error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': 'Profile update failed.'}), 500