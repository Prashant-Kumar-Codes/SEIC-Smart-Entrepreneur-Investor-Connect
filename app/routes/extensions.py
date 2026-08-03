from flask import Blueprint, render_template, request, session, flash, redirect, url_for, jsonify
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import random
import os
import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor

# ============================================================
# mail lives HERE — import it as:  from .extensions import mail
# This is the standard Flask pattern to avoid circular imports
# and "cannot import name 'mail' from 'app'" errors
# ============================================================
mail = Mail()


# ============================================================
# CONNECTION POOL — replaces per-query get_db_connection()
# ============================================================
# ThreadedConnectionPool is thread-safe and works with Gunicorn's
# gthread worker class (2 workers × 4 threads = 8 concurrent).
# Connections are pre-established; getting one from the pool is
# near-instant (~0ms vs ~200-500ms for a new Neon SSL connection).
# ============================================================

_pool = None


def _init_pool():
    """Initialise the connection pool (called once at module load or first use)."""
    global _pool
    if _pool is not None:
        return

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        from urllib.parse import urlparse
        parsed = urlparse(database_url)
        pool_kwargs = dict(
            host     = parsed.hostname,
            port     = parsed.port or 5432,
            user     = parsed.username,
            password = parsed.password,
            database = parsed.path.lstrip('/'),
            sslmode  = 'require' if 'neon' in (parsed.hostname or '') else 'prefer',
        )
        print(f"🗄 Initialising connection pool → {parsed.hostname}/{parsed.path.lstrip('/')}")
    else:
        pool_kwargs = dict(
            host     = os.getenv("POSTGRES_HOST"),
            port     = int(os.getenv("POSTGRES_PORT", 5432)),
            user     = os.getenv("POSTGRES_USER"),
            password = os.getenv("POSTGRES_PASSWORD"),
            database = os.getenv("POSTGRES_DATABASE"),
        )
        print(f"🗄 Initialising connection pool → {pool_kwargs['host']}/{pool_kwargs['database']}")

    _pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=2,
        maxconn=10,
        **pool_kwargs,
    )
    print("✅ Connection pool ready (min=2, max=10)")


# Eagerly initialise on import so workers forked by Gunicorn
# (with preload_app=True) share the pool.
try:
    _init_pool()
except Exception as e:
    # Don't crash on import — pool will be retried on first use
    print(f"⚠️  Pool init deferred: {e}")


def get_db_connection():
    """Get a connection FROM THE POOL (near-instant, no TCP/SSL setup).

    The caller is responsible for returning it via release_db_connection()
    OR the request-scoped teardown in db.py will handle it automatically.
    """
    global _pool
    if _pool is None:
        _init_pool()
    conn = _pool.getconn()
    conn.autocommit = False
    return conn


def release_db_connection(conn):
    """Return a connection to the pool (instead of closing it)."""
    global _pool
    if _pool is not None and conn is not None:
        try:
            # Roll back any uncommitted transaction to leave the
            # connection in a clean state for the next user.
            conn.rollback()
        except Exception:
            pass
        try:
            _pool.putconn(conn)
        except Exception:
            # Connection is broken — let the pool discard it
            try:
                _pool.putconn(conn, close=True)
            except Exception:
                pass


# ============================================================
# REQUEST-SCOPED CONNECTION  via Flask's g object
# ============================================================
# All code within a single request should call get_request_conn()
# to share ONE pooled connection, eliminating redundant round-trips.
# The connection is automatically returned to the pool at end of
# request via the teardown registered in app/init.py.
# ============================================================

from flask import g


def get_request_conn():
    """Get or create a pooled connection for the current request.

    Every call within the same request returns the SAME connection,
    so helpers and route handlers can share it without extra overhead.
    """
    if 'db_conn' not in g:
        g.db_conn = get_db_connection()
    return g.db_conn


def teardown_request_conn(exception=None):
    """Return the request-scoped connection to the pool.

    Registered as app.teardown_appcontext in init.py.
    """
    conn = g.pop('db_conn', None)
    if conn is not None:
        release_db_connection(conn)


# ============================================================
# SHARED HELPERS  (used by multiple route files)
# ============================================================

def get_unread_count(email, conn=None):
    """Count unread messages. Uses the given conn or opens a request-scoped one."""
    _conn = conn or get_request_conn()
    cursor = _conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM messages WHERE receiver_email = %s AND is_read = false", (email,))
    count = cursor.fetchone()[0]
    cursor.close()
    return count


def get_notification_count(email, conn=None):
    """Count unread notifications. Uses the given conn or opens a request-scoped one."""
    _conn = conn or get_request_conn()
    cursor = _conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM notifications WHERE email = %s AND is_read = false", (email,))
    count = cursor.fetchone()[0]
    cursor.close()
    return count


# ============================================================
# Gemini AI — Gemini client (server-side AI)
# ============================================================
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