from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import db, Repository, Job, Source
from datetime import datetime
import os
import subprocess
import threading

backup_bp = Blueprint('backup', __name__, url_prefix='/backup')

def run_borg_command(job_id, args):
    """Run a Borg command in a separate thread and update job status"""
    # Import Flask app to get application context
    from app import app
    
    # Use application context to access database
    with app.app_context():
        job = Job.query.get(job_id)
        if not job:
            return {"error": "Job not found"}
        
        try:
            # Get repository info
            repo = Repository.query.get(job.repository_id)
            if not repo:
                job.status = "failed"
                job.log_output = "Repository not found"
                job.completed_at = datetime.utcnow()
                db.session.commit()
                return {"error": "Repository not found"}
            
            # Set up environment for Borg
            env = os.environ.copy()
            if repo.passphrase:
                env["BORG_PASSPHRASE"] = repo.passphrase
            
            # Get debug flag from environment
            debug = os.environ.get("DEBUG", "False").lower() in ('true', '1', 't')
            
            # Get real borg path
            borg_path = None
            for path in ["/usr/bin/borg", "/usr/local/bin/borg"]:
                if os.path.exists(path):
                    borg_path = path
                    break
            
            # Determine command to run
            if not borg_path:
                # If borg is not installed, always use the mock
                command_to_run = "/home/localadmin/TowerOfBorg/mock_borg.py"
                print(f"Borg not found, using mock version")
            elif debug:
                # In debug mode, use the mock
                command_to_run = "/home/localadmin/TowerOfBorg/mock_borg.py"
                print(f"Debug mode: using mock borg")
            else:
                # Normal mode, use real borg
                command_to_run = borg_path
                print(f"Using real borg command at {borg_path}")
            
            # Run command
            print(f"Running command: {command_to_run} {' '.join(args)}")
            result = subprocess.run(
                [command_to_run] + args,
                env=env,
                capture_output=True,
                text=True
            )
            print(f"Command result: {result.returncode}")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            
            # Combine output for better display
            combined_output = ""
            if result.stdout and result.stdout.strip():
                combined_output += result.stdout
            
            if result.stderr and result.stderr.strip():
                # Only add a separator if we have both stdout and stderr
                if combined_output:
                    combined_output += "\n\n"
                combined_output += result.stderr
            
            # Update job with results
            job.log_output = combined_output
            job.completed_at = datetime.utcnow()
            
            if result.returncode == 0:
                job.status = "success"
            else:
                job.status = "failed"
            
            db.session.commit()
            return {
                "status": job.status,
                "output": job.log_output
            }
        except Exception as e:
            # Handle exceptions
            job.status = "failed"
            job.log_output = f"Error: {str(e)}"
            job.completed_at = datetime.utcnow()
            db.session.commit()
            return {"error": str(e)}

def borg_init(repo_path, encryption=None, passphrase=None):
    """Initialize a new Borg repository"""
    args = ["init"]
    if encryption:
        args.append(f"--encryption={encryption}")
    args.append(repo_path)
    
    env = os.environ.copy()
    if passphrase:
        env["BORG_PASSPHRASE"] = passphrase
    
    # Get debug flag from environment
    debug = os.environ.get("DEBUG", "False").lower() in ('true', '1', 't')
    
    # Get real borg path
    borg_path = None
    for path in ["/usr/bin/borg", "/usr/local/bin/borg"]:
        if os.path.exists(path):
            borg_path = path
            break
    
    # Determine command to run
    if not borg_path:
        # If borg is not installed, always use the mock
        command_to_run = "/home/localadmin/TowerOfBorg/mock_borg.py"
    elif debug:
        # In debug mode, use the mock
        command_to_run = "/home/localadmin/TowerOfBorg/mock_borg.py"
    else:
        # Normal mode, use real borg
        command_to_run = borg_path
    
    result = subprocess.run(
        [command_to_run] + args,
        env=env,
        capture_output=True,
        text=True
    )
    
    # Combine output for better display
    combined_output = ""
    if result.stdout and result.stdout.strip():
        combined_output += result.stdout
    
    if result.stderr and result.stderr.strip():
        # Only add a separator if we have both stdout and stderr
        if combined_output:
            combined_output += "\n\n"
        combined_output += result.stderr
    
    return {
        "success": result.returncode == 0,
        "output": combined_output,
        "error": result.stderr if result.returncode != 0 else ""
    }

