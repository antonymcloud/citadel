"""Backup routes for the Tower of Borg application."""

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from towerofborg.models import db
from towerofborg.models.repository import Repository
from towerofborg.models.job import Job
from towerofborg.models.source import Source
from towerofborg.backup.utils import run_backup_job, list_archives as list_archives_util, extract_stats_from_output

backup_bp = Blueprint('backup', __name__, url_prefix='/backup')

@backup_bp.route('/')
@login_required
def list_repositories():
    """Show all repositories"""
    repos = Repository.query.filter_by(user_id=current_user.id).all()
    return render_template('backup/repositories.html', repos=repos)

@backup_bp.route('/repository/new', methods=['GET', 'POST'])
@login_required
def add_repository():
    """Create a new repository"""
    if request.method == 'POST':
        name = request.form.get('name')
        path = request.form.get('path')
        encryption = request.form.get('encryption')
        passphrase = request.form.get('passphrase')
        
        # Validate inputs
        if not name or not path:
            flash('Repository name and path are required.', 'danger')
            return redirect(url_for('backup.add_repository'))
        
        # Check if repository already exists
        if Repository.query.filter_by(name=name, user_id=current_user.id).first():
            flash('A repository with that name already exists.', 'danger')
            return redirect(url_for('backup.add_repository'))
        
        # Create repository
        repository = Repository(
            name=name,
            path=path,
            encryption=encryption if encryption != 'none' else None,
            passphrase=passphrase if passphrase else None,
            user_id=current_user.id
        )
        db.session.add(repository)
        db.session.commit()
        
        flash('Repository created successfully.', 'success')
        return redirect(url_for('backup.repository_detail', repo_id=repository.id))
    
    return render_template('backup/add_repository.html')

@backup_bp.route('/repository/<int:repo_id>')
@login_required
def repository_detail(repo_id):
    """View a repository and its archives"""
    repository = Repository.query.get_or_404(repo_id)
    
    # Security check - make sure the repository belongs to the current user
    if repository.user_id != current_user.id:
        flash('You do not have permission to view this repository.', 'danger')
        return redirect(url_for('backup.list_repositories'))
    
    # Get jobs for this repository
    jobs = Job.query.filter_by(repository_id=repo_id).order_by(Job.timestamp.desc()).limit(10).all()
    
    # Get archives (if any)
    archives = []
    list_job = Job.query.filter_by(repository_id=repo_id, job_type='list', status='success').order_by(Job.timestamp.desc()).first()
    if list_job:
        archives = list_job.get_metadata().get('archives', [])
    
    # Get sources for backup form
    sources = Source.query.filter_by(user_id=current_user.id).all()
    
    return render_template('backup/repository_detail.html', 
                           repo=repository, 
                           jobs=jobs, 
                           archives=archives,
                           sources=sources)

# Add more routes for creating backups, pruning, etc.

