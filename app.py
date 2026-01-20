#!/usr/bin/env python3
"""
Admin UI for Microsoft 365 Email Automation System
Flask application providing operational control and monitoring
"""

import os
import sys
import logging
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_wtf.csrf import CSRFProtect
from datetime import datetime

# Add the parent directory to the path to import email_automation modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def create_app():
    """Application factory pattern for Flask app creation"""
    app = Flask(__name__)
    
    # Configuration
    # TODO: Set UI port via environment variable UI_PORT (default: 5000)
    # TODO: Enable authentication if exposed publicly
    # TODO: Set production secret key via UI_SECRET_KEY environment variable
    app.config['SECRET_KEY'] = os.getenv('UI_SECRET_KEY', 'dev-key-change-in-production')
    app.config['WTF_CSRF_ENABLED'] = True
    app.config['WTF_CSRF_TIME_LIMIT'] = None
    
    # Initialize CSRF protection
    csrf = CSRFProtect(app)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Register blueprints
    from routes.dashboard import dashboard_bp
    from routes.recipients import recipients_bp
    from routes.control import control_bp
    
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(recipients_bp)
    app.register_blueprint(control_bp)
    
    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('error.html', 
                             error_code=404, 
                             error_message="Page not found"), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return render_template('error.html', 
                             error_code=500, 
                             error_message="Internal server error"), 500
    
    # Template globals
    @app.template_global()
    def current_year():
        return datetime.now().year
    
    return app

def main():
    """Main entry point for the admin UI"""
    app = create_app()
    
    # Configuration from environment
    port = int(os.getenv('UI_PORT', 5000))
    debug = os.getenv('UI_DEBUG', 'false').lower() == 'true'
    
    print(f"Starting Email Automation Admin UI on port {port}")
    print("Access the dashboard at: http://localhost:{}/".format(port))
    
    # TODO: Configure for production deployment (HTTPS, authentication, etc.)
    app.run(host='0.0.0.0', port=port, debug=debug)

if __name__ == '__main__':
    main()