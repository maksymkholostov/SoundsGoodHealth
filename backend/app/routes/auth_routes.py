# backend/app/routes/auth_routes.py
"""
Routes for user authentication and profile management.
"""
from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for, session, flash
from flask_login import login_required, login_user, logout_user, current_user
from werkzeug.security import generate_password_hash # Keep only necessary security imports
import traceback
import os # For SECRET_KEY example in app factory update

# Create blueprint
auth_web_bp = Blueprint('auth_web', __name__) # No url_prefix needed here

# --- Authentication Pages ---

@auth_web_bp.route('/login', methods=['GET', 'POST'])
def login_page():
    """Serve the login page and handle login requests."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        try:
            if not username or not password:
                flash("Username and password are required", "warning")
                return render_template('login.html', error="Username and password are required")

            # Authenticate user using auth service
            if not hasattr(current_app, 'auth_service'):
                 current_app.logger.error("Authentication service not configured.")
                 flash("Login service is currently unavailable. Please try again later.", "danger")
                 return render_template('login.html', error="Authentication service not available")

            # Authenticate user
            user, error = current_app.auth_service.authenticate(username, password)

            if error:
                current_app.logger.warning(f"Login failed for {username}: {error}")
                flash(error, "danger") # Display error message to user
                return render_template('login.html', error=error)

            if not user:
                 current_app.logger.warning(f"Invalid credentials for user: {username}")
                 flash("Invalid username or password", "danger")
                 return render_template('login.html', error="Invalid username or password")

            # Set up session FIRST before login_user to avoid conflicts
            session.permanent = True # Make session persistent
            session['user_id'] = user.id
            session['is_admin'] = getattr(user, 'is_admin', False)
            session['username'] = user.username

            # Use Flask-Login to handle login (remember=True keeps user logged in)
            login_user(user, remember=True)

            # Record login and update user (optional, handle errors gracefully)
            try:
                if hasattr(user, 'record_login'): # Check if method exists
                    user.record_login()
                    current_app.auth_service.user_repo.save(user) # Assumes repo exists on service
            except Exception as update_e:
                # Non-critical error, just log it
                current_app.logger.warning(f"Error updating user login time for {username}: {str(update_e)}")

            # Redirect after successful login
            next_page = request.args.get('next')
            # Validate next_page to prevent open redirect vulnerability
            if next_page and (next_page.startswith('/') or url_for('auth_web.login_page') in next_page): # Basic validation
                 current_app.logger.info(f"User {username} logged in. Redirecting to requested page: {next_page}")
                 return redirect(next_page)
            else:
                 # Default redirect to index page (using core_web blueprint)
                 try:
                     index_url = url_for('core_web.index')
                     current_app.logger.info(f"User {username} logged in. Redirecting to default index: {index_url}")
                     return redirect(index_url)
                 except Exception:
                     current_app.logger.warning("Could not generate URL for 'core_web.index', redirecting to '/'.")
                     return redirect('/') # Absolute fallback

        except Exception as e:
            current_app.logger.error(f"Login error: {str(e)}", exc_info=True)
            flash("An unexpected error occurred during login. Please try again.", "danger")
            return render_template('login.html', error="An error occurred during login")

    # GET request handling
    # Check if already logged in, redirect to index if so
    if current_user.is_authenticated:
        try: return redirect(url_for('core_web.index'))
        except: return redirect('/')

    # Handle ron_mode for GET request
    ron_mode = request.args.get('ron_mode', 'false').lower() in ('true', '1', 'yes')
    if 'ron_mode' in request.args and not request.args.get('ron_mode'):
        ron_mode = True # Also true if present without value

    return render_template('login.html', ron_mode=ron_mode)

@auth_web_bp.route('/register', methods=['GET', 'POST'])
def register_page():
    """Serve the registration page and handle registration requests."""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password') # Add confirmation check

        # Basic Validation
        if not username or not email or not password or not confirm_password:
            flash("All fields are required.", "warning")
            return render_template('register.html', error="All fields are required", username=username, email=email)
        if password != confirm_password:
            flash("Passwords do not match.", "warning")
            return render_template('register.html', error="Passwords do not match", username=username, email=email)
        # Add more validation (email format, password strength) here if desired

        try:
            if not hasattr(current_app, 'auth_service'):
                 current_app.logger.error("Authentication service not configured.")
                 flash("Registration service is currently unavailable.", "danger")
                 return render_template('register.html', error="Authentication service not available")

            # Register the user (service should handle username/email uniqueness checks)
            user, error = current_app.auth_service.register_user(
                username=username,
                email=email,
                password=password
            )

            if error:
                flash(error, "danger") # Show specific error from service
                return render_template('register.html', error=error, username=username, email=email)

            # Log the user in immediately after successful registration
            if user:
                session['user_id'] = user.id
                session['is_admin'] = getattr(user, 'is_admin', False)
                session['username'] = user.username
                try:
                    login_user(user, remember=True) # Log in with Flask-Login
                except Exception as e:
                    current_app.logger.warning(f"Could not use login_user after registration: {str(e)}")

                flash("Registration successful! Welcome.", "success")
                current_app.logger.info(f"New user registered and logged in: {username}")
                # Redirect to index page
                try: return redirect(url_for('core_web.index'))
                except: return redirect('/')

            # Should not happen if service returns user or error, but handle defensively
            flash("Registration failed unexpectedly.", "danger")
            return render_template('register.html', error="Registration failed unexpectedly", username=username, email=email)

        except Exception as e:
            current_app.logger.error(f"Error in registration: {str(e)}", exc_info=True)
            flash(f"An unexpected error occurred during registration.", "danger")
            return render_template('register.html', error=f"An error occurred: {str(e)}", username=username, email=email)

    # GET request - show registration form
    # If already logged in, redirect away
    if current_user.is_authenticated:
        try: return redirect(url_for('core_web.index'))
        except: return redirect('/')
    return render_template('register.html')

@auth_web_bp.route('/logout')
@login_required
def logout():
    """Handle user logout."""
    username = current_user.username # Get username before logging out
    
    # Properly log out the user
    logout_user()
    
    # Clear the session completely
    session.clear()
    
    # Log the action
    current_app.logger.info(f"User {username} logged out.")
    
    # Create response to redirect to login page
    response = redirect('/login')
    
    # Remove Flask session cookies
    response.delete_cookie('session')
    
    # Add a flash message to show on the login page
    flash("You have been successfully logged out.", "info")
    
    return response

@auth_web_bp.route('/test-logout')
def test_logout():
    """Test route to diagnose logout issues."""
    return """
    <html>
        <head><title>Logout Test</title></head>
        <body>
            <h1>Logout Test</h1>
            <p>Click the link below to test logout:</p>
            <a href="/logout">Logout</a>
            <p>After logout, you should be redirected to the login page.</p>
        </body>
    </html>
    """

@auth_web_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Handle forgot password requests."""
    if request.method == 'POST':
        email = request.form.get('email')

        if not email:
            flash("Email address is required.", "warning")
            return render_template('reset_password.html', error="Email is required")

        try:
            if not hasattr(current_app, 'auth_service'):
                 current_app.logger.error("Authentication service not configured for password reset.")
                 flash("Password reset service is currently unavailable.", "error")
                 return render_template('reset_password.html', error="Service unavailable")

            # Find user by email (service method)
            user = current_app.auth_service.user_repo.get_by_email(email) # Assumes repo on service

            if not user:
                # Don't reveal if email exists - security best practice
                current_app.logger.info(f"Password reset requested for non-existent or incorrect email: {email}")
            else:
                # Generate a reset token (service method)
                token = current_app.auth_service.generate_password_reset_token(user.id)
                reset_url = url_for('auth_web.reset_password_confirm', token=token, _external=True)

                # --- Send Email ---
                # This part requires an email sending setup (e.g., Flask-Mail)
                # mail_service = current_app.extensions.get('mail')
                # if mail_service:
                #    subject = "Password Reset Request"
                #    sender = current_app.config.get('MAIL_DEFAULT_SENDER')
                #    recipients = [user.email]
                #    body = f"Click the link to reset your password: {reset_url}"
                #    html_body = render_template('email/reset_password.html', reset_url=reset_url) # Example template
                #    # Send email using service
                #    mail_service.send_email(subject, sender, recipients, body, html_body)
                #    current_app.logger.info(f"Password reset email sent to {email}")
                # else:
                #    current_app.logger.error("Mail service not configured. Cannot send password reset email.")
                #    # Fallback for debugging/testing (REMOVE IN PRODUCTION)
                flash(f"DEBUG: Password reset link: <a href='{reset_url}'>{reset_url}</a>", "info")
                current_app.logger.info(f"DEBUG ONLY: Password reset link for {email}: {reset_url}")


            # Always show the same message whether user exists or not
            flash("If an account with that email exists, instructions to reset your password have been sent.", "info")
            # Redirect to login page after request submitted
            return redirect(url_for('auth_web.login_page'))

        except Exception as e:
            current_app.logger.error(f"Error in forgot_password process for {email}: {str(e)}", exc_info=True)
            flash("An error occurred while processing your request. Please try again later.", "error")
            # Show the form again on general error
            return render_template('reset_password.html', error="An error occurred.")

    # GET request - show forgot password form
    if current_user.is_authenticated:
        try: return redirect(url_for('core_web.index'))
        except: return redirect('/')
    return render_template('reset_password.html')

