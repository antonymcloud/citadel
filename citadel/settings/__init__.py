"""Settings module for the Citadel application."""

from flask import Blueprint

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

def init_settings(app):
    """Initialize the settings module."""
    # Import routes here to avoid circular dependencies
    from citadel.settings.routes import settings_bp as settings_routes_bp
    
    # Register the blueprint
    app.register_blueprint(settings_routes_bp)
