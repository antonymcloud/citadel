"""Routes for source management in the Citadel application."""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from citadel.models import db
from citadel.models.source import Source
from citadel.models.job import Job

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
        
        # Create new source
        source = Source(
            name=name,
            source_type=source_type,
            path=path,
            user_id=current_user.id
        )
        
        # Add SSH settings if needed
        if source_type == 'ssh':
            source.ssh_host = request.form.get('ssh_host')
            source.ssh_user = request.form.get('ssh_user')
            source.ssh_port = int(request.form.get('ssh_port', 22))
            source.ssh_key_path = request.form.get('ssh_key_path')
            
            if not source.ssh_host or not source.ssh_user:
                flash('SSH host and user are required for SSH sources.', 'danger')
                return render_template('source/add_source.html')
        
        db.session.add(source)
        db.session.commit()
        
        flash('Source added successfully.', 'success')
        return redirect(url_for('sources.list_sources'))
    
    return render_template('source/add_source.html')

@sources_bp.route('/<int:source_id>')
@login_required
def source_detail(source_id):
    source = Source.query.get_or_404(source_id)
    
    # Security check
    if source.user_id != current_user.id:
        flash('You do not have permission to view this source.', 'danger')
        return redirect(url_for('sources.list_sources'))
    
    # Get jobs that used this source
    jobs = Job.query.filter_by(source_id=source_id).order_by(Job.timestamp.desc()).limit(10).all()
    
    return render_template('source/source_detail.html', source=source, jobs=jobs)

@sources_bp.route('/<int:source_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_source(source_id):
    source = Source.query.get_or_404(source_id)
    
    # Security check
    if source.user_id != current_user.id:
        flash('You do not have permission to edit this source.', 'danger')
        return redirect(url_for('sources.list_sources'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        path = request.form.get('path')
        
        # Validate inputs
        if not name or not path:
            flash('Source name and path are required.', 'danger')
            return render_template('source/edit_source.html', source=source)
        
        # Check if name already exists (excluding current source)
        existing_source = Source.query.filter_by(name=name, user_id=current_user.id).first()
        if existing_source and existing_source.id != source_id:
            flash('A source with this name already exists.', 'danger')
            return render_template('source/edit_source.html', source=source)
        
        # Update source
        source.name = name
        source.path = path
        
        # Update SSH settings if applicable
        if source.source_type == 'ssh':
            source.ssh_host = request.form.get('ssh_host')
            source.ssh_user = request.form.get('ssh_user')
            source.ssh_port = int(request.form.get('ssh_port', 22))
            source.ssh_key_path = request.form.get('ssh_key_path')
            
            if not source.ssh_host or not source.ssh_user:
                flash('SSH host and user are required for SSH sources.', 'danger')
                return render_template('source/edit_source.html', source=source)
        
        db.session.commit()
        
        flash('Source updated successfully.', 'success')
        return redirect(url_for('sources.source_detail', source_id=source.id))
    
    return render_template('source/edit_source.html', source=source)

@sources_bp.route('/<int:source_id>/delete', methods=['POST'])
@login_required
def delete_source(source_id):
    source = Source.query.get_or_404(source_id)
    
    # Security check
    if source.user_id != current_user.id:
        flash('You do not have permission to delete this source.', 'danger')
        return redirect(url_for('sources.list_sources'))
    
    # Check if source is used in any jobs
    jobs = Job.query.filter_by(source_id=source_id).count()
    if jobs > 0:
        flash('This source cannot be deleted because it is used in backup jobs.', 'danger')
        return redirect(url_for('sources.source_detail', source_id=source.id))
    
    # Delete source
    db.session.delete(source)
    db.session.commit()
    
    flash('Source deleted successfully.', 'success')
    return redirect(url_for('sources.list_sources'))
