"""
Script to update existing jobs with statistics extracted from their log output.
This is a one-time migration to populate the job_metadata field for existing jobs.
"""
from app import app
from models import db, Job
import json
from backup import extract_stats_from_output

def update_jobs_with_stats():
    """Update existing jobs with statistics extracted from their log output."""
    with app.app_context():
        # Get all successful jobs
        jobs = Job.query.filter_by(status='success').all()
        
        print(f"Found {len(jobs)} successful jobs")
        
        for job in jobs:
            print(f"Processing job {job.id} ({job.job_type})...")
            
            # Skip jobs that already have metadata
            if job.job_metadata:
                print(f"Job {job.id} already has metadata, skipping")
                continue
                
            # Skip jobs without log output
            if not job.log_output:
                print(f"Job {job.id} has no log output, skipping")
                continue
                
            # Only process create and prune jobs
            if job.job_type not in ['create', 'prune']:
                print(f"Job {job.id} is not a create or prune job, skipping")
                continue
                
            # Extract statistics from log output
            stats = extract_stats_from_output(job.log_output)
            
            if stats:
                print(f"Extracted statistics for job {job.id}")
                
                # Store statistics in job metadata
                metadata = job.get_metadata()
                metadata["stats"] = stats
                job.set_metadata(metadata)
                
                # Save changes
                db.session.commit()
                print(f"Updated job {job.id} with statistics")
            else:
                print(f"No statistics found for job {job.id}")
        
        print("Done!")

if __name__ == "__main__":
    update_jobs_with_stats()
