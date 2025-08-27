#!/usr/bin/env python3
import sys
import json
import os
import subprocess
import time
import random
from datetime import datetime, timedelta

# Get the debug flag
debug = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 't')

# Check if JSON output is requested
json_mode = "--json" in sys.argv

# Print mock indication only when needed for debugging
if debug and not json_mode:
    print(f"Mock Borg Command: {' '.join(sys.argv[1:])}", file=sys.stderr)

# If in debug mode and real borg exists, run the real command and capture its output
real_borg_output = ""
if debug:
    try:
        # Check if real borg exists
        borg_paths = ["/usr/bin/borg", "/usr/local/bin/borg"]
        real_borg = None
        for path in borg_paths:
            if os.path.exists(path):
                real_borg = path
                break
        
        if real_borg:
            print(f"Debug mode: Also running real borg command", file=sys.stderr)
            real_result = subprocess.run(
                [real_borg] + sys.argv[1:],
                capture_output=True,
                text=True,
                env=os.environ.copy()  # Copy environment variables
            )
            
            if real_result.returncode == 0:
                real_borg_output = real_result.stdout
                # If stdout is empty but we have stderr and the command succeeded, use stderr as output
                if not real_borg_output.strip() and real_result.stderr.strip():
                    real_borg_output = real_result.stderr
                print(f"Real borg output:\n{real_borg_output}", file=sys.stderr)
            else:
                print(f"Real borg error (code {real_result.returncode}):\n{real_result.stderr}", file=sys.stderr)
    except Exception as e:
        print(f"Error running real borg: {str(e)}", file=sys.stderr)

# Generate simulated JSON progress
def generate_json_progress():
    """Generate simulated JSON progress messages in Borg's format"""
    # Generate progress updates - Borg uses progress_percent type
    for i in range(0, 101, 10):
        if i > 0:  # Add small delay except for first message
            time.sleep(0.3)
        
        msg = {
            "type": "progress_percent",
            "operation": 1,  # Borg uses an opaque integer ID
            "msgid": "extract" if i < 100 else None,
            "message": f"{i}.0% Processing: simulated_file_{i}.txt" if i < 100 else None,
            "current": i if i < 100 else None,
            "total": 100 if i < 100 else None,
            "info": ["simulated_file_{}.txt".format(i)] if i < 100 else None,
            "time": time.time(),
            "finished": i == 100
        }
        print(json.dumps(msg))
        sys.stdout.flush()

def generate_file_status():
    """Generate file status updates in JSON format"""
    files = [
        "/home/user/documents/file1.txt",
        "/home/user/documents/file2.pdf",
        "/home/user/pictures/img1.jpg",
        "/home/user/pictures/img2.png",
        "/home/user/videos/video1.mp4"
    ]
    
    statuses = ["A", "M", "U"]  # Added, Modified, Unchanged (Borg uses single-char statuses)
    
    for file in files:
        status = random.choice(statuses)
        msg = {
            "type": "file_status",
            "status": status,
            "path": file
        }
        print(json.dumps(msg))
        sys.stdout.flush()
        time.sleep(0.2)

def generate_summary(archive_name="backup-2025-08-27"):
    """Generate a backup summary in Borg's format"""
    # For create command, return a proper archive object
    now = time.time()
    return {
        "archive": {
            "name": archive_name,
            "id": "abc123def456789012345678901234567890",
            "start": now - 5,
            "end": now,
            "duration": 5.0,
            "stats": {
                "compressed_size": 12345678,
                "deduplicated_size": 9876543,
                "nfiles": 123,
                "original_size": 15678901
            },
            "hostname": "mock-host",
            "username": "mock-user",
            "comment": "Mock backup created with mock_borg.py"
        }
    }

