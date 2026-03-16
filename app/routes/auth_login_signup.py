from .extensions import *

login_signup_auth = Blueprint('login_signup_auth', __name__)


# =====================================================================
# LOGIN / SIGNUP PAGE
# =====================================================================

@login_signup_auth.route('/login_signup', methods=['GET'])
def login_signup():
    redirect_to = request.args.get('redirect_to', '')
    print(f"📄 login_signup page | redirect_to='{redirect_to}'")
    return render_template('auth/login_signup.html', redirect_to=redirect_to)


# =====================================================================
# OTP VERIFY PAGE (GET)
# =====================================================================

@login_signup_auth.route('/verify', methods=['GET'])
def verify_page():
    if 'verification_email' not in session:
        flash('Please sign up first to verify your email.', 'error')
        return redirect(url_for('login_signup_auth.login_signup'))

    email = session['verification_email']
    print(f"📄 Verify page → {email}")

    mycon  = get_db_connection()
    cursor = mycon.cursor()
    cursor.execute("SELECT otp_created_at FROM login_data WHERE email = %s", (email,))
    result = cursor.fetchone()
    cursor.close()
    mycon.close()

    remaining = 600
    if result and result[0]:
        elapsed   = (datetime.utcnow() - result[0]).total_seconds()
        remaining = max(0, 600 - int(elapsed))

    print(f"⏱ OTP remaining: {remaining}s for {email}")
    return render_template('auth/verify.html', remaining=remaining)


# =====================================================================
# OTP VERIFY (POST)
# =====================================================================

@login_signup_auth.route('/verify', methods=['POST'])
def verify():
    try:
        email = session.get('verification_email')
        print(f"🔐 Verify POST → {email}")

        if not email:
            flash('Session expired. Please sign up again.', 'error')
            return redirect(url_for('login_signup_auth.login_signup'))

        otp = request.form.get('otp', '').strip()
        print(f"🔑 OTP entered: {otp}")

        if not otp or len(otp) != 6:
            flash('Please enter a valid 6-digit OTP.', 'error')
            return redirect(url_for('login_signup_auth.verify_page'))

        mycon  = get_db_connection()
        cursor = mycon.cursor()
        # Always look up by email
        cursor.execute("SELECT otp, otp_created_at FROM login_data WHERE email = %s", (email,))
        result = cursor.fetchone()

        if not result:
            cursor.close(); mycon.close()
            print(f"❌ No DB record for email: {email}")
            flash('User not found. Please sign up again.', 'error')
            return redirect(url_for('login_signup_auth.login_signup'))

        stored_otp, otp_created_at = result
        print(f"🗄 Stored OTP: {stored_otp} | Created: {otp_created_at}")

        if datetime.utcnow() - otp_created_at > timedelta(minutes=10):
            cursor.close(); mycon.close()
            print(f"⌛ OTP expired for {email}")
            flash('OTP has expired. Please request a new one.', 'error')
            return redirect(url_for('login_signup_auth.verify_page'))

        if stored_otp != otp:
            cursor.close(); mycon.close()
            print(f"❌ OTP mismatch for {email}: got '{otp}' expected '{stored_otp}'")
            flash('Invalid OTP. Please try again.', 'error')
            return redirect(url_for('login_signup_auth.verify_page'))

        cursor.execute("UPDATE login_data SET is_verified = true, otp = NULL WHERE email = %s", (email,))
        mycon.commit()
        cursor.close(); mycon.close()

        print(f"[OK] Email verified: {email}")
        session.pop('verification_email', None)
        session.pop('verification_username', None)

        flash('Email verified successfully! You can now log in.', 'success')
        return redirect(url_for('login_signup_auth.login_signup'))

    except Exception as e:
        print(f"❌ Verify error: {e}")
        import traceback; traceback.print_exc()
        flash('Verification failed. Please try again.', 'error')
        return redirect(url_for('login_signup_auth.verify_page'))


# =====================================================================
# RESEND OTP
# =====================================================================