@auth_web_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password_confirm(token):
    """Handle password reset confirmation using the token."""
    try:
        if not hasattr(current_app, 'auth_service'):
            current_app.logger.error("Authentication service not configured for password reset confirmation.")
            flash("Password reset service is unavailable.", "error")
            return render_template('reset_password_confirm.html', error="Service unavailable", expired=True)

        # Verify the token and get user ID (service method)
        user_id = current_app.auth_service.verify_password_reset_token(token)

        if not user_id:
            current_app.logger.warning(f"Invalid or expired password reset token used: {token}")
            flash("This password reset link is invalid or has expired.", "error")
            return render_template('reset_password_confirm.html', error="Invalid or expired reset link", expired=True)

        # Get the user object
        user = current_app.auth_service.get_user_by_id(user_id)
        if not user:
            # Should not happen if token was valid, but check defensively
            current_app.logger.error(f"User ID {user_id} from valid reset token not found.")
            flash("This password reset link is invalid or has expired.", "error") # Use same message
            return render_template('reset_password_confirm.html', error="User not found", expired=True)

        if request.method == 'POST':
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')

            # Validation
            if not password or not confirm_password:
                flash("Please enter and confirm your new password.", "warning")
                return render_template('reset_password_confirm.html', error="Both password fields are required", token=token)
            if password != confirm_password:
                flash("The passwords do not match.", "warning")
                return render_template('reset_password_confirm.html', error="Passwords do not match", token=token)
            # Add password strength validation here if needed
            if len(password) < 8:
                flash("Password must be at least 8 characters long.", "warning")
                return render_template('reset_password_confirm.html', error="Password too short", token=token)

            # Update the password (service method or user model method)
            # Assuming user model has update_password or set_password
            if hasattr(user, 'update_password'):
                 user.update_password(password)
            elif hasattr(user, 'set_password'):
                 user.set_password(password)
            else:
                 # Fallback if methods don't exist (less ideal)
                 user.password_hash = generate_password_hash(password)

            current_app.auth_service.user_repo.save(user) # Save updated user

            # Optionally invalidate the token if it's single-use
            # current_app.auth_service.invalidate_reset_token(token) # Needs service method

            current_app.logger.info(f"Password reset successfully via token for user {user.username}")
            flash("Your password has been updated successfully. You can now log in.", "success")
            return redirect(url_for('auth_web.login_page'))

        # GET request - show the password reset form
        return render_template('reset_password_confirm.html', token=token)

    except Exception as e:
         current_app.logger.error(f"Error during password reset confirmation for token {token}: {str(e)}", exc_info=True)
         flash("An unexpected error occurred during the password reset process.", "error")
         # Show error page, maybe without the form if token might be compromised by error
         return render_template('reset_password_confirm.html', error="An unexpected error occurred.", expired=True)


