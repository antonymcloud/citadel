"""Database models for the Citadel application."""

from flask_sqlalchemy import SQLAlchemy

# Initialize SQLAlchemy
db = SQLAlchemy()

# Import models to make them available when importing the package
from citadel.models.user import User
from citadel.models.repository import Repository
from citadel.models.job import Job
from citadel.models.source import Source
from citadel.models.schedule import Schedule
