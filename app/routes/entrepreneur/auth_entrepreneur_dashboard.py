from ..extensions import *
from ...models.ai_entrepreneur_scoring import compute_and_save_entrepreneur_profile_score

entrepreneur_dashboard_bp = Blueprint('entrepreneur_dashboard_bp', __name__)

# --- API: All Investors with Match Score ---
@entrepreneur_dashboard_bp.route('/api/dashboard/all_investors')
def api_all_investors():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    email = session.get('user_email')
    conn = get_request_conn()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Try to use pre-computed match scores from ai_match_cache first
    cursor.execute("""
        SELECT ip.email, ld.username, ld.is_verified, ip.firm_name, ip.investment_focus,
               ip.profile_image_url, ip.profile_score, ip.bio, ip.location, ip.investor_type,
               ip.total_investments,
               COALESCE(amc.score, 0) AS match_score
        FROM investor_profiles ip
        JOIN login_data ld ON ip.email = ld.email
        LEFT JOIN ai_match_cache amc
            ON amc.investor_email = ip.email
            AND amc.entrepreneur_email = %s
            AND amc.direction = 'entrepreneur_to_investor'
        ORDER BY match_score DESC
    """, (email,))
    investors = cursor.fetchall()

    # Coerce Decimal → float for JSON serialization
    for inv in investors:
        if inv.get('match_score') is not None:
            inv['match_score'] = round(float(inv['match_score']), 3)

    cursor.close()
    return jsonify({'success': True, 'investors': investors})


