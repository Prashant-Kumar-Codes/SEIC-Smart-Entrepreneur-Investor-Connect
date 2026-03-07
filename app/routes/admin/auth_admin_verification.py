# ========================================================================
# Admin Verification Blueprint
# Purpose: Simple admin dashboard to approve or reject pending users
# ========================================================================

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from routes.extensions import get_db_connection

admin_verification = Blueprint('admin_verification', __name__)


# ========================================================================
# DECORATOR: Require Admin Access
# ========================================================================

def require_admin(f):
    """
    Decorator to ensure only admin users can access verification routes.
    """
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'error')
            return redirect(url_for('login_signup_auth.login_signup'))
        
        if session.get('user_role') != 'admin':
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('login_signup_auth.login_signup'))
        
        return f(*args, **kwargs)
    
    return decorated_function


# ========================================================================
# GET: Admin Verification Dashboard
# ========================================================================

# ========================================================================
# GET: Admin Verification Dashboard - Show Only Unauthorized Users
# ========================================================================

@admin_verification.route('/admin/verification', methods=['GET'])
@require_admin
def verification_dashboard():
    """
    Display admin dashboard with unauthorized users ready for approval/rejection.
    """
    try:
        mycon = get_db_connection()
        cursor = mycon.cursor(dictionary=True)
        
        # Get only unauthorized users who are verified
        cursor.execute("""
            SELECT id, username, email, role, created_at
            FROM login_data 
            WHERE is_verified = 1 AND authorized = 'not_authorized'
            ORDER BY created_at DESC
        """)
        
        users = cursor.fetchall()
        cursor.close()
        mycon.close()
        
        # Format dates
        for user in users:
            user['created_at'] = user['created_at'].strftime('%Y-%m-%d %H:%M') if user['created_at'] else 'N/A'
        
        print(f"[ADMIN] Dashboard loaded | unauthorized users: {len(users)}")
        
        return render_template(
            'auth/admin/admin_dashboard.html',
            users=users,
            admin_username=session.get('username')
        )
    
    except Exception as e:
        print(f"[ERROR] Failed to load dashboard: {e}")
        import traceback
        traceback.print_exc()
        flash('Failed to load dashboard.', 'error')
        return redirect(url_for('login_signup_auth.admin_dashboard'))


# ========================================================================
# POST: Authorize User
# ========================================================================

@admin_verification.route('/admin/verify/approve', methods=['POST'])
@require_admin
def approve_user():
    """
    Authorize a pending user.
    """
    try:
        data = request.get_json()
        user_email = data.get('email', '').strip()
        
        if not user_email:
            return jsonify({'success': False, 'message': 'Email is required.'}), 400
        
        mycon = get_db_connection()
        cursor = mycon.cursor(dictionary=True)
        
        # Check if user exists and is unauthorized
        cursor.execute("SELECT username, role FROM login_data WHERE email = %s", (user_email,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            mycon.close()
            return jsonify({'success': False, 'message': 'User not found.'}), 404
        
        # Update authorized status
        cursor.execute(
            "UPDATE login_data SET authorized = 'authorized' WHERE email = %s",
            (user_email,)
        )
        mycon.commit()
        cursor.close()
        mycon.close()
        
        print(f"[OK] User authorized: {user_email} ({user['role']})")
        
        return jsonify({
            'success': True,
            'message': f"{user['username']} has been authorized."
        }), 200
    
    except Exception as e:
        print(f"[ERROR] Failed to authorize user: {e}")
        return jsonify({'success': False, 'message': 'Failed to authorize user.'}), 500


# ========================================================================
# POST: Reject and Delete User
# ========================================================================

@admin_verification.route('/admin/verify/reject', methods=['POST'])
@require_admin
def reject_user():
    """
    Reject a pending user and delete their account.
    """
    try:
        data = request.get_json()
        user_email = data.get('email', '').strip()
        
        if not user_email:
            return jsonify({'success': False, 'message': 'Email is required.'}), 400
        
        mycon = get_db_connection()
        cursor = mycon.cursor(dictionary=True)
        
        # Get user info before deletion
        cursor.execute("SELECT username, role FROM login_data WHERE email = %s", (user_email,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            mycon.close()
            return jsonify({'success': False, 'message': 'User not found.'}), 404
        
        # DELETE the user account
        cursor.execute("DELETE FROM login_data WHERE email = %s", (user_email,))
        mycon.commit()
        cursor.close()
        mycon.close()
        
        print(f"[DELETED] User rejected and account deleted: {user_email} ({user['role']})")
        
        return jsonify({
            'success': True,
            'message': f"{user['username']}'s account has been deleted."
        }), 200
    
    except Exception as e:
        print(f"[ERROR] Failed to reject user: {e}")
        return jsonify({'success': False, 'message': 'Failed to reject user.'}), 500