# --- Profile Management ---

@auth_web_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile_page():
    """Serve the user profile page and handle profile updates."""
    user_id = current_user.id # Get user ID from Flask-Login

    # Fetch user fresh for both GET and POST to ensure data is current
    try:
        user = current_app.auth_service.get_user_by_id(user_id)
        if not user:
             flash('User profile not found.', 'error')
             # Redirect to logout or login if user somehow doesn't exist
             return redirect(url_for('auth_web.logout'))
    except Exception as load_e:
         current_app.logger.error(f"Error loading user for profile page: {load_e}", exc_info=True)
         flash('Could not load profile information.', 'error')
         try: return redirect(url_for('core_web.index'))
         except: return redirect('/')


    if request.method == 'POST':
        try:
            # Get form data
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip()
            current_password = request.form.get('current_password') # Might be empty
            new_password = request.form.get('new_password') # Might be empty
            confirm_new_password = request.form.get('confirm_new_password') # Might be empty

            # --- Input Validation ---
            if not username or not email:
                 flash('Username and Email cannot be empty.', 'warning')
                 return render_template('profile.html', user=user, stats=_get_profile_stats(user_id)) # Re-render form

            # --- Password Change Logic ---
            password_changed = False
            if new_password: # User intends to change password
                if not current_password:
                    flash('Please enter your current password to set a new one.', 'warning')
                    return render_template('profile.html', user=user, stats=_get_profile_stats(user_id))
                if not user.check_password(current_password): # Assumes check_password method
                    flash('Incorrect current password.', 'error')
                    return render_template('profile.html', user=user, stats=_get_profile_stats(user_id))
                if new_password != confirm_new_password:
                    flash('New passwords do not match.', 'warning')
                    return render_template('profile.html', user=user, stats=_get_profile_stats(user_id))
                # Add password strength check
                if len(new_password) < 8:
                     flash('New password must be at least 8 characters long.', 'warning')
                     return render_template('profile.html', user=user, stats=_get_profile_stats(user_id))

                # Update password hash on user object (using model method preferably)
                if hasattr(user, 'set_password'): user.set_password(new_password)
                elif hasattr(user, 'update_password'): user.update_password(new_password)
                else: user.password_hash = generate_password_hash(new_password) # Fallback
                password_changed = True
                current_app.logger.info(f"User {user.username} is changing password.")


            # --- Username Change Logic ---
            username_changed = False
            if username != user.username:
                # Check if new username is taken by *another* user
                existing_user = current_app.auth_service.get_user_by_username(username)
                if existing_user and existing_user.id != user.id:
                    flash(f"Username '{username}' is already taken.", 'error')
                    return render_template('profile.html', user=user, stats=_get_profile_stats(user_id))
                user.username = username
                username_changed = True
                current_app.logger.info(f"User {user_id} changing username to {username}.")


            # --- Email Change Logic ---
            email_changed = False
            if email != user.email:
                # Add email format validation if needed
                # Check if new email is taken by *another* user
                existing_user = current_app.auth_service.get_user_by_email(email)
                if existing_user and existing_user.id != user.id:
                    flash(f"Email address '{email}' is already in use.", 'error')
                    return render_template('profile.html', user=user, stats=_get_profile_stats(user_id))
                user.email = email
                email_changed = True
                current_app.logger.info(f"User {user.username} changing email to {email}.")


            # --- Save Changes ---
            if password_changed or username_changed or email_changed:
                 current_app.auth_service.update_user(user) # Assumes service/repo save method
                 current_app.logger.info(f"User profile updated successfully for {user.username}")
                 flash('Profile updated successfully!', 'success')
                 # Update session if username changed
                 if username_changed:
                     session['username'] = user.username
            else:
                 flash('No changes were made to your profile.', 'info')

            # Redirect back to profile page after POST
            return redirect(url_for('auth_web.profile_page'))

        except Exception as e:
            current_app.logger.error(f"Error updating profile for user {user_id}: {str(e)}", exc_info=True)
            flash('An error occurred while updating your profile. Please try again.', 'error')
            # Re-render form with current user data on error
            return render_template('profile.html', user=user, stats=_get_profile_stats(user_id))

    # GET request - show profile page
    stats = _get_profile_stats(user_id) # Get stats for display
    return render_template('profile.html', user=user, stats=stats)