# --- API: All Entrepreneurs with Profile Score ---
@entrepreneur_dashboard_bp.route('/api/dashboard/all_entrepreneurs')
def api_all_entrepreneurs():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    conn = get_request_conn()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT ep.email, ld.username, ld.is_verified, ep.startup_name, ep.industry,
               ep.profile_image_url, ep.profile_score, ep.bio, ep.location, ep.stage,
               ep.funding_required, ep.team_size
        FROM entrepreneur_profile ep
        JOIN login_data ld ON ep.email = ld.email
    """)
    entrepreneurs = cursor.fetchall()
    cursor.close()
    return jsonify({'success': True, 'entrepreneurs': entrepreneurs})


# =====================================================================
# HELPERS — all accept an optional cursor to share the request connection
# =====================================================================

def _get_entrepreneur_profile(cursor, email):
    cursor.execute("""
        SELECT
            ld.email, ld.username, ld.age, ld.gender,
            ep.startup_name, ep.bio, ep.industry, ep.location,
            ep.website_url, ep.profile_image_url,
            ep.linkedin_url, ep.twitter_url,
            ep.profile_views, ep.investors_connected, ep.total_pitches,
            ep.profile_score, ep.funding_required, ep.funding_progress_pct
        FROM login_data ld
        LEFT JOIN entrepreneur_profile ep ON ld.email = ep.email
        WHERE ld.email = %s
    """, (email,))
    return cursor.fetchone()


def _get_top_investors(cursor, entrepreneur_email, limit=3):
    """
    Fetch top investor profiles. Priority:
    1. Investors who have sent a connection request to this entrepreneur
    2. Investors whose investment_focus overlaps with the entrepreneur's industry
    3. Other active investors
    Returns only REAL data from database - no padding with placeholder data
    """
    try:
        cursor.execute("""
            SELECT
                ip.email,
                ld.username,
                ip.firm_name,
                ip.investment_focus,
                ip.profile_image_url,
                ip.investor_type,
                c.status AS connection_status
            FROM investor_profiles ip
            JOIN login_data ld ON ip.email = ld.email
            LEFT JOIN connections c
                ON c.investor_email = ip.email
                AND c.entrepreneur_email = %s
            WHERE ld.is_verified = true
            ORDER BY
                CASE
                    WHEN c.status = 'accepted' THEN 1
                    WHEN c.status = 'pending'  THEN 2
                    ELSE 3
                END,
                ip.total_investments DESC,
                ip.created_at DESC
            LIMIT %s
        """, (entrepreneur_email, limit))
        return cursor.fetchall()
    except Exception as e:
        print(f"❌ Error fetching top investors: {e}")
        return []


def _get_upcoming_meetings(cursor, entrepreneur_email, limit=3):
    """
    Fetch upcoming scheduled meetings for the entrepreneur (REAL data only).
    Shows only meetings that are scheduled and not cancelled.
    """
    try:
        cursor.execute("""
            SELECT
                m.meeting_id,
                m.meeting_type,
                m.scheduled_at,
                m.status,
                ld.username AS investor_name,
                ip.profile_image_url AS investor_image
            FROM meetings m
            JOIN login_data ld ON ld.email = m.investor_email
            LEFT JOIN investor_profiles ip ON ip.email = m.investor_email
            WHERE m.entrepreneur_email = %s
              AND m.scheduled_at >= NOW()
              AND m.status IN ('scheduled', 'completed')
            ORDER BY m.scheduled_at ASC
            LIMIT %s
        """, (entrepreneur_email, limit))
        return cursor.fetchall()
    except Exception as e:
        print(f"❌ Error fetching meetings: {e}")
        return []


def _get_deal_counts(cursor, entrepreneur_email):
    """
    Count connections/deals per stage for the Deal Tracker.
    Returns real counts from the deals table.
    """
    counts = {
        'introduced': 0,
        'discussion': 0,
        'diligence': 0,
        'term_sheet': 0,
        'closed': 0,
    }

    try:
        cursor.execute("""
            SELECT deal_stage, COUNT(*) AS cnt
            FROM deals
            WHERE entrepreneur_email = %s
            GROUP BY deal_stage
        """, (entrepreneur_email,))
        rows = cursor.fetchall()

        stage_map = {
            'introduced': 'introduced',
            'in_discussion': 'discussion',
            'due_diligence': 'diligence',
            'term_sheet': 'term_sheet',
            'closed': 'closed',
        }

        for row in rows:
            key = stage_map.get(row['deal_stage'])
            if key:
                counts[key] = row['cnt']
    except Exception as e:
        print(f"❌ Error fetching deal counts: {e}")

    # Return as object with attributes
    result = type('DealCounts', (), counts)()
    return result


def _get_investor_match_count(cursor, entrepreneur_email):
    """Count investors who have shown interest (accepted connections)."""
    try:
        cursor.execute("""
            SELECT COUNT(*) FROM connections
            WHERE entrepreneur_email = %s AND status = 'accepted'
        """, (entrepreneur_email,))
        return cursor.fetchone()[0]
    except Exception:
        return 0


def time_ago(dt):
    from datetime import datetime
    now   = datetime.now()
    delta = now - dt
    s     = int(delta.total_seconds())
    if s < 60:      return "just now"
    if s < 3600:    return f"{s // 60}m ago"
    if s < 86400:   return f"{s // 3600}h ago"
    if s < 604800:  return f"{s // 86400}d ago"
    return dt.strftime("%b %d")


# ── Backward-compatible wrappers (for any external callers) ──
def get_entrepreneur_profile(email):
    conn = get_request_conn()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    result = _get_entrepreneur_profile(cursor, email)
    cursor.close()
    return result


# =====================================================================
# HOME DASHBOARD  (new main landing page)
# =====================================================================

@entrepreneur_dashboard_bp.route('/dashboard/entrepreneur')
@entrepreneur_dashboard_bp.route('/dashboard/entrepreneur/home')
def entrepreneur_home():
    if 'user_id' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('login_signup_auth.login_signup'))

    email = session.get('user_email')
    print(f"🏠 Entrepreneur Home → {email}")

    # ── Single connection, single cursor for ALL dashboard queries ──
    conn   = get_request_conn()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    profile              = _get_entrepreneur_profile(cursor, email)
    top_investors        = _get_top_investors(cursor, email, limit=3)
    meetings             = _get_upcoming_meetings(cursor, email, limit=3)
    deal_counts          = _get_deal_counts(cursor, email)
    investor_match_count = _get_investor_match_count(cursor, email)

    cursor.close()

    # These use the same request conn internally
    unread_msgs   = get_unread_count(email)
    unread_notifs = get_notification_count(email)

    # Log what we're sending to template
    print(f"📊 Dashboard Data:")
    print(f"  - Profile: {'Yes' if profile else 'No'}")
    print(f"  - Top Investors: {len(top_investors)} found")
    print(f"  - Meetings: {len(meetings)} upcoming")
    print(f"  - Deal Counts: {deal_counts.__dict__ if deal_counts else 'None'}")
    print(f"  - Investor Matches: {investor_match_count}")

    return render_template(
        'auth/entrepreneur/entrepreneur_dashboard.html',
        profile              = profile,
        top_investors        = top_investors,
        meetings             = meetings,
        deal_counts          = deal_counts,
        investor_match_count = investor_match_count,
        unread_msgs          = unread_msgs,
        unread_notifs        = unread_notifs,
    )


# =====================================================================
# CREATE PITCH POST
# =====================================================================

@entrepreneur_dashboard_bp.route('/api/posts/create', methods=['POST'])
def create_post():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    email            = session.get('user_email')
    data             = request.get_json()
    title            = data.get('title', '').strip()
    description      = data.get('description', '').strip()
    funding_goal     = data.get('funding_goal')
    funding_currency = data.get('funding_currency', 'USD')
    industry_tag     = data.get('industry_tag', '').strip()
    stage            = data.get('stage', 'idea')
    pitch_deck_url   = data.get('pitch_deck_url', '').strip()
    video_url        = data.get('video_url', '').strip()

    if not title or not description:
        return jsonify({'success': False, 'message': 'Title and description are required.'}), 400

    try:
        conn   = get_request_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_posts
                (email, title, description,
                 industry_tag, pitch_deck_url, video_url)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (email, title, description,
              industry_tag, pitch_deck_url or None, video_url or None))
        cursor.execute("""
            UPDATE entrepreneur_profile SET total_pitches = total_pitches + 1
            WHERE email = %s
        """, (email,))
        conn.commit()
        post_id = cursor.lastrowid
        cursor.close()
        print(f"✅ Pitch created: post_id={post_id} by {email}")
        return jsonify({'success': True, 'post_id': post_id}), 201

    except Exception as e:
        print(f"❌ Create post error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': 'Failed to create post.'}), 500


# =====================================================================
# POST INTERACTION
# =====================================================================

@entrepreneur_dashboard_bp.route('/api/posts/<int:post_id>/interact', methods=['POST'])
def interact_post(post_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    email            = session.get('user_email')
    data             = request.get_json()
    interaction_type = data.get('type')

    VALID = {'like', 'save', 'interested', 'view'}
    if interaction_type not in VALID:
        return jsonify({'success': False, 'message': 'Invalid interaction type.'}), 400

    count_col_map = {'like': 'likes_count', 'save': 'saves_count',
                     'interested': 'likes_count', 'view': 'views_count'}
    try:
        conn   = get_request_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO post_interactions (user_email, post_id, interaction_type)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (email, post_id, interaction_type))
        if cursor.rowcount > 0:
            col = count_col_map[interaction_type]
            cursor.execute(f"UPDATE user_posts SET {col} = {col} + 1 WHERE post_id = %s", (post_id,))
        conn.commit()
        cursor.close()
        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"❌ Interact error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': 'Interaction failed.'}), 500


# =====================================================================
# EDIT PROFILE
# =====================================================================

@entrepreneur_dashboard_bp.route('/api/profile/edit', methods=['POST'])
def edit_profile():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    email = session.get('user_email')
    data  = request.get_json()

    try:
        conn   = get_request_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO entrepreneur_profile
                (email, startup_name, bio, industry, location, website_url, linkedin_url, twitter_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (email) DO UPDATE SET
                startup_name = EXCLUDED.startup_name,
                bio          = EXCLUDED.bio,
                industry     = EXCLUDED.industry,
                location     = EXCLUDED.location,
                website_url  = EXCLUDED.website_url,
                linkedin_url = EXCLUDED.linkedin_url,
                twitter_url  = EXCLUDED.twitter_url
        """, (email,
              data.get('startup_name','').strip(), data.get('bio','').strip(),
              data.get('industry','').strip(),     data.get('location','').strip(),
              data.get('website_url','').strip(),  data.get('linkedin_url','').strip(),
              data.get('twitter_url','').strip()))
        conn.commit()
        cursor.close()

        # Trigger profile scoring
        try:
            result = compute_and_save_entrepreneur_profile_score(email, conn)
            if result:
                print(f"✅ Profile score updated for {email}")
            else:
                print(f"⚠️ Profile score update was skipped or failed for {email}")
        except Exception as scoring_err:
            import traceback
            print(f"⚠️ Warning: Could not update profile score for {email}: {scoring_err}")
            # Don't fail the entire request if scoring fails

        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"❌ Edit profile error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': 'Profile update failed.'}), 500


