"""
Recipients routes for Email Automation Admin UI
Handles recipient display and management with security measures
"""

import asyncio
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_wtf import FlaskForm
from flask_wtf.csrf import validate_csrf
from wtforms import StringField, validators
from wtforms.validators import DataRequired, Email

from database import ui_db, AddRecipientForm
from security import FormValidator, secure_form_handler, rate_limit, SecurityMiddleware, rate_limiter

recipients_bp = Blueprint('recipients', __name__, url_prefix='/recipients')
logger = logging.getLogger(__name__)

class WTFAddRecipientForm(FlaskForm):
    """WTForms class for CSRF protection"""
    first_name = StringField('First Name', validators=[DataRequired()])
    company = StringField('Company', validators=[DataRequired()])
    role = StringField('Role')
    email = StringField('Email', validators=[DataRequired(), Email()])
    initial_mail_date = StringField('Initial Email Send Date')

@recipients_bp.route('/')
def list():
    """Recipients overview page with status table"""
    try:
        # Get page number and sort parameters from query string
        page = request.args.get('page', 1, type=int)
        sort_by = request.args.get('sort_by', 'id', type=str)
        sort_order = request.args.get('sort_order', 'asc', type=str)
        per_page = 20
        
        # Run async function in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Initialize database if needed
            if not ui_db.db_manager:
                loop.run_until_complete(ui_db.initialize())
            
            # Get recipients with status (paginated and sorted)
            recipients, total_count = loop.run_until_complete(
                ui_db.get_recipients_with_status(page=page, per_page=per_page, sort_by=sort_by, sort_order=sort_order)
            )
            
            # Calculate pagination info
            total_pages = (total_count + per_page - 1) // per_page  # Ceiling division
            has_prev = page > 1
            has_next = page < total_pages
            
            return render_template(
                'recipients.html', 
                recipients=recipients,
                page=page,
                per_page=per_page,
                total_count=total_count,
                total_pages=total_pages,
                has_prev=has_prev,
                has_next=has_next,
                sort_by=sort_by,
                sort_order=sort_order
            )
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Error loading recipients: {e}")
        flash(f"Error loading recipients: {str(e)}", 'error')
        return render_template('recipients.html', recipients=[], error=str(e))

@recipients_bp.route('/new', methods=['GET', 'POST'])
@secure_form_handler(FormValidator)
def add_form():
    """Add recipient form page with security validation"""
    # Apply rate limit only to POST requests
    if request.method == 'POST':
        identifier = request.remote_addr
        if not rate_limiter.is_allowed(identifier, max_requests=1000, window_seconds=300):
            SecurityMiddleware.log_security_event("RATE_LIMIT_EXCEEDED", f"IP: {identifier}")
            flash("Too many requests. Please try again later.", 'error')
            return render_template('add_recipient.html', form=WTFAddRecipientForm())
    
    form = WTFAddRecipientForm()
    
    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                # Use cleaned data from security middleware
                if hasattr(request, 'cleaned_data'):
                    recipient_data = request.cleaned_data
                else:
                    # Fallback to form data with manual validation
                    validator = FormValidator(request.form.to_dict())
                    if not validator.validate_recipient_form():
                        for error in validator.get_errors():
                            flash(error, 'error')
                        return render_template('add_recipient.html', form=form)
                    recipient_data = validator.get_cleaned_data()
                
                # Run async function in event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    # Initialize database if needed
                    if not ui_db.db_manager:
                        loop.run_until_complete(ui_db.initialize())
                    
                    # Add recipient
                    success, message = loop.run_until_complete(ui_db.add_recipient(recipient_data))
                    
                    if success:
                        flash(message, 'success')
                        SecurityMiddleware.log_security_event("RECIPIENT_ADDED", f"Email: {recipient_data['email']}")
                        return redirect(url_for('recipients.list'))
                    else:
                        flash(message, 'error')
                        
                finally:
                    loop.close()
                    
            except Exception as e:
                logger.error(f"Error adding recipient: {e}")
                flash(f"Error adding recipient: {str(e)}", 'error')
                SecurityMiddleware.log_security_event("RECIPIENT_ADD_ERROR", str(e))
        else:
            # Form validation failed
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"{field}: {error}", 'error')
    
    return render_template('add_recipient.html', form=form)

