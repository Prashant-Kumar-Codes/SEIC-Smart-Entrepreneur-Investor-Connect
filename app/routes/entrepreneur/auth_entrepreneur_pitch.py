from ..extensions import *
from ...models.ai_matchmaking import async_trigger_on_pitch_save
from ...models.ai_entrepreneur_scoring import compute_and_save_entrepreneur_profile_score

entrepreneur_pitch_deck_auth = Blueprint('entrepreneur_pitch_deck_auth', '__name__')


@entrepreneur_pitch_deck_auth.route('/dashboard/entrepreneur/pitch-deck')
def pitch_deck_page():
    if 'user_id' not in session:
        flash('Please log in first.', 'error')
        return redirect(url_for('login_signup_auth.login_signup'))

    email = session.get('user_email')
    print(f"📄 Pitch Deck → {email}")

    conn   = get_request_conn()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT ld.email, ld.username, ep.startup_name, ep.profile_image_url,
               ep.total_pitches, ep.investors_connected, ep.profile_views,
               ep.funding_required, ep.funding_progress_pct,
               ep.pitch_deck_url, ep.video_pitch_url
        FROM login_data ld
        LEFT JOIN entrepreneur_profile ep ON ld.email = ep.email
        WHERE ld.email = %s
    """, (email,))
    profile = cursor.fetchone()

    cursor.execute("SELECT * FROM pitch_content WHERE email = %s", (email,))
    pitch = cursor.fetchone() or {}
    cursor.close()

    return render_template(
        'auth/entrepreneur/entrepreneur_pitch_deck.html',
        profile       = profile,
        pitch         = pitch,
        unread_msgs   = get_unread_count(email),
        unread_notifs = get_notification_count(email),
    )


@entrepreneur_pitch_deck_auth.route('/api/pitch/enhance', methods=['POST'])
def enhance_pitch():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    data         = request.get_json()
    section_name = data.get('section', '').strip()
    content      = data.get('content', '').strip()
    startup_name = data.get('startup_name', '').strip()

    if not content:
        return jsonify({'success': False, 'message': 'No content to enhance.'}), 400

    context = f" for a startup called '{startup_name}'" if startup_name else ''
    system_prompt = (
        "You are a world-class startup pitch coach who has helped founders raise over $2B. "
        "You write crisp, compelling, investor-ready pitch content that is specific, data-driven, "
        "and emotionally resonant. Avoid jargon and buzzwords. Be direct, confident, and clear. "
        "Return ONLY the enhanced content — no preamble, no explanation, no quotes around it."
    )
    user_prompt = (
        f"Enhance the following '{section_name}' section of a startup pitch deck{context}. "
        f"Keep the same core facts but make it sharper, more compelling, and investor-ready. "
        f"Match the original length roughly (±20%). Use a professional but engaging tone.\n\n"
        f"Original:\n{content}"
    )

    try:
        client = get_gemini_client()
        response = client.models.generate_content(
            model="gemini-2.5-flash", contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt, max_output_tokens=800, temperature=0.4))
        enhanced = response.text.strip()
        if not enhanced:
            return jsonify({"success": False, "message": "Empty response from AI."}), 500
        print(f"✅ AI enhanced '{section_name}' for {session.get('user_email')}")
        return jsonify({"success": True, "enhanced": enhanced}), 200
    except Exception as e:
        error_msg = str(e).lower()
        if any(x in error_msg for x in ["api key", "authentication", "401"]):
            return jsonify({"success": False, "message": "AI service configuration error."}), 500
        elif any(x in error_msg for x in ["quota", "rate limit", "429"]):
            return jsonify({"success": False, "message": "AI rate limit reached. Try again shortly."}), 429
        elif any(x in error_msg for x in ["blocked", "safety"]):
            return jsonify({"success": False, "message": "Request blocked by AI safety filters."}), 400
        else:
            print(f"❌ AI enhance error: {e}")
            import traceback; traceback.print_exc()
            return jsonify({"success": False, "message": "AI enhancement failed. Try again."}), 500


@entrepreneur_pitch_deck_auth.route('/api/pitch/save', methods=['POST'])
def save_pitch():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    email = session.get('user_email')
    data  = request.get_json()

    try:
        conn   = get_request_conn()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            INSERT INTO pitch_content
                (email, problem, solution, market, business_model,
                 traction, team, financials, the_ask, video_pitch_url)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (email) DO UPDATE SET
                problem = EXCLUDED.problem, solution = EXCLUDED.solution,
                market = EXCLUDED.market, business_model = EXCLUDED.business_model,
                traction = EXCLUDED.traction, team = EXCLUDED.team,
                financials = EXCLUDED.financials, the_ask = EXCLUDED.the_ask,
                video_pitch_url = EXCLUDED.video_pitch_url, updated_at = NOW()
        """, (email, data.get('problem','').strip() or None, data.get('solution','').strip() or None,
              data.get('market','').strip() or None, data.get('business_model','').strip() or None,
              data.get('traction','').strip() or None, data.get('team','').strip() or None,
              data.get('financials','').strip() or None, data.get('the_ask','').strip() or None,
              data.get('video_pitch_url','').strip() or None))
        conn.commit()

        cursor.execute("SELECT * FROM entrepreneur_profile WHERE email = %s", (email,))
        profile = cursor.fetchone() or {}
        cursor.execute("SELECT * FROM pitch_content WHERE email = %s", (email,))
        pitch = cursor.fetchone() or {}
        cursor.close()

        print(f"✅ Pitch saved: {email}")
        try:
            async_trigger_on_pitch_save(email, profile, pitch)
        except Exception as embed_err:
            print(f"⚠️ Embedding queue error: {embed_err}")
        try:
            result = compute_and_save_entrepreneur_profile_score(email, conn)
            if result: print(f"✅ Profile score updated after pitch save for {email}")
            else: print(f"⚠️ Profile score skipped for {email}")
        except Exception as scoring_err:
            print(f"⚠️ Profile scoring error: {scoring_err}")

        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"❌ Save pitch error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': 'Failed to save pitch.'}), 500