@backup_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_backup():
    """Create a new backup"""
    # Get repositories and sources for the form
    repositories = Repository.query.filter_by(user_id=current_user.id).all()
    sources = Source.query.filter_by(user_id=current_user.id).all()
    
    # Check if we have repositories and sources
    if not repositories:
        flash('You need to create a repository first.', 'warning')
        return redirect(url_for('backup.add_repository'))
    
    if not sources:
        flash('You need to create a backup source first.', 'warning')
        return redirect(url_for('sources.add_source'))
    
    # Handle form submission
    if request.method == 'POST':
        repository_id = request.form.get('repository_id')
        source_id = request.form.get('source_id')
        archive_name = request.form.get('archive_name')
        
        # Handle custom path sources
        if source_id == 'custom':
            custom_path = request.form.get('custom_path')
            if not custom_path:
                flash('Custom path is required when using a custom source.', 'danger')
                return render_template('backup/create_backup.html', 
                                      repos=repositories, 
                                      sources=sources,
                                      preselected_repo=repository_id)
            
            # Create a temporary source for this backup
            temp_source = Source(
                name=f"Temporary source ({custom_path})",
                source_type='local',
                path=custom_path,
                user_id=current_user.id
            )
            db.session.add(temp_source)
            db.session.commit()
            source_id = temp_source.id
        
        # Validate inputs
        if not repository_id or not source_id:
            flash('Repository and source are required.', 'danger')
            return render_template('backup/create_backup.html', 
                                  repos=repositories, 
                                  sources=sources,
                                  preselected_repo=repository_id,
                                  preselected_source=source_id,
                                  default_archive_name=archive_name)
        
        # Generate a default archive name if not provided
        if not archive_name:
            date_str = datetime.utcnow().strftime('%Y-%m-%d_%H%M%S')
            archive_name = f"backup-{date_str}"
        
        # Create backup job
        job = Job(
            job_type='create',
            status='created',
            repository_id=repository_id,
            user_id=current_user.id,
            source_id=source_id,
            archive_name=archive_name,
            timestamp=datetime.utcnow()
        )
        
        db.session.add(job)
        db.session.commit()
        
        # Start the backup job
        run_backup_job(job.id)
        
        flash('Backup job started.', 'success')
        return redirect(url_for('backup.job_detail', job_id=job.id))
    
    # Handle GET request with preselected repository or source
    repo_id = request.args.get('repo_id')
    source_id = request.args.get('source_id')
    
    # Generate a default archive name with date
    date_str = datetime.utcnow().strftime('%Y-%m-%d_%H%M%S')
    default_archive_name = f"backup-{date_str}"
    
    return render_template('backup/create_backup.html', 
                          repos=repositories, 
                          sources=sources,
                          preselected_repo=repo_id,
                          preselected_source=source_id,
                          default_archive_name=default_archive_name)

@backup_bp.route('/job/<int:job_id>')
@login_required
def job_detail(job_id):
    """View a job and its details"""
    job = Job.query.get_or_404(job_id)
    
    # Security check - make sure the job belongs to the current user
    if job.user_id != current_user.id:
        flash('You do not have permission to view this job.', 'danger')
        return redirect(url_for('backup.list_repositories'))
    
    return render_template('backup/job_detail.html', job=job)

@backup_bp.route('/jobs')
@login_required
def list_jobs():
    """List all backup jobs"""
    # Get all jobs for the current user, excluding 'list' jobs
    jobs = Job.query.filter_by(user_id=current_user.id) \
                   .filter(Job.job_type != 'list') \
                   .order_by(Job.timestamp.desc()) \
                   .all()
    
    return render_template('backup/jobs.html', jobs=jobs)

@backup_bp.route('/repository/<int:repo_id>/prune', methods=['POST'])
@login_required
def prune_repository(repo_id):
    """Prune a repository according to retention policy"""
    repository = Repository.query.get_or_404(repo_id)
    
    # Security check - make sure the repository belongs to the current user
    if repository.user_id != current_user.id:
        flash('You do not have permission to prune this repository.', 'danger')
        return redirect(url_for('backup.list_repositories'))
    
    # Get prune parameters from form
    keep_daily = request.form.get('keep_daily', type=int)
    keep_weekly = request.form.get('keep_weekly', type=int)
    keep_monthly = request.form.get('keep_monthly', type=int)
    keep_yearly = request.form.get('keep_yearly', type=int)
    
    # Create prune job
    job = Job(
        job_type='prune',
        status='created',
        repository_id=repo_id,
        user_id=current_user.id,
        timestamp=datetime.utcnow()
    )
    
    # Set metadata properly using the set_metadata method
    metadata = {
        'keep_daily': keep_daily,
        'keep_weekly': keep_weekly,
        'keep_monthly': keep_monthly,
        'keep_yearly': keep_yearly
    }
    job.set_metadata(metadata)
    
    db.session.add(job)
    db.session.commit()
    
    # Run the prune job
    run_backup_job(job.id)
    
    # Handle AJAX requests differently than form submissions
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'status': job.status,
            'job_id': job.id
        })
    
    flash('Prune job created successfully.', 'success')
    return redirect(url_for('backup.repository_detail', repo_id=repo_id))

