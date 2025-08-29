"""Authentication related models."""

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from citadel.models import db
from datetime import datetime
import json

class User(UserMixin, db.Model):
    """User model for authentication."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    preferences_json = db.Column(db.Text, nullable=True)
    
    # Relationships
    repositories = db.relationship('Repository', backref='user', lazy=True)
    jobs = db.relationship('Job', backref='user', lazy=True)
    sources = db.relationship('Source', backref='user', lazy=True)
    schedules = db.relationship('Schedule', backref='user', lazy=True)
    
    def set_password(self, password):
        """Set the password hash."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check the password against the hash."""
        return check_password_hash(self.password_hash, password)
    
    @property
    def preferences(self):
        """Get user preferences."""
        if not self.preferences_json:
            return {}
        try:
            return json.loads(self.preferences_json)
        except json.JSONDecodeError:
            return {}
    
    @preferences.setter
    def preferences(self, value):
        """Set user preferences."""
        if value is None:
            self.preferences_json = None
        else:
            self.preferences_json = json.dumps(value)
    
    def __repr__(self):
        return f'<User {self.username}>'
