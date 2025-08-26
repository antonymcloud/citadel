from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    repositories = db.relationship('Repository', backref='owner', lazy=True)
    jobs = db.relationship('Job', backref='user', lazy=True)
    sources = db.relationship('Source', backref='owner', lazy=True)
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'is_admin': self.is_admin
        }

class Repository(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    path = db.Column(db.String(255), nullable=False)
    encryption = db.Column(db.String(50), default=None)
    passphrase = db.Column(db.String(255), default=None)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    jobs = db.relationship('Job', backref='repository', lazy=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Repository {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'path': self.path,
            'encryption': self.encryption,
            'created_at': self.created_at.isoformat()
        }

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
    
    # Add relationship to Source
    source = db.relationship('Source', backref='jobs', lazy=True)
    
    def __repr__(self):
        return f'<Job {self.id} {self.job_type} {self.status}>'
    
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
            'log_output': self.log_output
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

class Source(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    source_type = db.Column(db.String(20), nullable=False)  # 'local' or 'ssh'
    path = db.Column(db.String(255), nullable=False)
    ssh_host = db.Column(db.String(100), default=None)
    ssh_port = db.Column(db.Integer, default=22)
    ssh_user = db.Column(db.String(100), default=None)
    ssh_key_path = db.Column(db.String(255), default=None)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        if self.source_type == 'local':
            return f'<Source {self.name} (local:{self.path})>'
        else:
            return f'<Source {self.name} (ssh:{self.ssh_user}@{self.ssh_host}:{self.path})>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'source_type': self.source_type,
            'path': self.path,
            'ssh_host': self.ssh_host,
            'ssh_port': self.ssh_port,
            'ssh_user': self.ssh_user,
            'ssh_key_path': self.ssh_key_path,
            'created_at': self.created_at.isoformat()
        }
    
    def get_formatted_path(self):
        """Return the fully formatted path for use with borg commands"""
        if self.source_type == 'local':
            return self.path
        else:
            # SSH source format: user@host:/path or ssh://user@host:port/path
            if self.ssh_port == 22:
                return f"{self.ssh_user}@{self.ssh_host}:{self.path}"
            else:
                return f"ssh://{self.ssh_user}@{self.ssh_host}:{self.ssh_port}/{self.path.lstrip('/')}"
