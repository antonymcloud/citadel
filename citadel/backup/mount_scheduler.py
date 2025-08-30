"""Scheduled tasks for mount management."""

import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from flask import current_app

from citadel.backup.mount_management import get_orphaned_mounts, unmount_orphaned

logger = logging.getLogger(__name__)

# Global scheduler instance
mount_scheduler = None

def schedule_mount_cleanup(app, interval_hours=12):
    """Set up a scheduled task to clean up orphaned mounts.
    
    Args:
        app: Flask application instance
        interval_hours: How often to run the cleanup (in hours)
    """
    global mount_scheduler
    
    if mount_scheduler:
        # Already scheduled, just return
        return
    
    mount_scheduler = BackgroundScheduler()
    
    # Schedule cleanup job
    mount_scheduler.add_job(
        func=cleanup_orphaned_mounts,
        trigger=IntervalTrigger(hours=interval_hours),
        id='mount_cleanup',
        name='Mount Cleanup',
        replace_existing=True,
        args=[app]
    )
    
    # Add a job that runs soon after startup to check for orphaned mounts
    mount_scheduler.add_job(
        func=cleanup_orphaned_mounts,
        trigger=IntervalTrigger(minutes=5),  # Run 5 minutes after startup
        id='mount_cleanup_startup',
        name='Initial Mount Cleanup',
        replace_existing=True,
        args=[app],
        max_instances=1,
        next_run_time=datetime.now()  # Run once immediately
    )
    
    # Start the scheduler
    mount_scheduler.start()
    
    logger.info(f"Mount cleanup scheduled to run every {interval_hours} hours")

def cleanup_orphaned_mounts(app):
    """Run the mount cleanup task."""
    with app.app_context():
        try:
            # Get configuration
            max_age_hours = current_app.config.get('MOUNT_MAX_AGE_HOURS', 24)
            auto_unmount = current_app.config.get('AUTO_UNMOUNT_ORPHANED', True)
            
            # Get orphaned mounts
            orphaned = get_orphaned_mounts(max_age_hours=max_age_hours)
            
            if not orphaned:
                logger.info("No orphaned mounts found")
                return
            
            logger.info(f"Found {len(orphaned)} orphaned mounts older than {max_age_hours} hours")
            
            # Unmount if configured to do so
            if auto_unmount:
                results = unmount_orphaned(max_age_hours=max_age_hours, force=False)
                logger.info(f"Cleanup results: {len(results)} mounts processed")
            else:
                logger.info(f"Auto-unmount disabled, skipping unmount of {len(orphaned)} orphaned mounts")
        
        except Exception as e:
            logger.error(f"Error in scheduled mount cleanup: {str(e)}")

def shutdown_mount_scheduler():
    """Shut down the mount scheduler."""
    global mount_scheduler
    
    if mount_scheduler:
        mount_scheduler.shutdown()
        mount_scheduler = None
        logger.info("Mount scheduler shut down")
