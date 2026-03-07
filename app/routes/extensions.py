from flask import Blueprint, render_template, request, session, flash, redirect, url_for, jsonify
from flask_mail import Mail, Message
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import random
import os

# ============================================================
# mail lives HERE — import it as:  from .extensions import mail
# This is the standard Flask pattern to avoid circular imports
# and "cannot import name 'mail' from 'app'" errors
# ============================================================
mail = Mail()


def get_db_connection():
    conn = mysql.connector.connect(
        host     = os.getenv("MYSQL_HOST"),
        user     = os.getenv("MYSQL_USER"),
        password = os.getenv("MYSQL_PASSWORD"),
        database = os.getenv("MYSQL_DATABASE")
    )
    print(f"🗄 DB connected → host={os.getenv('MYSQL_HOST')} db={os.getenv('MYSQL_DATABASE')}")
    return conn


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