# =====================================================================
# SEND MESSAGE
# =====================================================================

@entrepreneur_dashboard_bp.route('/api/messages/send', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    sender_email   = session.get('user_email')
    data           = request.get_json()
    receiver_email = data.get('receiver_email', '').strip()
    message_text   = data.get('message_text', '').strip()

    if not receiver_email or not message_text:
        return jsonify({'success': False, 'message': 'Receiver and message are required.'}), 400

    try:
        conn   = get_request_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO messages (sender_email, receiver_email, message_text)
            VALUES (%s, %s, %s)
        """, (sender_email, receiver_email, message_text))
        conn.commit()
        cursor.close()
        return jsonify({'success': True}), 201
    except Exception as e:
        print(f"❌ Send message error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': 'Message failed to send.'}), 500


# =====================================================================
# MARK MESSAGES READ
# =====================================================================

@entrepreneur_dashboard_bp.route('/api/messages/read', methods=['POST'])
def mark_messages_read():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    email         = session.get('user_email')
    data          = request.get_json()
    partner_email = data.get('partner_email', '').strip()

    try:
        conn   = get_request_conn()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE messages SET is_read = true, read_at = NOW()
            WHERE receiver_email = %s AND sender_email = %s AND is_read = false
        """, (email, partner_email))
        conn.commit()
        cursor.close()
        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"❌ Mark read error: {e}")
        return jsonify({'success': False, 'message': 'Failed.'}), 500


