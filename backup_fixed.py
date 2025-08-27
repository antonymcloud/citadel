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
