"""
Investor Dashboard Blueprint
Main routes for investor home, feed, and dashboard views
"""
from ..extensions import *

investor_dashboard_bp = Blueprint('investor_dashboard_bp', __name__)


# =====================================================================
# HELPERS
# =====================================================================

def get_investor_profile(email):
    """Get investor profile data"""
    mycon = get_db_connection()
    cursor = mycon.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT
            ld.email, ld.username, ld.age, ld.gender,
            ip.firm_name, ip.bio, ip.investment_focus, ip.location,
            ip.website_url, ip.profile_image_url,
            ip.total_investments, ip.startups_connected, ip.profile_views,
            ipp.min_ticket_size, ipp.max_ticket_size,
            ipp.available_funds, ipp.investment_utilization_pct
        FROM login_data ld
        LEFT JOIN investor_profiles ip ON ld.email = ip.email
        LEFT JOIN investor_portfolio_profile ipp ON ld.email = ipp.email
        WHERE ld.email = %s
    """, (email,))
    profile = cursor.fetchone()
    cursor.close(); mycon.close()
    return profile


def get_feed_posts(limit=20, offset=0):
    """Get feed posts from entrepreneurs"""
    mycon = get_db_connection()
    cursor = mycon.cursor(cursor_factory=RealDictCursor)
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
    posts = cursor.fetchall()
    cursor.close(); mycon.close()
    return posts


def get_message_threads(email):
    """Get message threads for investor"""
    mycon = get_db_connection()
    cursor = mycon.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT
            m.message_id,
            CASE WHEN m.sender_email = %s THEN m.receiver_email ELSE m.sender_email END AS partner_email,
            m.message_text AS last_message,
            m.sent_at, m.is_read, m.sender_email,
            ld.username AS partner_name,
            ep.profile_image_url AS partner_image_ent,
            ip.profile_image_url AS partner_image_inv
        FROM messages m
        JOIN (
            SELECT MAX(message_id) AS max_id FROM messages
            WHERE sender_email = %s OR receiver_email = %s
            GROUP BY LEAST(sender_email, receiver_email), GREATEST(sender_email, receiver_email)
        ) latest ON m.message_id = latest.max_id
        JOIN login_data ld
            ON ld.email = CASE WHEN m.sender_email = %s THEN m.receiver_email ELSE m.sender_email END
        LEFT JOIN entrepreneur_profile ep ON ep.email = ld.email
        LEFT JOIN investor_profiles ip ON ip.email = ld.email
        ORDER BY m.sent_at DESC
        LIMIT 20
    """, (email, email, email, email))
    threads = cursor.fetchall()
    cursor.close(); mycon.close()
    return threads


def get_unread_count(email):
    """Get unread messages count"""
    mycon = get_db_connection()
    cursor = mycon.cursor()
    cursor.execute("SELECT COUNT(*) FROM messages WHERE receiver_email = %s AND is_read = false", (email,))
    count = cursor.fetchone()[0]
    cursor.close(); mycon.close()
    return count


def get_notification_count(email):
    """Get unread notifications count"""
    mycon = get_db_connection()
    cursor = mycon.cursor()
    cursor.execute("SELECT COUNT(*) FROM notifications WHERE email = %s AND is_read = false", (email,))
    count = cursor.fetchone()[0]
    cursor.close(); mycon.close()
    return count


def get_interested_startups(investor_email, limit=10):
    """Get startups investor has expressed interest in"""
    mycon = get_db_connection()
    cursor = mycon.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT
            ii.interest_id, ii.entrepreneur_email, ii.status, ii.created_at,
            ep.startup_name, ep.industry, ep.stage, ep.profile_image_url,
            ld.username
        FROM investor_interests ii
        JOIN entrepreneur_profile ep ON ii.entrepreneur_email = ep.email
        JOIN login_data ld ON ep.email = ld.email
        WHERE ii.investor_email = %s
        ORDER BY ii.created_at DESC
        LIMIT %s
    """, (investor_email, limit))
    startups = cursor.fetchall()
    cursor.close(); mycon.close()
    return startups


def get_portfolio(investor_email, limit=10):
    """Get investor's investment portfolio"""
    mycon = get_db_connection()
    cursor = mycon.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("""
            SELECT
                ip.investment_id, ip.startup_name, ip.investment_amount,
                ip.equity_percentage, ip.investment_date, ip.sector, ip.status,
                ld.username
            FROM investor_portfolio ip
            LEFT JOIN login_data ld ON ip.entrepreneur_email = ld.email
            WHERE ip.investor_email = %s
            ORDER BY ip.investment_date DESC
            LIMIT %s
        """, (investor_email, limit))
        portfolio = cursor.fetchall()
    except Exception:
        portfolio = []
    cursor.close(); mycon.close()
    return portfolio