# Handle different commands
if len(sys.argv) > 1:
    command = sys.argv[1]
    
    # If we have real output in debug mode, just print it and exit
    if debug and real_borg_output:
        print(real_borg_output)
        sys.exit(0)
    
    # If debug mode, print headers to stderr
    if debug:
        print("=== MOCK OUTPUT ===", file=sys.stderr)
    
    # Get archive and source path info for create commands
    archive_path = None
    archive_name = None
    source_path = None
    for arg in sys.argv:
        if "::" in arg:
            archive_path = arg
            archive_name = arg.split("::")[-1]
        elif arg not in ["create", "list", "init", "prune", "--verbose", "--stats", "--progress", "--json"] and not arg.startswith("--"):
            source_path = arg
    
    # Always output clean mock data to stdout without headers
    if command == "list":
        if json_mode:
            # JSON list output - follows Borg's format
            archives = []
            today = datetime.now()
            
            # Create archive entries
            for i in range(5):
                date = (today - timedelta(days=i))
                archives.append({
                    "name": f"archive{i+1}",
                    "id": f"mock-id-{i}abcdef0123456789abcdef0123456789abcdef",
                    "start": date.timestamp(),
                    "time": date.timestamp()  # Borg uses both 'time' and 'start'
                })
            
            # Add any specific archive that was created
            if archive_name:
                archives.append({
                    "name": archive_name,
                    "id": "mock-id-specialabcdef0123456789abcdef0123456789",
                    "start": today.timestamp(),
                    "time": today.timestamp()
                })
            
            # Create the full result object
            result = {
                "archives": archives,
                "encryption": {
                    "mode": "repokey"
                },
                "repository": {
                    "id": "mock-repo-" + datetime.now().strftime("%Y%m%d%H%M%S"),
                    "last_modified": datetime.now().timestamp(),
                    "location": source_path or "unknown_path"
                }
            }
            
            print(json.dumps(result))
        else:
            # Mock text list output
            today = datetime.now()
            yesterday = today - timedelta(days=1)
            print(f"archive1                              {today.strftime('%a, %Y-%m-%d %H:%M:%S')}")
            print(f"archive2                              {yesterday.strftime('%a, %Y-%m-%d %H:%M:%S')}")
            
            # Also list any archive name that was used in create command
            if archive_name:
                print(f"{archive_name}                    {today.strftime('%a, %Y-%m-%d %H:%M:%S')}")
    
    elif command == "create":
        if json_mode:
            # JSON create output - emulate Borg's format with --log-json and --json
            # First output log messages about starting
            print(json.dumps({
                "type": "log_message",
                "time": time.time(),
                "levelname": "INFO",
                "name": "borg.archiver",
                "message": "Mock Borg: Starting backup operation"
            }))
            sys.stdout.flush()
            time.sleep(0.3)
            
            # Output initial archive progress
            print(json.dumps({
                "type": "archive_progress",
                "original_size": 0,
                "compressed_size": 0,
                "deduplicated_size": 0,
                "nfiles": 0,
                "path": source_path or "unknown_path",
                "time": time.time()
            }))
            sys.stdout.flush()
            time.sleep(0.3)
            
            # Progress messages
            generate_json_progress()
            
            # File status if --list was specified
            if "--list" in sys.argv:
                generate_file_status()
            
            # Final archive progress
            print(json.dumps({
                "type": "archive_progress",
                "original_size": 15678901,
                "compressed_size": 12345678,
                "deduplicated_size": 9876543,
                "nfiles": 123,
                "path": "",
                "time": time.time(),
                "finished": True
            }))
            sys.stdout.flush()
            
            # Log completion
            print(json.dumps({
                "type": "log_message",
                "time": time.time(),
                "levelname": "INFO",
                "name": "borg.archiver",
                "message": "Mock Borg: Backup completed successfully"
            }))
            sys.stdout.flush()
            
            # Output the archive summary (this isn't part of --log-json but part of --json)
            # For actual archive info, this would be printed to stdout separately
            print(json.dumps(generate_summary(archive_name or "backup-2025-08-27")))
            sys.stdout.flush()
        else:
            # Text create output
            is_verbose = "--verbose" in sys.argv
            show_stats = "--stats" in sys.argv
            show_progress = "--progress" in sys.argv
            
            print("Creating archive...")
            
            if show_progress:
                print("Scanning source directories...")
                print("                       100.00% Analyzing files")
                print("                       100.00% Creating archive")
                print("                       100.00% Compressing data")
            
            if is_verbose:
                print(f"Processing files from source directory: {source_path}")
                print(f"Creating backup archive: {archive_path}")
                print("Archive created with 1234 files, 5678 directories")
            
            if show_stats:
                print("------------------------------------------------------------------------------")
                print("Archive name: " + (archive_name if archive_path else "archive"))
                print("Archive fingerprint: 01234567890123456789012345678901234567890123456789")
                print("Time (start): " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                print("Time (end):   " + (datetime.now() + timedelta(seconds=5)).strftime("%Y-%m-%d %H:%M:%S"))
                print("Duration: 5.00 seconds")
                print("Number of files: 1234")
                print("Utilization of max. archive size: 0%")
                print("                       Original size      Compressed size    Deduplicated size")
                print("This archive:               1.00 GB            500.00 MB            250.00 MB")
                print("All archives:               5.00 GB              2.50 GB              1.25 GB")
                print("                       Unique chunks         Total chunks")
                print("Chunk index:                    1000                2000")
                print("------------------------------------------------------------------------------")
            
            print("Archive created successfully.")
    
    elif command == "init":
        if json_mode:
            # JSON init output
            result = {
                "repository": {
                    "id": "mock-repo-" + datetime.now().strftime("%Y%m%d%H%M%S"),
                    "location": source_path or "unknown_path",
                    "encrypted": "--encryption" in " ".join(sys.argv),
                    "created": datetime.now().isoformat()
                }
            }
            print(json.dumps(result))
        else:
            # Text init output
            print("Initializing repository...")
            print("Repository initialized.")
    
    elif command == "prune":
        if json_mode:
            # JSON prune output
            print(json.dumps({"type": "log_message", "level": "info", "message": "Mock Borg: Starting prune operation"}))
            time.sleep(0.5)
            
            for i in range(3):
                print(json.dumps({
                    "type": "log_message",
                    "level": "info",
                    "message": f"Mock Borg: Pruning archive{i+1}"
                }))
                time.sleep(0.3)
            
            print(json.dumps({
                "type": "prune_summary",
                "stats": {
                    "total_archives": 8,
                    "kept_archives": 5,
                    "pruned_archives": 3,
                    "deleted_size": 51200000,
                    "original_size": 1073741824,
                    "deduplicated_size": 536870912
                }
            }))
        else:
            # Text prune output
            print("Pruning repository...")
            print("Keeping archives: 7 daily, 4 weekly, 6 monthly")
            print("Pruning archive: archive1")
            print("Pruning archive: archive2")
            print("----------------")
            print("                       Original size      Deduplicated size")
            print("All archives:                 1.00 GB            500.00 MB")
            print("Deleted data:               102.40 MB             51.20 MB")
    
    else:
        # Unknown command
        if json_mode:
            print(json.dumps({
                "type": "error",
                "message": f"Unknown command: {command}"
            }))
        else:
            print(f"Error: Unknown command '{command}'", file=sys.stderr)
        sys.exit(1)
else:
    # No command specified
    if json_mode:
        print(json.dumps({
            "type": "error",
            "message": "No command specified"
        }))
    else:
        print("Error: No command specified", file=sys.stderr)
    sys.exit(1)

# Exit with success
sys.exit(0)
