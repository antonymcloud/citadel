"""Sources module for the Citadel application."""

# Import routes to make them available
from citadel.sources.routes import sources_bp

def init_sources(app):
    """Initialize sources module with the given app."""
    # Register blueprint
    app.register_blueprint(sources_bp)
