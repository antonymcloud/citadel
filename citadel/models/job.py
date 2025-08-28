"""Job model for the Citadel application."""
from datetime import datetime
import json
from citadel.models import db

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_type = db.Column(db.String(20), nullable=False)  # create, prune, list, etc.
    status = db.Column(db.String(20), nullable=False)  # running, success, failed
    repository_id = db.Column(db.Integer, db.ForeignKey('repository.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    archive_name = db.Column(db.String(100), default=None)
    source_id = db.Column(db.Integer, db.ForeignKey('source.id'), default=None)
    source_path = db.Column(db.String(255), default=None)  # For backward compatibility
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, default=None)
    log_output = db.Column(db.Text, default=None)
    job_metadata = db.Column(db.Text, default=None)  # JSON serialized metadata
    
    # Add relationship to Source
    source = db.relationship('Source', backref='jobs', lazy=True)
    
    def __repr__(self):
        return f'<Job {self.id} {self.job_type} {self.status}>'
    
    def get_metadata(self):
        """Get metadata as a Python dictionary"""
        if self.job_metadata:
            try:
                return json.loads(self.job_metadata)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata_dict):
        """Set metadata from a Python dictionary"""
        self.job_metadata = json.dumps(metadata_dict)
    
    def to_dict(self):
        return {
            'id': self.id,
            'job_type': self.job_type,
            'status': self.status,
            'repository_id': self.repository_id,
            'archive_name': self.archive_name,
            'source_id': self.source_id,
            'source_path': self.source_path,
            'timestamp': self.timestamp.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'log_output': self.log_output,
            'metadata': self.get_metadata()
        }
        
    def cancel(self):
        """Mark a job as cancelled"""
        if self.status == 'running':
            self.status = 'cancelled'
            self.completed_at = datetime.utcnow()
            self.log_output = (self.log_output or '') + '\n\n--- Job cancelled by user ---'
            db.session.commit()
            return True
        return False