@recipients_bp.route('/add', methods=['POST'])
def add_submit():
    """Handle recipient addition form submission (alternative endpoint)"""
    # Apply rate limit
    identifier = request.remote_addr
    if not rate_limiter.is_allowed(identifier, max_requests=1000, window_seconds=300):
        SecurityMiddleware.log_security_event("RATE_LIMIT_EXCEEDED", f"IP: {identifier}")
        flash("Too many requests. Please try again later.", 'error')
        return redirect(url_for('recipients.add_form'))
    
    try:
        # Validate CSRF token
        validate_csrf(request.form.get('csrf_token'))
        
        # Validate form data
        validator = FormValidator(request.form.to_dict())
        
        if not validator.validate_recipient_form():
            for error in validator.get_errors():
                flash(error, 'error')
            return redirect(url_for('recipients.add_form'))
        
        # Run async function in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Initialize database if needed
            if not ui_db.db_manager:
                loop.run_until_complete(ui_db.initialize())
            
            # Add recipient using cleaned data
            success, message = loop.run_until_complete(ui_db.add_recipient(validator.get_cleaned_data()))
            
            if success:
                flash(message, 'success')
                SecurityMiddleware.log_security_event("RECIPIENT_ADDED", f"Email: {validator.get_cleaned_data()['email']}")
                return redirect(url_for('recipients.list'))
            else:
                flash(message, 'error')
                return redirect(url_for('recipients.add_form'))
                
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Error in add_submit: {e}")
        flash(f"Error adding recipient: {str(e)}", 'error')
        SecurityMiddleware.log_security_event("RECIPIENT_ADD_ERROR", str(e))
        return redirect(url_for('recipients.add_form'))


@recipients_bp.route('/<int:recipient_id>/edit', methods=['GET', 'POST'])
def edit_form(recipient_id):
    """Edit recipient form page"""
    # Apply rate limit only to POST requests
    if request.method == 'POST':
        identifier = request.remote_addr
        if not rate_limiter.is_allowed(identifier, max_requests=1000, window_seconds=300):
            SecurityMiddleware.log_security_event("RATE_LIMIT_EXCEEDED", f"IP: {identifier}")
            flash("Too many requests. Please try again later.", 'error')
            return redirect(url_for('recipients.list'))
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Initialize database if needed
            if not ui_db.db_manager:
                loop.run_until_complete(ui_db.initialize())
            
            # Get recipient by ID
            recipient = loop.run_until_complete(ui_db.get_recipient_by_id(recipient_id))
            
            if not recipient:
                flash(f"Recipient with ID {recipient_id} not found", 'error')
                return redirect(url_for('recipients.list'))
            
            if request.method == 'POST':
                # Validate CSRF token
                validate_csrf(request.form.get('csrf_token'))
                
                # Validate form data
                validator = FormValidator(request.form.to_dict())
                
                if not validator.validate_recipient_form():
                    for error in validator.get_errors():
                        flash(error, 'error')
                    return render_template('edit_recipient.html', recipient=recipient)
                
                # Update recipient
                success, message = loop.run_until_complete(
                    ui_db.update_recipient(recipient_id, validator.get_cleaned_data())
                )
                
                if success:
                    flash(message, 'success')
                    SecurityMiddleware.log_security_event("RECIPIENT_UPDATED", f"ID: {recipient_id}")
                    return redirect(url_for('recipients.list'))
                else:
                    flash(message, 'error')
            
            return render_template('edit_recipient.html', recipient=recipient)
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Error editing recipient: {e}")
        flash(f"Error editing recipient: {str(e)}", 'error')
        return redirect(url_for('recipients.list'))

@recipients_bp.route('/<int:recipient_id>/edit', methods=['POST'])
def edit(recipient_id):
    """Handle recipient edit form submission"""
    return edit_form(recipient_id)

@recipients_bp.route('/<int:recipient_id>/delete', methods=['POST'])
def delete(recipient_id):
    """Delete recipient"""
    # Apply rate limit
    identifier = request.remote_addr
    if not rate_limiter.is_allowed(identifier, max_requests=1000, window_seconds=300):
        SecurityMiddleware.log_security_event("RATE_LIMIT_EXCEEDED", f"IP: {identifier}")
        flash("Too many requests. Please try again later.", 'error')
        return redirect(url_for('recipients.list'))
    
    loop = None
    try:
        # Validate CSRF token
        validate_csrf(request.form.get('csrf_token'))
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Initialize database if needed
        if not ui_db.db_manager:
            loop.run_until_complete(ui_db.initialize())
        
        # Delete recipient with retry logic
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                success, message = loop.run_until_complete(ui_db.delete_recipient(recipient_id))
                
                if success:
                    flash(message, 'success')
                    SecurityMiddleware.log_security_event("RECIPIENT_DELETED", f"ID: {recipient_id}")
                else:
                    flash(message, 'error')
                
                return redirect(url_for('recipients.list'))
                
            except Exception as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    logger.warning(f"Database locked, retrying... (attempt {attempt + 1}/{max_retries})")
                    loop.run_until_complete(asyncio.sleep(retry_delay))
                    retry_delay *= 2  # Exponential backoff
                else:
                    raise
            
    except Exception as e:
        logger.error(f"Error deleting recipient: {e}")
        flash(f"Error deleting recipient: {str(e)}", 'error')
        SecurityMiddleware.log_security_event("RECIPIENT_DELETE_ERROR", str(e))
        return redirect(url_for('recipients.list'))
    
    finally:
        if loop:
            loop.close()
