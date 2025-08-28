"""Tower of Borg - A web interface for Borg backup."""

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
    logging.getLogger('towerofborg').setLevel(numeric_level)
    logging.getLogger('towerofborg.analytics').setLevel(numeric_level)
    
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
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URI', 'sqlite:///../towerofborg.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        DEBUG=True,
        LOG_LEVEL=os.environ.get('LOG_LEVEL', 'DEBUG')
    )
    
    # Load environment variables starting with TOWEROFBORG_
    app.config.from_prefixed_env(prefix='TOWEROFBORG')
    
    # Configure logging
    configure_logging(app)
    
    # Initialize database
    from towerofborg.models import db
    db.init_app(app)
    
    # Import modules
    from towerofborg.models.user import User
    from towerofborg.models.repository import Repository
    from towerofborg.models.job import Job
    from towerofborg.models.source import Source
    from towerofborg.models.schedule import Schedule
    
    from towerofborg.auth import init_auth, auth_bp
    from towerofborg.backup import init_backup, backup_bp
    from towerofborg.sources import init_sources, sources_bp
    from towerofborg.schedules import init_schedules, schedules_bp
    from towerofborg.analytics import init_analytics, analytics_bp
    from towerofborg.utils import init_scheduler, shutdown_scheduler
    from towerofborg.test_routes import test_bp
    
    # Initialize modules
    init_auth(app)
    init_backup(app)
    init_sources(app)
    init_schedules(app)
    init_analytics(app)
    
    # Register test blueprint (not initialized through a module function)
    app.register_blueprint(test_bp)
    
    # Initialize scheduler
    scheduler = init_scheduler(app)
    
    # Register shutdown function
    atexit.register(shutdown_scheduler)
    
    # Register error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500
    
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
            from towerofborg.auth.routes import create_user
            create_user('admin', os.environ.get('ADMIN_PASSWORD', 'towerofborg'), is_admin=True)
            print('Admin user created with default or configured password')
    
    return app
