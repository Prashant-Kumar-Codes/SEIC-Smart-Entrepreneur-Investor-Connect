from flask import Flask
from dotenv import load_dotenv
from app.config.config import Config
import logging
import os
import sys
import io
from logging.handlers import RotatingFileHandler
from datetime import datetime

# Import mail from extensions — the single source of truth
from app.routes.extensions import mail

# Fix: Force UTF-8 encoding on Windows console output
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8', errors='replace')

load_dotenv()


def setup_logging(app):
    """Configure logging for the Flask app"""
    
    # Remove default Flask logger handlers
    app.logger.handlers.clear()
    
    # ===== CONSOLE HANDLER (stdout - for Render dashboard) =====
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    
    # ===== FILE HANDLER (local fallback) =====
    if not os.path.exists('logs'):
        os.makedirs('logs', exist_ok=True)
    
    app_log_file = f'logs/app-{datetime.now().strftime("%Y%m%d")}.log'
    file_handler = RotatingFileHandler(app_log_file, maxBytes=10485760, backupCount=10, encoding='utf-8')
    file_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    
    # Set log levels
    console_handler.setLevel(logging.INFO)
    file_handler.setLevel(logging.DEBUG)
    
    # Add handlers
    app.logger.addHandler(console_handler)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.DEBUG)
    
    # Set werkzeug logger level to reduce noise
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.INFO)
    werkzeug_logger.addHandler(console_handler)
    
    return app.logger


def create_app():
    app = Flask(__name__,
                static_folder='static',
                template_folder='templates')

    app.config.from_object(Config)
    
    # Setup logging first
    logger = setup_logging(app)
    logger.info("=" * 80)
    logger.info(">> SEIC App Starting...")
    logger.info("=" * 80)

    # Initialise mail with the app (mail object lives in extensions.py)
    mail.init_app(app)
    logger.info("[OK] Flask-Mail initialised successfully")
    logger.info(f"[MAIL] Mail Server: {app.config.get('MAIL_SERVER')}")
    logger.info(f"[ENV] Environment: {os.getenv('ENVIRONMENT', 'production')}")

    # # Getting the embedding model
    # from app.models.ai_matchmaking import get_embedding_model
    # get_embedding_model()

    # ========== BLUEPRINTS ==========
    logger.info("\n[BLUEPRINTS] Registering Blueprints...")
    
    from app.routes.auth_home import home_auth
    app.register_blueprint(home_auth)
    logger.debug("✓ auth_home")

    from app.routes.auth_login_signup import login_signup_auth
    app.register_blueprint(login_signup_auth)
    logger.debug("✓ auth_login_signup")

    #Entrepreneurs Blueprints
    logger.info("[ENTREPRENEUR] Registering Routes:")
    from app.routes.entrepreneur.auth_entrepreneur_dashboard import entrepreneur_dashboard_bp
    app.register_blueprint(entrepreneur_dashboard_bp)
    logger.debug("  [+] Dashboard")
    
    from app.routes.entrepreneur.auth_entrepreneur_profile import entrepreneur_profile_auth
    app.register_blueprint(entrepreneur_profile_auth)
    logger.debug("  [+] Profile")
    
    from app.routes.entrepreneur.auth_entrepreneur_pitch import entrepreneur_pitch_deck_auth
    app.register_blueprint(entrepreneur_pitch_deck_auth)
    logger.debug("  [+] Pitch Deck")

    from app.routes.entrepreneur.auth_entrepreneur_chat import entrepreneur_chat_auth
    app.register_blueprint(entrepreneur_chat_auth)
    logger.debug("  [+] AI Chat")
    
    from app.routes.entrepreneur.auth_entrepreneur_feed import entrepreneur_feed_auth
    app.register_blueprint(entrepreneur_feed_auth)
    logger.debug("  [+] Feed")
    
    #Investors Blueprints
    logger.info("[INVESTOR] Registering Routes:")
    from app.routes.investor.auth_investor_dashboard import investor_dashboard_bp
    app.register_blueprint(investor_dashboard_bp)
    logger.debug("  [+] Dashboard")
    
    from app.routes.investor.auth_investor_profile import investor_my_profile_auth
    app.register_blueprint(investor_my_profile_auth)
    logger.debug("  [+] Profile")
    
    from app.routes.investor.auth_investor_chat import investor_chat_auth
    app.register_blueprint(investor_chat_auth)
    logger.debug("  [+] AI Chat")
    
    from app.routes.investor.auth_investor_protfolio import investor_portfolio_auth
    app.register_blueprint(investor_portfolio_auth)
    logger.debug("  [+] Portfolio")
    
    # Matching Blueprint
    from app.routes.auth_match import match_auth
    app.register_blueprint(match_auth)
    logger.debug("  [+] Matching")

    # Admin Verification Blueprint
    logger.info("[ADMIN] Registering Routes:")
    from app.routes.admin.auth_admin_verification import admin_verification
    app.register_blueprint(admin_verification)
    logger.debug("  [+] Verification")

    logger.info("=" * 80)
    logger.info("[SUCCESS] All Blueprints Loaded Successfully!")
    logger.info("[READY] SEIC App is Ready to Handle Requests")
    logger.info("=" * 80 + "\n")

    # # ========== REQUEST LOGGING MIDDLEWARE ==========
    # @app.before_request
    # def log_request():
    #     from flask import request
    #     logger.info(f"📍 {request.method} {request.path}")
    #     if request.args:
    #         logger.debug(f"   Query: {dict(request.args)}")

    # @app.after_request
    # def log_response(response):
    #     from flask import request
    #     status_emoji = "✅" if response.status_code < 400 else "⚠️" if response.status_code < 500 else "❌"
    #     logger.info(f"{status_emoji} {response.status_code} | {request.method} {request.path}")
    #     return response

    # @app.errorhandler(Exception)
    # def handle_error(error):
    #     logger.error(f"🔴 EXCEPTION: {type(error).__name__}: {str(error)}", exc_info=True)
    #     return {"error": "Internal Server Error"}, 500

    return app