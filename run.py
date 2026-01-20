#!/usr/bin/env python3
"""
Production-ready entry point for Email Automation Admin UI
Handles configuration, logging, and deployment setup
"""

import os
import sys
import logging
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from config import ui_config

def setup_logging():
    """Configure logging for the application"""
    log_level = getattr(logging, ui_config.log_level, logging.INFO)
    
    # Create logs directory if it doesn't exist
    log_file_path = Path(ui_config.log_file)
    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(ui_config.log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set specific log levels for noisy libraries
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

def validate_environment():
    """Validate environment and dependencies"""
    errors = []
    
    # Check Python version
    if sys.version_info < (3, 8):
        errors.append("Python 3.8 or higher is required")
    
    # Check database file exists (for SQLite)
    if ui_config.database_url.startswith('sqlite:'):
        db_path = ui_config.database_url.replace('sqlite:///', '')
        if not os.path.exists(db_path):
            logging.warning(f"Database file not found: {db_path}")
            logging.info("Database will be created when the main email automation system runs")
    
    # Check SSL files if HTTPS is enabled
    if ui_config.use_https:
        if not os.path.exists(ui_config.ssl_cert_path):
            errors.append(f"SSL certificate not found: {ui_config.ssl_cert_path}")
        if not os.path.exists(ui_config.ssl_key_path):
            errors.append(f"SSL key not found: {ui_config.ssl_key_path}")
    
    if errors:
        for error in errors:
            logging.error(f"Environment validation error: {error}")
        sys.exit(1)
    
    logging.info("Environment validation passed")

def main():
    """Main entry point"""
    try:
        # Setup logging first
        setup_logging()
        
        # Validate environment
        validate_environment()
        
        # Print startup information
        ui_config.print_startup_info()
        
        # Create Flask application
        app = create_app()
        
        # Configure Flask with our settings
        app.config.update(ui_config.get_flask_config())
        
        # Setup SSL context if needed
        ssl_context = ui_config.get_ssl_context()
        
        # Production deployment warnings
        if ui_config.is_production():
            if not ui_config.require_auth:
                logging.warning("⚠️  Authentication is disabled in production mode!")
            if not ui_config.use_https:
                logging.warning("⚠️  HTTPS is disabled in production mode!")
        
        # Start the server
        logging.info(f"Starting Email Automation Admin UI on {ui_config.host}:{ui_config.port}")
        
        app.run(
            host=ui_config.host,
            port=ui_config.port,
            debug=ui_config.debug,
            ssl_context=ssl_context,
            threaded=True
        )
        
    except KeyboardInterrupt:
        logging.info("Server stopped by user")
    except Exception as e:
        logging.error(f"Failed to start server: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()