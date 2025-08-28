"""Utility functions for schedule management."""
from datetime import datetime, timedelta
import threading
import os

from citadel.models import db
from citadel.models.job import Job
from citadel.backup.utils import run_backup_job

def calculate_next_run(schedule):
    """Calculate the next run time for a schedule"""
    now = datetime.utcnow()
    
    if schedule.frequency == 'daily':
        next_run = now.replace(hour=schedule.hour, minute=schedule.minute, second=0, microsecond=0)
        if next_run <= now:
            next_run = next_run + timedelta(days=1)
    
    elif schedule.frequency == 'weekly':
        # Map day of week to 0-6 (Monday is 0)
        day_map = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
        target_day = day_map.get(schedule.day_of_week.lower(), 0)
        
        # Calculate days until next occurrence
        current_day = now.weekday()
        days_ahead = target_day - current_day
        if days_ahead <= 0:  # Target day already passed this week
            days_ahead += 7
        
        # Set the next run time
        next_run = now.replace(hour=schedule.hour, minute=schedule.minute, second=0, microsecond=0)
        next_run = next_run + timedelta(days=days_ahead)
    
    elif schedule.frequency == 'monthly':
        # Set day of month (1-31)
        day = min(max(1, schedule.day_of_month), 31)
        
        # Start with current month
        next_run = now.replace(day=1, hour=schedule.hour, minute=schedule.minute, second=0, microsecond=0)
        
        # Try to set the day of month, handling month length issues
        month_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        if now.year % 4 == 0 and (now.year % 100 != 0 or now.year % 400 == 0):
            month_days[1] = 29  # Leap year
        
        # Use the minimum of requested day and actual days in month
        target_day = min(day, month_days[next_run.month - 1])
        next_run = next_run.replace(day=target_day)
        
        # If next_run is in the past, move to next month
        if next_run <= now:
            if next_run.month == 12:
                next_run = next_run.replace(year=next_run.year + 1, month=1)
            else:
                next_run = next_run.replace(month=next_run.month + 1)
            
            # Adjust day for the next month's length
            month_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
            if next_run.year % 4 == 0 and (next_run.year % 100 != 0 or next_run.year % 400 == 0):
                month_days[1] = 29  # Leap year
            
            target_day = min(day, month_days[next_run.month - 1])
            next_run = next_run.replace(day=target_day)
    
    else:
        # Unknown frequency, default to tomorrow
        next_run = now + timedelta(days=1)
    
    return next_run

def run_scheduled_backup(schedule_id):
    """Run a scheduled backup job"""
    from citadel.models.schedule import Schedule
    from citadel.models.source import Source
    from citadel.models.repository import Repository
    
    schedule = Schedule.query.get(schedule_id)
    if not schedule or not schedule.is_active:
        return
    
    # Set last run time
    schedule.last_run = datetime.utcnow()
    
    # Create a new backup job
    source = Source.query.get(schedule.source_id)
    repository = Repository.query.get(schedule.repository_id)
    
    if not source or not repository:
        schedule.next_run = calculate_next_run(schedule)
        db.session.commit()
        return
    
    # Generate archive name with date
    date_str = datetime.utcnow().strftime('%Y-%m-%d_%H%M%S')
    prefix = schedule.archive_prefix or source.name
    archive_name = f"{prefix}-{date_str}"
    
    # Create backup job
    job = Job(
        job_type='create',
        status='created',
        repository_id=repository.id,
        user_id=schedule.user_id,
        source_id=source.id,
        archive_name=archive_name,
        timestamp=datetime.utcnow()
    )
    
    db.session.add(job)
    db.session.commit()
    
    # Associate job with schedule
    job.schedules.append(schedule)
    db.session.commit()
    
    # Run the backup job
    run_backup_job(job.id)
    
    # If auto-prune is enabled, create a prune job after backup
    if schedule.auto_prune:
        # Wait for backup to complete before pruning
        def create_prune_job():
            # Reload job to get updated status
            db.session.expire_all()
            completed_job = Job.query.get(job.id)
            
            # Only prune if backup was successful
            if completed_job and completed_job.status == 'success':
                prune_job = Job(
                    job_type='prune',
                    status='created',
                    repository_id=repository.id,
                    user_id=schedule.user_id,
                    timestamp=datetime.utcnow()
                )
                
                # Set retention options in metadata
                metadata = {
                    'keep_daily': schedule.keep_daily,
                    'keep_weekly': schedule.keep_weekly,
                    'keep_monthly': schedule.keep_monthly
                }
                prune_job.set_metadata(metadata)
                
                db.session.add(prune_job)
                db.session.commit()
                
                # Associate prune job with schedule
                prune_job.schedules.append(schedule)
                db.session.commit()
                
                # Run the prune job
                run_backup_job(prune_job.id)
        
        # Start a thread to wait for backup and run prune
        thread = threading.Thread(target=create_prune_job)
        thread.daemon = True
        thread.start()
    
    # Calculate next run time
    schedule.next_run = calculate_next_run(schedule)
    db.session.commit()
