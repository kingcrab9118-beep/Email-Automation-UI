"""
Dashboard route for Email Automation Admin UI
Displays system overview and metrics
"""

import asyncio
import logging
import sys
import os
from flask import Blueprint, render_template, current_app, flash
from datetime import datetime

# Add parent directory to path for email_automation imports
email_automation_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if email_automation_path not in sys.path:
    sys.path.insert(0, email_automation_path)

# Also add email_automation directory itself
email_automation_dir = os.path.join(email_automation_path, 'email_automation')
if email_automation_dir not in sys.path:
    sys.path.insert(0, email_automation_dir)

from database import ui_db

dashboard_bp = Blueprint('dashboard', __name__)
logger = logging.getLogger(__name__)

@dashboard_bp.route('/')
def index():
    """Dashboard overview page"""
    try:
        # Run async operations in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Initialize database if not already done
            if not ui_db.db_manager:
                loop.run_until_complete(ui_db.initialize())
            
            # Get dashboard metrics from database
            metrics = loop.run_until_complete(ui_db.get_dashboard_metrics())
            
            return render_template('dashboard.html', metrics=metrics)
            
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        flash(f"Error loading dashboard: {str(e)}", 'error')
        return render_template('dashboard.html', 
                             metrics=None, 
                             error="Failed to load dashboard data")