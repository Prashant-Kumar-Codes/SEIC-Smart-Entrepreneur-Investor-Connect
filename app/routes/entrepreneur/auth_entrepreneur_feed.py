from ..extensions import *

entrepreneur_feed_auth = Blueprint('entrepreneur_feed_auth', __name__)


# =====================================================================
# HELPERS
# =====================================================================

def get_entrepreneur_profile(email):
    """Fetch joined entrepreneur profile + login_data row."""
    mycon  = get_db_connection()
    cursor = mycon.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT
            ld.email, ld.username, ld.age, ld.gender,
            ep.startup_name, ep.bio, ep.industry, ep.location,
            ep.website_url, ep.profile_image_url,
            ep.linkedin_url, ep.twitter_url,
            ep.profile_views, ep.investors_connected, ep.total_pitches
        FROM login_data ld
        LEFT JOIN entrepreneur_profile ep ON ld.email = ep.email
        WHERE ld.email = %s
    """, (email,))
    profile = cursor.fetchone()
    cursor.close()
    mycon.close()
    return profile


def get_feed_posts(limit=20, offset=0):
    """Fetch pitch feed with author info, newest first."""
    mycon  = get_db_connection()
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
    cursor.close()
    mycon.close()
    return posts


def get_message_threads(email):
    """Get latest message per conversation partner for inbox sidebar."""
    mycon  = get_db_connection()
    cursor = mycon.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT
            m.message_id,
            CASE
                WHEN m.sender_email   = %s THEN m.receiver_email
                ELSE m.sender_email
            END AS partner_email,
            m.message_text AS last_message,
            m.sent_at,
            m.is_read,
            m.sender_email,
            ld.username AS partner_name,
            ep.profile_image_url  AS partner_image,
            ip.profile_image_url  AS partner_image_investor
        FROM messages m
        JOIN (
            SELECT
                MAX(message_id) AS max_id
            FROM messages
            WHERE sender_email = %s OR receiver_email = %s
            GROUP BY LEAST(sender_email, receiver_email), GREATEST(sender_email, receiver_email)
        ) latest ON m.message_id = latest.max_id
        JOIN login_data ld
            ON ld.email = CASE
                WHEN m.sender_email = %s THEN m.receiver_email
                ELSE m.sender_email
            END
        LEFT JOIN entrepreneur_profile ep
            ON ep.email = ld.email
        LEFT JOIN investor_profiles ip
            ON ip.email = ld.email
        ORDER BY m.sent_at DESC
        LIMIT 20
    """, (email, email, email, email))
    threads = cursor.fetchall()
    cursor.close()
    mycon.close()
    return threads


def get_unread_count(email):
    """Count unread messages for navbar badge."""
    mycon  = get_db_connection()
    cursor = mycon.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM messages WHERE receiver_email = %s AND is_read = false",
        (email,)
    )
    count = cursor.fetchone()[0]
    cursor.close()
    mycon.close()
    return count


def get_notification_count(email):
    """Count unread notifications for navbar badge."""
    mycon  = get_db_connection()
    cursor = mycon.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM notifications WHERE email = %s AND is_read = false",
        (email,)
    )
    count = cursor.fetchone()[0]
    cursor.close()
    mycon.close()
    return count

def get_profile_data(email):
    """Fetch complete entrepreneur profile."""
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
    cursor.close()
    mycon.close()
    return profile

def time_ago(dt):
    """Convert datetime to '2h ago' style string."""
    from datetime import datetime
    now   = datetime.now()
    delta = now - dt
    s     = int(delta.total_seconds())
    if s < 60:      return "just now"
    if s < 3600:    return f"{s // 60}m ago"
    if s < 86400:   return f"{s // 3600}h ago"
    if s < 604800:  return f"{s // 86400}d ago"
    return dt.strftime("%b %d")


# =====================================================================
# MAIN DASHBOARD ROUTE
# =====================================================================

@entrepreneur_feed_auth.route('/dashboard/entrepreneur/feed')
def entrepreneur_feed():
    if 'user_id' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('login_signup_auth.login_signup'))

    email = session.get('user_email')
    print(f"📊 Pitch Feed → {email}")

    profile       = get_profile_data(email)
    posts         = get_feed_posts(limit=20)
    threads       = get_message_threads(email)
    unread_msgs   = get_unread_count(email)
    unread_notifs = get_notification_count(email)

    # Attach human-readable time to posts
    for p in posts:
        p['time_ago'] = time_ago(p['created_at'])

    from datetime import datetime
    return render_template(
        'auth/entrepreneur/entrepreneur_feed.html',
        profile       = profile,
        posts         = posts,
        threads       = threads,
        unread_msgs   = unread_msgs,
        unread_notifs = unread_notifs,
        now_year      = datetime.now().year
    )


# =====================================================================
# CREATE PITCH POST
# =====================================================================