# =====================================================================
# LOAD MORE FEED  (pagination)
# =====================================================================

def _get_feed_posts(cursor, limit=20, offset=0):
    cursor.execute("""
        SELECT
            pp.post_id, pp.email, pp.title, pp.description,
            pp.industry_tag,
            pp.pitch_deck_url, pp.video_url, pp.thumbnail_url,
            pp.likes_count, pp.comments_count, pp.saves_count, pp.views_count,
            pp.created_at,
            ld.username,
            ep.startup_name, ep.profile_image_url
        FROM user_posts pp
        JOIN login_data ld ON pp.email = ld.email
        LEFT JOIN entrepreneur_profile ep ON pp.email = ep.email
        WHERE pp.is_active = 1
        ORDER BY pp.created_at DESC
        LIMIT %s OFFSET %s
    """, (limit, offset))
    return cursor.fetchall()


@entrepreneur_dashboard_bp.route('/api/feed', methods=['GET'])
def load_feed():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    offset = int(request.args.get('offset', 0))
    limit  = int(request.args.get('limit', 10))

    conn   = get_request_conn()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    posts  = _get_feed_posts(cursor, limit=limit, offset=offset)
    cursor.close()

    for p in posts:
        p['time_ago']   = time_ago(p['created_at'])
        p['created_at'] = p['created_at'].isoformat()

    return jsonify({'success': True, 'posts': posts}), 200


# =====================================================================
# SCHEDULE MEETING
# =====================================================================