@entrepreneur_pitch_deck_auth.route('/api/pitch/deck-url', methods=['POST'])
def save_deck_url():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    email = session.get('user_email')
    data  = request.get_json()
    url   = data.get('pitch_deck_url', '').strip()
    try:
        conn = get_request_conn(); cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO entrepreneur_profile (email, pitch_deck_url) VALUES (%s, %s)
            ON CONFLICT (email) DO UPDATE SET pitch_deck_url = EXCLUDED.pitch_deck_url
        """, (email, url or None))
        conn.commit(); cursor.close()
        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"❌ Deck URL save error: {e}")
        return jsonify({'success': False, 'message': 'Failed.'}), 500


@entrepreneur_pitch_deck_auth.route('/api/pitch/video-upload', methods=['POST'])
def upload_pitch_video():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    if 'video' not in request.files:
        return jsonify({'success': False, 'message': 'No video file received.'}), 400

    email = session.get('user_email')
    video = request.files['video']
    ALLOWED = {'mp4', 'mov', 'avi', 'webm', 'mkv'}
    ext = video.filename.rsplit('.', 1)[-1].lower() if '.' in video.filename else ''
    if ext not in ALLOWED:
        return jsonify({'success': False, 'message': f'Unsupported file type: .{ext}'}), 400
    MAX_BYTES = 200 * 1024 * 1024
    video.seek(0, 2); size = video.tell(); video.seek(0)
    if size > MAX_BYTES:
        return jsonify({'success': False, 'message': 'File too large (max 200MB).'}), 400

    try:
        import uuid, os as _os
        from werkzeug.utils import secure_filename
        upload_folder = _os.path.join('static', 'uploads', 'pitch_videos')
        _os.makedirs(upload_folder, exist_ok=True)
        filename  = f"{uuid.uuid4().hex}_{secure_filename(video.filename)}"
        save_path = _os.path.join(upload_folder, filename)
        video.save(save_path)
        video_url = f"/static/uploads/pitch_videos/{filename}"

        conn = get_request_conn(); cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO entrepreneur_profile (email, video_pitch_url) VALUES (%s, %s)
            ON CONFLICT (email) DO UPDATE SET video_pitch_url = EXCLUDED.video_pitch_url
        """, (email, video_url))
        cursor.execute("INSERT INTO pitch_content (email) VALUES (%s) ON CONFLICT DO NOTHING", (email,))
        cursor.execute("UPDATE pitch_content SET video_pitch_url = %s WHERE email = %s", (video_url, email))
        conn.commit(); cursor.close()

        print(f"✅ Video uploaded: {filename} for {email}")
        return jsonify({'success': True, 'video_url': video_url}), 200
    except Exception as e:
        print(f"❌ Video upload error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': 'Video upload failed.'}), 500
