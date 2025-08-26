#!/usr/bin/env python3
import sys
import json
import datetime
import os
import subprocess

# Get the debug flag
debug = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 't')

# Print mock indication only when needed for debugging
if debug:
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
    
    # Always output clean mock data to stdout without headers
    if command == "list":
        # Mock list output
        today = datetime.datetime.now()
        yesterday = today - datetime.timedelta(days=1)
        print(f"archive1                              {today.strftime('%a, %Y-%m-%d %H:%M:%S')}")
        print(f"archive2                              {yesterday.strftime('%a, %Y-%m-%d %H:%M:%S')}")
        
        # Also list any archive name that was used in create command
        # This looks for the archive name in the second argument of create command
        if len(sys.argv) > 2 and "::" in sys.argv[2]:
            repo_path = sys.argv[2]
            archive_name = repo_path.split("::")[-1]
            print(f"{archive_name}                    {today.strftime('%a, %Y-%m-%d %H:%M:%S')}")
    
    elif command == "create":
        # Mock create output
        print("Creating archive...")
        print("Archive created successfully.")
    
    elif command == "init":
        # Mock init output
        print("Initializing repository...")
        print("Repository initialized.")
    
    elif command == "prune":
        # Mock prune output
        print("Pruning repository...")
        print("Keeping archives: 7 daily, 4 weekly, 6 monthly")
        print("Pruning archive: archive1")
        print("Pruning archive: archive2")
        print("----------------")
        print("                       Original size      Deduplicated size")
        print("All archives:                 1.00 GB            500.00 MB")
        print("Deleted data:               102.40 MB             51.20 MB")
        print("----------------")
        print("Prune finished successfully.")

# Exit successfully
sys.exit(0)
