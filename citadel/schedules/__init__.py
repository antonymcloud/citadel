"""Schedules module for the Citadel application."""

# Import routes to make them available
from citadel.schedules.routes import schedules_bp

def init_schedules(app):
    """Initialize schedules module with the given app."""
    # Register blueprint
    app.register_blueprint(schedules_bp)
