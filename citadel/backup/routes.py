"""Backup routes for the Citadel application."""

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from citadel.models import db
from citadel.models.repository import Repository
from citadel.models.job import Job
from citadel.models.source import Source
from citadel.models.schedule import Schedule
from citadel.backup.utils import run_backup_job, list_archives as list_archives_util, extract_stats_from_output
import logging

logger = logging.getLogger(__name__)

backup_bp = Blueprint('backup', __name__, url_prefix='/backup')

@backup_bp.route('/')
@login_required
def list_repositories():
    """Show all repositories"""
    repos = Repository.query.filter_by(user_id=current_user.id).all()
    return render_template('backup/repositories/repositories.html', repos=repos)

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
    
    return render_template('backup/repositories/add_repository.html')

@backup_bp.route('/repository/<int:repo_id>')
@login_required
def repository_detail(repo_id):
    """View a repository and its archives"""
    repository = Repository.query.get_or_404(repo_id)
    
    # Security check - make sure the repository belongs to the current user
    if repository.user_id != current_user.id:
        flash('You do not have permission to view this repository.', 'danger')
        return redirect(url_for('backup.list_repositories'))
    
    # Get jobs for this repository, excluding 'list' jobs
    jobs = Job.query.filter_by(repository_id=repo_id).filter(Job.job_type != 'list').order_by(Job.timestamp.desc()).limit(10).all()
    
    # Get archives (if any)
    archives = []
    list_job = Job.query.filter_by(repository_id=repo_id, job_type='list', status='success').order_by(Job.timestamp.desc()).first()
    if list_job:
        archives = list_job.get_metadata().get('archives', [])
    
    # Get sources for backup form
    sources = Source.query.filter_by(user_id=current_user.id).all()
    
    # Get any schedules using this repository (if any)
    schedules = Schedule.query.filter_by(repository_id=repo_id).all()

    return render_template('backup/repositories/repository_detail.html', 
                           repo=repository, 
                           jobs=jobs, 
                           archives=archives,
                           sources=sources,
                           schedules=schedules)

