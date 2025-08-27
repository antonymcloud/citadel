from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import db, Repository, Job, Source
from datetime import datetime
import os
import subprocess
import threading
import json

backup_bp = Blueprint('backup', __name__, url_prefix='/backup')


def extract_stats_from_output(output):
    """Extract statistics from Borg command output"""
    stats = {}
    
    print("DEBUG: Extracting stats from output")
    print(f"DEBUG: Output length: {len(output) if output else 0}")
    
    # Look for the statistics section which is delimited by dashed lines
    dash_line = "------------------------------------------------------------------------------"
    if dash_line in output:
        print("DEBUG: Found dash line in regular format")
        sections = output.split(dash_line)
        print(f"DEBUG: Found {len(sections)} sections separated by dash lines")
    elif f"[WARN] {dash_line}" in output:
        # Handle mock output with [WARN] prefix
        print("DEBUG: Found dash line in mock format")
        sections = output.split(f"[WARN] {dash_line}")
        print(f"DEBUG: Found {len(sections)} sections separated by dash lines")
    else:
        print("DEBUG: No dash line found in output")
        return stats
        
    if len(sections) >= 3:  # At least one section between two delimiters
        stats_section = sections[1].strip()
        print(f"DEBUG: Stats section length: {len(stats_section)}")
        print(f"DEBUG: Stats section preview: {stats_section[:100]}...")
        
        # Parse the statistics section
        lines = stats_section.split('\n')
        for line in lines:
            # Remove [WARN] prefix if present
            if line.startswith("[WARN] "):
                line = line[7:]
            
            line = line.strip()
            
            # Extract archive name and fingerprint
            if line.startswith("Archive name: "):
                stats["archive_name"] = line.replace("Archive name: ", "").strip()
            elif line.startswith("Archive fingerprint: "):
                stats["archive_fingerprint"] = line.replace("Archive fingerprint: ", "").strip()
            
            # Extract timestamps
            elif line.startswith("Time (start): "):
                stats["start_time"] = line.replace("Time (start): ", "").strip()
            elif line.startswith("Time (end): "):
                stats["end_time"] = line.replace("Time (end): ", "").strip()
            
            # Extract duration
            elif line.startswith("Duration: "):
                duration_str = line.replace("Duration: ", "").strip()
                if "seconds" in duration_str:
                    stats["duration"] = float(duration_str.replace(" seconds", "").strip())
            
            # Extract number of files
            elif line.startswith("Number of files: "):
                stats["nfiles"] = int(line.replace("Number of files: ", "").strip())
            
            # Extract size information
            elif "Original size" in line and "Compressed size" in line and "Deduplicated size" in line:
                # This is the header line for size information
                continue
            elif line.startswith("This archive:"):
                # Parse sizes for this archive
                parts = line.split()
                if len(parts) >= 8:
                    stats["original_size"] = parse_size(parts[2] + " " + parts[3])
                    stats["compressed_size"] = parse_size(parts[4] + " " + parts[5])
                    stats["deduplicated_size"] = parse_size(parts[6] + " " + parts[7])
            elif line.startswith("All archives:"):
                # Parse sizes for all archives
                parts = line.split()
                if len(parts) >= 8:
                    stats["all_archives_original_size"] = parse_size(parts[2] + " " + parts[3])
                    stats["all_archives_compressed_size"] = parse_size(parts[4] + " " + parts[5])
                    stats["all_archives_deduplicated_size"] = parse_size(parts[6] + " " + parts[7])
            
            # Extract additional metrics
            elif line.startswith("Unique chunks"):
                parts = line.split()
                if len(parts) >= 9:
                    try:
                        stats["unique_chunks"] = int(parts[2])
                        stats["unique_chunks_size"] = parse_size(parts[4] + " " + parts[5])
                        stats["unique_chunks_avg_size"] = parse_size(parts[7] + " " + parts[8])
                    except (ValueError, IndexError):
                        pass
            
            # For prune operations
            elif line.startswith("Keeping archive: "):
                if "kept_archives" not in stats:
                    stats["kept_archives"] = []
                stats["kept_archives"].append(line.replace("Keeping archive: ", "").strip())
            elif line.startswith("Pruning archive: "):
                if "pruned_archives" not in stats:
                    stats["pruned_archives"] = []
                stats["pruned_archives"].append(line.replace("Pruning archive: ", "").strip())
    
    # Add counts for prune operations
    if "kept_archives" in stats:
        stats["kept_archives_count"] = len(stats["kept_archives"])
    if "pruned_archives" in stats:
        stats["pruned_archives_count"] = len(stats["pruned_archives"])
    
    # Calculate compression and deduplication ratios
    if "original_size" in stats and "compressed_size" in stats and stats["original_size"] > 0:
        stats["compression_ratio"] = stats["compressed_size"] / stats["original_size"] * 100
    if "original_size" in stats and "deduplicated_size" in stats and stats["original_size"] > 0:
        stats["deduplication_ratio"] = stats["deduplicated_size"] / stats["original_size"] * 100
    
    print(f"DEBUG: Extracted stats: {stats}")
    
    return stats