def get_saved_startups(investor_email, limit=10):
    """Get investor's saved startups"""
    mycon = get_db_connection()
    cursor = mycon.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT
            ss.save_id, ss.saved_at, ss.notes,
            ep.email, ep.startup_name, ep.industry, ep.stage,
            ep.profile_image_url, ld.username
        FROM saved_startups ss
        JOIN entrepreneur_profile ep ON ss.entrepreneur_email = ep.email
        JOIN login_data ld ON ep.email = ld.email
        WHERE ss.investor_email = %s
        ORDER BY ss.saved_at DESC
        LIMIT %s
    """, (investor_email, limit))
    startups = cursor.fetchall()
    cursor.close(); mycon.close()
    return startups


def get_matched_entrepreneurs(investor_email, limit=6):
    """Get entrepreneurs matching investor's focus areas"""
    mycon = get_db_connection()
    cursor = mycon.cursor(cursor_factory=RealDictCursor)
    try:
        # Get investor's investment focus
        cursor.execute("""
            SELECT investment_focus FROM investor_profiles WHERE email = %s
        """, (investor_email,))
        inv_pref = cursor.fetchone()
        
        query = """
            SELECT
                ep.email, ep.startup_name, ep.industry, ep.stage,
                ep.profile_image_url, ld.username
            FROM entrepreneur_profile ep
            JOIN login_data ld ON ep.email = ld.email
            WHERE ld.role = 'entrepreneur'
        """
        params = []
        
        if inv_pref and inv_pref.get('investment_focus'):
            query += " AND ep.industry LIKE %s"
            params.append(f"%{inv_pref['investment_focus']}%")
        
        query += " ORDER BY ep.profile_views DESC LIMIT %s"
        params.append(limit)
        
        cursor.execute(query, params)
        entrepreneurs = cursor.fetchall()
    except Exception:
        entrepreneurs = []
    cursor.close(); mycon.close()
    return entrepreneurs


def get_deal_counts(investor_email):
    """
    Return deal counts per stage as a plain dict so the template can do
    deal_counts.introduced, deal_counts.values()|sum, etc.
    """
    mycon  = get_db_connection()
    cursor = mycon.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT deal_stage, COUNT(*) AS cnt
        FROM deals
        WHERE investor_email = %s
        GROUP BY deal_stage
    """, (investor_email,))
    rows = cursor.fetchall()
    cursor.close(); mycon.close()

    counts = {
        'introduced': 0,
        'discussion':  0,
        'diligence':   0,
        'term_sheet':  0,
        'closed':      0,
    }
    stage_map = {
        'introduced':   'introduced',
        'in_discussion': 'discussion',
        'due_diligence': 'diligence',
        'term_sheet':   'term_sheet',
        'closed':       'closed',
    }
    for r in rows:
        key = stage_map.get(r['deal_stage'])
        if key:
            counts[key] = r['cnt']
    return counts


def get_top_startups(investor_email, limit=5):
    """
    Fetch the top matched entrepreneurs for the investor dashboard.

    Returns per row:
        email, startup_name, username, industry, stage,
        profile_image_url, funding_required,
        traction          (from pitch_content),
        connection_status (pending | accepted | none),
        ai_match_score    (from ai_match_cache, falls back to 0)
    """
    mycon  = get_db_connection()
    cursor = mycon.cursor(cursor_factory=RealDictCursor)

    # Get investor focus to filter
    cursor.execute(
        "SELECT investment_focus FROM investor_profiles WHERE email = %s",
        (investor_email,)
    )
    inv = cursor.fetchone() or {}
    focus = inv.get('investment_focus', '') or ''

    # Build query — COALESCE match score from cache
    cursor.execute("""
        SELECT
            ep.email,
            ep.startup_name,
            ep.industry,
            ep.stage,
            ep.profile_image_url,
            ep.funding_required,
            ld.username,
            pc.traction,
            COALESCE(amc.score * 100, 0)  AS ai_match_score,
            COALESCE(ii.status, 'none')    AS connection_status
        FROM entrepreneur_profile ep
        JOIN login_data ld ON ep.email = ld.email
        LEFT JOIN pitch_content pc
            ON pc.email = ep.email
        LEFT JOIN ai_match_cache amc
            ON amc.entrepreneur_email = ep.email
            AND amc.investor_email = %s
            AND amc.direction = 'investor_to_entrepreneur'
        LEFT JOIN investor_interests ii
            ON ii.entrepreneur_email = ep.email
            AND ii.investor_email = %s
        WHERE ld.role = 'entrepreneur'
        ORDER BY ai_match_score DESC, ep.profile_views DESC
        LIMIT %s
    """, (investor_email, investor_email, limit))

    startups = cursor.fetchall()
    cursor.close(); mycon.close()

    # Coerce Decimal → int for template
    for s in startups:
        if s.get('ai_match_score') is not None:
            s['ai_match_score'] = int(float(s['ai_match_score']))

    return startups


def get_upcoming_meetings(investor_email, limit=3):
    """Fetch scheduled meetings for the investor, newest first."""
    mycon  = get_db_connection()
    cursor = mycon.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT
            m.meeting_id,
            m.scheduled_at,
            m.meeting_type,
            m.status,
            ep.startup_name,
            ld.username
        FROM meetings m
        LEFT JOIN entrepreneur_profile ep ON m.entrepreneur_email = ep.email
        LEFT JOIN login_data ld ON m.entrepreneur_email = ld.email
        WHERE m.investor_email = %s
          AND m.status = 'scheduled'
          AND m.scheduled_at >= NOW()
        ORDER BY m.scheduled_at ASC
        LIMIT %s
    """, (investor_email, limit))
    meetings = cursor.fetchall()
    cursor.close(); mycon.close()
    return meetings


