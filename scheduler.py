from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import logging
from models import Schedule
from schedules import execute_scheduled_backup

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
            
            # Initial load of schedules
            refresh_schedules(app)

def refresh_schedules(app):
    """Refresh all active schedules"""
    with app.app_context():
        logger.info("Refreshing schedules")
        
        # Get all active schedules
        schedules = Schedule.query.filter_by(is_active=True).all()
        
        for schedule in schedules:
            # Create job ID
            job_id = f"schedule_{schedule.id}"
            
            # Remove existing job if it exists
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)
            
            # Get cron expression
            cron_expression = schedule.get_cron_expression()
            if not cron_expression:
                logger.warning(f"Invalid cron expression for schedule {schedule.id}")
                continue
            
            # Parse cron expression
            minute, hour, day, month, day_of_week = cron_expression.split()
            
            # Create trigger
            trigger = CronTrigger(
                minute=minute,
                hour=hour,
                day=day if day != '*' else None,
                month=month if month != '*' else None,
                day_of_week=day_of_week if day_of_week != '*' else None
            )
            
            # Add job
            scheduler.add_job(
                execute_scheduled_backup,
                trigger=trigger,
                args=[schedule.id],
                id=job_id,
                replace_existing=True
            )
            
            logger.info(f"Scheduled job {job_id} with cron: {cron_expression}")

def shutdown_scheduler():
    """Shutdown the scheduler"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler shutdown")
