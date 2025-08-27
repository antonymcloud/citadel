"""Schedules module for the Tower of Borg application."""

# Import routes to make them available
from towerofborg.schedules.routes import schedules_bp

def init_schedules(app):
    """Initialize schedules module with the given app."""
    # Register blueprint
    app.register_blueprint(schedules_bp)