def get_investor_profile_score(profile):
    """
    Compute a simple completeness score (0–100) from the investor profile dict.
    Used to fill the shield widget in the dashboard stat card.
    """
    if not profile:
        return 0
    fields = [
        'firm_name', 'bio', 'investment_focus', 'location',
        'website_url', 'profile_image_url', 'linkedin_url',
        'min_ticket_size', 'max_ticket_size',
    ]
    filled = sum(1 for f in fields if profile.get(f))
    return round((filled / len(fields)) * 100)


def get_investment_stage_pct(deal_counts):
    """
    Returns a 0–100 int representing how far along the deal pipeline is.
    Weighted by stage: introduced=1, discussion=2, diligence=3,
                       term_sheet=4, closed=5  (max weight 5)
    """
    weights = {
        'introduced': 1, 'discussion': 2, 'diligence': 3,
        'term_sheet': 4, 'closed': 5
    }
    total_weight = sum(deal_counts.get(k, 0) * w for k, w in weights.items())
    total_deals  = sum(deal_counts.values())
    if total_deals == 0:
        return 0
    # Scale: max possible weight per deal = 5
    return min(100, round((total_weight / (total_deals * 5)) * 100))


def time_ago(dt):
    """Format datetime as 'X time ago'"""
    from datetime import datetime
    now = datetime.now()
    delta = now - dt
    s = int(delta.total_seconds())
    if s < 60:      return "just now"
    if s < 3600:    return f"{s // 60}m ago"
    if s < 86400:   return f"{s // 3600}h ago"
    if s < 604800:  return f"{s // 86400}d ago"
    return dt.strftime("%b %d")


# =====================================================================
# HOME DASHBOARD
# =====================================================================

@investor_dashboard_bp.route('/dashboard/investor')
@investor_dashboard_bp.route('/dashboard/investor/home')
def investor_home():
    """Investor dashboard home page"""
    if 'user_id' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('login_signup_auth.login_signup'))
    
    email = session.get('user_email')
    print(f"🏠 Investor Home → {email}")
    
    profile = get_investor_profile(email)
    if not profile:
        # Create default investor profile if doesn't exist
        mycon = get_db_connection()
        cursor = mycon.cursor()
        try:
            cursor.execute("""
                INSERT INTO investor_profiles (email, firm_name)
                VALUES (%s, %s)
            """, (email, session.get('username', '')))
            mycon.commit()
        except Exception:
            pass
        cursor.close(); mycon.close()
        profile = get_investor_profile(email)
    
    interested_startups  = get_interested_startups(email, limit=3)
    portfolio            = get_portfolio(email, limit=3)
    matched_entrepreneurs = get_matched_entrepreneurs(email, limit=6)
    top_startups         = get_top_startups(email, limit=5)
    meetings             = get_upcoming_meetings(email, limit=3)
    deal_counts          = get_deal_counts(email)
    unread_msgs          = get_unread_count(email)
    unread_notifs        = get_notification_count(email)

    # Derived stats
    startup_match_count   = len(matched_entrepreneurs)
    investment_stage_pct  = get_investment_stage_pct(deal_counts)

    # Attach profile score to profile dict so template can use profile.profile_score
    if profile:
        profile['profile_score'] = get_investor_profile_score(profile)

    return render_template(
        'auth/investor/investor_dashboard.html',
        active_nav='home',
        profile=profile,
        interested_startups=interested_startups,
        portfolio=portfolio,
        matched_entrepreneurs=matched_entrepreneurs,
        top_startups=top_startups,
        meetings=meetings,
        deal_counts=deal_counts,
        startup_match_count=startup_match_count,
        investment_stage_pct=investment_stage_pct,
        unread_msgs=unread_msgs,
        unread_notifs=unread_notifs
    )


