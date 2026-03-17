# ========================================================================
# Admin Verification Blueprint
# Purpose: Simple admin dashboard to approve or reject pending users
# ========================================================================

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from datetime import datetime
import sys
import os
from app.routes.extensions import *

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
    Supports filtering by status, search query, and pagination.
    """
    try:
        # Get parameters
        status_filter = request.args.get('status', 'pending')
        search_query = request.args.get('search', '').strip()
        page = request.args.get('page', 1, type=int)
        per_page = 10
        
        mycon = get_db_connection()
        cursor = mycon.cursor(cursor_factory=RealDictCursor)
        
        # Build the base query
        where_clauses = []
        params = []
        
        # Status filter
        if status_filter == 'pending':
            where_clauses.append("is_verified = true AND authorized = 'not_authorized'")
        elif status_filter == 'authorized':
            where_clauses.append("authorized = 'authorized'")
        elif status_filter == 'rejected':
            where_clauses.append("authorized = 'rejected'")
        # else: status_filter == 'all' -> no additional filter
        
        # Search filter
        if search_query:
            where_clauses.append("(username ILIKE %s OR email ILIKE %s OR role ILIKE %s)")
            search_param = f"%{search_query}%"
            params.extend([search_param, search_param, search_param])
        
        # Build WHERE clause
        where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM login_data {where_clause}"
        cursor.execute(count_query, params)
        total_records = cursor.fetchone()['total']
        
        # Calculate pagination
        total_pages = (total_records + per_page - 1) // per_page
        if page < 1:
            page = 1
        if page > total_pages and total_pages > 0:
            page = total_pages
        
        offset = (page - 1) * per_page
        
        # Get paginated results
        query = f"""
            SELECT id, username, email, role, authorized, created_at, is_verified
            FROM login_data 
            {where_clause}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        cursor.execute(query, params)
        users = cursor.fetchall()
        
        cursor.close()
        mycon.close()
        
        # Format dates and add status info
        for user in users:
            user['created_at'] = user['created_at'].strftime('%Y-%m-%d %H:%M') if user['created_at'] else 'N/A'
            
            # Add status_class and status_badge
            if user['authorized'] == 'authorized':
                user['status_class'] = 'authorized'
                user['status_badge'] = 'Authorized'
            elif user['authorized'] == 'rejected':
                user['status_class'] = 'rejected'
                user['status_badge'] = 'Rejected'
            else:
                user['status_class'] = 'pending'
                user['status_badge'] = 'Pending'
        
        print(f"[ADMIN] Dashboard loaded | Status: {status_filter} | Search: {search_query} | Page: {page} | Total: {total_records}")
        
        return render_template(
            'auth/admin/admin_dashboard.html',
            users=users,
            admin_username=session.get('username'),
            status_filter=status_filter,
            search_query=search_query,
            current_page=page,
            total_pages=total_pages,
            total_records=total_records
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
        cursor = mycon.cursor(cursor_factory=RealDictCursor)
        
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
        cursor = mycon.cursor(cursor_factory=RealDictCursor)
        
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


# ========================================================================
# GET: Get User Details
# ========================================================================

@admin_verification.route('/admin/user-details', methods=['GET'])
@require_admin
def get_user_details():
    """
    Fetch detailed user information for admin review.
    """
    try:
        email = request.args.get('email', '').strip()
        
        if not email:
            return jsonify({'success': False, 'message': 'Email is required.'}), 400
        
        mycon = get_db_connection()
        cursor = mycon.cursor(cursor_factory=RealDictCursor)
        
        # Get basic user info
        cursor.execute("""
            SELECT id, username, email, age, role, gender, is_verified, authorized, created_at
            FROM login_data
            WHERE email = %s
        """, (email,))
        
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            mycon.close()
            return jsonify({'success': False, 'message': 'User not found.'}), 404
        
        # Get role-specific details
        if user['role'] == 'entrepreneur':
            cursor.execute("""
                SELECT startup_name, bio, industry, location, website_url
                FROM entrepreneur_profile
                WHERE email = %s
            """, (email,))
            profile = cursor.fetchone()
            
            if profile:
                user.update(profile)
        
        elif user['role'] == 'investor':
            cursor.execute("""
                SELECT firm_name as company_name, bio, investment_focus, location, website_url
                FROM investor_profiles
                WHERE email = %s
            """, (email,))
            profile = cursor.fetchone()
            
            if profile:
                user.update(profile)
        
        cursor.close()
        mycon.close()
        
        # Format date
        if user.get('created_at'):
            user['created_at'] = user['created_at'].strftime('%Y-%m-%d %H:%M')
        
        print(f"[OK] User details fetched: {email}")
        
        return jsonify({
            'success': True,
            'user': user
        }), 200
    
    except Exception as e:
        print(f"[ERROR] Failed to fetch user details: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Failed to fetch user details.'}), 500
