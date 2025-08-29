"""Utility functions for backup operations."""

import os
import subprocess
import threading
import json
import shutil
import time
from datetime import datetime, timedelta

from citadel.models import db
from citadel.models.job import Job
from citadel.models.repository import Repository

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
    
    # Process the section that contains the statistics table
    try:
        # Extract individual stats
        lines = stats_section.strip().split('\n')
        
        # Try to parse statistics table (Original size, Compressed size, etc.)
        size_data = {}
        table_headers = []
        
        # First find the header line with column names
        header_line = None
        for line in lines:
            if "Original size" in line and "Compressed size" in line:
                header_line = line.strip()
                break
        
        # If we found the header line, parse it
        if header_line:
            # Simple approach: take the position-based values from the table
            # For example, first column is Original size, second is Compressed size, etc.
            stats_rows = []
            this_archive_row = None
            all_archives_row = None
            
            # Find the data rows
            for line in lines:
                line = line.strip()
                if "This archive:" in line:
                    this_archive_row = line
                elif "All archives:" in line:
                    all_archives_row = line
            
            # Parse the data if we found it
            if this_archive_row:
                # Extract values
                try:
                    # Get the data part after the colon
                    data_part = this_archive_row.split(':', 1)[1].strip()
                    # Split into columns, ensuring we have at least 3 values
                    cols = data_part.split()
                    if len(cols) >= 3:
                        stats['this_archive_original_size'] = cols[0] + " " + cols[1]
                        stats['this_archive_compressed_size'] = cols[2] + " " + cols[3]
                        stats['this_archive_deduplicated_size'] = cols[4] + " " + cols[5]
                except (IndexError, ValueError) as e:
                    print(f"DEBUG: Error parsing This archive row: {e}")
            
            if all_archives_row:
                try:
                    # Get the data part after the colon
                    data_part = all_archives_row.split(':', 1)[1].strip()
                    # Split into columns, ensuring we have at least 3 values
                    cols = data_part.split()
                    if len(cols) >= 3:
                        stats['all_archives_original_size'] = cols[0] + " " + cols[1]
                        stats['all_archives_compressed_size'] = cols[2] + " " + cols[3]
                        stats['all_archives_deduplicated_size'] = cols[4] + " " + cols[5]
                except (IndexError, ValueError) as e:
                    print(f"DEBUG: Error parsing All archives row: {e}")
        
        # Extract other key statistics from the output
        for line in lines:
            line = line.strip()
            
            # Skip lines we already processed and empty lines
            if not line or "Original size" in line or "This archive:" in line or "All archives:" in line:
                continue
                
            # Parse lines that have key-value format with a colon
            if ":" in line:
                try:
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        key = parts[0].strip().lower().replace(' ', '_')
                        value = parts[1].strip()
                        
                        # Special handling for known keys
                        if key == 'number_of_files':
                            try:
                                stats['nfiles'] = int(value)
                            except ValueError:
                                stats[key] = value
                        elif key == 'duration':
                            if "minutes" in value and "seconds" in value:
                                try:
                                    # Parse something like "5 minutes 30.00 seconds"
                                    min_parts = value.split('minutes')[0].strip()
                                    sec_parts = value.split('minutes')[1].split('seconds')[0].strip()
                                    minutes = float(min_parts)
                                    seconds = float(sec_parts)
                                    stats['duration'] = minutes * 60 + seconds
                                except (ValueError, IndexError):
                                    stats[key] = value
                            else:
                                stats[key] = value
                        else:
                            # For other keys, try to convert to number if it looks like one
                            try:
                                if '.' in value and value.replace('.', '', 1).isdigit():
                                    stats[key] = float(value)
                                elif value.isdigit():
                                    stats[key] = int(value)
                                else:
                                    stats[key] = value
                            except (ValueError, AttributeError):
                                stats[key] = value
                except Exception as e:
                    print(f"DEBUG: Error parsing line '{line}': {e}")
    except Exception as e:
        print(f"DEBUG: Error extracting stats: {e}")
        return stats
    
    # Calculate compression and deduplication ratios
    try:
        # Helper function to extract numeric value from size string
        def extract_size_bytes(size_str):
            if not size_str or not isinstance(size_str, str):
                return 0
                
            parts = size_str.split()
            if len(parts) != 2:
                return 0
                
            try:
                value = float(parts[0])
                unit = parts[1].upper()
                
                # Convert to bytes based on unit
                if unit == 'B':
                    return value
                elif unit == 'KB':
                    return value * 1024
                elif unit == 'MB':
                    return value * 1024 * 1024
                elif unit == 'GB':
                    return value * 1024 * 1024 * 1024
                elif unit == 'TB':
                    return value * 1024 * 1024 * 1024 * 1024
                else:
                    return 0
            except (ValueError, IndexError):
                return 0
        
        # Calculate compression ratio
        if 'this_archive_original_size' in stats and 'this_archive_compressed_size' in stats:
            original_bytes = extract_size_bytes(stats['this_archive_original_size'])
            compressed_bytes = extract_size_bytes(stats['this_archive_compressed_size'])
            
            if original_bytes > 0 and compressed_bytes > 0:
                stats['compression_ratio'] = original_bytes / compressed_bytes
        
        # Calculate deduplication ratio
        if 'this_archive_original_size' in stats and 'this_archive_deduplicated_size' in stats:
            original_bytes = extract_size_bytes(stats['this_archive_original_size'])
            deduplicated_bytes = extract_size_bytes(stats['this_archive_deduplicated_size'])
            
            if original_bytes > 0 and deduplicated_bytes > 0:
                stats['deduplication_ratio'] = original_bytes / deduplicated_bytes
    except Exception as e:
        print(f"DEBUG: Error calculating ratios: {e}")
    
    return stats

