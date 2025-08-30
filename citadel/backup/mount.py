"""Module for mounting Borg archives."""

import os
import logging
import subprocess
import time
import signal
import shutil
from pathlib import Path
from datetime import datetime
from threading import Thread
from flask import current_app

from citadel.models import db
from citadel.models.job import Job
from citadel.models.repository import Repository

logger = logging.getLogger(__name__)

def check_mount_status(mount_path):
    """Check if a path is a mounted filesystem.
    
    Args:
        mount_path: Path to check
        
    Returns:
        bool: True if mounted, False otherwise
    """
    try:
        # Check if the path exists
        if not os.path.exists(mount_path):
            return False
            
        # Check if it's actually a mount point
        return os.path.ismount(mount_path)
    except Exception as e:
        logger.error(f"Error checking mount status for {mount_path}: {str(e)}")
        return False

def mount_archive(job_id, app):
    """Start a thread to mount a Borg archive."""
    thread = Thread(target=_mount_archive_thread, args=(job_id, app))
    thread.daemon = True
    thread.start()
    return thread

def _mount_archive_thread(job_id, app):
    """Run a mount job in a separate thread."""
    with app.app_context():
        job = Job.query.get(job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return
        
        try:
            # Set job as running
            job.status = 'running'
            job.timestamp = datetime.utcnow()
            db.session.commit()
            
            # Get repository
            repository = Repository.query.get(job.repository_id)
            if not repository:
                job.status = 'failed'
                job.log_output = 'Repository not found'
                db.session.commit()
                return
            
            # Get mount parameters from job metadata
            metadata = job.get_metadata() or {}
            archive_name = metadata.get('archive_name')
            mount_point = metadata.get('mount_point')
            
            if not archive_name or not mount_point:
                job.status = 'failed'
                job.log_output = 'Missing archive name or mount point'
                db.session.commit()
                return
            
            # Ensure mount point exists
            mount_path = Path(mount_point)
            if not mount_path.exists():
                try:
                    mount_path.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    job.status = 'failed'
                    job.log_output = f'Failed to create mount point: {str(e)}'
                    db.session.commit()
                    return
            
            # Build borg mount command
            cmd = ["borg", "mount"]
            
            # Add repository path and archive name
            cmd.append(f"{repository.path}::{archive_name}")
            
            # Add mount point
            cmd.append(mount_point)
            
            # Set environment variables for encryption if needed
            env = os.environ.copy()
            if repository.encryption and repository.passphrase:
                env["BORG_PASSPHRASE"] = repository.passphrase
            
            # Start the mount process
            try:
                logger.info(f"Starting mount process: {' '.join(cmd)}")
                mount_process = subprocess.Popen(
                    cmd,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1  # Line buffered
                )
                
                # Store process ID in job metadata for later unmounting
                metadata['mount_pid'] = mount_process.pid
                metadata['mount_status'] = 'mounting'
                job.set_metadata(metadata)
                db.session.commit()
                
                # Read initial output to check for errors
                output = ""
                for i in range(10):  # Wait for up to 10 seconds for initial output
                    line = mount_process.stdout.readline()
                    if line:
                        output += line
                        if "error" in line.lower() or "critical" in line.lower():
                            logger.error(f"Mount error: {line}")
                            mount_process.terminate()
                            job.status = 'failed'
                            job.log_output = output
                            job.completed_at = datetime.utcnow()
                            job.set_metadata(metadata)
                            db.session.commit()
                            return
                    
                    # Check if mount process is still running
                    if mount_process.poll() is not None:
                        if mount_process.returncode != 0:
                            logger.error(f"Mount failed with return code {mount_process.returncode}")
                            job.status = 'failed'
                            job.log_output = output
                            job.completed_at = datetime.utcnow()
                            job.set_metadata(metadata)
                            db.session.commit()
                            return
                        break
                    
                    time.sleep(1)
                
                # Check if the mount point has content
                if len(os.listdir(mount_point)) == 0:
                    # Wait a bit more for the mount to complete
                    time.sleep(5)
                    if len(os.listdir(mount_point)) == 0:
                        logger.error("Mount point is empty after mounting")
                        mount_process.terminate()
                        job.status = 'failed'
                        job.log_output = output + "\nMount point is empty after mounting. Mount failed."
                        job.completed_at = datetime.utcnow()
                        job.set_metadata(metadata)
                        db.session.commit()
                        return
                
                # Mount successful
                metadata['mount_status'] = 'mounted'
                job.status = 'success'
                job.log_output = output + "\nMount successful"
                job.set_metadata(metadata)
                db.session.commit()
                
                logger.info(f"Archive {archive_name} successfully mounted at {mount_point}")
                
            except Exception as e:
                logger.exception(f"Error mounting archive: {str(e)}")
                job.status = 'failed'
                job.log_output = f"Mount failed: {str(e)}"
                job.completed_at = datetime.utcnow()
                db.session.commit()
                
        except Exception as e:
            logger.exception(f"Error in mount thread: {str(e)}")
            job.status = 'failed'
            job.log_output = f"Error: {str(e)}"
            job.completed_at = datetime.utcnow()
            db.session.commit()

def unmount_archive(job_id, app):
    """Unmount a previously mounted archive."""
    thread = Thread(target=_unmount_archive_thread, args=(job_id, app))
    thread.daemon = True
    thread.start()
    return thread

def _unmount_archive_thread(job_id, app):
    """Run an unmount job in a separate thread."""
    with app.app_context():
        job = Job.query.get(job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return
        
        try:
            # Set job as running
            job.status = 'running'
            job.timestamp = datetime.utcnow()
            db.session.commit()
            
            # Get mount parameters from job metadata
            metadata = job.get_metadata() or {}
            mount_point = metadata.get('mount_point')
            mount_pid = metadata.get('mount_pid')
            
            if not mount_point:
                job.status = 'failed'
                job.log_output = 'Missing mount point'
                db.session.commit()
                return
            
            # Try to terminate the mount process if we have its PID
            if mount_pid:
                try:
                    # Check if the process is still running using kill with signal 0
                    # This doesn't actually kill the process, but checks if it exists
                    os.kill(mount_pid, 0)
                    
                    # If we get here, the process exists, so terminate it
                    os.kill(mount_pid, signal.SIGTERM)
                    logger.info(f"Terminated mount process with PID {mount_pid}")
                    
                    # Give it a moment to terminate
                    time.sleep(2)
                except OSError:
                    # Process doesn't exist
                    logger.info(f"Process with PID {mount_pid} no longer exists")
                except Exception as e:
                    logger.error(f"Error terminating mount process: {str(e)}")
            
            # Try to unmount using the fusermount command
            try:
                unmount_cmd = ["fusermount", "-u", mount_point]
                logger.info(f"Running unmount command: {' '.join(unmount_cmd)}")
                result = subprocess.run(
                    unmount_cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode != 0:
                    logger.error(f"Error unmounting: {result.stderr}")
                    # Try alternative method if fusermount fails
                    alt_cmd = ["umount", mount_point]
                    logger.info(f"Trying alternative unmount: {' '.join(alt_cmd)}")
                    alt_result = subprocess.run(
                        alt_cmd,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if alt_result.returncode != 0:
                        logger.error(f"Alternative unmount failed: {alt_result.stderr}")
                        # Continue anyway, as we'll clean up the job
                
                # Update job status
                metadata['mount_status'] = 'unmounted'
                job.status = 'success'
                job.log_output = f"Archive unmounted from {mount_point}"
                job.completed_at = datetime.utcnow()
                job.set_metadata(metadata)
                db.session.commit()
                
                logger.info(f"Archive successfully unmounted from {mount_point}")
                
            except Exception as e:
                logger.exception(f"Error unmounting archive: {str(e)}")
                job.status = 'failed'
                job.log_output = f"Unmount failed: {str(e)}"
                job.completed_at = datetime.utcnow()
                db.session.commit()
                
        except Exception as e:
            logger.exception(f"Error in unmount thread: {str(e)}")
            job.status = 'failed'
            job.log_output = f"Error: {str(e)}"
            job.completed_at = datetime.utcnow()
            db.session.commit()

def get_temporary_mount_path(archive_name, user_id):
    """Generate a temporary mount path for an archive."""
    # Create a unique directory name based on time, archive name and user
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() else "_" for c in archive_name)
    mount_dir = f"archive_mount_{safe_name}_{user_id}_{timestamp}"
    
    # Get the base directory for mounts from app config or use /tmp/citadel/mounts
    base_dir = current_app.config.get('MOUNT_BASE_DIR', '/tmp/citadel/mounts')
    
    # Create the full path
    mount_path = os.path.join(base_dir, mount_dir)
    
    # Ensure the base directory exists
    os.makedirs(base_dir, exist_ok=True)
    
    return mount_path

def check_mount_status(mount_point):
    """Check if a path is mounted and accessible."""
    try:
        # Check if mount point exists
        if not os.path.exists(mount_point):
            return False
        
        # Check if the mount point is actually mounted
        # One way is to check if it appears in the output of the mount command
        result = subprocess.run(
            ["mount"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if mount_point in result.stdout:
            # Check if we can list files in the mount point
            files = os.listdir(mount_point)
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error checking mount status: {str(e)}")
        return False
