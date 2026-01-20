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
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database import ui_db

dashboard_bp = Blueprint('dashboard', __name__)
logger = logging.getLogger(__name__)

def get_scheduler_status():
    """Safely get scheduler status from backend"""
    try:
        from email_automation.scheduler.scheduler import SequenceScheduler
        from email_automation.config import Config
        from email_automation.db.database import DatabaseManager
        
        # Create temporary instances to check status
        config = Config()
        db_manager = DatabaseManager(config.database_url)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(db_manager.initialize())
            scheduler = SequenceScheduler(config, db_manager)
            status = loop.run_until_complete(scheduler.get_scheduler_status())
            loop.run_until_complete(db_manager.close())
            return status.get('scheduler_running', False)
        finally:
            loop.close()
            
    except Exception as e:
        logger.warning(f"Could not get scheduler status: {e}")
        return False

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
            
            # Get scheduler status
            scheduler_running = get_scheduler_status()
            metrics.scheduler_running = scheduler_running
            
            return render_template('dashboard.html', metrics=metrics)
            
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        flash(f"Error loading dashboard: {str(e)}", 'error')
        return render_template('dashboard.html', 
                             metrics=None, 
                             error="Failed to load dashboard data")