@entrepreneur_feed_auth.route('/api/posts/create', methods=['POST'])
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

        # Increment entrepreneur's total_pitches
        cursor.execute("""
            UPDATE entrepreneur_profile SET total_pitches = total_pitches + 1
            WHERE email = %s
        """, (email,))

        mycon.commit()
        post_id = cursor.lastrowid
        cursor.close()
        mycon.close()

        print(f"✅ Pitch created: post_id={post_id} by {email}")
        return jsonify({'success': True, 'post_id': post_id}), 201

    except Exception as e:
        print(f"❌ Create post error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': 'Failed to create post.'}), 500


# =====================================================================
# POST INTERACTION  (like / save / interested)
# =====================================================================

@entrepreneur_feed_auth.route('/api/posts/<int:post_id>/interact', methods=['POST'])
def interact_post(post_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    email            = session.get('user_email')
    data             = request.get_json()
    interaction_type = data.get('type')   # 'like' | 'save' | 'interested' | 'view'

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

        # Upsert interaction (ignore duplicate)
        cursor.execute("""
            INSERT INTO post_interactions (user_email, post_id, interaction_type)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (email, post_id, interaction_type))

        toggled = cursor.rowcount > 0   # 1 = new interaction, 0 = already existed

        if toggled:
            col = count_col_map[interaction_type]
            cursor.execute(f"""
                UPDATE user_posts SET {col} = {col} + 1 WHERE post_id = %s
            """, (post_id,))

        mycon.commit()
        cursor.close()
        mycon.close()
        return jsonify({'success': True, 'toggled': toggled}), 200

    except Exception as e:
        print(f"❌ Interact error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': 'Interaction failed.'}), 500


# =====================================================================
# EDIT ENTREPRENEUR PROFILE (simple)
# =====================================================================

@entrepreneur_feed_auth.route('/api/profile/edit', methods=['POST'])
def edit_profile():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    email = session.get('user_email')
    data  = request.get_json()

    fields = {
        'startup_name':  data.get('startup_name', '').strip(),
        'bio':           data.get('bio', '').strip(),
        'industry':      data.get('industry', '').strip(),
        'location':      data.get('location', '').strip(),
        'website_url':   data.get('website_url', '').strip(),
        'linkedin_url':  data.get('linkedin_url', '').strip(),
        'twitter_url':   data.get('twitter_url', '').strip(),
    }

    try:
        mycon  = get_db_connection()
        cursor = mycon.cursor()

        # Upsert profile row
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
              fields['startup_name'], fields['bio'], fields['industry'],
              fields['location'],     fields['website_url'],
              fields['linkedin_url'], fields['twitter_url']))

        mycon.commit()
        cursor.close()
        mycon.close()
        return jsonify({'success': True}), 200

    except Exception as e:
        print(f"❌ Edit profile error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': 'Profile update failed.'}), 500


# =====================================================================
# EDIT ENTREPRENEUR PROFILE (full - all fields)
# =====================================================================

@entrepreneur_feed_auth.route('/api/profile/edit/full', methods=['POST'])
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
        return jsonify({'success': True}), 200

    except Exception as e:
        print(f"❌ Full profile edit error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': 'Profile update failed.'}), 500


# =====================================================================
# SEND MESSAGE
# =====================================================================

@entrepreneur_feed_auth.route('/api/messages/send', methods=['POST'])
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
        mycon  = get_db_connection()
        cursor = mycon.cursor()
        cursor.execute("""
            INSERT INTO messages (sender_email, receiver_email, message_text)
            VALUES (%s, %s, %s)
        """, (sender_email, receiver_email, message_text))
        mycon.commit()
        cursor.close()
        mycon.close()
        return jsonify({'success': True}), 201

    except Exception as e:
        print(f"❌ Send message error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': 'Message failed to send.'}), 500


# =====================================================================
# MARK MESSAGES AS READ
# =====================================================================

@entrepreneur_feed_auth.route('/api/messages/read', methods=['POST'])
def mark_messages_read():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    email        = session.get('user_email')
    data         = request.get_json()
    partner_email = data.get('partner_email', '').strip()

    try:
        mycon  = get_db_connection()
        cursor = mycon.cursor()
        cursor.execute("""
            UPDATE messages
            SET is_read = true, read_at = NOW()
            WHERE receiver_email = %s AND sender_email = %s AND is_read = false
        """, (email, partner_email))
        mycon.commit()
        cursor.close()
        mycon.close()
        return jsonify({'success': True}), 200

    except Exception as e:
        print(f"❌ Mark read error: {e}")
        return jsonify({'success': False, 'message': 'Failed to mark messages as read.'}), 500


# =====================================================================
# LOAD MORE FEED  (pagination)
# =====================================================================

@entrepreneur_feed_auth.route('/api/feed', methods=['GET'])
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


# =====================================================================
# PROFILE VIEW TRACKER
# =====================================================================

@entrepreneur_feed_auth.route('/api/profile/<viewed_email>/view', methods=['POST'])
def log_profile_view(viewed_email):
    viewer_email = session.get('user_email')

    try:
        mycon  = get_db_connection()
        cursor = mycon.cursor()
        cursor.execute("""
            INSERT INTO profile_view_logs (viewed_email, viewer_email)
            VALUES (%s, %s)
        """, (viewed_email, viewer_email))

        cursor.execute("""
            UPDATE entrepreneur_profile
            SET profile_views = profile_views + 1
            WHERE email = %s
        """, (viewed_email,))

        mycon.commit()
        cursor.close()
        mycon.close()
        return jsonify({'success': True}), 200

    except Exception as e:
        print(f"❌ Profile view log error: {e}")
        return jsonify({'success': False}), 500