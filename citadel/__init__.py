"""Citadel - A web interface for Borg backup."""

from flask import Flask, render_template, redirect, url_for, jsonify
from flask_login import current_user, login_required
import os
import atexit
import logging
import sys
from dotenv import load_dotenv

def configure_logging(app):
    """Configure logging for the application."""
    log_level = app.config.get('LOG_LEVEL', 'DEBUG')
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.DEBUG

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Create console handler if not already present
    has_console_handler = any(isinstance(h, logging.StreamHandler) and h.stream == sys.stdout 
                             for h in root_logger.handlers)
    
    if not has_console_handler:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # Set specific logger levels
    logging.getLogger('citadel').setLevel(numeric_level)
    logging.getLogger('citadel.analytics').setLevel(numeric_level)
    
    app.logger.debug("Logging configured successfully")

def create_app(config=None):
    """Create and configure the Flask application."""
    # Load environment variables
    load_dotenv()
    
    app = Flask(__name__, 
                template_folder='templates',
                static_folder='../static')
    
    # Load default configuration
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-key-change-in-production'),
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URI', f'sqlite:///{os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "instance", "citadel.db"))}'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        DEBUG=True,
        LOG_LEVEL=os.environ.get('LOG_LEVEL', 'DEBUG')
    )
    
    # Load environment variables starting with CITADEL_
    app.config.from_prefixed_env(prefix='CITADEL')
    
    # Configure logging
    configure_logging(app)
    
    # Initialize database
    from citadel.models import db
    db.init_app(app)
    
    # Import modules
    from citadel.models.user import User
    from citadel.models.repository import Repository
    from citadel.models.job import Job
    from citadel.models.source import Source
    from citadel.models.schedule import Schedule
    
    from citadel.auth import init_auth, auth_bp
    from citadel.backup import init_backup, backup_bp
    from citadel.sources import init_sources, sources_bp
    from citadel.schedules import init_schedules, schedules_bp
    from citadel.analytics import init_analytics, analytics_bp
    from citadel.settings import init_settings, settings_bp
    from citadel.utils import init_scheduler, shutdown_scheduler
    
    # Initialize modules
    init_auth(app)
    init_backup(app)
    init_sources(app)
    init_schedules(app)
    init_analytics(app)
    init_settings(app)
    
    # Initialize scheduler only if not disabled
    if os.environ.get('DISABLE_SCHEDULER', 'false').lower() != 'true':
        scheduler = init_scheduler(app)
        # Register shutdown function
        atexit.register(shutdown_scheduler)
        
        # Register mount scheduler shutdown
        from citadel.backup.mount_scheduler import shutdown_mount_scheduler
        atexit.register(shutdown_mount_scheduler)
    else:
        app.logger.info("Scheduler disabled via environment variable")
    
    # Register error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500
    
    # Register template filters
    @app.template_filter('filesize')
    def filesize_filter(size):
        """Format size in bytes to human-readable format"""
        if size is None:
            return "Unknown"
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"
    
    @app.template_filter('datetime')
    def datetime_filter(dt_str):
        """Format datetime string to human-readable format"""
        from datetime import datetime
        if not dt_str:
            return "Unknown"
        
        try:
            if isinstance(dt_str, str):
                dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            else:
                dt = dt_str
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, AttributeError):
            return dt_str
    
    # Index route
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return redirect(url_for('auth.login'))
    
    # Dashboard route
    @app.route('/dashboard')
    @login_required
    def dashboard():
        repos = Repository.query.filter_by(user_id=current_user.id).all()
        # Exclude 'list' jobs from recent jobs and eagerly load relationships
        recent_jobs = Job.query.filter_by(user_id=current_user.id).filter(Job.job_type != 'list') \
                    .options(db.joinedload(Job.source), db.joinedload(Job.repository)) \
                    .order_by(Job.timestamp.desc()).limit(10).all()
        # Also get sources for the dashboard
        sources = Source.query.filter_by(user_id=current_user.id).all()
        # Get active schedules
        schedules = Schedule.query.filter_by(user_id=current_user.id, is_active=True).all()
        return render_template('common/dashboard.html', repos=repos, jobs=recent_jobs, sources=sources, schedules=schedules)
    
    # API route for jobs
    @app.route('/api/jobs')
    @login_required
    def list_jobs():
        # Exclude 'list' jobs from API response and eagerly load relationships
        jobs = Job.query.filter_by(user_id=current_user.id).filter(Job.job_type != 'list') \
              .options(db.joinedload(Job.source), db.joinedload(Job.repository)) \
              .all()
        return jsonify([job.to_dict() for job in jobs])
    
    # Create admin user if none exists
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            from citadel.auth.routes import create_user
            create_user('admin', os.environ.get('ADMIN_PASSWORD', 'citadel'), is_admin=True)
            print('Admin user created with default or configured password')
    
    return app