def parse_size(size_str):
    """Parse size string (e.g., "1.00 GB") to bytes"""
    try:
        value, unit = size_str.split()
        value = float(value)
        
        # Convert to bytes based on unit
        if unit == "B":
            return value
        elif unit == "KB":
            return value * 1024
        elif unit == "MB":
            return value * 1024 * 1024
        elif unit == "GB":
            return value * 1024 * 1024 * 1024
        elif unit == "TB":
            return value * 1024 * 1024 * 1024 * 1024
        else:
            return value  # Unable to parse unit, return as is
    except:
        return 0  # Return 0 if parsing fails

def format_size(size_bytes):
    """Format bytes to human-readable size"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes/(1024*1024):.2f} MB"
    elif size_bytes < 1024 * 1024 * 1024 * 1024:
        return f"{size_bytes/(1024*1024*1024):.2f} GB"
    else:
        return f"{size_bytes/(1024*1024*1024*1024):.2f} TB"

def format_stats_for_display(stats):
    """Format statistics for display in the job output"""
    formatted = "\n\n"
    formatted += "📊 BACKUP STATISTICS 📊\n"
    formatted += "=" * 50 + "\n"
    
    if "archive_name" in stats:
        formatted += f"Archive: {stats['archive_name']}\n"
    
    if "start_time" in stats and "end_time" in stats:
        formatted += f"Time: {stats['start_time']} to {stats['end_time']}\n"
    
    if "duration" in stats:
        formatted += f"Duration: {stats['duration']:.2f} seconds\n"
    
    if "nfiles" in stats:
        formatted += f"Files: {stats['nfiles']}\n"
    
    formatted += "-" * 50 + "\n"
    
    if "original_size" in stats:
        formatted += f"Original Size:      {format_size(stats['original_size'])}\n"
    
    if "compressed_size" in stats:
        formatted += f"Compressed Size:    {format_size(stats['compressed_size'])}\n"
        
    if "deduplicated_size" in stats:
        formatted += f"Deduplicated Size:  {format_size(stats['deduplicated_size'])}\n"
    
    # Calculate and display ratios
    if "compression_ratio" in stats:
        savings = 100 - stats['compression_ratio']
        formatted += f"Compression Ratio:  {stats['compression_ratio']:.1f}% ({savings:.1f}% saved)\n"
    elif "original_size" in stats and "compressed_size" in stats:
        ratio = stats['compressed_size'] / stats['original_size'] * 100
        savings = 100 - ratio
        formatted += f"Compression Ratio:  {ratio:.1f}% ({savings:.1f}% saved)\n"
    
    if "deduplication_ratio" in stats:
        savings = 100 - stats['deduplication_ratio']
        formatted += f"Deduplication Ratio: {stats['deduplication_ratio']:.1f}% ({savings:.1f}% saved)\n"
    elif "original_size" in stats and "deduplicated_size" in stats:
        ratio = stats['deduplicated_size'] / stats['original_size'] * 100
        savings = 100 - ratio
        formatted += f"Deduplication Ratio: {ratio:.1f}% ({savings:.1f}% saved)\n"
    
    # Add unique chunks information if available
    if "unique_chunks" in stats and "unique_chunks_size" in stats:
        formatted += f"\nUnique Chunks: {stats['unique_chunks']} ({format_size(stats['unique_chunks_size'])})\n"
        if "unique_chunks_avg_size" in stats:
            formatted += f"Average Chunk Size: {format_size(stats['unique_chunks_avg_size'])}\n"
    
    # Add pruning information if available
    if "kept_archives_count" in stats or "pruned_archives_count" in stats:
        formatted += "\n" + "-" * 50 + "\n"
        formatted += "PRUNING SUMMARY:\n"
        
        if "kept_archives_count" in stats:
            formatted += f"Archives kept: {stats['kept_archives_count']}\n"
        if "pruned_archives_count" in stats:
            formatted += f"Archives pruned: {stats['pruned_archives_count']}\n"
        
    # Add repository total information if available
    if "all_archives_original_size" in stats:
        formatted += "\n" + "-" * 50 + "\n"
        formatted += "REPOSITORY TOTALS:\n"
        formatted += f"All Archives Size:         {format_size(stats['all_archives_original_size'])}\n"
        formatted += f"All Archives Compressed:   {format_size(stats['all_archives_compressed_size'])}\n"
        formatted += f"All Archives Deduplicated: {format_size(stats['all_archives_deduplicated_size'])}\n"
        
        # Calculate total space saved
        if stats['all_archives_original_size'] and stats['all_archives_deduplicated_size']:
            saved = stats['all_archives_original_size'] - stats['all_archives_deduplicated_size']
            savings_percent = (saved / stats['all_archives_original_size']) * 100
            formatted += f"Total Space Saved:        {format_size(saved)} ({savings_percent:.1f}%)\n"
    
    formatted += "=" * 50 + "\n"
    return formatted
    
    formatted += "\n"
    formatted += "Size Information:\n"
    formatted += "-" * 50 + "\n"
    
    if "original_size" in stats and "compressed_size" in stats and "deduplicated_size" in stats:
        formatted += f"Original size:     {format_size(stats['original_size'])}\n"
        formatted += f"Compressed size:   {format_size(stats['compressed_size'])}\n"
        formatted += f"Deduplicated size: {format_size(stats['deduplicated_size'])}\n"
        
        # Calculate compression and deduplication ratios
        if stats['original_size'] > 0:
            compression_ratio = stats['compressed_size'] / stats['original_size']
            dedup_ratio = stats['deduplicated_size'] / stats['original_size']
            formatted += f"Compression ratio: {compression_ratio:.2%}\n"
            formatted += f"Deduplication ratio: {dedup_ratio:.2%}\n"
    
    return formatted

def run_borg_command(job_id, args):
    """Run a Borg command in a separate thread and update job status"""
    # Import Flask app to get application context
    from app import app
    import json
    
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
            
            # Run command with real-time output streaming
            print(f"Running command: {command_to_run} {' '.join(args)}")
            
            # Initialize output buffer with empty string - we'll be storing plain text
            job.log_output = ""
            db.session.commit()
            
            # Check if the last argument is "--json" and remove it if found
            if '--json' in args:
                args.remove('--json')
            
            # Start the process with pipe for stdout and stderr
            process = subprocess.Popen(
                [command_to_run] + args,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Line buffered
            )
            
            # Helper function to read from stream and update job
            def read_stream(stream, is_stderr=False):
                for line in iter(stream.readline, ''):
                    # Update job log in database
                    with app.app_context():
                        # Fetch job again to avoid stale data
                        current_job = Job.query.get(job_id)
                        if not current_job:
                            continue
                            
                        try:
                            # Format line with stream indicator
                            formatted_line = line.rstrip()
                            if is_stderr and formatted_line:
                                prefix = "[ERROR] " if any(err in line.lower() for err in ['error', 'exception', 'fatal']) else "[WARN] "
                                formatted_line = prefix + formatted_line
                            
                            # Append to log_output
                            if current_job.log_output:
                                current_job.log_output += "\n" + formatted_line
                            else:
                                current_job.log_output = formatted_line
                            
                            db.session.commit()
                        except Exception as e:
                            print(f"Error processing output line: {e}")
                            try:
                                # Add error message to log
                                error_msg = f"[ERROR] Failed to process output: {str(e)}"
                                if current_job.log_output:
                                    current_job.log_output += "\n" + error_msg
                                else:
                                    current_job.log_output = error_msg
                                db.session.commit()
                            except:
                                pass  # Last resort, can't do much here
            
            # Create threads to read stdout and stderr concurrently
            stdout_thread = threading.Thread(target=read_stream, args=(process.stdout,))
            stderr_thread = threading.Thread(target=read_stream, args=(process.stderr, True))
            
            # Set as daemon threads so they don't block program exit
            stdout_thread.daemon = True
            stderr_thread.daemon = True
            
            # Start threads
            stdout_thread.start()
            stderr_thread.start()
            
            # Wait for process to complete
            return_code = process.wait()
            
            # Wait for output threads to finish
            stdout_thread.join()
            stderr_thread.join()
            
            # Update job with final status
            job = Job.query.get(job_id)  # Refresh job object
            job.completed_at = datetime.utcnow()
            
            if return_code == 0:
                job.status = "success"
                
                # For create and prune commands, extract statistics
                if args[0] in ["create", "prune"] and job.log_output:
                    print(f"DEBUG: Extracting stats for {args[0]} command")
                    stats = extract_stats_from_output(job.log_output)
                    if stats:
                        print(f"DEBUG: Found stats, storing in metadata")
                        # Store statistics in job metadata
                        metadata = job.get_metadata()
                        print(f"DEBUG: Current metadata: {metadata}")
                        metadata["stats"] = stats
                        job.set_metadata(metadata)
                        print(f"DEBUG: Updated job metadata: {job.job_metadata}")
                        
                        # Add formatted stats to the end of the log output
                        job.log_output += "\n\n" + format_stats_for_display(stats)
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
    
    # Add JSON flag
    args.append("--json")
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
    
    # Start process with pipe for stdout and stderr
    process = subprocess.Popen(
        [command_to_run] + args,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Capture output from the process
    stdout, stderr = process.communicate()
    
    try:
        # Try to parse stdout as JSON
        if stdout and stdout.strip():
            json_data = json.loads(stdout)
            return {
                "success": process.returncode == 0,
                "output": stdout,
                "json_data": json_data,
                "error": stderr if process.returncode != 0 else ""
            }
    except json.JSONDecodeError:
        pass
    
    # Combine output for better display if not JSON
    combined_output = ""
    if stdout and stdout.strip():
        combined_output += stdout
    
    if stderr and stderr.strip():
        # Only add a separator if we have both stdout and stderr
        if combined_output:
            combined_output += "\n\n"
        combined_output += stderr
    
    return {
        "success": process.returncode == 0,
        "output": combined_output,
        "error": stderr if process.returncode != 0 else ""
    }

@backup_bp.route('/repositories')
@login_required
def list_repositories():
    repos = Repository.query.filter_by(user_id=current_user.id).all()
    return render_template('backup/repositories.html', repos=repos)

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
            return render_template('backup/add_repository.html')
        
        # Check if repository already exists
        existing_repo = Repository.query.filter_by(name=name, user_id=current_user.id).first()
        if existing_repo:
            flash('A repository with this name already exists.', 'danger')
            return render_template('backup/add_repository.html')
        
        # Initialize repository if it doesn't exist
        init_required = request.form.get('init') == 'on'
        if init_required:
            init_result = borg_init(path, encryption, passphrase)
            if not init_result["success"]:
                flash(f'Failed to initialize repository: {init_result["error"]}', 'danger')
                return render_template('backup/add_repository.html')
        
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
    
    return render_template('backup/add_repository.html')

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
    return render_template('backup/repository_detail.html', repo=repo, jobs=jobs)

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
                return render_template('backup/create_backup.html', repos=repos, sources=sources)
            
            source_path = backup_source.get_formatted_path()
        elif custom_path:
            # Use custom path
            source_path = custom_path
        else:
            flash('Either a source or a custom path is required.', 'danger')
            repos = Repository.query.filter_by(user_id=current_user.id).all()
            sources = Source.query.filter_by(user_id=current_user.id).all()
            return render_template('backup/create_backup.html', repos=repos, sources=sources)
        
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
            "--json",
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
    return render_template('backup/create_backup.html', repos=repos, sources=sources)

@backup_bp.route('/jobs')
@login_required
def list_jobs():
    # Exclude 'list' jobs from the job history and eagerly load relationships
    jobs = Job.query.filter_by(user_id=current_user.id).filter(Job.job_type != 'list') \
             .options(db.joinedload(Job.source), db.joinedload(Job.repository)) \
             .order_by(Job.timestamp.desc()).all()
    return render_template('backup/jobs.html', jobs=jobs)

@backup_bp.route('/jobs/<int:job_id>')
@login_required
def job_detail(job_id):
    # Use joinedload to eagerly load the source and repository relationships
    job = Job.query.options(db.joinedload(Job.source), db.joinedload(Job.repository)).get_or_404(job_id)
    
    # Ensure user has access to this job
    if job.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to view this job.', 'danger')
        return redirect(url_for('backup.list_jobs'))
    
    return render_template('backup/job_detail.html', job=job)

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
    
    # Get offset parameter (used for incremental output fetching)
    offset = request.args.get('offset', type=int, default=0)
    
    # Get job output from the specified offset
    log_output = job.log_output
    if offset > 0 and log_output and len(log_output) > offset:
        log_output = log_output[offset:]
    
    return jsonify({
        "id": job.id,
        "status": job.status,
        "log_output": log_output,
        "total_output_length": len(job.log_output or ""),
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
    args = ["list", "--json", repo.path]
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
        "--json",
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
