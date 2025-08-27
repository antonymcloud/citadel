from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import db, Source, Job
from datetime import datetime

sources_bp = Blueprint('sources', __name__, url_prefix='/sources')

@sources_bp.route('/')
@login_required
def list_sources():
    sources = Source.query.filter_by(user_id=current_user.id).all()
    return render_template('source/sources.html', sources=sources)

@sources_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_source():
    if request.method == 'POST':
        name = request.form.get('name')
        source_type = request.form.get('source_type')
        path = request.form.get('path')
        
        # Validate inputs
        if not name or not path or not source_type:
            flash('Source name, type, and path are required.', 'danger')
            return render_template('source/add_source.html')
        
        # Check if source already exists
        existing_source = Source.query.filter_by(name=name, user_id=current_user.id).first()
        if existing_source:
            flash('A source with this name already exists.', 'danger')
            return render_template('source/add_source.html')
        
        # Create source object
        new_source = Source(
            name=name,
            source_type=source_type,
            path=path,
            user_id=current_user.id
        )
        
        # Add SSH details if it's an SSH source
        if source_type == 'ssh':
            ssh_host = request.form.get('ssh_host')
            ssh_port = request.form.get('ssh_port', 22)
            ssh_user = request.form.get('ssh_user')
            ssh_key_path = request.form.get('ssh_key_path')
            
            if not ssh_host or not ssh_user:
                flash('SSH host and username are required for SSH sources.', 'danger')
                return render_template('source/add_source.html')
            
            new_source.ssh_host = ssh_host
            new_source.ssh_port = int(ssh_port)
            new_source.ssh_user = ssh_user
            new_source.ssh_key_path = ssh_key_path
        
        db.session.add(new_source)
        db.session.commit()
        
        flash('Source added successfully.', 'success')
        return redirect(url_for('sources.list_sources'))
    
    return render_template('source/add_source.html')

@sources_bp.route('/<int:source_id>')
@login_required
def source_detail(source_id):
    source = Source.query.get_or_404(source_id)
    
    # Ensure user has access to this source
    if source.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to view this source.', 'danger')
        return redirect(url_for('sources.list_sources'))
    
    # Get jobs that used this source
    jobs = Job.query.filter_by(source_id=source_id).order_by(Job.timestamp.desc()).all()
    return render_template('source/source_detail.html', source=source, jobs=jobs)

@sources_bp.route('/<int:source_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_source(source_id):
    source = Source.query.get_or_404(source_id)
    
    # Ensure user has access to this source
    if source.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to edit this source.', 'danger')
        return redirect(url_for('sources.list_sources'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        path = request.form.get('path')
        
        # Validate inputs
        if not name or not path:
            flash('Source name and path are required.', 'danger')
            return render_template('source/edit_source.html', source=source)
        
        # Update source
        source.name = name
        source.path = path
        
        # Update SSH details if it's an SSH source
        if source.source_type == 'ssh':
            ssh_host = request.form.get('ssh_host')
            ssh_port = request.form.get('ssh_port', 22)
            ssh_user = request.form.get('ssh_user')
            ssh_key_path = request.form.get('ssh_key_path')
            
            if not ssh_host or not ssh_user:
                flash('SSH host and username are required for SSH sources.', 'danger')
                return render_template('source/edit_source.html', source=source)
            
            source.ssh_host = ssh_host
            source.ssh_port = int(ssh_port)
            source.ssh_user = ssh_user
            source.ssh_key_path = ssh_key_path
        
        db.session.commit()
        
        flash('Source updated successfully.', 'success')
        return redirect(url_for('sources.source_detail', source_id=source.id))
    
    return render_template('source/edit_source.html', source=source)

@sources_bp.route('/<int:source_id>/delete', methods=['POST'])
@login_required
def delete_source(source_id):
    source = Source.query.get_or_404(source_id)
    
    # Ensure user has access to this source
    if source.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to delete this source.', 'danger')
        return redirect(url_for('sources.list_sources'))
    
    # Check if source is used in any jobs
    job_count = Job.query.filter_by(source_id=source_id).count()
    if job_count > 0:
        flash(f'Cannot delete source: it is used by {job_count} jobs.', 'danger')
        return redirect(url_for('sources.source_detail', source_id=source.id))
    
    # Delete source
    db.session.delete(source)
    db.session.commit()
    
    flash('Source deleted successfully.', 'success')
    return redirect(url_for('sources.list_sources'))
