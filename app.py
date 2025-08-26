from flask import Flask, render_template, redirect, url_for, flash, jsonify, request
from flask_login import LoginManager, login_required, current_user
import os
from dotenv import load_dotenv
from models import db, User, Repository, Job
from auth import auth_bp, init_login_manager
from backup import backup_bp

# Load environment variables
load_dotenv()

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URI', 'sqlite:///towerofborg.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

# Initialize login manager
login_manager = init_login_manager(app)

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(backup_bp)

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('auth.login'))

@app.route('/dashboard')
@login_required
def dashboard():
    repos = Repository.query.filter_by(user_id=current_user.id).all()
    # Exclude 'list' jobs from recent jobs
    recent_jobs = Job.query.filter_by(user_id=current_user.id).filter(Job.job_type != 'list').order_by(Job.timestamp.desc()).limit(10).all()
    return render_template('dashboard.html', repos=repos, jobs=recent_jobs)

@app.route('/api/jobs')
@login_required
def list_jobs():
    # Exclude 'list' jobs from API response
    jobs = Job.query.filter_by(user_id=current_user.id).filter(Job.job_type != 'list').all()
    return jsonify([job.to_dict() for job in jobs])

# Create admin user if none exists
def create_admin():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            from auth import create_user
            create_user('admin', os.environ.get('ADMIN_PASSWORD', 'towerofborg'), is_admin=True)
            print('Admin user created with default or configured password')

if __name__ == '__main__':
    create_admin()  # Call the function directly before running the app
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)), debug=True)