@backup_bp.route('/repositories')
@login_required
def list_repositories():
    repos = Repository.query.filter_by(user_id=current_user.id).all()
    return render_template('repositories.html', repos=repos)

@backup_bp.route('/repositories/add', methods=['GET', 'POST'])
@login_required
def add_repository():
    if request.method == 'POST':
        name = request.form.get('name')
        path = request.form.get('path')
        encryption = request.form.get('encryption')
        passphrase = request.form.get('passphrase')
        
        # Validate inputs
        if not name or not path:
            flash('Repository name and path are required.', 'danger')
            return render_template('add_repository.html')
        
        # Check if repository already exists
        existing_repo = Repository.query.filter_by(name=name, user_id=current_user.id).first()
        if existing_repo:
            flash('A repository with this name already exists.', 'danger')
            return render_template('add_repository.html')
        
        # Initialize repository if it doesn't exist
        init_required = request.form.get('init') == 'on'
        if init_required:
            init_result = borg_init(path, encryption, passphrase)
            if not init_result["success"]:
                flash(f'Failed to initialize repository: {init_result["error"]}', 'danger')
                return render_template('add_repository.html')
        
        # Create repository record
        new_repo = Repository(
            name=name,
            path=path,
            encryption=encryption,
            passphrase=passphrase,
            user_id=current_user.id
        )
        db.session.add(new_repo)
        db.session.commit()
        
        flash('Repository added successfully.', 'success')
        return redirect(url_for('backup.list_repositories'))
    
    return render_template('add_repository.html')

@backup_bp.route('/repositories/<int:repo_id>')
@login_required
def repository_detail(repo_id):
    repo = Repository.query.get_or_404(repo_id)
    
    # Ensure user has access to this repository
    if repo.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to view this repository.', 'danger')
        return redirect(url_for('backup.list_repositories'))
    
    # Get jobs but exclude 'list' jobs
    jobs = Job.query.filter_by(repository_id=repo_id).filter(Job.job_type != 'list').order_by(Job.timestamp.desc()).all()
    return render_template('repository_detail.html', repo=repo, jobs=jobs)

@backup_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_backup():
    if request.method == 'POST':
        repo_id = request.form.get('repository_id')
        source_id = request.form.get('source_id')
        custom_path = request.form.get('custom_path')
        archive_name = request.form.get('archive_name')
        
        # Get repository
        repo = Repository.query.get(repo_id)
        if not repo or (repo.user_id != current_user.id and not current_user.is_admin):
            flash('Invalid repository selected.', 'danger')
            repos = Repository.query.filter_by(user_id=current_user.id).all()
            sources = Source.query.filter_by(user_id=current_user.id).all()
            return render_template('create_backup.html', repos=repos, sources=sources)
        
        # Determine source path (either from source or custom)
        backup_source = None
        source_path = None
        
        if source_id and source_id != 'custom':
            # Get source from database
            backup_source = Source.query.get(source_id)
            if not backup_source or (backup_source.user_id != current_user.id and not current_user.is_admin):
                flash('Invalid source selected.', 'danger')
                repos = Repository.query.filter_by(user_id=current_user.id).all()
                sources = Source.query.filter_by(user_id=current_user.id).all()
                return render_template('create_backup.html', repos=repos, sources=sources)
            
            source_path = backup_source.get_formatted_path()
        elif custom_path:
            # Use custom path
            source_path = custom_path
        else:
            flash('Either a source or a custom path is required.', 'danger')
            repos = Repository.query.filter_by(user_id=current_user.id).all()
            sources = Source.query.filter_by(user_id=current_user.id).all()
            return render_template('create_backup.html', repos=repos, sources=sources)
        
        # Use timestamp if archive name not provided
        if not archive_name:
            archive_name = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        
        # Create job
        job = Job(
            job_type="create",
            status="running",
            repository_id=repo_id,
            user_id=current_user.id,
            archive_name=archive_name,
            source_id=backup_source.id if backup_source else None,
            source_path=source_path if not backup_source else None
        )
        db.session.add(job)
        db.session.commit()
        
        # Run backup in background thread
        archive_path = f"{repo.path}::{archive_name}"
        args = [
            "create",
            "--verbose",
            "--stats",
            "--progress",
            archive_path,
            source_path
        ]
        
        thread = threading.Thread(
            target=run_borg_command,
            args=(job.id, args)
        )
        thread.daemon = True
        thread.start()
        
        flash('Backup job started.', 'success')
        return redirect(url_for('backup.job_detail', job_id=job.id))
    
    repos = Repository.query.filter_by(user_id=current_user.id).all()
    sources = Source.query.filter_by(user_id=current_user.id).all()
    return render_template('create_backup.html', repos=repos, sources=sources)