# =====================================================================
# FEED
# =====================================================================

@investor_dashboard_bp.route('/dashboard/investor/feed')
def investor_feed():
    """Investor feed - view pitches from entrepreneurs"""
    if 'user_id' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('login_signup_auth.login_signup'))
    
    email = session.get('user_email')
    print(f"📰 Investor Feed → {email}")
    
    page = request.args.get('page', 1, type=int)
    limit = 10
    offset = (page - 1) * limit
    
    profile = get_investor_profile(email)
    posts = get_feed_posts(limit=limit, offset=offset)
    unread_msgs = get_unread_count(email)
    unread_notifs = get_notification_count(email)
    
    return render_template(
        'auth/investor/investor_feed.html',
        active_nav='feed',
        profile=profile,
        posts=posts,
        page=page,
        unread_msgs=unread_msgs,
        unread_notifs=unread_notifs
    )


# =====================================================================
# CREATE POST
# =====================================================================

@investor_dashboard_bp.route('/api/posts/create', methods=['POST'])
def create_post():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    email       = session.get('user_email')
    data        = request.get_json()
    title       = data.get('title', '').strip()
    description = data.get('description', '').strip()
    industry_tag     = data.get('industry_tag', '').strip()
    pitch_deck_url   = data.get('pitch_deck_url', '').strip()
    video_url        = data.get('video_url', '').strip()

    if not title or not description:
        return jsonify({'success': False, 'message': 'Title and description are required.'}), 400

    try:
        mycon  = get_db_connection()
        cursor = mycon.cursor()
        cursor.execute("""
            INSERT INTO user_posts
                (email, title, description,
                 industry_tag, pitch_deck_url, video_url)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (email, title, description,
              industry_tag, pitch_deck_url or None, video_url or None))

        mycon.commit()
        post_id = cursor.lastrowid
        cursor.close()
        mycon.close()

        print(f"✅ User post created: post_id={post_id} by {email}")
        return jsonify({'success': True, 'post_id': post_id}), 201

    except Exception as e:
        print(f"❌ Create post error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': 'Failed to create post.'}), 500


# =====================================================================
# POST INTERACTION  (like / save / interested)
# =====================================================================

@investor_dashboard_bp.route('/api/posts/<int:post_id>/interact', methods=['POST'])
def interact_post(post_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    email            = session.get('user_email')
    data             = request.get_json()
    interaction_type = data.get('type')

    VALID = {'like', 'save', 'interested', 'view'}
    if interaction_type not in VALID:
        return jsonify({'success': False, 'message': 'Invalid interaction type.'}), 400

    count_col_map = {
        'like': 'likes_count',
        'save': 'saves_count',
        'interested': 'likes_count',
        'view': 'views_count'
    }

    try:
        mycon  = get_db_connection()
        cursor = mycon.cursor()

        cursor.execute("""
            INSERT INTO post_interactions (user_email, post_id, interaction_type)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (email, post_id, interaction_type))

        toggled = cursor.rowcount > 0

        if toggled:
            col = count_col_map[interaction_type]
            cursor.execute(f"UPDATE user_posts SET {col} = {col} + 1 WHERE post_id = %s", (post_id,))

        mycon.commit()
        cursor.close()
        mycon.close()
        return jsonify({'success': True, 'toggled': toggled}), 200

    except Exception as e:
        print(f"❌ Interact error: {e}")
        return jsonify({'success': False, 'message': 'Interaction failed.'}), 500

# =====================================================================
# LOAD MORE FEED  (pagination)
# =====================================================================

@investor_dashboard_bp.route('/api/feed', methods=['GET'])
def load_feed():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    offset = int(request.args.get('offset', 0))
    limit  = int(request.args.get('limit', 10))
    posts  = get_feed_posts(limit=limit, offset=offset)

    for p in posts:
        p['time_ago']  = time_ago(p['created_at'])
        p['created_at'] = p['created_at'].isoformat()

    return jsonify({'success': True, 'posts': posts}), 200

