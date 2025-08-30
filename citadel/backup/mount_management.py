"""Management commands for handling orphaned mounts."""

import os
import logging
import subprocess
import json
from datetime import datetime, timedelta
from flask import current_app
from citadel.models import db
from citadel.models.job import Job
from citadel.backup.mount import check_mount_status

logger = logging.getLogger(__name__)

def get_all_active_mounts():
    """Get a list of all active Borg mounts in the system."""
    # Get all successful mount jobs
    mount_jobs = Job.query.filter_by(job_type='mount', status='success').all()
    
    active_mounts = []
    for job in mount_jobs:
        metadata = job.get_metadata() or {}
        mount_point = metadata.get('mount_point')
        
        if mount_point and check_mount_status(mount_point):
            active_mounts.append({
                'job_id': job.id,
                'mount_point': mount_point,
                'archive_name': metadata.get('archive_name', 'Unknown'),
                'mounted_at': job.timestamp.isoformat() if job.timestamp else None,
                'user_id': job.user_id,
                'repository_id': job.repository_id
            })
    
    return active_mounts

def get_orphaned_mounts(max_age_hours=24):
    """Get mounts that are older than the specified age."""
    active_mounts = get_all_active_mounts()
    
    # Calculate the cutoff time
    cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
    
    orphaned_mounts = []
    for mount in active_mounts:
        if mount.get('mounted_at'):
            try:
                mounted_at = datetime.fromisoformat(mount['mounted_at'])
                if mounted_at < cutoff_time:
                    orphaned_mounts.append(mount)
            except (ValueError, TypeError):
                # If we can't parse the timestamp, assume it's old
                orphaned_mounts.append(mount)
    
    return orphaned_mounts

def unmount_orphaned(max_age_hours=24, force=False):
    """Unmount all orphaned mounts."""
    from citadel.backup.mount import unmount_archive
    
    orphaned_mounts = get_orphaned_mounts(max_age_hours)
    results = []
    
    for mount in orphaned_mounts:
        job_id = mount.get('job_id')
        mount_point = mount.get('mount_point')
        
        if not job_id or not mount_point:
            continue
        
        logger.info(f"Unmounting orphaned mount: {mount_point} (Job ID: {job_id})")
        
        try:
            # Create an unmount job
            unmount_job = Job(
                job_type='unmount',
                status='pending',
                repository_id=mount.get('repository_id'),
                user_id=mount.get('user_id'),
                timestamp=datetime.utcnow()
            )
            
            # Copy the mount point from the original job
            unmount_metadata = {
                'mount_job_id': job_id,
                'mount_point': mount_point,
                'automated': True,
                'reason': 'Orphaned mount cleanup'
            }
            unmount_job.set_metadata(unmount_metadata)
            
            db.session.add(unmount_job)
            db.session.commit()
            
            # Unmount directly if force=True, otherwise just queue the job
            if force:
                # Get the app
                app = current_app._get_current_object()
                unmount_archive(unmount_job.id, app)
            
            results.append({
                'job_id': job_id,
                'unmount_job_id': unmount_job.id,
                'mount_point': mount_point,
                'status': 'unmounting' if force else 'queued'
            })
            
        except Exception as e:
            logger.error(f"Error unmounting orphaned mount {mount_point}: {str(e)}")
            results.append({
                'job_id': job_id,
                'mount_point': mount_point,
                'status': 'error',
                'error': str(e)
            })
    
    return results

def get_system_mounts():
    """Get all mounts from the system, regardless of Borg status."""
    try:
        result = subprocess.run(
            ["mount"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        mounts = []
        for line in result.stdout.splitlines():
            parts = line.split(' ')
            if len(parts) >= 3:
                mounts.append({
                    'device': parts[0],
                    'mount_point': parts[2],
                    'type': parts[4] if len(parts) > 4 else 'unknown'
                })
        
        return mounts
    except Exception as e:
        logger.error(f"Error getting system mounts: {str(e)}")
        return []

def find_borg_mounts():
    """Find all Borg mounts in the system."""
    system_mounts = get_system_mounts()
    
    # Filter for FUSE mounts which are typically used by Borg
    fuse_mounts = [m for m in system_mounts if 'fuse' in m.get('type', '').lower()]
    
    # Get the base directory for Citadel mounts
    base_dir = current_app.config.get('MOUNT_BASE_DIR', '/tmp/citadel/mounts')
    
    # Filter for mounts in the Citadel mount directory
    citadel_mounts = [m for m in fuse_mounts if m.get('mount_point', '').startswith(base_dir)]
    
    return citadel_mounts

def force_unmount_all(base_dir=None):
    """Force unmount all Borg mounts in the system."""
    if base_dir is None:
        base_dir = current_app.config.get('MOUNT_BASE_DIR', '/tmp/citadel/mounts')
    
    # Get all system mounts
    system_mounts = get_system_mounts()
    
    # Filter for mounts in the Citadel mount directory
    citadel_mounts = [m for m in system_mounts if m.get('mount_point', '').startswith(base_dir)]
    
    results = []
    for mount in citadel_mounts:
        mount_point = mount.get('mount_point')
        if not mount_point:
            continue
        
        logger.info(f"Force unmounting: {mount_point}")
        
        try:
            # Try to unmount using fusermount
            subprocess.run(
                ["fusermount", "-u", "-z", mount_point],
                capture_output=True,
                check=False,
                timeout=10
            )
            
            # Check if it's still mounted
            if not os.path.ismount(mount_point):
                results.append({
                    'mount_point': mount_point,
                    'status': 'unmounted'
                })
                continue
            
            # Try alternative umount if fusermount fails
            subprocess.run(
                ["umount", "-f", mount_point],
                capture_output=True,
                check=False,
                timeout=10
            )
            
            # Check again
            if not os.path.ismount(mount_point):
                results.append({
                    'mount_point': mount_point,
                    'status': 'unmounted'
                })
            else:
                results.append({
                    'mount_point': mount_point,
                    'status': 'failed',
                    'error': 'Could not unmount even with force option'
                })
            
        except Exception as e:
            logger.error(f"Error force unmounting {mount_point}: {str(e)}")
            results.append({
                'mount_point': mount_point,
                'status': 'error',
                'error': str(e)
            })
    
    return results