def _get_profile_stats(user_id):
    """Helper function to get statistics for the profile page."""
    stats = { 'dictionaries': 0, 'recordings': 0, 'augmented': 0 }
    try:
        # Use services if available, otherwise return defaults
        if hasattr(current_app, 'dictionary_service'):
             user_dicts = current_app.dictionary_service.get_user_dictionaries(user_id)
             stats['dictionaries'] = len(user_dicts) if user_dicts else 0
        if hasattr(current_app, 'recording_service') and hasattr(current_app.recording_service, 'get_user_recordings'):
             # This method needs to be implemented in the service
             user_recs = current_app.recording_service.get_user_recordings(user_id)
             stats['recordings'] = len(user_recs) if user_recs else 0
        if hasattr(current_app, 'augmentation_service') and hasattr(current_app.augmentation_service, 'get_user_augmentations'):
             # This method needs to be implemented in the service
             user_augs = current_app.augmentation_service.get_user_augmentations(user_id)
             stats['augmented'] = len(user_augs) if user_augs else 0
    except Exception as stat_e:
         current_app.logger.warning(f"Could not retrieve all stats for profile page (user {user_id}): {str(stat_e)}")
    return stats


def init_auth_web_routes(auth_service):
    """
    Initialize auth web routes with the auth service.
    
    Args:
        auth_service: Instance of AuthService
        
    Returns:
        Configured Blueprint
    """
    return auth_web_bp