def extract_size_bytes(size_str):
    """Extract bytes from a size string like '1.23 GB'"""
    if not size_str or not isinstance(size_str, str):
        return 0
        
    parts = size_str.split()
    if len(parts) != 2:
        return 0
        
    try:
        value = float(parts[0])
        unit = parts[1].upper()
        
        # Convert to bytes based on unit
        if unit == 'B':
            return value
        elif unit == 'KB':
            return value * 1024
        elif unit == 'MB':
            return value * 1024 * 1024
        elif unit == 'GB':
            return value * 1024 * 1024 * 1024
        elif unit == 'TB':
            return value * 1024 * 1024 * 1024 * 1024
        else:
            return 0
    except (ValueError, IndexError):
        return 0

def parse_size(size_str):
    """Parse a size string like '1.23 GB' to bytes"""
    if not size_str or not isinstance(size_str, str):
        return 0
        
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
        
def format_size(size_bytes):
    """Format a size in bytes to a human-readable string"""
    if size_bytes is None:
        return "0 B"
    
    if not isinstance(size_bytes, (int, float)):
        try:
            size_bytes = float(size_bytes)
        except (ValueError, TypeError):
            return "Unknown"
    
    if size_bytes == 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    i = 0
    while size_bytes >= 1024 and i < len(units) - 1:
        size_bytes /= 1024
        i += 1
    
    return f"{size_bytes:.2f} {units[i]}"

def normalize_archive_data(archives):
    """Normalize archive data to ensure consistent format and fill missing fields"""
    normalized_archives = []
    
    for archive in archives:
        # Create a copy to avoid modifying the original
        norm_archive = dict(archive)
        
        # Ensure the archive has required fields
        if 'name' not in norm_archive or not norm_archive['name']:
            norm_archive['name'] = "Unnamed Archive"
        
        # Normalize time field
        if 'time' not in norm_archive or not norm_archive['time']:
            norm_archive['time'] = datetime.utcnow().isoformat()
        elif isinstance(norm_archive['time'], datetime):
            norm_archive['time'] = norm_archive['time'].isoformat()
        
        # Normalize size field
        if 'size' not in norm_archive or norm_archive['size'] is None:
            norm_archive['size'] = 0
        elif isinstance(norm_archive['size'], str):
            try:
                # Try to parse if it's a string with units like "5.00 GB"
                norm_archive['size'] = parse_size(norm_archive['size'])
            except (ValueError, TypeError):
                norm_archive['size'] = 0
        
        # Format size for display
        norm_archive['size_formatted'] = format_size(norm_archive['size'])
        
        # Ensure comment field exists
        if 'comment' not in norm_archive:
            norm_archive['comment'] = ""
        
        normalized_archives.append(norm_archive)
    
    return normalized_archives

