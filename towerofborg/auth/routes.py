"""Authentication routes for the Tower of Borg application."""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from towerofborg.models import db
from towerofborg.models.user import User

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
bcrypt = Bcrypt()

def create_user(username, password, is_admin=False):
    """Helper function to create a new user"""
    password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    user = User(username=username, password_hash=password_hash, is_admin=is_admin)
    db.session.add(user)
    db.session.commit()
    return user

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = 'remember' in request.form
        
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('Login failed. Please check your username and password.', 'danger')
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated and not current_user.is_admin:
        flash('You are already logged in.', 'info')
        return redirect(url_for('dashboard'))
    
    # Only admins can create new users
    if current_user.is_authenticated and not current_user.is_admin:
        flash('Only administrators can create new users.', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register.html')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return render_template('auth/register.html')
        
        create_user(username, password)
        flash('User registered successfully. You can now log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html')

@auth_bp.route('/profile')
@login_required
def profile():
    return render_template('auth/profile.html')

@auth_bp.route('/change_password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not bcrypt.check_password_hash(current_user.password_hash, current_password):
        flash('Current password is incorrect.', 'danger')
        return redirect(url_for('auth.profile'))
    
    if new_password != confirm_password:
        flash('New passwords do not match.', 'danger')
        return redirect(url_for('auth.profile'))
    
    current_user.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
    db.session.commit()
    
    flash('Password changed successfully.', 'success')
    return redirect(url_for('auth.profile'))
