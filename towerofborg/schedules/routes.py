"""Routes for schedule management in the Tower of Borg application."""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from towerofborg.models import db
from towerofborg.models.repository import Repository
from towerofborg.models.source import Source
from towerofborg.models.schedule import Schedule
from towerofborg.models.job import Job
from towerofborg.schedules.utils import calculate_next_run

schedules_bp = Blueprint('schedules', __name__, url_prefix='/schedules')

@schedules_bp.route('/')
@login_required
def list_schedules():
    """List all schedules for the current user"""
    schedules = Schedule.query.filter_by(user_id=current_user.id).all()
    return render_template('schedule/schedules.html', schedules=schedules)

@schedules_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_schedule():
    """Add a new backup schedule"""
    # Get repositories and sources for the form
    repositories = Repository.query.filter_by(user_id=current_user.id).all()
    sources = Source.query.filter_by(user_id=current_user.id).all()
    
    if not repositories:
        flash('You need to create a repository first.', 'warning')
        return redirect(url_for('backup.new_repository'))
    
    if not sources:
        flash('You need to create a backup source first.', 'warning')
        return redirect(url_for('sources.add_source'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        repository_id = request.form.get('repository_id')
        source_id = request.form.get('source_id')
        frequency = request.form.get('frequency')
        hour = request.form.get('hour', type=int)
        minute = request.form.get('minute', type=int)
        day_of_week = request.form.get('day_of_week')
        day_of_month = request.form.get('day_of_month', type=int)
        archive_prefix = request.form.get('archive_prefix')
        
        # Retention settings
        keep_daily = request.form.get('keep_daily', type=int)
        keep_weekly = request.form.get('keep_weekly', type=int)
        keep_monthly = request.form.get('keep_monthly', type=int)
        auto_prune = 'auto_prune' in request.form
        
        # Validate inputs
        if not name or not repository_id or not source_id or not frequency:
            flash('Schedule name, repository, source and frequency are required.', 'danger')
            return render_template('schedule/add_schedule.html', 
                                  repositories=repositories,
                                  sources=sources)
        
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
            keep_daily=keep_daily,
            keep_weekly=keep_weekly,
            keep_monthly=keep_monthly,
            auto_prune=auto_prune
        )
        
        # Set day of week or month based on frequency
        if frequency == 'weekly':
            schedule.day_of_week = day_of_week
        elif frequency == 'monthly':
            schedule.day_of_month = day_of_month
        
        # Calculate next run time
        schedule.next_run = calculate_next_run(schedule)
        
        db.session.add(schedule)
        db.session.commit()
        
        flash('Schedule created successfully.', 'success')
        return redirect(url_for('schedules.list_schedules'))
    
    return render_template('schedule/add_schedule.html', 
                          repositories=repositories,
                          sources=sources)

@schedules_bp.route('/<int:schedule_id>')
@login_required
def view_schedule(schedule_id):
    """View a schedule and its history"""
    schedule = Schedule.query.get_or_404(schedule_id)
    
    # Security check
    if schedule.user_id != current_user.id:
        flash('You do not have permission to view this schedule.', 'danger')
        return redirect(url_for('schedules.list_schedules'))
    
    # Get jobs associated with this schedule
    jobs = Job.query.join(Job.schedules).filter(Schedule.id == schedule_id).order_by(Job.timestamp.desc()).limit(10).all()
    
    return render_template('schedule/view_schedule.html', schedule=schedule, jobs=jobs)

@schedules_bp.route('/<int:schedule_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_schedule(schedule_id):
    """Edit an existing schedule"""
    schedule = Schedule.query.get_or_404(schedule_id)
    
    # Security check
    if schedule.user_id != current_user.id:
        flash('You do not have permission to edit this schedule.', 'danger')
        return redirect(url_for('schedules.list_schedules'))
    
    # Get repositories and sources for the form
    repositories = Repository.query.filter_by(user_id=current_user.id).all()
    sources = Source.query.filter_by(user_id=current_user.id).all()
    
    if request.method == 'POST':
        name = request.form.get('name')
        repository_id = request.form.get('repository_id')
        source_id = request.form.get('source_id')
        frequency = request.form.get('frequency')
        hour = request.form.get('hour', type=int)
        minute = request.form.get('minute', type=int)
        day_of_week = request.form.get('day_of_week')
        day_of_month = request.form.get('day_of_month', type=int)
        archive_prefix = request.form.get('archive_prefix')
        
        # Retention settings
        keep_daily = request.form.get('keep_daily', type=int)
        keep_weekly = request.form.get('keep_weekly', type=int)
        keep_monthly = request.form.get('keep_monthly', type=int)
        auto_prune = 'auto_prune' in request.form
        
        # Validate inputs
        if not name or not repository_id or not source_id or not frequency:
            flash('Schedule name, repository, source and frequency are required.', 'danger')
            return render_template('schedule/edit_schedule.html', 
                                  schedule=schedule,
                                  repositories=repositories,
                                  sources=sources)
        
        # Update schedule
        schedule.name = name
        schedule.repository_id = repository_id
        schedule.source_id = source_id
        schedule.frequency = frequency
        schedule.hour = hour
        schedule.minute = minute
        schedule.archive_prefix = archive_prefix
        schedule.keep_daily = keep_daily
        schedule.keep_weekly = keep_weekly
        schedule.keep_monthly = keep_monthly
        schedule.auto_prune = auto_prune
        
        # Set day of week or month based on frequency
        if frequency == 'weekly':
            schedule.day_of_week = day_of_week
            schedule.day_of_month = None
        elif frequency == 'monthly':
            schedule.day_of_month = day_of_month
            schedule.day_of_week = None
        else:  # daily
            schedule.day_of_week = None
            schedule.day_of_month = None
        
        # Recalculate next run time
        schedule.next_run = calculate_next_run(schedule)
        
        db.session.commit()
        
        flash('Schedule updated successfully.', 'success')
        return redirect(url_for('schedules.view_schedule', schedule_id=schedule.id))
    
    return render_template('schedule/edit_schedule.html', 
                          schedule=schedule,
                          repositories=repositories,
                          sources=sources)

@schedules_bp.route('/<int:schedule_id>/toggle', methods=['POST'])
@login_required
def toggle_schedule(schedule_id):
    """Toggle a schedule's active status"""
    schedule = Schedule.query.get_or_404(schedule_id)
    
    # Security check
    if schedule.user_id != current_user.id:
        flash('You do not have permission to modify this schedule.', 'danger')
        return redirect(url_for('schedules.list_schedules'))
    
    schedule.is_active = not schedule.is_active
    
    # If activating, recalculate next run time
    if schedule.is_active:
        schedule.next_run = calculate_next_run(schedule)
    
    db.session.commit()
    
    status = 'activated' if schedule.is_active else 'deactivated'
    flash(f'Schedule {status} successfully.', 'success')
    
    return redirect(url_for('schedules.view_schedule', schedule_id=schedule.id))