@backup_bp.route('/repository/<int:repo_id>/archives')
@login_required
def list_archives(repo_id):
    """API endpoint to list archives in a repository"""
    repository = Repository.query.get_or_404(repo_id)
    
    # Security check - make sure the repository belongs to the current user
    if repository.user_id != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403
    
    try:
        # Mock implementation for listing archives
        # In a real implementation, we would call Borg to list archives
        archives = [
            {"name": f"backup-{(datetime.utcnow() - timedelta(days=i)).strftime('%Y-%m-%d')}", 
             "time": (datetime.utcnow() - timedelta(days=i)).isoformat(),
             "size": 1024 * 1024 * (i + 1)}
            for i in range(5)
        ]
        
        return jsonify(archives)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@backup_bp.route('/job/<int:job_id>/status')
@login_required
def get_job_status(job_id):
    """API endpoint to get the status of a job"""
    job = Job.query.get_or_404(job_id)
    
    # Security check - make sure the job belongs to the current user
    if job.user_id != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403
    
    # Return the job status and basic info
    return jsonify({
        'id': job.id,
        'status': job.status,
        'job_type': job.job_type,
        'timestamp': job.timestamp.isoformat() if job.timestamp else None,
        'completed_at': job.completed_at.isoformat() if job.completed_at else None,
        'log_output': job.log_output
    })

@backup_bp.route('/api/jobs/<int:job_id>')
@login_required
def api_get_job_status(job_id):
    """API endpoint to get the status of a job (for AJAX requests)"""
    job = Job.query.get_or_404(job_id)
    
    # Security check - make sure the job belongs to the current user
    if job.user_id != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403
    
    # Get the offset parameter for incremental updates
    offset = request.args.get('offset', 0, type=int)
    
    # Get the log output from the offset position
    log_output = job.log_output[offset:] if job.log_output and offset < len(job.log_output) else ""
    
    # Return the job status and basic info
    return jsonify({
        'id': job.id,
        'status': job.status,
        'job_type': job.job_type,
        'timestamp': job.timestamp.isoformat() if job.timestamp else None,
        'completed_at': job.completed_at.isoformat() if job.completed_at else None,
        'log_output': log_output,
        'total_output_length': len(job.log_output) if job.log_output else 0
    })

@backup_bp.route('/api/jobs/<int:job_id>/cancel', methods=['POST'])
@login_required
def api_cancel_job(job_id):
    """API endpoint to cancel a running job"""
    job = Job.query.get_or_404(job_id)
    
    # Security check - make sure the job belongs to the current user
    if job.user_id != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403
    
    # Check if the job is running
    if job.status != 'running':
        return jsonify({
            'status': 'error',
            'error': 'Job is not running'
        })
    
    try:
        # Update the job status
        job.status = 'cancelled'
        job.completed_at = datetime.utcnow()
        job.log_output = (job.log_output or '') + '\n\n[Job was cancelled by user]'
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Job cancelled successfully'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@backup_bp.route('/repository/<int:repo_id>/update', methods=['POST'])
@login_required
def update_repository(repo_id):
    """Update repository settings"""
    repository = Repository.query.get_or_404(repo_id)
    
    # Security check - make sure the repository belongs to the current user
    if repository.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Permission denied'}), 403
    
    # Update max_size if provided
    if 'max_size' in request.form:
        try:
            max_size = float(request.form.get('max_size'))
            if max_size < 1:
                return jsonify({'success': False, 'error': 'Max size must be at least 1 GB'}), 400
                
            repository.max_size = max_size
            db.session.commit()
            return jsonify({'success': True})
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid value for max_size'}), 400
    
    return jsonify({'success': False, 'error': 'No valid parameters provided'}), 400
