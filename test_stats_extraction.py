from app import app
from models import db, Job, Repository, User
from backup import run_borg_command
import os

def test_stats_extraction():
    with app.app_context():
        # Get test repository
        repository = Repository.query.first()
        if not repository:
            print("No repository found. Please create one first.")
            return
        
        # Get test user
        user = User.query.first()
        if not user:
            print("No user found. Please create one first.")
            return
        
        # Create a test job
        job = Job(
            job_type="create",
            status="running",
            repository_id=repository.id,
            user_id=user.id,
            archive_name="test-archive"
        )
        db.session.add(job)
        db.session.commit()
        
        print(f"Created test job with ID {job.id}")
        
        # Set debug environment variable
        os.environ["DEBUG"] = "True"
        
        # Run a backup command to create an archive
        args = [
            "create",
            "--stats",
            f"{repository.path}::test-archive",
            "/home/localadmin/TowerOfBorg/migrations"  # Some sample files to backup
        ]
        
        print(f"Running backup command: {args}")
        
        # Run the command and get result
        result = run_borg_command(job.id, args)
        
        print(f"Backup command result: {result}")
        
        # Refresh job from database
        job = Job.query.get(job.id)
        
        print(f"Job status: {job.status}")
        print(f"Job metadata: {job.job_metadata}")
        
        if job.job_metadata:
            print("Job has metadata!")
        else:
            print("Job has no metadata!")

if __name__ == "__main__":
    test_stats_extraction()
