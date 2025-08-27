"""Source model for the Tower of Borg application."""
from datetime import datetime
from towerofborg.models import db

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
