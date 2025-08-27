"""Schedule model for the Tower of Borg application."""
from datetime import datetime
from towerofborg.models import db

# Association table for Schedule-Job many-to-many relationship
schedule_job = db.Table('schedule_job',
    db.Column('schedule_id', db.Integer, db.ForeignKey('schedule.id'), primary_key=True),
    db.Column('job_id', db.Integer, db.ForeignKey('job.id'), primary_key=True)
)

class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    repository_id = db.Column(db.Integer, db.ForeignKey('repository.id'), nullable=False)
    source_id = db.Column(db.Integer, db.ForeignKey('source.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    archive_prefix = db.Column(db.String(100), default=None)
    
    # Schedule configuration
    frequency = db.Column(db.String(20), nullable=False)  # daily, weekly, monthly
    hour = db.Column(db.Integer, default=0)  # Hour of day (0-23)
    minute = db.Column(db.Integer, default=0)  # Minute of hour (0-59)
    day_of_week = db.Column(db.String(20), default=None)  # For weekly: mon, tue, wed, etc.
    day_of_month = db.Column(db.Integer, default=None)  # For monthly: 1-31
    
    # Retention settings
    keep_daily = db.Column(db.Integer, default=7)
    keep_weekly = db.Column(db.Integer, default=4)
    keep_monthly = db.Column(db.Integer, default=6)
    
    # Auto-prune after backup
    auto_prune = db.Column(db.Boolean, default=True)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_run = db.Column(db.DateTime, default=None)
    next_run = db.Column(db.DateTime, default=None)
    
    # Relationships
    repository = db.relationship('Repository', backref='schedules')
    source = db.relationship('Source', backref='schedules')
    jobs = db.relationship('Job', 
                          secondary='schedule_job',
                          backref=db.backref('schedules', lazy='dynamic'),
                          lazy='dynamic')
    
    def __repr__(self):
        return f'<Schedule {self.name} ({self.frequency})>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'repository_id': self.repository_id,
            'source_id': self.source_id,
            'frequency': self.frequency,
            'hour': self.hour,
            'minute': self.minute,
            'day_of_week': self.day_of_week,
            'day_of_month': self.day_of_month,
            'is_active': self.is_active,
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'next_run': self.next_run.isoformat() if self.next_run else None
        }
    
    def get_cron_expression(self):
        """Return a cron expression for this schedule"""
        if self.frequency == 'daily':
            return f"{self.minute} {self.hour} * * *"
        elif self.frequency == 'weekly':
            # day_of_week should be 0-6 (0=Monday in APScheduler, different from cron)
            day_map = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
            day = day_map.get(self.day_of_week.lower(), 0)
            return f"{self.minute} {self.hour} * * {day}"
        elif self.frequency == 'monthly':
            # day_of_month should be 1-31
            day = min(max(1, self.day_of_month), 31)
            return f"{self.minute} {self.hour} {day} * *"
        return None
