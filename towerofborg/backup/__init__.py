"""Backup module for the Tower of Borg application."""

# Import routes to make them available
from towerofborg.backup.routes import backup_bp

def init_backup(app):
    """Initialize backup module with the given app."""
    # Register blueprint
    app.register_blueprint(backup_bp)
