"""Initialize the analytics module."""

from flask import Blueprint

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')

# Import routes after defining the blueprint but before registering it
from citadel.analytics import routes

def init_analytics(app):
    """Initialize the analytics module."""
    app.register_blueprint(analytics_bp)
    return app
