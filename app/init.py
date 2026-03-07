from flask import Flask
from dotenv import load_dotenv
from app.config.config import Config

# Import mail from extensions — the single source of truth
from app.routes.extensions import mail

load_dotenv()


def create_app():
    app = Flask(__name__,
                static_folder='static',
                template_folder='templates')

    app.config.from_object(Config)

    # Initialise mail with the app (mail object lives in extensions.py)
    mail.init_app(app)
    print("[OK] Flask-Mail initialised")
    print('hello')

    # # Getting the embedding model
    # from app.models.ai_matchmaking import get_embedding_model
    # get_embedding_model()

    # ========== BLUEPRINTS ==========
    from app.routes.auth_home import home_auth
    app.register_blueprint(home_auth)

    from app.routes.auth_login_signup import login_signup_auth
    app.register_blueprint(login_signup_auth)


    #Entrepreneurs Blueprints
    from app.routes.entrepreneur.auth_entrepreneur_dashboard import entrepreneur_dashboard_bp
    app.register_blueprint(entrepreneur_dashboard_bp)
    
    from app.routes.entrepreneur.auth_entrepreneur_profile import entrepreneur_profile_auth
    app.register_blueprint(entrepreneur_profile_auth)
    
    from app.routes.entrepreneur.auth_entrepreneur_pitch import entrepreneur_pitch_deck_auth
    app.register_blueprint(entrepreneur_pitch_deck_auth)

    from app.routes.entrepreneur.auth_entrepreneur_chat import entrepreneur_chat_auth
    app.register_blueprint(entrepreneur_chat_auth)
    
    from app.routes.entrepreneur.auth_entrepreneur_feed import entrepreneur_feed_auth
    app.register_blueprint(entrepreneur_feed_auth)
    
    
    #Investors Blueprints
    from app.routes.investor.auth_investor_dashboard import investor_dashboard_bp
    app.register_blueprint(investor_dashboard_bp)
    
    from app.routes.investor.auth_investor_profile import investor_my_profile_auth
    app.register_blueprint(investor_my_profile_auth)
    
    from app.routes.investor.auth_investor_chat import investor_chat_auth
    app.register_blueprint(investor_chat_auth)
    
    from app.routes.investor.auth_investor_protfolio import investor_portfolio_auth
    app.register_blueprint(investor_portfolio_auth)
    
    from app.routes.auth_match import match_auth
    app.register_blueprint(match_auth)

    # Admin Verification Blueprint
    from app.routes.admin.auth_admin_verification import admin_verification
    app.register_blueprint(admin_verification)

    #return the app
    return app