@entrepreneur_dashboard_bp.route('/api/meetings/schedule', methods=['POST'])
def schedule_meeting():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    email        = session.get('user_email')
    data         = request.get_json()
    investor_email = (data.get('investor_email') or '').strip()
    meeting_type = (data.get('meeting_type') or '').strip()
    scheduled_at = (data.get('scheduled_at') or '').strip()

    if not investor_email or not meeting_type or not scheduled_at:
        return jsonify({'success': False, 'message': 'All fields are required.'}), 400

    try:
        conn   = get_request_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO meetings (entrepreneur_email, investor_email, meeting_type, scheduled_at, status)
            VALUES (%s, %s, %s, %s, 'scheduled')
        """, (email, investor_email, meeting_type, scheduled_at))
        conn.commit()
        cursor.close()
        print(f"✅ Meeting scheduled: {email} ↔ {investor_email}")
        return jsonify({'success': True, 'message': 'Meeting scheduled successfully!'}), 201

    except Exception as e:
        print(f"❌ Schedule meeting error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': 'Failed to schedule meeting.'}), 500


# =====================================================================
# INVESTOR MATCHES PAGE
# =====================================================================

@entrepreneur_dashboard_bp.route('/dashboard/entrepreneur/matches')
def entrepreneur_matches():
    if 'user_id' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('login_signup_auth.login_signup'))

    email = session.get('user_email')
    print(f"🎯 Investor Matches → {email}")

    conn   = get_request_conn()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Profile (for sidebar)
    cursor.execute("""
        SELECT ld.email, ld.username,
               ep.startup_name, ep.profile_image_url,
               ep.total_pitches, ep.investors_connected, ep.profile_views,
               ep.funding_required, ep.funding_progress_pct,
               ep.stage, ep.industry, ep.location, ep.bio
        FROM login_data ld
        LEFT JOIN entrepreneur_profile ep ON ld.email = ep.email
        WHERE ld.email = %s
    """, (email,))
    profile = cursor.fetchone()

    # Get top N investor matches (ranked by score)
    top_investors = _get_top_investors(cursor, email, limit=50)

    cursor.close()

    from datetime import datetime
    return render_template(
        'auth/entrepreneur/entrepreneur_matches.html',
        profile       = profile,
        matches       = top_investors,
        match_count   = len(top_investors),
        unread_msgs   = get_unread_count(email),
        unread_notifs = get_notification_count(email),
        now_year      = datetime.now().year,
    )


# =====================================================================
# DEALS TRACKING
# =====================================================================

@entrepreneur_dashboard_bp.route('/dashboard/entrepreneur/deals')
def entrepreneur_deals():
    """View all deals entrepreneur is involved in"""
    if 'user_id' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('login_signup_auth.login_signup'))

    email = session.get('user_email')
    print(f"📊 Entrepreneur Deals → {email}")

    conn   = get_request_conn()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Get all deals for entrepreneur
    cursor.execute("""
        SELECT
            d.deal_id, d.investor_email, d.deal_stage,
            d.deal_value, d.equity_offered, d.notes,
            d.created_at, d.updated_at,
            ip.firm_name, ip.full_name, ip.investor_type,
            ip.profile_image_url, ld.username
        FROM deals d
        LEFT JOIN investor_profiles ip ON d.investor_email = ip.email
        LEFT JOIN login_data ld ON d.investor_email = ld.email
        WHERE d.entrepreneur_email = %s
        ORDER BY d.updated_at DESC
    """, (email,))
    deals = cursor.fetchall()

    # Get deal counts by stage
    cursor.execute("""
        SELECT deal_stage, COUNT(*) as count
        FROM deals
        WHERE entrepreneur_email = %s
        GROUP BY deal_stage
    """, (email,))
    stage_counts = {row['deal_stage']: row['count'] for row in cursor.fetchall()}

    # Profile for sidebar
    profile = _get_entrepreneur_profile(cursor, email)

    cursor.close()

    return render_template(
        'auth/entrepreneur/entrepreneur_deals.html',
        active_nav='deals',
        profile=profile,
        deals=deals,
        stage_counts=stage_counts,
        unread_msgs=get_unread_count(email),
        unread_notifs=get_notification_count(email)
    )


# =====================================================================
# PROFILE VIEW TRACKER
# =====================================================================

@entrepreneur_dashboard_bp.route('/api/profile/<viewed_email>/view', methods=['POST'])
def log_profile_view(viewed_email):
    viewer_email = session.get('user_email')
    try:
        conn   = get_request_conn()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO profile_view_logs (viewed_email, viewer_email) VALUES (%s, %s)",
                       (viewed_email, viewer_email))
        cursor.execute("UPDATE entrepreneur_profile SET profile_views = profile_views + 1 WHERE email = %s",
                       (viewed_email,))
        conn.commit()
        cursor.close()
        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"❌ Profile view log error: {e}")
        return jsonify({'success': False}), 500