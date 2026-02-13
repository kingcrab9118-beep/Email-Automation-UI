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


@recipients_bp.route('/import-csv', methods=['POST'])
def import_csv():
    """Import recipients from CSV file"""
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
        
        # Check if file was uploaded
        if 'csv_file' not in request.files:
            flash("No file uploaded", 'error')
            return redirect(url_for('recipients.list'))
        
        file = request.files['csv_file']
        
        if file.filename == '':
            flash("No file selected", 'error')
            return redirect(url_for('recipients.list'))
        
        if not file.filename.endswith('.csv'):
            flash("Please upload a CSV file", 'error')
            return redirect(url_for('recipients.list'))
        
        # Read and process CSV
        import csv
        import io
        from datetime import datetime
        
        # Decode file content
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.DictReader(stream)
        
        results = {
            'total': 0,
            'successful': 0,
            'failed': 0,
            'errors': []
        }
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Initialize database if needed
        if not ui_db.db_manager:
            loop.run_until_complete(ui_db.initialize())
        
        for row in csv_reader:
            results['total'] += 1
            
            try:
                # Validate required fields
                required_fields = ['first_name', 'company', 'email']
                missing_fields = [field for field in required_fields if field not in row or not row[field].strip()]
                
                if missing_fields:
                    results['failed'] += 1
                    results['errors'].append({
                        'row': results['total'],
                        'email': row.get('email', 'unknown'),
                        'error': f'Missing required fields: {", ".join(missing_fields)}'
                    })
                    continue
                
                # Prepare recipient data
                recipient_data = {
                    'first_name': row['first_name'].strip(),
                    'company': row['company'].strip(),
                    'role': row.get('role', '').strip(),
                    'email': row['email'].strip().lower()
                }
                
                # Handle initial_mail_date if present
                if 'initial_mail_date' in row and row['initial_mail_date'].strip():
                    try:
                        # Try to parse the date
                        date_str = row['initial_mail_date'].strip()
                        # Support multiple date formats
                        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y']:
                            try:
                                parsed_date = datetime.strptime(date_str, fmt)
                                # If only date (no time), set default time to 09:00:00
                                if fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y']:
                                    parsed_date = parsed_date.replace(hour=9, minute=0, second=0)
                                recipient_data['initial_mail_date'] = parsed_date.strftime('%Y-%m-%d %H:%M:%S')
                                break
                            except ValueError:
                                continue
                    except Exception as e:
                        logger.warning(f"Could not parse initial_mail_date '{row['initial_mail_date']}' for {recipient_data['email']}: {e}")
                
                # Validate form data
                validator = FormValidator(recipient_data)
                
                if not validator.validate_recipient_form():
                    results['failed'] += 1
                    results['errors'].append({
                        'row': results['total'],
                        'email': recipient_data['email'],
                        'error': '; '.join(validator.get_errors())
                    })
                    continue
                
                # Add recipient
                success, message = loop.run_until_complete(ui_db.add_recipient(validator.get_cleaned_data()))
                
                if success:
                    results['successful'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append({
                        'row': results['total'],
                        'email': recipient_data['email'],
                        'error': message
                    })
            
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'row': results['total'],
                    'email': row.get('email', 'unknown'),
                    'error': str(e)
                })
                logger.error(f"Error processing CSV row {results['total']}: {e}")
        
        # Show results
        if results['successful'] > 0:
            flash(f"Successfully imported {results['successful']} out of {results['total']} recipients", 'success')
        
        if results['failed'] > 0:
            error_summary = f"Failed to import {results['failed']} recipients. "
            if len(results['errors']) <= 5:
                for error in results['errors']:
                    flash(f"Row {error['row']} ({error['email']}): {error['error']}", 'error')
            else:
                flash(error_summary + "Check logs for details.", 'error')
                for error in results['errors'][:5]:
                    logger.error(f"CSV import error - Row {error['row']} ({error['email']}): {error['error']}")
        
        SecurityMiddleware.log_security_event("CSV_IMPORT", f"Total: {results['total']}, Success: {results['successful']}, Failed: {results['failed']}")
        
        return redirect(url_for('recipients.list'))
        
    except Exception as e:
        logger.error(f"Error importing CSV: {e}")
        flash(f"Error importing CSV file: {str(e)}", 'error')
        SecurityMiddleware.log_security_event("CSV_IMPORT_ERROR", str(e))
        return redirect(url_for('recipients.list'))
    
    finally:
        if loop:
            loop.close()


