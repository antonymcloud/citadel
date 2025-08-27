"""Repository model for the Tower of Borg application."""
from datetime import datetime
from towerofborg.models import db

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
