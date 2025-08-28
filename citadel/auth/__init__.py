"""Authentication module for the Citadel application."""
from flask_login import LoginManager

# Initialize extensions that will be configured in the app factory
login_manager = LoginManager()

# Import routes to make them available
from citadel.auth.routes import auth_bp

def init_auth(app):
    """Initialize authentication module with the given app."""
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    
    # Register blueprint
    app.register_blueprint(auth_bp)

@login_manager.user_loader
def load_user(user_id):
    """Load a user from the database."""
    from citadel.models.user import User
    return User.query.get(int(user_id))