@investor_dashboard_bp.route('/discover')
def discover_startups():
    """Discover and explore startups"""
    if 'user_id' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('login_signup_auth.login_signup'))
    
    email = session.get('user_email')
    sector = request.args.get('sector', '')
    stage = request.args.get('stage', '')
    location = request.args.get('location', '')
    
    print(f"🔍 Discover Startups → {email}")
    
    mycon = get_db_connection()
    cursor = mycon.cursor(cursor_factory=RealDictCursor)
    
    query = """
        SELECT
            ep.email, ep.startup_name, ep.industry, ep.stage,
            ep.location, ep.profile_image_url, ep.funding_required,
            ep.profile_score, ld.username
        FROM entrepreneur_profile ep
        JOIN login_data ld ON ep.email = ld.email
        WHERE ld.role = 'entrepreneur'
    """
    params = []
    
    if sector:
        query += " AND ep.industry = %s"
        params.append(sector)
    
    if stage:
        query += " AND ep.stage = %s"
        params.append(stage)
    
    if location:
        query += " AND ep.location LIKE %s"
        params.append(f"%{location}%")
    
    query += " ORDER BY ep.profile_views DESC LIMIT 50"
    
    cursor.execute(query, params)
    startups = cursor.fetchall()
    cursor.close(); mycon.close()
    
    profile = get_investor_profile(email)
    unread_msgs = get_unread_count(email)
    
    return render_template(
        'auth/investor/discover_startups.html',
        active_nav='discover',
        profile=profile,
        startups=startups,
        unread_msgs=unread_msgs,
        filters={'sector': sector, 'stage': stage, 'location': location}
    )


# =====================================================================
# MY INTERESTS
# =====================================================================

@investor_dashboard_bp.route('/interests')
def my_interests():
    """View startups investor has expressed interest in"""
    if 'user_id' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('login_signup_auth.login_signup'))
    
    email = session.get('user_email')
    print(f"❤️ My Interests → {email}")
    
    profile = get_investor_profile(email)
    interested = get_interested_startups(email, limit=50)
    unread_msgs = get_unread_count(email)
    
    return render_template(
        'auth/investor/investor_interests.html',
        active_nav='interests',
        profile=profile,
        interested_startups=interested,
        unread_msgs=unread_msgs
    )


# =====================================================================
# PORTFOLIO
# =====================================================================

@investor_dashboard_bp.route('/portfolio')
def portfolio():
    """View investor's investment portfolio"""
    if 'user_id' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('login_signup_auth.login_signup'))
    
    email = session.get('user_email')
    print(f"💼 Portfolio → {email}")
    
    profile = get_investor_profile(email)
    investments = get_portfolio(email, limit=50)
    unread_msgs = get_unread_count(email)
    
    return render_template(
        'auth/investor/investor_portfolio.html',
        active_nav='portfolio',
        profile=profile,
        investments=investments,
        unread_msgs=unread_msgs
    )


# =====================================================================
# DEAL TRACKING
# =====================================================================

@investor_dashboard_bp.route('/deals')
def view_deals():
    """View all deals investor is involved in"""
    if 'user_id' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('login_signup_auth.login_signup'))
    
    email = session.get('user_email')
    print(f"📊 Deals → {email}")
    
    mycon = get_db_connection()
    cursor = mycon.cursor(cursor_factory=RealDictCursor)
    
    # Get all deals for investor
    cursor.execute("""
        SELECT
            d.deal_id, d.entrepreneur_email, d.deal_stage,
            d.deal_value, d.equity_offered, d.notes,
            d.created_at, d.updated_at,
            ep.startup_name, ep.industry, ep.stage as funding_stage,
            ep.profile_image_url, ld.username
        FROM deals d
        LEFT JOIN entrepreneur_profile ep ON d.entrepreneur_email = ep.email
        LEFT JOIN login_data ld ON d.entrepreneur_email = ld.email
        WHERE d.investor_email = %s
        ORDER BY d.updated_at DESC
    """, (email,))
    deals = cursor.fetchall()
    
    # Get deal counts by stage
    cursor.execute("""
        SELECT deal_stage, COUNT(*) as count
        FROM deals
        WHERE investor_email = %s
        GROUP BY deal_stage
    """, (email,))
    stage_counts = {row['deal_stage']: row['count'] for row in cursor.fetchall()}
    
    cursor.close()
    mycon.close()
    
    profile = get_investor_profile(email)
    unread_msgs = get_unread_count(email)
    
    return render_template(
        'auth/investor/investor_deals.html',
        active_nav='deals',
        profile=profile,
        deals=deals,
        stage_counts=stage_counts,
        unread_msgs=unread_msgs
    )


