"""
Control routes for Email Automation Admin UI
Provides manual automation controls
"""

import asyncio
import logging
import sys
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_wtf.csrf import validate_csrf

# Add parent directory to path for email_automation imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

control_bp = Blueprint('control', __name__, url_prefix='/control')
logger = logging.getLogger(__name__)

# Global variables to hold backend instances
_scheduler = None
_reply_tracker = None
_app_instance = None

def get_backend_instances():
    """Get or create backend instances for control operations"""
    global _scheduler, _reply_tracker, _app_instance
    
    try:
        if not _app_instance:
            from email_automation.main import EmailAutomationApp
            from email_automation.config import Config
            
            config = Config()
            _app_instance = EmailAutomationApp(config)
            
            # Initialize in async context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_app_instance.initialize())
                _scheduler = _app_instance.scheduler
                _reply_tracker = _app_instance.reply_tracker
            finally:
                loop.close()
        
        return _scheduler, _reply_tracker, _app_instance
        
    except Exception as e:
        logger.error(f"Error getting backend instances: {e}")
        return None, None, None

@control_bp.route('/')
def panel():
    """Control panel page"""
    try:
        # Get current system status
        scheduler_status = None
        reply_tracker_status = None
        
        try:
            scheduler, reply_tracker, app = get_backend_instances()
            
            if scheduler:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    scheduler_status = loop.run_until_complete(scheduler.get_scheduler_status())
                finally:
                    loop.close()
            
            if reply_tracker:
                reply_tracker_status = reply_tracker.get_monitoring_status()
                
        except Exception as e:
            logger.warning(f"Could not get system status: {e}")
        
        return render_template('control.html', 
                             scheduler_status=scheduler_status,
                             reply_tracker_status=reply_tracker_status)
        
    except Exception as e:
        logger.error(f"Error loading control panel: {e}")
        flash(f"Error loading control panel: {str(e)}", 'error')
        return render_template('control.html', 
                             scheduler_status=None,
                             reply_tracker_status=None)

@control_bp.route('/start-scheduler', methods=['POST'])
def start_scheduler():
    """Start the email scheduler"""
    try:
        validate_csrf(request.form.get('csrf_token'))
        
        scheduler, _, _ = get_backend_instances()
        
        if not scheduler:
            flash('Scheduler not available. Check system configuration.', 'error')
            return redirect(url_for('control.panel'))
        
        # Start the scheduler
        scheduler.start()
        flash('Email scheduler started successfully.', 'success')
        logger.info("Scheduler started via admin UI")
        
    except Exception as e:
        logger.error(f"Error starting scheduler: {e}")
        flash(f'Error starting scheduler: {str(e)}', 'error')
    
    return redirect(url_for('control.panel'))

@control_bp.route('/stop-scheduler', methods=['POST'])
def stop_scheduler():
    """Stop the email scheduler"""
    try:
        validate_csrf(request.form.get('csrf_token'))
        
        scheduler, _, _ = get_backend_instances()
        
        if not scheduler:
            flash('Scheduler not available. Check system configuration.', 'error')
            return redirect(url_for('control.panel'))
        
        # Stop the scheduler
        scheduler.shutdown()
        flash('Email scheduler stopped successfully.', 'success')
        logger.info("Scheduler stopped via admin UI")
        
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}")
        flash(f'Error stopping scheduler: {str(e)}', 'error')
    
    return redirect(url_for('control.panel'))

@control_bp.route('/run-email-cycle', methods=['POST'])
def run_email_cycle():
    """Trigger immediate email sending cycle"""
    try:
        validate_csrf(request.form.get('csrf_token'))
        
        scheduler, _, _ = get_backend_instances()
        
        if not scheduler:
            flash('Scheduler not available. Check system configuration.', 'error')
            return redirect(url_for('control.panel'))
        
        # Run email processing cycle
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(scheduler.process_due_emails())
            flash('Email sending cycle completed successfully.', 'success')
            logger.info("Manual email cycle triggered via admin UI")
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"Error running email cycle: {e}")
        flash(f'Error running email cycle: {str(e)}', 'error')
    
    return redirect(url_for('control.panel'))

@control_bp.route('/run-reply-check', methods=['POST'])
def run_reply_check():
    """Trigger immediate reply checking"""
    try:
        validate_csrf(request.form.get('csrf_token'))
        
        _, reply_tracker, _ = get_backend_instances()
        
        if not reply_tracker:
            flash('Reply tracker not available. Check system configuration.', 'error')
            return redirect(url_for('control.panel'))
        
        # Run reply checking
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(reply_tracker.scan_inbox())
            flash('Reply checking completed successfully.', 'success')
            logger.info("Manual reply check triggered via admin UI")
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"Error running reply check: {e}")
        flash(f'Error running reply check: {str(e)}', 'error')
    
    return redirect(url_for('control.panel'))

@control_bp.route('/system-status')
def system_status():
    """Get current system status as JSON"""
    try:
        scheduler, reply_tracker, _ = get_backend_instances()
        
        status = {
            'scheduler_available': scheduler is not None,
            'reply_tracker_available': reply_tracker is not None,
            'scheduler_running': False,
            'reply_monitoring_active': False
        }
        
        if scheduler:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                scheduler_status = loop.run_until_complete(scheduler.get_scheduler_status())
                status['scheduler_running'] = scheduler_status.get('scheduler_running', False)
                status['pending_emails'] = scheduler_status.get('pending_emails', 0)
            finally:
                loop.close()
        
        if reply_tracker:
            reply_status = reply_tracker.get_monitoring_status()
            status['reply_monitoring_active'] = reply_status.get('monitoring_active', False)
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return jsonify({'error': str(e)}), 500