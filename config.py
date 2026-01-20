"""
Configuration management for Admin UI
Handles environment variables and deployment settings
"""

import os
import secrets
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class UIConfig:
    """Configuration class for the Admin UI"""
    
    def __init__(self):
        # Load environment variables
        self.load_config()
        
        # Validate configuration
        self.validate_config()
    
    def load_config(self):
        """Load configuration from environment variables"""
        
        # TODO: Set UI port via environment variable UI_PORT (default: 5000)
        self.port = int(os.getenv('UI_PORT', 5000))
        
        # TODO: Enable debug mode via UI_DEBUG (default: false for production)
        self.debug = os.getenv('UI_DEBUG', 'false').lower() == 'true'
        
        # TODO: Set production secret key via UI_SECRET_KEY environment variable
        # Generate a random secret key if not provided (for development only)
        self.secret_key = os.getenv('UI_SECRET_KEY')
        if not self.secret_key:
            if self.debug:
                self.secret_key = 'dev-key-change-in-production'
                logger.warning("Using development secret key. Set UI_SECRET_KEY for production!")
            else:
                # Generate a random secret key for production if not set
                self.secret_key = secrets.token_hex(32)
                logger.warning("Generated random secret key. Set UI_SECRET_KEY environment variable for persistence!")
        
        # Database configuration (reuse from main application)
        self.database_url = os.getenv('DATABASE_URL', 'sqlite:///email_automation.db')
        
        # Security settings
        # TODO: Enable authentication if exposed publicly
        self.require_auth = os.getenv('UI_REQUIRE_AUTH', 'false').lower() == 'true'
        self.auth_username = os.getenv('UI_AUTH_USERNAME', 'admin')
        self.auth_password = os.getenv('UI_AUTH_PASSWORD', '')
        
        # TODO: Configure HTTPS settings for production
        self.use_https = os.getenv('UI_USE_HTTPS', 'false').lower() == 'true'
        self.ssl_cert_path = os.getenv('UI_SSL_CERT_PATH', '')
        self.ssl_key_path = os.getenv('UI_SSL_KEY_PATH', '')
        
        # Session configuration
        self.session_timeout = int(os.getenv('UI_SESSION_TIMEOUT', 3600))  # 1 hour default
        
        # Rate limiting
        self.rate_limit_enabled = os.getenv('UI_RATE_LIMIT_ENABLED', 'true').lower() == 'true'
        self.rate_limit_per_minute = int(os.getenv('UI_RATE_LIMIT_PER_MINUTE', 60))
        
        # Logging configuration
        self.log_level = os.getenv('UI_LOG_LEVEL', 'INFO').upper()
        self.log_file = os.getenv('UI_LOG_FILE', 'admin_ui.log')
        
        # CSRF protection
        self.csrf_enabled = os.getenv('UI_CSRF_ENABLED', 'true').lower() == 'true'
        self.csrf_time_limit = int(os.getenv('UI_CSRF_TIME_LIMIT', 3600))  # 1 hour
        
        # Host configuration
        # TODO: Set allowed hosts for production deployment
        self.host = os.getenv('UI_HOST', '0.0.0.0')  # Bind to all interfaces by default
        self.allowed_hosts = os.getenv('UI_ALLOWED_HOSTS', '').split(',') if os.getenv('UI_ALLOWED_HOSTS') else []
        
        # Reverse proxy configuration
        self.behind_proxy = os.getenv('UI_BEHIND_PROXY', 'false').lower() == 'true'
        self.proxy_fix_enabled = self.behind_proxy
    
    def validate_config(self):
        """Validate configuration settings"""
        errors = []
        
        # Validate port
        if not (1 <= self.port <= 65535):
            errors.append(f"Invalid port number: {self.port}")
        
        # Validate secret key
        if len(self.secret_key) < 16:
            errors.append("Secret key is too short (minimum 16 characters)")
        
        # Validate authentication settings
        if self.require_auth and not self.auth_password:
            errors.append("Authentication enabled but no password set (UI_AUTH_PASSWORD)")
        
        # Validate HTTPS settings
        if self.use_https:
            if not self.ssl_cert_path or not os.path.exists(self.ssl_cert_path):
                errors.append("HTTPS enabled but SSL certificate not found")
            if not self.ssl_key_path or not os.path.exists(self.ssl_key_path):
                errors.append("HTTPS enabled but SSL key not found")
        
        # Validate database URL
        if not self.database_url:
            errors.append("Database URL not configured")
        
        # Log validation errors
        if errors:
            for error in errors:
                logger.error(f"Configuration error: {error}")
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")
        
        logger.info("Configuration validation passed")
    
    def get_flask_config(self) -> dict:
        """Get Flask configuration dictionary"""
        return {
            'SECRET_KEY': self.secret_key,
            'WTF_CSRF_ENABLED': self.csrf_enabled,
            'WTF_CSRF_TIME_LIMIT': self.csrf_time_limit,
            'PERMANENT_SESSION_LIFETIME': self.session_timeout,
            'SESSION_COOKIE_SECURE': self.use_https,
            'SESSION_COOKIE_HTTPONLY': True,
            'SESSION_COOKIE_SAMESITE': 'Lax',
        }
    
    def get_ssl_context(self):
        """Get SSL context for HTTPS"""
        if self.use_https and self.ssl_cert_path and self.ssl_key_path:
            return (self.ssl_cert_path, self.ssl_key_path)
        return None
    
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return not self.debug
    
    def print_startup_info(self):
        """Print startup information"""
        protocol = "https" if self.use_https else "http"
        print(f"\n{'='*60}")
        print(f"EMAIL AUTOMATION ADMIN UI")
        print(f"{'='*60}")
        print(f"Server: {protocol}://{self.host}:{self.port}")
        print(f"Debug Mode: {'Enabled' if self.debug else 'Disabled'}")
        print(f"Authentication: {'Required' if self.require_auth else 'Disabled'}")
        print(f"CSRF Protection: {'Enabled' if self.csrf_enabled else 'Disabled'}")
        print(f"Rate Limiting: {'Enabled' if self.rate_limit_enabled else 'Disabled'}")
        print(f"Database: {self.database_url}")
        
        if self.debug:
            print(f"\n⚠️  DEVELOPMENT MODE - NOT FOR PRODUCTION USE")
        
        if not self.require_auth:
            print(f"\n⚠️  NO AUTHENTICATION - INTERNAL USE ONLY")
        
        print(f"{'='*60}\n")

# Global configuration instance
ui_config = UIConfig()

def get_config() -> UIConfig:
    """Get the global configuration instance"""
    return ui_config