@investor_dashboard_bp.route('/meetings')
def view_meetings():
    """View all scheduled meetings"""
    if 'user_id' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('login_signup_auth.login_signup'))
    
    email = session.get('user_email')
    print(f"📅 Meetings → {email}")
    
    mycon = get_db_connection()
    cursor = mycon.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT
            m.meeting_id, m.entrepreneur_email, m.scheduled_at,
            m.meeting_type, m.status, m.created_at,
            ep.startup_name, ep.profile_image_url,
            ld.username
        FROM meetings m
        LEFT JOIN entrepreneur_profile ep ON m.entrepreneur_email = ep.email
        LEFT JOIN login_data ld ON m.entrepreneur_email = ld.email
        WHERE m.investor_email = %s
        ORDER BY m.scheduled_at DESC
    """, (email,))
    meetings = cursor.fetchall()
    cursor.close()
    mycon.close()
    
    profile = get_investor_profile(email)
    unread_msgs = get_unread_count(email)
    
    return render_template(
        'auth/investor/investor_meetings.html',
        active_nav='meetings',
        profile=profile,
        meetings=meetings,
        unread_msgs=unread_msgs
    )


# =====================================================================
# SAVED STARTUPS
# =====================================================================

@investor_dashboard_bp.route('/saved')
def saved_startups():
    """View investor's saved startups"""
    if 'user_id' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('login_signup_auth.login_signup'))
    
    email = session.get('user_email')
    print(f"💾 Saved Startups → {email}")
    
    profile = get_investor_profile(email)
    saved = get_saved_startups(email, limit=50)
    unread_msgs = get_unread_count(email)
    
    return render_template(
        'auth/investor/investor_saved.html',
        active_nav='saved',
        profile=profile,
        saved_startups=saved,
        unread_msgs=unread_msgs
    )


# =====================================================================
# MESSAGES
# =====================================================================

@investor_dashboard_bp.route('/messages')
def messages():
    """View investor messages"""
    if 'user_id' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('login_signup_auth.login_signup'))
    
    email = session.get('user_email')
    print(f"💬 Messages → {email}")
    
    profile = get_investor_profile(email)
    threads = get_message_threads(email)
    unread_msgs = get_unread_count(email)
    
    return render_template(
        'auth/investor/investor_messages.html',
        active_nav='messages',
        profile=profile,
        threads=threads,
        unread_msgs=unread_msgs
    )


# =====================================================================
# API: SCHEDULE MEETING / FIRST CALL
# =====================================================================