@login_signup_auth.route('/resend_otp', methods=['POST'])
def resend_otp():
    try:
        email    = session.get('verification_email')
        username = session.get('verification_username', 'User')
        print(f"📧 Resend OTP → {email}")

        if not email:
            flash('Session expired. Please sign up again.', 'error')
            return redirect(url_for('login_signup_auth.login_signup'))

        otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])

        mycon  = get_db_connection()
        cursor = mycon.cursor()
        cursor.execute("UPDATE login_data SET otp = %s, otp_created_at = %s WHERE email = %s", (otp, datetime.utcnow(), email))
        mycon.commit()
        cursor.close(); mycon.close()
        print(f"🗄 New OTP saved for {email}")

        try:
            send_otp_email(email, otp, username)
            return jsonify({'success': True, 'message': 'New OTP sent to your email!'})
        except Exception as e:
            print(f"[WARNING] Email send failed: {e}")
            return jsonify({'success': False, 'message': 'Failed to send email. Please check your internet or try again later.'}), 500

    except Exception as e:
        print(f"❌ Resend OTP error: {e}")
        return jsonify({'success': False, 'message': 'An error occurred. Please try again.'}), 500


# =====================================================================
# LOGIN  (JSON API — called by JS fetch)
# =====================================================================

@login_signup_auth.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'GET':
        return redirect(url_for('login_signup_auth.login_signup'))

    try:
        data     = request.get_json()
        email    = data.get('email', '').strip()
        password = data.get('password', '')
        role     = data.get('role', '').strip()

        print(f"🔐 Login attempt → email:{email} role:{role}")

        if not email or not password or not role:
            return jsonify({'success': False, 'message': 'Email, password and role are required.'}), 400

        mycon  = get_db_connection()
        cursor = mycon.cursor()

        # CHANGE 1: First, check if the user is verified.
        cursor.execute("SELECT is_verified FROM login_data WHERE email = %s", (email,))
        is_verified_result = cursor.fetchone()

        if not is_verified_result:
            print(f"❌ No user found for email: {email}")
            return jsonify({'success': False, 'message': 'No account found with this email. Please Sign Up first.'}), 401

        if not is_verified_result[0]:
            print(f"[WARNING] Account not verified: {email}")
            # Fetch username for the session
            cursor.execute("SELECT username FROM login_data WHERE email = %s", (email,))
            username_result = cursor.fetchone()
            session['verification_email']    = email
            session['verification_username'] = username_result[0] if username_result else 'User'
            cursor.close()
            mycon.close()
            return jsonify({
                'success': False,
                'message': 'Your account is not verified. Please check your inbox for the OTP or sign up again.',
                'redirect_to_verify': True
            }), 403

        # CHANGE 2: User is verified, now fetch all data for login (INCLUDING AUTHORIZATION STATUS)
        cursor.execute(
            "SELECT id, username, email, age, gender, role, password, authorized FROM login_data WHERE email = %s",
            (email,)
        )
        user = cursor.fetchone()
        cursor.close(); mycon.close()

        # This check is technically redundant now but good for safety
        if not user:
            print(f"❌ Verified user suddenly not found: {email}")
            return jsonify({'success': False, 'message': 'An unexpected error occurred. Please try again.'}), 500

        user_id, username, user_email, age, gender, db_role, hashed_password, authorized = user
        print(f"[USER] Found verified user: {username} | db_role:{db_role} | authorized:{authorized}")

        # Check role matches what they selected
        if db_role != role:
            print(f"[WARNING] Role mismatch: form='{role}' db='{db_role}'")
            return jsonify({'success': False, 'message': f"Wrong role selected. Your account role is '{db_role}'."}), 401

        # Check password
        if not check_password_hash(hashed_password, password):
            print(f"❌ Wrong password: {email}")
            return jsonify({'success': False, 'message': 'Invalid email or password.'}), 401


        # All checks passed — set session (including authorization status)
        session.permanent  = True
        session['user_id']     = user_id
        session['username']    = username
        session['user_email']  = user_email
        session['user_age']    = age
        session['user_gender'] = gender
        session['user_role']   = db_role
        session['user_authorized'] = authorized  # NEW: Store authorization status for profile display

        print(f"[OK] Login OK: {username} | role:{db_role} | authorized:{authorized}")
        print(f"📋 id:{user_id} email:{user_email} age:{age} gender:{gender}")

        from flask import current_app
        role_redirects = {
            'entrepreneur': url_for('entrepreneur_dashboard_bp.entrepreneur_home'),
            'investor':     url_for('investor_dashboard_bp.investor_home'),
            'admin':        url_for('admin_verification.verification_dashboard' if 'admin_verification.verification_dashboard' in [rule.endpoint for rule in current_app.url_map.iter_rules()] else ''),
        }
        redirect_url = role_redirects.get(db_role)
        if not redirect_url:
            return jsonify({'success': False, 'message': f"Unknown role: {db_role}"}), 400

        print(f"➡ Redirecting → {redirect_url}")
        return jsonify({'success': True, 'message': f'Welcome back, {username}!', 'redirect_url': redirect_url}), 200

    except Exception as e:
        print(f"❌ Login error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': 'Login failed. Please try again.'}), 500


# =====================================================================
# SIGNUP  (JSON API — called by JS fetch)
# =====================================================================

@login_signup_auth.route('/signup', methods=['POST'])
def signup():
    try:
        data     = request.get_json()
        username = data.get('username', '').strip()
        email    = data.get('email', '').strip()
        age      = data.get('age')
        gender   = data.get('gender', '').strip()
        role     = data.get('role', '').strip()
        password = data.get('password', '')

        print(f"📝 Signup → {username} | {email} | age:{age} | {gender} | {role}")

        if not all([username, email, age, gender, role, password]):
            return jsonify({'success': False, 'message': 'All fields are required.'}), 400
        if len(password) < 6:
            return jsonify({'success': False, 'message': 'Password must be at least 6 characters.'}), 400

        hashed_password = generate_password_hash(password)
        otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])

        mycon  = get_db_connection()
        cursor = mycon.cursor()

        # CHANGE 1 & 2: Always check email, and also check is_verified
        cursor.execute("SELECT username, is_verified FROM login_data WHERE email = %s", (email,))
        existing = cursor.fetchone()

        if existing:
            existing_username, is_verified = existing
            cursor.close(); mycon.close()

            if is_verified:
                # Fully registered account — tell them to log in
                print(f"[WARNING] Email already registered & verified: {email}")
                return jsonify({
                    'success': False,
                    'message': 'This email is already registered. Please log in instead.'
                }), 409
            else:
                # CHANGE 3: Account exists but is unverified — tell them clearly and redirect to verify
                print(f"[WARNING] Email exists but not verified: {email}")
                session['verification_email']    = email
                session['verification_username'] = existing_username
                return jsonify({
                    'success': False,
                    'message': f'An account with this email already exists but is not verified yet. Please check your inbox for the OTP and verify your account.',
                    'redirect_to_verify': True
                }), 409

        # Fresh signup — insert user (with authorized = 'not_authorized' by default)
        cursor.execute(
            """INSERT INTO login_data (username, email, age, gender, role, password, otp, otp_created_at, is_verified, authorized)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, false, 'not_authorized')""",
            (username, email, age, gender, role, hashed_password, otp, datetime.utcnow())
        )
        mycon.commit()
        cursor.close(); mycon.close()
        print(f"[OK] User inserted: {email} | authorized: not_authorized")

        session['verification_email']    = email
        session['verification_username'] = username

        try:
            send_otp_email(email, otp, username)
            print(f"[OK] OTP email sent -> {email}")
            return jsonify({
                'success': True,
                'message': 'Account created! Please check your email for the OTP.'
            }), 201
        except Exception as e:
            print(f"[WARNING] OTP email failed: {e}")
            return jsonify({
                'success': True, # Still 201 because user is created, but with a warning
                'message': 'Account created, but we failed to send the OTP email. Please use the "Resend OTP" button on the next page.',
                'redirect_to_verify': True
            }), 201

    except Exception as e:
        print(f"❌ Signup error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': 'Registration failed. Please try again.'}), 500


# =====================================================================
# LOGOUT
# =====================================================================

@login_signup_auth.route('/logout', methods=['POST', 'GET'])
def logout():
    print(f"🚪 Logout → {session.get('username', 'Unknown')}")
    session.clear()
    return redirect(url_for('login_signup_auth.login_signup'))


# =====================================================================
# HELPER: Send OTP Email
# mail is imported from extensions via "from .extensions import *"
# =====================================================================

def send_otp_email(email, otp, username):
    print(f"📧 Sending OTP email → {email} (user: {username})")

    msg = Message(
        subject    = "Your OTP for EISC Verification",
        recipients = [email],
        html       = f"""
<html>
<head>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
      background:#f3f4f6; margin:0; padding:0; color:#1f2937;
    }}
    .wrap  {{ max-width:600px; margin:0 auto; background:#fff; }}
    .hdr   {{
      background: linear-gradient(135deg,#667eea,#764ba2);
      color:#fff; padding:40px 30px; text-align:center;
    }}
    .hdr h1 {{ margin:0 0 8px; font-size:26px; }}
    .hdr p  {{ margin:0; opacity:.9; font-size:15px; }}
    .body   {{ padding:36px 30px; }}
    .otp-box {{
      text-align:center; padding:28px;
      background:linear-gradient(135deg,#f0fdf4,#dcfce7);
      border-radius:12px; margin:24px 0;
    }}
    .otp-label {{
      font-size:13px; font-weight:600; color:#6b7280;
      text-transform:uppercase; letter-spacing:1px; margin-bottom:12px;
    }}
    .otp-code  {{ font-size:46px; font-weight:900; color:#667eea; letter-spacing:10px; }}
    .note {{
      background:#f9fafb; border-left:4px solid #667eea;
      padding:16px; border-radius:8px; color:#4b5563; font-size:14px;
    }}
    .warn {{
      background:linear-gradient(135deg,#fef3c7,#fde68a);
      border-left:4px solid #f59e0b;
      padding:16px; border-radius:8px; margin-top:16px;
      color:#78350f; font-size:14px;
    }}
    .ftr {{
      text-align:center; padding:24px;
      background:#f9fafb; color:#6b7280; font-size:13px;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hdr">
      <h1>🔐 Email Verification</h1>
      <p>Entrepreneurs and Investors Smart Connect</p>
    </div>
    <div class="body">
      <p>Hello <strong>{username}</strong>,</p>
      <p>Welcome to EISC! Use the code below to verify your email address.</p>
      <div class="otp-box">
        <div class="otp-label">Your One-Time Password</div>
        <div class="otp-code">{otp}</div>
      </div>
      <div class="note">
        This OTP is valid for <strong>10 minutes</strong>.
        Enter it on the verification page to complete registration.
      </div>
      <div class="warn">
        ⚠️ Didn't request this? You can safely ignore this email.
      </div>
    </div>
    <div class="ftr">
      <strong>EISC Team</strong><br>Connecting Entrepreneurs and Investors
    </div>
  </div>
</body>
</html>"""
    )
    mail.send(msg)
    print(f"[OK] OTP email dispatched -> {email}")


# =====================================================================
# DELETING UNVERIFIED USERS
# =====================================================================

def delete_unverified_users():
    """
    Connects to the database and deletes users who signed up more than
    24 hours ago and are still not verified.
    """
    try:
        mycon = get_db_connection()
        cursor = mycon.cursor()

        # Calculate the cutoff time (24 hours ago)
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        
        # Find unverified users who are older than 24 hours
        cursor.execute(
            "SELECT email FROM login_data WHERE is_verified = false AND otp_created_at < %s",
            (cutoff_time,)
        )
        users_to_delete = cursor.fetchall()
        
        if not users_to_delete:
            print("🧹 No unverified users older than 24 hours to delete.")
            cursor.close()
            mycon.close()
            return 0

        # Delete the identified users
        email_list = [user[0] for user in users_to_delete]
        query = "DELETE FROM login_data WHERE email IN (%s)" % ','.join(['%s'] * len(email_list))
        
        cursor.execute(query, email_list)
        mycon.commit()
        
        deleted_count = cursor.rowcount
        print(f"🧹 Deleted {deleted_count} unverified users: {email_list}")

        cursor.close()
        mycon.close()
        
        return deleted_count

    except Exception as e:
        print(f"❌ Error deleting unverified users: {e}")
        import traceback
        traceback.print_exc()
        return -1

# =====================================================================
# CLEANUP ROUTE (for manual or scheduled execution)
# =====================================================================

@login_signup_auth.route('/cleanup/unverified-users', methods=['POST'])
def cleanup_unverified_users_route():
    # Simple token-based security to prevent unauthorized access
    auth_token = request.headers.get('Authorization')
    # In a real app, use a more secure, centrally managed token
    # For this example, we'll use a simple hardcoded token
    expected_token = "Bearer YOUR_SECRET_CLEANUP_TOKEN"

    if auth_token != expected_token:
        print("🚫 Unauthorized cleanup attempt.")
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    print("🚀 Starting manual cleanup of unverified users...")
    deleted_count = delete_unverified_users()

    if deleted_count >= 0:
        return jsonify({
            'success': True,
            'message': f'Cleanup successful. Deleted {deleted_count} unverified users.'
        }), 200
    else:
        return jsonify({
            'success': False,
            'message': 'An error occurred during cleanup.'
        }), 500