@recipients_bp.route('/bulk-delete', methods=['POST'])
def bulk_delete():
    """Bulk delete recipients"""
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
        
        # Get recipient IDs from form
        recipient_ids = request.form.getlist('recipient_ids')
        
        if not recipient_ids:
            flash("No recipients selected", 'error')
            return redirect(url_for('recipients.list'))
        
        # Convert to integers
        recipient_ids = [int(id) for id in recipient_ids]
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Initialize database if needed
        if not ui_db.db_manager:
            loop.run_until_complete(ui_db.initialize())
        
        # Delete recipients
        success_count = 0
        failed_count = 0
        
        for recipient_id in recipient_ids:
            try:
                success, message = loop.run_until_complete(ui_db.delete_recipient(recipient_id))
                if success:
                    success_count += 1
                else:
                    failed_count += 1
                    logger.error(f"Failed to delete recipient {recipient_id}: {message}")
            except Exception as e:
                failed_count += 1
                logger.error(f"Error deleting recipient {recipient_id}: {e}")
        
        # Show results
        if success_count > 0:
            flash(f"Successfully deleted {success_count} recipient(s)", 'success')
            SecurityMiddleware.log_security_event("BULK_DELETE", f"Deleted {success_count} recipients")
        
        if failed_count > 0:
            flash(f"Failed to delete {failed_count} recipient(s)", 'error')
        
        return redirect(url_for('recipients.list'))
        
    except Exception as e:
        logger.error(f"Error in bulk delete: {e}")
        flash(f"Error deleting recipients: {str(e)}", 'error')
        SecurityMiddleware.log_security_event("BULK_DELETE_ERROR", str(e))
        return redirect(url_for('recipients.list'))
    
    finally:
        if loop:
            loop.close()


@recipients_bp.route('/export-csv', methods=['GET'])
def export_csv():
    """Export all recipients to CSV file"""
    # Apply rate limit
    identifier = request.remote_addr
    if not rate_limiter.is_allowed(identifier, max_requests=1000, window_seconds=300):
        SecurityMiddleware.log_security_event("RATE_LIMIT_EXCEEDED", f"IP: {identifier}")
        flash("Too many requests. Please try again later.", 'error')
        return redirect(url_for('recipients.list'))
    
    loop = None
    try:
        import csv
        import io
        from flask import make_response
        from datetime import datetime
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Initialize database if needed
        if not ui_db.db_manager:
            loop.run_until_complete(ui_db.initialize())
        
        # Get all recipients with status
        query = """
        SELECT 
            r.id, r.first_name, r.company, r.role, r.email, r.status, r.initial_mail_date,
            MAX(CASE WHEN es.step = 1 AND es.sent_at IS NOT NULL THEN 1 ELSE 0 END) as first_mail_sent,
            MAX(CASE WHEN es.step = 2 AND es.sent_at IS NOT NULL THEN 1 ELSE 0 END) as reminder1_sent,
            MAX(CASE WHEN es.step = 3 AND es.sent_at IS NOT NULL THEN 1 ELSE 0 END) as reminder2_sent,
            MAX(CASE WHEN es.replied = 1 THEN 1 ELSE 0 END) as has_replied,
            MAX(es.sent_at) as last_activity,
            MIN(CASE WHEN es.sent_at IS NULL AND es.replied = 0 THEN es.scheduled_at ELSE NULL END) as next_activity
        FROM recipients r
        LEFT JOIN email_sequence es ON r.id = es.recipient_id
        GROUP BY r.id, r.first_name, r.company, r.role, r.email, r.status, r.initial_mail_date
        ORDER BY r.id ASC
        """
        
        results = loop.run_until_complete(ui_db.db_manager.execute_query(query))
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'ID', 'First Name', 'Company', 'Role', 'Email', 'Status', 
            'Initial Mail Date', 'First Mail Sent', 'Reminder 1 Sent', 
            'Reminder 2 Sent', 'Has Replied', 'Last Activity', 'Next Activity'
        ])
        
        # Write data
        for row in results:
            writer.writerow([
                row[0],  # id
                row[1],  # first_name
                row[2],  # company
                row[3],  # role
                row[4],  # email
                row[5],  # status
                row[6] if row[6] else '',  # initial_mail_date
                'Yes' if row[7] else 'No',  # first_mail_sent
                'Yes' if row[8] else 'No',  # reminder1_sent
                'Yes' if row[9] else 'No',  # reminder2_sent
                'Yes' if row[10] else 'No',  # has_replied
                row[11] if row[11] else '',  # last_activity
                row[12] if row[12] else ''   # next_activity
            ])
        
        # Create response
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=recipients_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        SecurityMiddleware.log_security_event("CSV_EXPORT", f"Exported {len(results)} recipients")
        
        return response
        
    except Exception as e:
        logger.error(f"Error exporting CSV: {e}")
        flash(f"Error exporting CSV file: {str(e)}", 'error')
        SecurityMiddleware.log_security_event("CSV_EXPORT_ERROR", str(e))
        return redirect(url_for('recipients.list'))
    
    finally:
        if loop:
            loop.close()
