"""
Database migration script to initialize the Citadel database.
This script creates all tables from scratch.
"""

from citadel import create_app
from citadel.models import db
from citadel.models.user import User
from citadel.models.repository import Repository
from citadel.models.source import Source
from citadel.models.schedule import Schedule
from citadel.models.job import Job
import os

def init_db():
    """Initialize the database with all tables."""
    # Create app with scheduler disabled for initialization
    os.environ['DISABLE_SCHEDULER'] = 'true'
    app = create_app()
    
    with app.app_context():
        # Drop all tables first to ensure clean state
        db.drop_all()
        # Create all tables
        db.create_all()
        
        # Create admin user if configured or use default password
        from citadel.auth.routes import create_user
        admin_password = os.environ.get('ADMIN_PASSWORD', 'citadel')
        create_user('admin', admin_password, is_admin=True)
        print(f"Admin user created with {'configured' if 'ADMIN_PASSWORD' in os.environ else 'default'} password")
        
        print("Database initialized successfully!")

if __name__ == "__main__":
    init_db()