@backup_bp.route('/jobs')
@login_required
def list_jobs():
    # Exclude 'list' jobs from the job history and eagerly load relationships
    jobs = Job.query.filter_by(user_id=current_user.id).filter(Job.job_type != 'list') \
             .options(db.joinedload(Job.source), db.joinedload(Job.repository)) \
             .order_by(Job.timestamp.desc()).all()
    return render_template('jobs.html', jobs=jobs)

@backup_bp.route('/jobs/<int:job_id>')
@login_required
def job_detail(job_id):
    # Use joinedload to eagerly load the source and repository relationships
    job = Job.query.options(db.joinedload(Job.source), db.joinedload(Job.repository)).get_or_404(job_id)
    
    # Ensure user has access to this job
    if job.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to view this job.', 'danger')
        return redirect(url_for('backup.list_jobs'))
    
    return render_template('job_detail.html', job=job)

@backup_bp.route('/api/jobs/<int:job_id>/cancel', methods=['POST'])
@login_required
def cancel_job(job_id):
    job = Job.query.get_or_404(job_id)
    
    # Ensure user has access to this job
    if job.user_id != current_user.id and not current_user.is_admin:
        return jsonify({"error": "Access denied"}), 403
    
    if job.status != 'running':
        return jsonify({"error": "Only running jobs can be cancelled"}), 400
    
    # Mark job as cancelled
    if job.cancel():
        return jsonify({"status": "success", "message": "Job cancelled successfully"})
    else:
        return jsonify({"error": "Failed to cancel job"}), 500

@backup_bp.route('/api/jobs/<int:job_id>')
@login_required
def get_job_status(job_id):
    job = Job.query.get_or_404(job_id)
    
    # Ensure user has access to this job
    if job.user_id != current_user.id and not current_user.is_admin:
        return jsonify({"error": "Access denied"}), 403
    
    return jsonify({
        "id": job.id,
        "status": job.status,
        "log_output": job.log_output,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None
    })

@backup_bp.route('/api/list-archives/<int:repo_id>')
@login_required
def list_archives(repo_id):
    repo = Repository.query.get_or_404(repo_id)
    
    # Ensure user has access to this repository
    if repo.user_id != current_user.id and not current_user.is_admin:
        return jsonify({"error": "Access denied"}), 403
    
    # Create a job for listing archives
    job = Job(
        job_type="list",
        status="running",
        repository_id=repo_id,
        user_id=current_user.id
    )
    db.session.add(job)
    db.session.commit()
    
    # Run command in background thread
    args = ["list", repo.path]
    thread = threading.Thread(
        target=run_borg_command,
        args=(job.id, args)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({"job_id": job.id, "status": "running"})

@backup_bp.route('/api/prune/<int:repo_id>', methods=['POST'])
@login_required
def prune_repository(repo_id):
    repo = Repository.query.get_or_404(repo_id)
    
    # Ensure user has access to this repository
    if repo.user_id != current_user.id and not current_user.is_admin:
        return jsonify({"error": "Access denied"}), 403
    
    # Get prune options from request
    keep_daily = request.form.get('keep_daily', 7)
    keep_weekly = request.form.get('keep_weekly', 4)
    keep_monthly = request.form.get('keep_monthly', 6)
    
    # Create a job for pruning
    job = Job(
        job_type="prune",
        status="running",
        repository_id=repo_id,
        user_id=current_user.id
    )
    db.session.add(job)
    db.session.commit()
    
    # Run command in background thread
    args = [
        "prune",
        "--stats",  # Add stats for more detailed output
        f"--keep-daily={keep_daily}",
        f"--keep-weekly={keep_weekly}",
        f"--keep-monthly={keep_monthly}",
        repo.path
    ]
    thread = threading.Thread(
        target=run_borg_command,
        args=(job.id, args)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({"job_id": job.id, "status": "running"})
