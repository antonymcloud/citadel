"""Scheduler for automated backup jobs."""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('scheduler')

# Create scheduler
scheduler = BackgroundScheduler()

def init_scheduler(app):
    """Initialize the scheduler with the Flask app context"""
    with app.app_context():
        # Start scheduler
        if not scheduler.running:
            scheduler.start()
            logger.info("Scheduler started")
            
            # Schedule job to refresh schedules every hour
            scheduler.add_job(
                refresh_schedules,
                'interval',
                hours=1,
                args=[app],
                id='refresh_schedules',
                replace_existing=True
            )
            
            # Load initial schedules
            refresh_schedules(app)
            
    return scheduler

def shutdown_scheduler():
    """Shutdown the scheduler gracefully"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler shutdown")

def refresh_schedules(app):
    """Refresh all active schedules"""
    from citadel.models.schedule import Schedule
    from citadel.schedules.utils import run_scheduled_backup
    
    with app.app_context():
        logger.info("Refreshing schedules")
        
        # Get all active schedules
        schedules = Schedule.query.filter_by(is_active=True).all()
        logger.info(f"Found {len(schedules)} active schedules")
        
        # Update each schedule in the scheduler
        for schedule in schedules:
            job_id = f'schedule_{schedule.id}'
            
            # Remove existing job if present
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)
            
            # Create cron trigger based on schedule frequency
            cron_expression = schedule.get_cron_expression()
            if not cron_expression:
                logger.warning(f"Invalid cron expression for schedule {schedule.id}")
                continue
            
            # Parse cron expression (minute, hour, day, month, day_of_week)
            cron_parts = cron_expression.split()
            if len(cron_parts) != 5:
                logger.warning(f"Invalid cron expression format: {cron_expression}")
                continue
            
            # Add job to scheduler
            trigger = CronTrigger(
                minute=cron_parts[0],
                hour=cron_parts[1],
                day=cron_parts[2],
                month=cron_parts[3],
                day_of_week=cron_parts[4]
            )
            
            scheduler.add_job(
                run_scheduled_backup,
                trigger=trigger,
                args=[schedule.id],
                id=job_id,
                replace_existing=True
            )
            
            logger.info(f"Scheduled job {job_id} with cron: {cron_expression}")
        
        logger.info("Schedule refresh complete")
