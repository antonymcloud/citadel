"""Sources module for the Tower of Borg application."""

# Import routes to make them available
from towerofborg.sources.routes import sources_bp

def init_sources(app):
    """Initialize sources module with the given app."""
    # Register blueprint
    app.register_blueprint(sources_bp)
