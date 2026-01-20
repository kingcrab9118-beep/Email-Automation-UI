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
from security import FormValidator, secure_form_handler, rate_limit, SecurityMiddleware

recipients_bp = Blueprint('recipients', __name__, url_prefix='/recipients')
logger = logging.getLogger(__name__)

class WTFAddRecipientForm(FlaskForm):
    """WTForms class for CSRF protection"""
    first_name = StringField('First Name', validators=[DataRequired()])
    company = StringField('Company', validators=[DataRequired()])
    role = StringField('Role')
    email = StringField('Email', validators=[DataRequired(), Email()])

@recipients_bp.route('/')
def list():
    """Recipients overview page with status table"""
    try:
        # Run async function in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Initialize database if needed
            if not ui_db.db_manager:
                loop.run_until_complete(ui_db.initialize())
            
            # Get recipients with status
            recipients = loop.run_until_complete(ui_db.get_recipients_with_status())
            
            return render_template('recipients.html', recipients=recipients)
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Error loading recipients: {e}")
        flash(f"Error loading recipients: {str(e)}", 'error')
        return render_template('recipients.html', recipients=[], error=str(e))

@recipients_bp.route('/new', methods=['GET', 'POST'])
@rate_limit(max_requests=5, window_seconds=300)  # 5 submissions per 5 minutes
@secure_form_handler(FormValidator)
def add_form():
    """Add recipient form page with security validation"""
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
@rate_limit(max_requests=5, window_seconds=300)
def add_submit():
    """Handle recipient addition form submission (alternative endpoint)"""
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