@investor_dashboard_bp.route('/api/investor/meetings/schedule', methods=['POST'])
def schedule_meeting():
    """Schedule first meeting with entrepreneur"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    investor_email = session.get('user_email')
    data = request.get_json() or {}
    
    entrepreneur_email = data.get('entrepreneur_email', '').strip()
    scheduled_at = data.get('scheduled_at', '').strip()  # ISO format datetime
    meeting_type = data.get('meeting_type', 'video_call')  # 'video_call', 'in_person', 'phone'
    
    if not entrepreneur_email or not scheduled_at:
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    try:
        mycon = get_db_connection()
        cursor = mycon.cursor()
        
        cursor.execute("""
            INSERT INTO meetings (
                entrepreneur_email, investor_email, 
                scheduled_at, meeting_type,
                status, created_at
            ) VALUES (%s, %s, %s, %s, %s, NOW())
        """, (
            entrepreneur_email, investor_email,
            scheduled_at, meeting_type,
            'scheduled'
        ))
        
        mycon.commit()
        meeting_id = cursor.lastrowid
        cursor.close()
        mycon.close()
        
        print(f"✅ Meeting scheduled: {investor_email} → {entrepreneur_email}")
        return jsonify({
            'success': True,
            'message': 'Meeting scheduled',
            'meeting_id': meeting_id
        }), 200
        
    except Exception as e:
        print(f"❌ Schedule meeting error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# =====================================================================
# API: EXPRESS INTEREST IN STARTUP
# =====================================================================

@investor_dashboard_bp.route('/api/investor/interests/express', methods=['POST'])
def express_interest():
    """Express interest in a startup and save it for AI chat"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    investor_email = session.get('user_email')
    data = request.get_json() or {}
    
    entrepreneur_email = data.get('entrepreneur_email', '').strip()
    message = data.get('message', '').strip()
    
    if not entrepreneur_email:
        return jsonify({'success': False, 'message': 'Missing entrepreneur email'}), 400
    
    try:
        mycon = get_db_connection()
        cursor = mycon.cursor()
        
        # Insert or update interest
        cursor.execute("""
            INSERT INTO investor_interests (
                investor_email, entrepreneur_email, status, message, created_at
            ) VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (investor_email, entrepreneur_email) DO UPDATE SET
                status = EXCLUDED.status,
                message = EXCLUDED.message,
                updated_at = NOW()
        """, (investor_email, entrepreneur_email, 'pending', message))
        
        # Also add to saved_startups if not already there (for AI chat selector)
        try:
            cursor.execute("""
                INSERT INTO saved_startups (
                    investor_email, entrepreneur_email, saved_at
                ) VALUES (%s, %s, NOW())
                ON CONFLICT (investor_email, entrepreneur_email) DO UPDATE SET
                    saved_at = NOW()
            """, (investor_email, entrepreneur_email))
        except Exception:
            pass  # If save fails, interest is still recorded
        
        mycon.commit()
        cursor.close()
        mycon.close()
        
        print(f"✅ Interest expressed: {investor_email} → {entrepreneur_email}")
        return jsonify({
            'success': True,
            'message': 'Interest expressed successfully',
            'entrepreneur_email': entrepreneur_email
        }), 200
        
    except Exception as e:
        print(f"❌ Express interest error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# =====================================================================
# API: PROPOSE INVESTMENT
# =====================================================================

@investor_dashboard_bp.route('/api/investor/investments/propose', methods=['POST'])
def propose_investment():
    """Propose investment to startup"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    investor_email = session.get('user_email')
    data = request.get_json() or {}
    
    entrepreneur_email = data.get('entrepreneur_email', '').strip()
    investment_amount = float(data.get('investment_amount', 0))
    equity_percentage = float(data.get('equity_percentage', 0)) if data.get('equity_percentage') else None
    notes = data.get('notes', '').strip()
    
    if not entrepreneur_email or investment_amount <= 0:
        return jsonify({'success': False, 'message': 'Invalid investment details'}), 400
    
    try:
        mycon = get_db_connection()
        cursor = mycon.cursor()
        
        # Create or update deal
        cursor.execute("""
            INSERT INTO deals (
                entrepreneur_email, investor_email,
                deal_stage, deal_value, equity_offered,
                notes, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (entrepreneur_email, investor_email) DO UPDATE SET
                deal_stage = 'in_discussion',
                deal_value = EXCLUDED.deal_value,
                equity_offered = EXCLUDED.equity_offered,
                notes = EXCLUDED.notes,
                updated_at = NOW()
        """, (
            entrepreneur_email, investor_email,
            'introduced', investment_amount, equity_percentage,
            notes
        ))
        
        deal_id = cursor.lastrowid if cursor.rowcount > 0 else None
        
        # Also add to investor portfolio
        cursor.execute("""
            INSERT INTO investor_portfolio (
                investor_email, entrepreneur_email, startup_name,
                investment_amount, equity_percentage, investment_date,
                investment_stage, status, notes
            ) 
            SELECT %s, %s, ep.startup_name, %s, %s, CURDATE(), %s, %s, %s
            FROM entrepreneur_profile ep
            WHERE ep.email = %s
            ON CONFLICT (investor_email, entrepreneur_email) DO UPDATE SET
                investment_amount = EXCLUDED.investment_amount,
                equity_percentage = EXCLUDED.equity_percentage,
                updated_at = NOW()
        """, (
            investor_email, entrepreneur_email, investment_amount, 
            equity_percentage, 'proposed', 'active', notes,
            entrepreneur_email
        ))
        
        mycon.commit()
        cursor.close()
        mycon.close()
        
        print(f"✅ Investment proposed: {investor_email} → {entrepreneur_email} (₹{investment_amount})")
        return jsonify({
            'success': True,
            'message': 'Investment proposal sent',
            'deal_id': deal_id
        }), 200
        
    except Exception as e:
        print(f"❌ Propose investment error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# =====================================================================
# API: POST-MEETING DECISION
# =====================================================================

@investor_dashboard_bp.route('/api/investor/meetings/<int:meeting_id>/decide', methods=['POST'])
def post_meeting_decision(meeting_id):
    """Investor decision after meeting"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    investor_email = session.get('user_email')
    data = request.get_json() or {}
    
    decision = data.get('decision', '').strip()  # 'positive', 'neutral', 'negative'
    
    if decision not in ['positive', 'neutral', 'negative']:
        return jsonify({'success': False, 'message': 'Invalid decision'}), 400
    
    try:
        mycon = get_db_connection()
        cursor = mycon.cursor()
        
        # Get meeting details
        cursor.execute("""
            SELECT entrepreneur_email, status FROM meetings
            WHERE meeting_id = %s AND investor_email = %s
        """, (meeting_id, investor_email))
        
        meeting = cursor.fetchone()
        if not meeting:
            cursor.close()
            mycon.close()
            return jsonify({'success': False, 'message': 'Meeting not found'}), 404
        
        entrepreneur_email = meeting[0]
        
        # Update meeting status
        new_status = 'completed'
        
        cursor.execute("""
            UPDATE meetings
            SET status = %s, updated_at = NOW()
            WHERE meeting_id = %s
        """, (new_status, meeting_id))
        
        # If positive, create/update deal
        if decision == 'positive':
            cursor.execute("""
                INSERT INTO deals (
                    entrepreneur_email, investor_email,
                    deal_stage, status, created_at
                ) VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (entrepreneur_email, investor_email) DO UPDATE SET
                    deal_stage = 'in_discussion',
                    updated_at = NOW()
            """, (entrepreneur_email, investor_email, 'introduced', 'active'))
        
        mycon.commit()
        cursor.close()
        mycon.close()
        
        print(f"✅ Meeting decision: {decision} for meeting {meeting_id}")
        return jsonify({
            'success': True,
            'message': f'Decision recorded: {decision}'
        }), 200
        
    except Exception as e:
        print(f"❌ Post-meeting decision error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# =====================================================================
# API: SAVE STARTUP (BOOKMARK)
# =====================================================================

@investor_dashboard_bp.route('/api/investor/startups/save', methods=['POST'])
def save_startup():
    """Save/bookmark a startup"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    investor_email = session.get('user_email')
    data = request.get_json() or {}
    
    entrepreneur_email = data.get('entrepreneur_email', '').strip()
    notes = data.get('notes', '').strip()
    
    if not entrepreneur_email:
        return jsonify({'success': False, 'message': 'Missing entrepreneur email'}), 400
    
    try:
        mycon = get_db_connection()
        cursor = mycon.cursor()
        
        cursor.execute("""
            INSERT INTO saved_startups (
                investor_email, entrepreneur_email, notes, saved_at
            ) VALUES (%s, %s, %s, NOW())
            ON CONFLICT (investor_email, entrepreneur_email) DO UPDATE SET
                notes = EXCLUDED.notes
        """, (investor_email, entrepreneur_email, notes))
        
        mycon.commit()
        cursor.close()
        mycon.close()
        
        print(f"✅ Startup saved: {investor_email} saved {entrepreneur_email}")
        return jsonify({'success': True, 'message': 'Startup saved'}), 200
        
    except Exception as e:
        print(f"❌ Save startup error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# =====================================================================
# API: TRACK DEAL PROGRESS
# =====================================================================

@investor_dashboard_bp.route('/api/investor/deals/<int:deal_id>/update', methods=['POST'])
def update_deal_status(deal_id):
    """Update deal stage and progress"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    investor_email = session.get('user_email')
    data = request.get_json() or {}
    
    deal_stage = data.get('deal_stage', '').strip()  # 'introduced', 'in_discussion', 'due_diligence', 'term_sheet', 'closed'
    deal_value = float(data.get('deal_value', 0)) if data.get('deal_value') else None
    equity_offered = float(data.get('equity_offered', 0)) if data.get('equity_offered') else None
    
    valid_stages = ['introduced', 'in_discussion', 'due_diligence', 'term_sheet', 'closed']
    if deal_stage and deal_stage not in valid_stages:
        return jsonify({'success': False, 'message': f'Invalid stage. Must be one of {valid_stages}'}), 400
    
    try:
        mycon = get_db_connection()
        cursor = mycon.cursor()
        
        # Verify ownership
        cursor.execute("""
            SELECT investor_email FROM deals WHERE deal_id = %s
        """, (deal_id,))
        
        result = cursor.fetchone()
        if not result or result[0] != investor_email:
            cursor.close()
            mycon.close()
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
        # Update deal
        updates = []
        params = []
        
        if deal_stage:
            updates.append("deal_stage = %s")
            params.append(deal_stage)
        if deal_value is not None:
            updates.append("deal_value = %s")
            params.append(deal_value)
        if equity_offered is not None:
            updates.append("equity_offered = %s")
            params.append(equity_offered)
        
        if not updates:
            cursor.close()
            mycon.close()
            return jsonify({'success': False, 'message': 'No fields to update'}), 400
        
        updates.append("updated_at = NOW()")
        params.append(deal_id)
        
        query = f"UPDATE deals SET {', '.join(updates)} WHERE deal_id = %s"
        cursor.execute(query, params)
        
        mycon.commit()
        cursor.close()
        mycon.close()
        
        print(f"✅ Deal {deal_id} updated to stage {deal_stage}")
        return jsonify({'success': True, 'message': 'Deal updated'}), 200
        
    except Exception as e:
        print(f"❌ Update deal error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500