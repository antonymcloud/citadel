"""Backup module for the Citadel application."""

from flask import Blueprint

# Create blueprint
backup_bp = Blueprint('backup', __name__, url_prefix='/backup', template_folder='../templates/backup')

# Import routes to make them available
from citadel.backup.routes import *
from citadel.backup.mount_cli import mounts_cli

def init_backup(app):
    """Initialize backup module with the given app."""
    # Register blueprint
    app.register_blueprint(backup_bp)
    
    # Register CLI commands
    app.cli.add_command(mounts_cli)
    
    # Configure automatic mount cleanup
    if app.config.get('ENABLE_MOUNT_CLEANUP', True):
        # Import here to avoid circular imports
        from citadel.backup.mount_scheduler import schedule_mount_cleanup
        
        # Default to 12 hours between cleanups
        cleanup_interval = app.config.get('MOUNT_CLEANUP_INTERVAL_HOURS', 12)
        
        # Schedule the cleanup
        schedule_mount_cleanup(app, interval_hours=cleanup_interval)
