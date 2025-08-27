from app import app
from models import db, Job
import json

with app.app_context():
    job = Job.query.filter_by(status='success').first()
    print('Job found:', bool(job))
    if job:
        print('Job ID:', job.id)
        print('Job Status:', job.status)
        print('Job metadata:', job.job_metadata)
        
        if job.job_metadata:
            try:
                metadata = json.loads(job.job_metadata)
                print('Parsed metadata:', metadata)
                print('Has stats:', 'stats' in metadata)
                if 'stats' in metadata:
                    print('Stats content:', metadata['stats'])
            except json.JSONDecodeError as e:
                print('Error parsing metadata JSON:', e)
