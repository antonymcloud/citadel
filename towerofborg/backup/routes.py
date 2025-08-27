"""Backup routes for the Tower of Borg application."""

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from towerofborg.models import db
from towerofborg.models.repository import Repository
from towerofborg.models.job import Job
from towerofborg.models.source import Source
from towerofborg.backup.utils import run_backup_job, list_archives, extract_stats_from_output

backup_bp = Blueprint('backup', __name__, url_prefix='/backup')

@backup_bp.route('/')
@login_required
def index():
    """Show all repositories"""
    repositories = Repository.query.filter_by(user_id=current_user.id).all()
    return render_template('backup/repositories.html', repositories=repositories)

@backup_bp.route('/repository/new', methods=['GET', 'POST'])
@login_required
def new_repository():
    """Create a new repository"""
    if request.method == 'POST':
        name = request.form.get('name')
        path = request.form.get('path')
        encryption = request.form.get('encryption')
        passphrase = request.form.get('passphrase')
        
        # Validate inputs
        if not name or not path:
            flash('Repository name and path are required.', 'danger')
            return redirect(url_for('backup.new_repository'))
        
        # Check if repository already exists
        if Repository.query.filter_by(name=name, user_id=current_user.id).first():
            flash('A repository with that name already exists.', 'danger')
            return redirect(url_for('backup.new_repository'))
        
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
        return redirect(url_for('backup.view_repository', repo_id=repository.id))
    
    return render_template('backup/new_repository.html')

@backup_bp.route('/repository/<int:repo_id>')
@login_required
def view_repository(repo_id):
    """View a repository and its archives"""
    repository = Repository.query.get_or_404(repo_id)
    
    # Security check - make sure the repository belongs to the current user
    if repository.user_id != current_user.id:
        flash('You do not have permission to view this repository.', 'danger')
        return redirect(url_for('backup.index'))
    
    # Get jobs for this repository
    jobs = Job.query.filter_by(repository_id=repo_id).order_by(Job.timestamp.desc()).limit(10).all()
    
    # Get archives (if any)
    archives = []
    list_job = Job.query.filter_by(repository_id=repo_id, job_type='list', status='success').order_by(Job.timestamp.desc()).first()
    if list_job:
        archives = list_job.get_metadata().get('archives', [])
    
    # Get sources for backup form
    sources = Source.query.filter_by(user_id=current_user.id).all()
    
    return render_template('backup/view_repository.html', 
                           repository=repository, 
                           jobs=jobs, 
                           archives=archives,
                           sources=sources)

# Add more routes for creating backups, pruning, etc.
