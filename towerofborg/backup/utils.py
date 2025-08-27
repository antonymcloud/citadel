"""Utility functions for backup operations."""

import os
import subprocess
import threading
import json
from datetime import datetime

from towerofborg.models import db
from towerofborg.models.job import Job
from towerofborg.models.repository import Repository

def extract_stats_from_output(output):
    """Extract statistics from Borg command output"""
    stats = {}
    
    # Look for the statistics section which is delimited by dashed lines
    dash_line = "------------------------------------------------------------------------------"
    if dash_line in output:
        sections = output.split(dash_line)
    elif f"[WARN] {dash_line}" in output:
        # Handle mock output with [WARN] prefix
        sections = output.split(f"[WARN] {dash_line}")
    else:
        # No statistics found
        return stats
    
    # Find the section that contains the statistics
    stats_section = None
    for section in sections:
        if "This archive:" in section or "All archives:" in section:
            stats_section = section
            break
    
    if not stats_section:
        return stats
    
    # Extract individual stats
    lines = stats_section.strip().split('\n')
    for line in lines:
        line = line.strip()
        
        # Skip empty lines and headers
        if not line or "This archive:" in line or "All archives:" in line:
            continue
        
        # Parse the line which should be in format "Key:     Value"
        parts = line.split(':', 1)
        if len(parts) == 2:
            key = parts[0].strip().lower().replace(' ', '_')
            value = parts[1].strip()
            
            # Try to convert numeric values
            try:
                if '.' in value:
                    stats[key] = float(value)
                else:
                    stats[key] = int(value)
            except ValueError:
                # Handle special cases like sizes with units
                if any(unit in value for unit in ['B', 'KB', 'MB', 'GB', 'TB']):
                    stats[key] = value
                    # Also parse the size in bytes if available
                    size_parts = value.split()
                    if len(size_parts) >= 2 and size_parts[1].startswith('(') and size_parts[1].endswith('B)'):
                        try:
                            byte_size = size_parts[1].strip('()')
                            stats[f"{key}_bytes"] = parse_size(byte_size)
                        except ValueError:
                            pass
                else:
                    stats[key] = value
    
    # Calculate additional derived statistics
    if 'original_size_bytes' in stats and 'compressed_size_bytes' in stats and stats['original_size_bytes'] > 0:
        stats['compression_ratio'] = stats['original_size_bytes'] / stats['compressed_size_bytes']
    
    if 'original_size_bytes' in stats and 'deduplicated_size_bytes' in stats and stats['original_size_bytes'] > 0:
        stats['deduplication_ratio'] = stats['original_size_bytes'] / stats['deduplicated_size_bytes']
    
    return stats

def parse_size(size_str):
    """Parse a size string like '1.23 GB' to bytes"""
    size_str = size_str.strip()
    if size_str.endswith('B)'):
        size_str = size_str[:-1]  # Remove closing parenthesis
    if size_str.startswith('('):
        size_str = size_str[1:]  # Remove opening parenthesis
    
    parts = size_str.split()
    if len(parts) != 2:
        raise ValueError(f"Invalid size format: {size_str}")
    
    value = float(parts[0])
    unit = parts[1].upper()
    
    # Convert to bytes
    if unit == 'B':
        return int(value)
    elif unit == 'KB':
        return int(value * 1024)
    elif unit == 'MB':
        return int(value * 1024 * 1024)
    elif unit == 'GB':
        return int(value * 1024 * 1024 * 1024)
    elif unit == 'TB':
        return int(value * 1024 * 1024 * 1024 * 1024)
    else:
        raise ValueError(f"Unknown unit: {unit}")

def run_backup_job(job_id):
    """Run a backup job in a separate thread"""
    job = Job.query.get(job_id)
    if not job:
        return
    
    # Update job status
    job.status = 'running'
    db.session.commit()
    
    # Start a thread to run the job
    thread = threading.Thread(target=_run_backup_job_thread, args=(job_id,))
    thread.daemon = True
    thread.start()

def _run_backup_job_thread(job_id):
    """Thread function to run a backup job"""
    job = Job.query.get(job_id)
    if not job or job.status != 'running':
        return
    
    repository = job.repository
    
    try:
        # Prepare command based on job type
        cmd = ['borg']
        env = os.environ.copy()
        
        # Add encryption environment variable if needed
        if repository.encryption and repository.passphrase:
            env['BORG_PASSPHRASE'] = repository.passphrase
        
        if job.job_type == 'create':
            source = job.source
            cmd.extend([
                'create',
                f"{repository.path}::{job.archive_name}",
                source.get_formatted_path() if source else job.source_path,
                '--stats'
            ])
        elif job.job_type == 'list':
            cmd.extend([
                'list',
                repository.path,
                '--json'
            ])
        elif job.job_type == 'prune':
            cmd.extend([
                'prune',
                repository.path,
                '--keep-daily', '7',
                '--keep-weekly', '4',
                '--keep-monthly', '6',
                '--stats'
            ])
            
            # Add additional keep options if provided in metadata
            metadata = job.get_metadata()
            if metadata.get('keep_daily'):
                cmd[4] = str(metadata['keep_daily'])
            if metadata.get('keep_weekly'):
                cmd[6] = str(metadata['keep_weekly'])
            if metadata.get('keep_monthly'):
                cmd[8] = str(metadata['keep_monthly'])
                
        # Run the command
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env
        )
        
        output = process.communicate()[0]
        exit_code = process.returncode
        
        # Update job with results
        job.log_output = output
        job.completed_at = datetime.utcnow()
        
        if exit_code == 0:
            job.status = 'success'
            
            # Parse output if needed
            if job.job_type == 'create' or job.job_type == 'prune':
                stats = extract_stats_from_output(output)
                metadata = job.get_metadata()
                metadata['stats'] = stats
                job.set_metadata(metadata)
            elif job.job_type == 'list':
                try:
                    # Extract archive list from JSON output
                    archives = []
                    for line in output.strip().split('\n'):
                        if line.strip():
                            data = json.loads(line)
                            if 'archives' in data:
                                archives = data['archives']
                                break
                    metadata = {'archives': archives}
                    job.set_metadata(metadata)
                except json.JSONDecodeError:
                    pass
        else:
            job.status = 'failed'
        
        db.session.commit()
    except Exception as e:
        # Handle any exceptions
        job.status = 'failed'
        job.log_output = str(e)
        job.completed_at = datetime.utcnow()
        db.session.commit()

def list_archives(repository_id):
    """Create a job to list archives in a repository and return the job ID"""
    repository = Repository.query.get(repository_id)
    if not repository:
        return None
    
    # Create a new job
    job = Job(
        job_type='list',
        status='created',
        repository_id=repository.id,
        user_id=repository.user_id,
        timestamp=datetime.utcnow()
    )
    db.session.add(job)
    db.session.commit()
    
    # Run the job
    run_backup_job(job.id)
    
    return job.id
