from .extensions import *

home_auth  = Blueprint('home_auth', __name__)

@home_auth.route('/', methods=['GET'])
def home():
    # Pass the formatted count to template
    return render_template('auth/homepage.html')