"""Routes for the settings module."""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from citadel.models import db
from citadel.models.user import User

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

@settings_bp.route('/')
@login_required
def settings_home():
    """Settings home page."""
    return render_template('settings/settings.html')

@settings_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile_settings():
    """User profile settings."""
    if request.method == 'POST':
        # Get form data
        username = request.form.get('username')
        email = request.form.get('email')
        
        # Validate data
        if not username or not email:
            flash('Username and email are required.', 'danger')
            return redirect(url_for('settings.profile_settings'))
        
        # Check if the username is already taken by another user
        existing_user = User.query.filter(User.username == username, User.id != current_user.id).first()
        if existing_user:
            flash('Username already taken. Please choose another.', 'danger')
            return redirect(url_for('settings.profile_settings'))
        
        # Update user data
        current_user.username = username
        current_user.email = email
        
        # Save changes
        db.session.commit()
        
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('settings.profile_settings'))
    
    return render_template('settings/profile.html')

@settings_bp.route('/security', methods=['GET', 'POST'])
@login_required
def security_settings():
    """Security settings."""
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate inputs
        if not current_password or not new_password or not confirm_password:
            flash('All fields are required.', 'danger')
            return redirect(url_for('settings.security_settings'))
        
        if new_password != confirm_password:
            flash('New passwords do not match.', 'danger')
            return redirect(url_for('settings.security_settings'))
        
        # Verify current password
        if not current_user.check_password(current_password):
            flash('Current password is incorrect.', 'danger')
            return redirect(url_for('settings.security_settings'))
        
        # Update password
        current_user.set_password(new_password)
        db.session.commit()
        
        flash('Password updated successfully.', 'success')
        return redirect(url_for('settings.security_settings'))
    
    return render_template('settings/security.html')

@settings_bp.route('/appearance', methods=['GET', 'POST'])
@login_required
def appearance_settings():
    """Appearance settings."""
    if request.method == 'POST':
        theme = request.form.get('theme', 'light')
        
        # Update user preferences
        # Assuming User model has a preferences JSON field or similar
        current_user.preferences = current_user.preferences or {}
        current_user.preferences['theme'] = theme
        db.session.commit()
        
        flash('Appearance settings updated.', 'success')
        return redirect(url_for('settings.appearance_settings'))
    
    # Get current theme preference
    theme = 'light'
    if hasattr(current_user, 'preferences') and current_user.preferences:
        theme = current_user.preferences.get('theme', 'light')
    
    return render_template('settings/appearance.html', theme=theme)

@settings_bp.route('/notifications', methods=['GET', 'POST'])
@login_required
def notification_settings():
    """Notification settings."""
    if request.method == 'POST':
        email_notifications = 'email_notifications' in request.form
        backup_success = 'backup_success' in request.form
        backup_failure = 'backup_failure' in request.form
        
        # Update user preferences
        current_user.preferences = current_user.preferences or {}
        current_user.preferences['notifications'] = {
            'email_notifications': email_notifications,
            'backup_success': backup_success,
            'backup_failure': backup_failure
        }
        db.session.commit()
        
        flash('Notification settings updated.', 'success')
        return redirect(url_for('settings.notification_settings'))
    
    # Get current notification preferences
    notifications = {
        'email_notifications': False,
        'backup_success': False,
        'backup_failure': True
    }
    
    if hasattr(current_user, 'preferences') and current_user.preferences:
        user_notifications = current_user.preferences.get('notifications', {})
        notifications.update(user_notifications)
    
    return render_template('settings/notifications.html', notifications=notifications)