def run_backup_job(job_id):
    """Run a backup job in a separate thread"""
    from flask import current_app
    
    job = Job.query.get(job_id)
    if not job:
        print(f"DEBUG: Job {job_id} not found")
        return
    
    # Update job status
    job.status = 'running'
    db.session.commit()
    
    print(f"DEBUG: Starting job {job_id} of type {job.job_type}")
    
    # Create a copy of the current application for the thread
    app = current_app._get_current_object()
    
    # Start a thread to run the job
    thread = threading.Thread(target=_run_backup_job_thread, args=(job_id, app))
    thread.daemon = True
    thread.start()

def _run_backup_job_thread(job_id, app):
    """Thread function to run a backup job"""
    # Create an application context
    with app.app_context():
        job = Job.query.get(job_id)
        if not job or job.status != 'running':
            print(f"DEBUG: Job {job_id} not found or not running")
            return
        
        repository = job.repository
        print(f"DEBUG: Running job {job_id} of type {job.job_type} for repository {repository.name}")
        
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
            print(f"DEBUG: Executing command: {' '.join(cmd)}")
            
            # For testing/dev: Check if we're in mock mode
            if os.environ.get('MOCK_BORG', 'false').lower() == 'true' or not shutil.which('borg'):
                print(f"DEBUG: Running in mock mode (MOCK_BORG=true or borg not found)")
                # Simulate command execution with a mock output
                time.sleep(2)  # Simulate some processing time
                
                if job.job_type == 'create':
                    # Use current date and time for the mock output
                    current_date = datetime.utcnow()
                    formatted_date = current_date.strftime('%Y-%m-%d')
                    formatted_time = current_date.strftime('%H:%M:%S')
                    formatted_day = current_date.strftime('%a')
                    
                    output = f"""
                    ------------------------------------------------------------------------------
                    Repository: {repository.path}
                    Archive name: {job.archive_name}
                    Archive fingerprint: dac883078e9634dedd3b3958745fa858e7b23c268163f33c6a300fa7340b6ad8
                    Time (start): {formatted_day}, {formatted_date} {formatted_time}
                    Time (end): {formatted_day}, {formatted_date} {formatted_time}
                    Duration: 3 minutes 45.00 seconds
                    Number of files: 12345
                    Utilization of max. archive size: 0%
                    ------------------------------------------------------------------------------
                                    Original size      Compressed size    Deduplicated size
                    This archive:       1.00 GB            900.00 MB            500.00 MB
                    All archives:       5.00 GB              4.50 GB              2.50 GB
                    
                    Unique chunks         Total chunks
                    Chunk index:               50000               150000
                    ------------------------------------------------------------------------------
                    """
                    exit_code = 0
                elif job.job_type == 'list':
                    # Enhanced mock data with more complete archive information
                    current_date = datetime.utcnow()
                    archives = []
                    
                    # Generate 10 mock archives with different dates
                    for i in range(10):
                        archive_date = current_date - timedelta(days=i)
                        archive_name = f"backup-{archive_date.strftime('%Y-%m-%d_%H%M%S')}"
                        
                        # Vary sizes to show growth over time
                        size_mb = 500 - (i * 20)  # Decreasing size as we go back in time
                        
                        archives.append({
                            "name": archive_name,
                            "time": archive_date.isoformat(),
                            "size": 1024 * 1024 * size_mb,  # Convert MB to bytes
                            "comment": f"Daily backup {i+1}" if i < 5 else f"Weekly backup {i-4}",
                            "hostname": "mock-server",
                            "username": "mockuser",
                            "id": f"mock-id-{i}",
                            "command_line": ["borg", "create", "--stats", repository.path],
                        })
                    
                    output = json.dumps({"archives": archives})
                    exit_code = 0
                elif job.job_type == 'prune':
                    output = """
                    ------------------------------------------------------------------------------
                    Keeping archive: backup-2023-06-15_120000
                    Pruning archive: backup-2023-01-01_120000
                    ------------------------------------------------------------------------------
                                    Original size      Compressed size    Deduplicated size
                    Deleted data:       1.00 GB            900.00 MB            500.00 MB
                    All archives:       4.00 GB              3.60 GB              2.00 GB
                    ------------------------------------------------------------------------------
                    """
                    exit_code = 0
                else:
                    output = "Mock output for unknown job type"
                    exit_code = 1
            else:
                # Real execution with Borg
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=env
                )
                
                try:
                    output, _ = process.communicate(timeout=300)  # 5 minute timeout
                    exit_code = process.returncode
                except subprocess.TimeoutExpired:
                    # Kill the process if it times out
                    process.kill()
                    output, _ = process.communicate()
                    exit_code = -1
                    print(f"DEBUG: Command timed out after 5 minutes")
            
            print(f"DEBUG: Command completed with exit code {exit_code}")
            print(f"DEBUG: First 200 chars of output: {output[:200] if output else 'No output'}")
            
            # Update job with results
            job.log_output = output if output else "Command execution timed out after 5 minutes"
            job.completed_at = datetime.utcnow()
            
            if exit_code == 0:
                job.status = 'success'
                print(f"DEBUG: Job {job.id} marked as success")
                
                # Parse output if needed
                if job.job_type == 'create' or job.job_type == 'prune':
                    try:
                        stats = extract_stats_from_output(output)
                        print(f"DEBUG: Extracted stats: {stats.keys()}")
                        
                        # Create a metadata dictionary if not already exist
                        metadata = job.get_metadata() or {}
                        metadata['stats'] = stats
                        job.set_metadata(metadata)
                        print(f"DEBUG: Set job metadata with stats")
                    except Exception as e:
                        print(f"DEBUG: Error setting job stats: {e}")
                        # Don't let stats extraction failure fail the job
                        metadata = job.get_metadata() or {}
                        metadata['stats_error'] = str(e)
                        job.set_metadata(metadata)
                elif job.job_type == 'list':
                    try:
                        # Extract archive list from JSON output
                        archives = []
                        # First, try to parse the whole output as JSON
                        try:
                            data = json.loads(output)
                            if 'archives' in data:
                                archives = data['archives']
                        except json.JSONDecodeError:
                            # If that fails, try to parse each line as JSON
                            for line in output.strip().split('\n'):
                                if line.strip():
                                    try:
                                        data = json.loads(line)
                                        if 'archives' in data:
                                            archives = data['archives']
                                            break
                                    except json.JSONDecodeError:
                                        continue
                        
                        # Normalize archive data
                        normalized_archives = normalize_archive_data(archives)
                        
                        metadata = {'archives': normalized_archives}
                        job.set_metadata(metadata)
                        print(f"DEBUG: Set job metadata with {len(normalized_archives)} normalized archives")
                    except Exception as e:
                        # Log the error but don't fail the job
                        print(f"Error parsing list output: {str(e)}")
                        metadata = {'archives': [], 'error': str(e)}
                        job.set_metadata(metadata)
            else:
                job.status = 'failed'
                print(f"DEBUG: Job {job.id} marked as failed with exit code {exit_code}")
            
            print(f"DEBUG: Committing job {job.id} changes to database")
            db.session.commit()
            print(f"DEBUG: Database commit successful for job {job.id}")
        except Exception as e:
            # Handle any exceptions
            print(f"DEBUG: Exception in job {job_id}: {str(e)}")
            job.status = 'failed'
            job.log_output = (job.log_output or '') + f"\n\nError: {str(e)}"
            job.completed_at = datetime.utcnow()
            db.session.commit()
            print(f"DEBUG: Database commit successful for job {job.id} after exception")

def list_archives(repository_id):
    """Create a job to list archives in a repository and return the job ID"""
    from flask import current_app
    
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