@backup_bp.route('/repository/<int:repo_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_repository(repo_id):
    """Edit an existing repository"""
    repository = Repository.query.get_or_404(repo_id)
    
    # Security check - make sure the repository belongs to the current user
    if repository.user_id != current_user.id:
        flash('You do not have permission to edit this repository.', 'danger')
        return redirect(url_for('backup.list_repositories'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        path = request.form.get('path')
        encryption = request.form.get('encryption')
        passphrase = request.form.get('passphrase')
        max_size = request.form.get('max_size', type=float)
        
        # Validate inputs
        if not name or not path:
            flash('Repository name and path are required.', 'danger')
            return redirect(url_for('backup.edit_repository', repo_id=repo_id))
        
        # Check if repository name already exists and it's not the current one
        existing_repo = Repository.query.filter_by(name=name, user_id=current_user.id).first()
        if existing_repo and existing_repo.id != repository.id:
            flash('A repository with that name already exists.', 'danger')
            return redirect(url_for('backup.edit_repository', repo_id=repo_id))
        
        # Update repository
        repository.name = name
        repository.path = path
        repository.encryption = encryption if encryption != 'none' else None
        # Only update passphrase if provided
        if passphrase:
            repository.passphrase = passphrase
        if max_size:
            repository.max_size = max_size
        
        db.session.commit()
        
        flash('Repository updated successfully.', 'success')
        return redirect(url_for('backup.repository_detail', repo_id=repository.id))
    
    return render_template('backup/repositories/edit_repository.html', repo=repository)

@backup_bp.route('/repository/<int:repo_id>/delete', methods=['POST'])
@login_required
def delete_repository(repo_id):
    """Delete a repository"""
    repository = Repository.query.get_or_404(repo_id)
    
    # Security check - make sure the repository belongs to the current user
    if repository.user_id != current_user.id:
        flash('You do not have permission to delete this repository.', 'danger')
        return redirect(url_for('backup.list_repositories'))
    
    # Get the name for the success message
    repo_name = repository.name
    
    # Delete associated schedules first
    Schedule.query.filter_by(repository_id=repo_id).delete()
    
    # Delete associated jobs
    Job.query.filter_by(repository_id=repo_id).delete()
    
    # Delete the repository
    db.session.delete(repository)
    db.session.commit()
    
    flash(f'Repository "{repo_name}" has been deleted.', 'success')
    return redirect(url_for('backup.list_repositories'))

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

@backup_bp.route('/repository/<int:repo_id>/archives-view')
@login_required
def view_archives(repo_id):
    """View dedicated page for repository archives"""
    repository = Repository.query.get_or_404(repo_id)
    
    # Security check - make sure the repository belongs to the current user
    if repository.user_id != current_user.id:
        flash('You do not have permission to view this repository.', 'danger')
        return redirect(url_for('backup.list_repositories'))
    
    # Get the most recent list job (if any)
    list_job = Job.query.filter_by(repository_id=repo_id, job_type='list', status='success').order_by(Job.timestamp.desc()).first()
    
    archives = []
    if list_job:
        # Extract archives from job metadata
        archives = list_job.get_metadata().get('archives', [])
    
    return render_template('backup/archives.html', 
                           repo=repository, 
                           archives=archives,
                           list_job=list_job)

@backup_bp.route('/repository/<int:repo_id>/archives')
@login_required
def list_archives(repo_id):
    """API endpoint to list archives in a repository"""
    repository = Repository.query.get_or_404(repo_id)
    
    # Security check - make sure the repository belongs to the current user
    if repository.user_id != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403
    
    try:
        # Create a job to list archives using the real implementation
        job_id = list_archives_util(repo_id)
        
        if not job_id:
            return jsonify({"error": "Failed to create list job"}), 500
            
        # Return job ID so frontend can poll for completion
        return jsonify({"status": "running", "job_id": job_id})
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
        'total_output_length': len(job.log_output) if job.log_output else 0,
        'metadata': job.get_metadata(),
        'error': job.get_metadata().get('error') if job.get_metadata() else None
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

@backup_bp.route('/api/repository/<int:repo_id>/stats')
@login_required
def api_repository_stats(repo_id):
    """API endpoint to get repository statistics"""
    repository = Repository.query.get_or_404(repo_id)
    
    # Security check - make sure the repository belongs to the current user
    if repository.user_id != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403
    
    # Get all successful backup jobs for this repository
    backup_jobs = Job.query.filter_by(
        repository_id=repo_id, 
        job_type='create', 
        status='success'
    ).order_by(Job.timestamp.desc()).all()
    
    # Get all archives
    list_job = Job.query.filter_by(
        repository_id=repo_id, 
        job_type='list', 
        status='success'
    ).order_by(Job.timestamp.desc()).first()
    
    # Extract data for analytics
    total_jobs = Job.query.filter_by(repository_id=repo_id).count()
    successful_jobs = Job.query.filter_by(repository_id=repo_id, status='success').count()
    failed_jobs = Job.query.filter_by(repository_id=repo_id, status='failed').count()
    
    # Get size data from the most recent successful backup job
    latest_backup = backup_jobs[0] if backup_jobs else None
    latest_size = None
    last_backup_time = None
    average_size = 'Unknown'
    average_compression = 'Unknown'
    
    if latest_backup:
        last_backup_time = latest_backup.timestamp.isoformat()
        if latest_backup.get_metadata() and 'stats' in latest_backup.get_metadata():
            stats = latest_backup.get_metadata().get('stats', {})
            latest_size = stats.get('all_archives_deduplicated_size')
    
    # Get archives count
    archives_count = 0
    if list_job:
        archives = list_job.get_metadata().get('archives', [])
        archives_count = len(archives)
    
    # Collect size data for growth chart and calculate averages
    size_trend = []
    total_size_bytes = 0
    total_compression_ratio = 0
    valid_jobs_count = 0
    
    for job in backup_jobs[:30]:  # Limit to last 30 jobs for performance
        if job.get_metadata() and 'stats' in job.get_metadata():
            stats = job.get_metadata().get('stats', {})
            deduplicated_size = stats.get('this_archive_deduplicated_size')
            compression_ratio = stats.get('compression_ratio')
            
            if deduplicated_size:
                # Add to trend data
                size_trend.append({
                    'date': job.timestamp.isoformat(),
                    'size': deduplicated_size
                })
                
                # Calculate for averages if we have valid data
                from citadel.backup.utils import extract_size_bytes
                size_bytes = extract_size_bytes(deduplicated_size)
                if size_bytes > 0:
                    total_size_bytes += size_bytes
                    valid_jobs_count += 1
                
                # Add compression ratio if available
                if compression_ratio and isinstance(compression_ratio, (int, float)) and compression_ratio > 0:
                    total_compression_ratio += compression_ratio
    
    # Calculate averages if we have valid data
    if valid_jobs_count > 0:
        from citadel.backup.utils import format_size
        average_size = format_size(total_size_bytes / valid_jobs_count)
        if total_compression_ratio > 0:
            average_compression = f"{(total_compression_ratio / valid_jobs_count):.2f}x"
    
    # Reverse to get chronological order
    size_trend.reverse()
    
    # Calculate space usage percentage
    space_usage_percent = None
    if latest_size and repository.max_size:
        # Convert size string to bytes for calculation
        size_value = latest_size
        if isinstance(size_value, str):
            # Parse size string (e.g., "5.00 GB")
            parts = size_value.split()
            if len(parts) == 2:
                value = float(parts[0])
                unit = parts[1].upper()
                multiplier = 1
                if unit == 'KB':
                    multiplier = 1024
                elif unit == 'MB':
                    multiplier = 1024 * 1024
                elif unit == 'GB':
                    multiplier = 1024 * 1024 * 1024
                elif unit == 'TB':
                    multiplier = 1024 * 1024 * 1024 * 1024
                
                size_in_bytes = value * multiplier
                max_size_in_bytes = repository.max_size * 1024 * 1024 * 1024  # Convert GB to bytes
                space_usage_percent = (size_in_bytes / max_size_in_bytes) * 100
    
    return jsonify({
        'latest_size': latest_size,
        'max_size': repository.max_size,
        'space_usage_percent': space_usage_percent,
        'archives_count': archives_count,
        'total_jobs': total_jobs,
        'successful_jobs': successful_jobs,
        'failed_jobs': failed_jobs,
        'size_trend': size_trend,
        'last_backup_time': last_backup_time,
        'average_size': average_size,
        'average_compression': average_compression
    })

@backup_bp.route('/api/repository/<int:repo_id>/forecast')
@login_required
def api_repository_forecast(repo_id):
    """API endpoint to get repository growth forecast"""
    repository = Repository.query.get_or_404(repo_id)
    
    # Security check - make sure the repository belongs to the current user
    if repository.user_id != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403
    
    # Get all successful backup jobs for this repository
    backup_jobs = Job.query.filter_by(
        repository_id=repo_id, 
        job_type='create', 
        status='success'
    ).order_by(Job.timestamp.asc()).all()
    
    # Need at least 2 data points for forecasting
    if len(backup_jobs) < 2:
        return jsonify({
            'forecast_available': False,
            'message': 'Not enough data for forecasting'
        })
    
    # Extract size data for forecasting
    size_data = []
    for job in backup_jobs:
        if job.get_metadata() and 'stats' in job.get_metadata():
            stats = job.get_metadata().get('stats', {})
            # Use all_archives_deduplicated_size as the primary metric
            # since it represents the total repository size
            if 'all_archives_deduplicated_size' in stats:
                size_str = stats['all_archives_deduplicated_size']
                try:
                    from citadel.backup.utils import parse_size
                    size_data.append({
                        'date': job.timestamp.timestamp(),
                        'size': parse_size(size_str)
                    })
                except (ValueError, TypeError, IndexError) as e:
                    logger.debug(f"Error parsing size in forecast: {e}")
                    continue    
    
    # Need at least 2 data points after filtering
    if len(size_data) < 2:
        return jsonify({
            'forecast_available': False,
            'message': 'Not enough valid size data for forecasting'
        })
    
    # Simple linear regression for forecasting
    # This is a basic implementation - could be more sophisticated
    x = [d['date'] for d in size_data]
    y = [d['size'] for d in size_data]
    
    n = len(x)
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    
    # Calculate slope and intercept
    numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    denominator = sum((x[i] - mean_x) ** 2 for i in range(n))
    
    if denominator == 0:
        return jsonify({
            'forecast_available': False,
            'message': 'Cannot calculate forecast (constant data)'
        })
    
    slope = numerator / denominator
    intercept = mean_y - slope * mean_x
    
    # Forecast when repository will reach max size
    if repository.max_size and slope > 0:
        max_size_bytes = repository.max_size * 1024 * 1024 * 1024  # Convert GB to bytes
        time_to_max = (max_size_bytes - intercept) / slope
        
        # Convert to readable date
        max_date = datetime.fromtimestamp(time_to_max)
        days_until_max = (max_date - datetime.utcnow()).days
        
        return jsonify({
            'forecast_available': True,
            'growth_rate': slope,  # bytes per second
            'max_date': max_date.isoformat(),
            'days_until_max': days_until_max
        })
    
    return jsonify({
        'forecast_available': False,
        'message': 'Cannot calculate forecast (no max size or negative growth)'
    })

@backup_bp.route('/api/repository/<int:repo_id>/growth-chart')
@login_required
def api_repository_growth_chart(repo_id):
    """API endpoint to get repository growth chart data"""
    repository = Repository.query.get_or_404(repo_id)
    
    # Security check - make sure the repository belongs to the current user
    if repository.user_id != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403
    
    # Get all successful backup jobs for this repository
    backup_jobs = Job.query.filter_by(
        repository_id=repo_id, 
        job_type='create', 
        status='success'
    ).order_by(Job.timestamp.asc()).limit(100).all()
    
    # Need at least 2 data points for a meaningful chart
    if len(backup_jobs) < 2:
        # Generate sample data for client-side rendering
        sample_dates = [
            (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M'),
            (datetime.now() - timedelta(days=25)).strftime('%Y-%m-%d %H:%M'),
            (datetime.now() - timedelta(days=20)).strftime('%Y-%m-%d %H:%M'),
            (datetime.now() - timedelta(days=15)).strftime('%Y-%m-%d %H:%M'),
            (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d %H:%M'),
            (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d %H:%M'),
            datetime.now().strftime('%Y-%m-%d %H:%M')
        ]
        sample_sizes = [
            "1.2 GB", 
            "1.5 GB", 
            "1.8 GB", 
            "2.2 GB", 
            "2.5 GB", 
            "2.8 GB", 
            "3.0 GB"
        ]
        sample_labels = [f"Sample Backup {i+1}" for i in range(len(sample_dates))]
        
        # Format for client-side rendering
        return jsonify({
            'growth_data': {
                'labels': sample_dates,
                'data': [1.2, 1.5, 1.8, 2.2, 2.5, 2.8, 3.0]
            },
            'is_sample_data': True,
            'message': 'Showing sample data. Create at least 2 backups to see actual growth.'
        })

    # Helper function to extract size from job metadata
    def extract_job_size(job):
        if not job.get_metadata() or 'stats' not in job.get_metadata():
            return None
            
        stats = job.get_metadata().get('stats', {})

        # First try to get deduplicated size
        if 'all_archives_deduplicated_size' in stats:
            size_str = stats['all_archives_deduplicated_size']
            try:
                from citadel.backup.utils import parse_size
                # Try to go with GB
                size_bytes = (parse_size(size_str)) / (1024 * 1024 * 1024)
                if size_bytes < 0.01:
                    # Fallback to MB
                    size_bytes = (parse_size(size_str)) / (1024 * 1024)

                return size_bytes 
            except (ValueError, IndexError) as e:
                print(f"DEBUG: Error parsing size: {e}")
        
                
        return None
    
    # Collect all valid data points
    dates = []
    sizes = []
    labels = []
    
    for job in backup_jobs:
        size = extract_job_size(job)
        
        if size is not None:
            dates.append(job.timestamp.strftime('%Y-%m-%d %H:%M'))
            sizes.append(round(size, 2))  # Round to 2 decimal places
            labels.append(job.archive_name or f"Backup {job.id}")
    
    # Need at least 2 valid data points for a chart
    if len(dates) < 2:
        return jsonify({
            'growth_data': {
                'labels': sample_dates,
                'data': [1.2, 1.5, 1.8, 2.2, 2.5, 2.8, 3.0]
            },
            'is_sample_data': True,
            'message': 'Showing sample data. Valid size information not found in existing backups.'
        })
    
    # Return the growth chart data
    return jsonify({
        'growth_data': {
            'labels': dates,
            'data': sizes,
            'archive_names': labels
        },
        'is_sample_data': False
    })

@backup_bp.route('/api/repository/<int:repo_id>/frequency-chart')
@login_required
def api_repository_frequency_chart(repo_id):
    """API endpoint to get backup frequency chart data"""
    repository = Repository.query.get_or_404(repo_id)
    
    # Security check - make sure the repository belongs to the current user
    if repository.user_id != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403
    
    # Get all successful backup jobs for this repository
    backup_jobs = Job.query.filter_by(
        repository_id=repo_id, 
        job_type='create', 
        status='success'
    ).order_by(Job.timestamp.asc()).limit(100).all()
    
    # Need at least 2 data points for a meaningful chart
    if len(backup_jobs) < 1:
        # Return sample data in a format suitable for client-side chart rendering
        days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_counts = [2, 3, 1, 5, 2, 0, 1]  # Sample data
        hour_counts = [0, 0, 1, 0, 0, 2, 3, 2, 1, 0, 0, 0, 1, 1, 0, 0, 1, 1, 2, 0, 0, 0, 0, 0]  # Sample data
        
        return jsonify({
            'is_sample_data': True,
            'frequency_data': {
                'by_day': {
                    'labels': days_of_week,
                    'data': day_counts
                },
                'by_hour': {
                    'labels': [f"{h}:00" for h in range(24)],
                    'data': hour_counts
                }
            },
            'chart_html': generateSampleFrequencyChart()  # Fallback for older clients
        })
    
    # Count backups by day of week
    days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_counts = [0] * 7
    
    for job in backup_jobs:
        if job.timestamp:
            # Python's weekday() returns 0 for Monday, 6 for Sunday
            day_index = job.timestamp.weekday()
            day_counts[day_index] += 1
    
    # Count backups by hour of day
    hour_counts = [0] * 24
    for job in backup_jobs:
        if job.timestamp:
            hour = job.timestamp.hour
            hour_counts[hour] += 1
    
    # Return the data for chart generation
    return jsonify({
        'is_sample_data': False,
        'frequency_data': {
            'by_day': {
                'labels': days_of_week,
                'data': day_counts
            },
            'by_hour': {
                'labels': [f"{h}:00" for h in range(24)],
                'data': hour_counts
            }
        },
        'days_of_week': days_of_week,  # For backward compatibility
        'day_counts': day_counts,      # For backward compatibility
        'hour_counts': hour_counts,    # For backward compatibility
        'chart_html': generateFrequencyChartHtml(days_of_week, day_counts, hour_counts)  # Fallback for older clients
    })

# Helper functions for chart generation
def generateSampleGrowthChart():
    """Generate a sample growth chart when not enough data is available"""
    return """
    <div class="alert alert-info text-center">
        <i class="fas fa-info-circle me-2"></i>
        Not enough backup data available to generate a growth chart.
        Create more backups to see repository growth over time.
    </div>
    """

def generateGrowthChartHtml(data):
    """Generate HTML for growth chart"""
    # This is a simple implementation - could be more sophisticated
    if not data:
        return generateSampleGrowthChart()
    
    # In a real implementation, this would generate a chart
    return """
    <canvas id="growthChart"></canvas>
    <script>
        var ctx = document.getElementById('growthChart').getContext('2d');
        var chartData = """ + str(data).replace("'", '"') + """;
        var labels = chartData.map(d => d.date);
        var values = chartData.map(d => d.size);
        
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Repository Size',
                    data: values,
                    backgroundColor: 'rgba(54, 162, 235, 0.2)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Size'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Date'
                        }
                    }
                }
            }
        });
    </script>
    """

def generateSampleFrequencyChart():
    """Generate a sample frequency chart when not enough data is available"""
    return """
    <div class="alert alert-info text-center">
        <i class="fas fa-info-circle me-2"></i>
        Not enough backup data available to generate a frequency chart.
        Create more backups to see backup frequency patterns.
    </div>
    """

def generateFrequencyChartHtml(days, day_counts, hour_counts):
    """Generate HTML for frequency chart"""
    # This is a simple implementation - could be more sophisticated
    if not days or not day_counts or not hour_counts:
        return generateSampleFrequencyChart()
    
    # In a real implementation, this would generate a chart
    return """
    <div class="row">
        <div class="col-md-6">
            <canvas id="dayFrequencyChart"></canvas>
        </div>
        <div class="col-md-6">
            <canvas id="hourFrequencyChart"></canvas>
        </div>
    </div>
    <script>
        // Day of week chart
        var dayCtx = document.getElementById('dayFrequencyChart').getContext('2d');
        var dayChart = new Chart(dayCtx, {
            type: 'bar',
            data: {
                labels: """ + str(days).replace("'", '"') + """,
                datasets: [{
                    label: 'Backups by Day of Week',
                    data: """ + str(day_counts) + """,
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                    borderColor: 'rgba(75, 192, 192, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Number of Backups'
                        }
                    }
                }
            }
        });
        
        // Hour of day chart
        var hourCtx = document.getElementById('hourFrequencyChart').getContext('2d');
        var hourLabels = Array.from({length: 24}, (_, i) => i + ':00');
        var hourChart = new Chart(hourCtx, {
            type: 'bar',
            data: {
                labels: hourLabels,
                datasets: [{
                    label: 'Backups by Hour of Day',
                    data: """ + str(hour_counts) + """,
                    backgroundColor: 'rgba(153, 102, 255, 0.2)',
                    borderColor: 'rgba(153, 102, 255, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Number of Backups'
                        }
                    }
                }
            }
        });
    </script>
    """
