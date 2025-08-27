from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import db, Repository, Source, Schedule, Job
from datetime import datetime, timedelta
import threading
import os
from backup import run_borg_command

schedules_bp = Blueprint('schedules', __name__, url_prefix='/schedules')

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
            
        next_run = now.replace(hour=schedule.hour, minute=schedule.minute, second=0, microsecond=0)
        next_run = next_run + timedelta(days=days_ahead)
    
    elif schedule.frequency == 'monthly':
        # Get target day of month (1-31)
        target_day = min(max(1, schedule.day_of_month), 31)
        
        # Calculate next month that has the target day
        next_run = now.replace(day=1, hour=schedule.hour, minute=schedule.minute, second=0, microsecond=0)
        
        # If today's day is past the target day, move to next month
        if now.day > target_day or (now.day == target_day and 
                                   (now.hour > schedule.hour or 
                                    (now.hour == schedule.hour and now.minute >= schedule.minute))):
            next_run = next_run.replace(month=next_run.month + 1 if next_run.month < 12 else 1,
                                       year=next_run.year if next_run.month < 12 else next_run.year + 1)
        
        # Adjust day of month (handle month length differences)
        month_days = [31, 29 if next_run.year % 4 == 0 and (next_run.year % 100 != 0 or next_run.year % 400 == 0) else 28, 
                     31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        next_run = next_run.replace(day=min(target_day, month_days[next_run.month - 1]))
    
    return next_run

def execute_scheduled_backup(schedule_id):
    """Execute a scheduled backup"""
    # Import Flask app to get application context
    from app import app
    
    # Use application context to access database
    with app.app_context():
        schedule = Schedule.query.get(schedule_id)
        if not schedule or not schedule.is_active:
            return
        
        # Update last run time
        schedule.last_run = datetime.utcnow()
        
        # Create a backup job
        archive_name = schedule.archive_prefix or f"scheduled-{schedule.frequency}"
        archive_name = f"{archive_name}-{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        
        job = Job(
            job_type="create",
            status="running",
            repository_id=schedule.repository_id,
            source_id=schedule.source_id,
            user_id=schedule.user_id,
            archive_name=archive_name
        )
        
        db.session.add(job)
        db.session.commit()
        
        # Add job to schedule's jobs
        schedule.jobs.append(job)
        db.session.commit()
        
        # Run backup in background thread
        source_path = schedule.source.get_formatted_path()
        archive_path = f"{schedule.repository.path}::{archive_name}"
        args = [
            "create",
            "--verbose",
            "--stats",
            "--progress",
            archive_path,
            source_path
        ]
        
        # Run the backup command
        result = run_borg_command(job.id, args)
        
        # If auto-prune is enabled and backup was successful, run prune
        if schedule.auto_prune and result.get("status") == "success":
            # Create prune job
            prune_job = Job(
                job_type="prune",
                status="running",
                repository_id=schedule.repository_id,
                user_id=schedule.user_id
            )
            db.session.add(prune_job)
            db.session.commit()
            
            # Add job to schedule's jobs
            schedule.jobs.append(prune_job)
            db.session.commit()
            
            # Run prune command
            prune_args = [
                "prune",
                "--stats",
                f"--keep-daily={schedule.keep_daily}",
                f"--keep-weekly={schedule.keep_weekly}",
                f"--keep-monthly={schedule.keep_monthly}",
                schedule.repository.path
            ]
            
            run_borg_command(prune_job.id, prune_args)
        
        # Calculate next run time
        schedule.next_run = calculate_next_run(schedule)
        db.session.commit()
        
        return result

@schedules_bp.route('/')
@login_required
def list_schedules():
    schedules = Schedule.query.filter_by(user_id=current_user.id).all()
    return render_template('schedule/schedules.html', schedules=schedules)

@schedules_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_schedule():
    if request.method == 'POST':
        name = request.form.get('name')
        repository_id = request.form.get('repository_id')
        source_id = request.form.get('source_id')
        frequency = request.form.get('frequency')
        hour = int(request.form.get('hour', 0))
        minute = int(request.form.get('minute', 0))
        day_of_week = request.form.get('day_of_week')
        day_of_month = request.form.get('day_of_month')
        archive_prefix = request.form.get('archive_prefix')
        auto_prune = request.form.get('auto_prune') == 'on'
        keep_daily = int(request.form.get('keep_daily', 7))
        keep_weekly = int(request.form.get('keep_weekly', 4))
        keep_monthly = int(request.form.get('keep_monthly', 6))
        
        # Validate required fields
        if not name or not repository_id or not source_id or not frequency:
            flash('Name, repository, source and frequency are required.', 'danger')
            repos = Repository.query.filter_by(user_id=current_user.id).all()
            sources = Source.query.filter_by(user_id=current_user.id).all()
            return render_template('schedule/add_schedule.html', repos=repos, sources=sources)
        
        # Validate repository and source access
        repo = Repository.query.get(repository_id)
        source = Source.query.get(source_id)
        
        if not repo or repo.user_id != current_user.id:
            flash('Invalid repository selected.', 'danger')
            return redirect(url_for('schedules.add_schedule'))
        
        if not source or source.user_id != current_user.id:
            flash('Invalid source selected.', 'danger')
            return redirect(url_for('schedules.add_schedule'))
        
        # Create schedule
        schedule = Schedule(
            name=name,
            repository_id=repository_id,
            source_id=source_id,
            user_id=current_user.id,
            frequency=frequency,
            hour=hour,
            minute=minute,
            archive_prefix=archive_prefix,
            auto_prune=auto_prune,
            keep_daily=keep_daily,
            keep_weekly=keep_weekly,
            keep_monthly=keep_monthly
        )
        
        # Set day of week or month based on frequency
        if frequency == 'weekly' and day_of_week:
            schedule.day_of_week = day_of_week
        elif frequency == 'monthly' and day_of_month:
            schedule.day_of_month = int(day_of_month)
        
        # Calculate next run time
        schedule.next_run = calculate_next_run(schedule)
        
        # Save to database
        db.session.add(schedule)
        db.session.commit()
        
        flash('Schedule created successfully.', 'success')
        return redirect(url_for('schedules.list_schedules'))
    
    # GET request - show form
    repos = Repository.query.filter_by(user_id=current_user.id).all()
    sources = Source.query.filter_by(user_id=current_user.id).all()
    return render_template('schedule/add_schedule.html', repos=repos, sources=sources)

@schedules_bp.route('/<int:schedule_id>')
@login_required
def schedule_detail(schedule_id):
    schedule = Schedule.query.get_or_404(schedule_id)
    
    # Ensure user has access to this schedule
    if schedule.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to view this schedule.', 'danger')
        return redirect(url_for('schedules.list_schedules'))
    
    # Get recent jobs for this schedule
    jobs = schedule.jobs.order_by(Job.timestamp.desc()).limit(10).all()
    
    return render_template('schedule/schedule_detail.html', schedule=schedule, jobs=jobs)

@schedules_bp.route('/<int:schedule_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_schedule(schedule_id):
    schedule = Schedule.query.get_or_404(schedule_id)
    
    # Ensure user has access to this schedule
    if schedule.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to edit this schedule.', 'danger')
        return redirect(url_for('schedules.list_schedules'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        repository_id = request.form.get('repository_id')
        source_id = request.form.get('source_id')
        frequency = request.form.get('frequency')
        hour = int(request.form.get('hour', 0))
        minute = int(request.form.get('minute', 0))
        day_of_week = request.form.get('day_of_week')
        day_of_month = request.form.get('day_of_month')
        archive_prefix = request.form.get('archive_prefix')
        auto_prune = request.form.get('auto_prune') == 'on'
        keep_daily = int(request.form.get('keep_daily', 7))
        keep_weekly = int(request.form.get('keep_weekly', 4))
        keep_monthly = int(request.form.get('keep_monthly', 6))
        is_active = request.form.get('is_active') == 'on'
        
        # Validate required fields
        if not name or not repository_id or not source_id or not frequency:
            flash('Name, repository, source and frequency are required.', 'danger')
            repos = Repository.query.filter_by(user_id=current_user.id).all()
            sources = Source.query.filter_by(user_id=current_user.id).all()
            return render_template('schedule/edit_schedule.html', schedule=schedule, repos=repos, sources=sources)
        
        # Validate repository and source access
        repo = Repository.query.get(repository_id)
        source = Source.query.get(source_id)
        
        if not repo or repo.user_id != current_user.id:
            flash('Invalid repository selected.', 'danger')
            return redirect(url_for('schedules.edit_schedule', schedule_id=schedule.id))
        
        if not source or source.user_id != current_user.id:
            flash('Invalid source selected.', 'danger')
            return redirect(url_for('schedules.edit_schedule', schedule_id=schedule.id))
        
        # Update schedule
        schedule.name = name
        schedule.repository_id = repository_id
        schedule.source_id = source_id
        schedule.frequency = frequency
        schedule.hour = hour
        schedule.minute = minute
        schedule.archive_prefix = archive_prefix
        schedule.auto_prune = auto_prune
        schedule.keep_daily = keep_daily
        schedule.keep_weekly = keep_weekly
        schedule.keep_monthly = keep_monthly
        schedule.is_active = is_active
        
        # Reset day fields
        schedule.day_of_week = None
        schedule.day_of_month = None
        
        # Set day of week or month based on frequency
        if frequency == 'weekly' and day_of_week:
            schedule.day_of_week = day_of_week
        elif frequency == 'monthly' and day_of_month:
            schedule.day_of_month = int(day_of_month)
        
        # Calculate next run time
        schedule.next_run = calculate_next_run(schedule)
        
        # Save to database
        db.session.commit()
        
        flash('Schedule updated successfully.', 'success')
        return redirect(url_for('schedules.schedule_detail', schedule_id=schedule.id))
    
    # GET request - show form
    repos = Repository.query.filter_by(user_id=current_user.id).all()
    sources = Source.query.filter_by(user_id=current_user.id).all()
    return render_template('schedule/edit_schedule.html', schedule=schedule, repos=repos, sources=sources)

@schedules_bp.route('/<int:schedule_id>/delete', methods=['POST'])
@login_required
def delete_schedule(schedule_id):
    schedule = Schedule.query.get_or_404(schedule_id)
    
    # Ensure user has access to this schedule
    if schedule.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to delete this schedule.', 'danger')
        return redirect(url_for('schedules.list_schedules'))
    
    # Delete schedule
    db.session.delete(schedule)
    db.session.commit()
    
    flash('Schedule deleted successfully.', 'success')
    return redirect(url_for('schedules.list_schedules'))

@schedules_bp.route('/<int:schedule_id>/run', methods=['POST'])
@login_required
def run_schedule_now(schedule_id):
    schedule = Schedule.query.get_or_404(schedule_id)
    
    # Ensure user has access to this schedule
    if schedule.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to run this schedule.', 'danger')
        return redirect(url_for('schedules.list_schedules'))
    
    # Run schedule in background thread
    thread = threading.Thread(
        target=execute_scheduled_backup,
        args=(schedule.id,)
    )
    thread.daemon = True
    thread.start()
    
    flash('Scheduled backup started.', 'success')
    return redirect(url_for('schedules.schedule_detail', schedule_id=schedule.id))

@schedules_bp.route('/<int:schedule_id>/toggle', methods=['POST'])
@login_required
def toggle_schedule(schedule_id):
    schedule = Schedule.query.get_or_404(schedule_id)
    
    # Ensure user has access to this schedule
    if schedule.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to modify this schedule.', 'danger')
        return redirect(url_for('schedules.list_schedules'))
    
    # Toggle active status
    schedule.is_active = not schedule.is_active
    
    # If activating, calculate next run time
    if schedule.is_active:
        schedule.next_run = calculate_next_run(schedule)
    
    db.session.commit()
    
    status = "activated" if schedule.is_active else "deactivated"
    flash(f'Schedule {status} successfully.', 'success')
    return redirect(url_for('schedules.schedule_detail', schedule_id=schedule.id))
