"""Database models for the Tower of Borg application."""

from flask_sqlalchemy import SQLAlchemy

# Initialize SQLAlchemy
db = SQLAlchemy()

# Import models to make them available when importing the package
from towerofborg.models.user import User
from towerofborg.models.repository import Repository
from towerofborg.models.job import Job
from towerofborg.models.source import Source
from towerofborg.models.schedule import Schedule
