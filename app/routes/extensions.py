from flask import Blueprint, render_template, request, session, flash, redirect, url_for, jsonify
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import random
import os
import psycopg2

# ============================================================
# mail lives HERE — import it as:  from .extensions import mail
# This is the standard Flask pattern to avoid circular imports
# and "cannot import name 'mail' from 'app'" errors
# ============================================================
mail = Mail()


def get_db_connection():
    """Get PostgreSQL connection using DATABASE_URL or individual parameters"""
    try:
        # Try using DATABASE_URL first (preferred)
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            # Extract connection parameters from DATABASE_URL
            # Format: postgresql://user:password@host:port/database
            from urllib.parse import urlparse
            parsed = urlparse(database_url)
            conn = psycopg2.connect(
                host     = parsed.hostname,
                port     = parsed.port or 5432,
                user     = parsed.username,
                password = parsed.password,
                database = parsed.path.lstrip('/'),
                sslmode  = 'require' if 'render' in (parsed.hostname or '') else 'prefer'
            )
            print(f"🗄 DB connected via DATABASE_URL → {parsed.hostname}")
            return conn
    except Exception as e:
        print(f"⚠️  DATABASE_URL parsing failed: {e}. Falling back to individual parameters.")
    
    # Fallback to individual parameters
    try:
        conn = psycopg2.connect(
            host     = os.getenv("POSTGRES_HOST"),
            port     = int(os.getenv("POSTGRES_PORT", 5432)),
            user     = os.getenv("POSTGRES_USER"),
            password = os.getenv("POSTGRES_PASSWORD"),
            database = os.getenv("POSTGRES_DATABASE")
        )
        print(f"🗄 DB connected → host={os.getenv('POSTGRES_HOST')} db={os.getenv('POSTGRES_DATABASE')}")
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        raise


def get_unread_count(email):
    mycon  = get_db_connection()
    cursor = mycon.cursor()
    cursor.execute("SELECT COUNT(*) FROM messages WHERE receiver_email = %s AND is_read = 0", (email,))
    count = cursor.fetchone()[0]
    cursor.close(); mycon.close()
    return count


def get_notification_count(email):
    mycon  = get_db_connection()
    cursor = mycon.cursor()
    cursor.execute("SELECT COUNT(*) FROM notifications WHERE email = %s AND is_read = 0", (email,))
    count = cursor.fetchone()[0]
    cursor.close(); mycon.close()
    return count


# Gemini Ai ── Gemini client (server-side AI) ───
from google import genai
from google.genai import types

_gemini_client = None

def get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            raise RuntimeError('GEMINI_API_KEY not set in environment variables.')
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client