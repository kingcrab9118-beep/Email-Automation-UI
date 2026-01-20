"""
Tests for configuration management
"""

import pytest
import os
import tempfile
from unittest.mock import patch

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import UIConfig

class TestUIConfig:
    """Test cases for UIConfig class"""
    
    def test_default_configuration(self):
        """Test default configuration values"""
        with patch.dict(os.environ, {}, clear=True):
            config = UIConfig()
            
            assert config.port == 5000
            assert config.debug is False
            assert config.host == '0.0.0.0'
            assert config.csrf_enabled is True
            assert config.rate_limit_enabled is True
    
    def test_environment_variable_override(self):
        """Test configuration override via environment variables"""
        env_vars = {
            'UI_PORT': '8080',
            'UI_DEBUG': 'true',
            'UI_SECRET_KEY': 'test-secret-key',
            'UI_HOST': '127.0.0.1',
            'UI_CSRF_ENABLED': 'false'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = UIConfig()
            
            assert config.port == 8080
            assert config.debug is True
            assert config.secret_key == 'test-secret-key'
            assert config.host == '127.0.0.1'
            assert config.csrf_enabled is False
    
    def test_boolean_environment_variables(self):
        """Test boolean environment variable parsing"""
        test_cases = [
            ('true', True),
            ('True', True),
            ('TRUE', True),
            ('false', False),
            ('False', False),
            ('FALSE', False),
            ('', False),
            ('invalid', False)
        ]
        
        for env_value, expected in test_cases:
            with patch.dict(os.environ, {'UI_DEBUG': env_value}, clear=True):
                config = UIConfig()
                assert config.debug == expected, f"UI_DEBUG={env_value} should result in {expected}"
    
    def test_integer_environment_variables(self):
        """Test integer environment variable parsing"""
        with patch.dict(os.environ, {
            'UI_PORT': '3000',
            'UI_SESSION_TIMEOUT': '7200',
            'UI_RATE_LIMIT_PER_MINUTE': '120'
        }, clear=True):
            config = UIConfig()
            
            assert config.port == 3000
            assert config.session_timeout == 7200
            assert config.rate_limit_per_minute == 120
    
    def test_secret_key_generation(self):
        """Test secret key generation when not provided"""
        with patch.dict(os.environ, {'UI_DEBUG': 'true'}, clear=True):
            config = UIConfig()
            
            # In debug mode, should use development key
            assert config.secret_key == 'dev-key-change-in-production'
        
        with patch.dict(os.environ, {'UI_DEBUG': 'false'}, clear=True):
            config = UIConfig()
            
            # In production mode without key, should generate random key
            assert len(config.secret_key) >= 32
            assert config.secret_key != 'dev-key-change-in-production'
    
    def test_validation_invalid_port(self):
        """Test validation with invalid port number"""
        with patch.dict(os.environ, {'UI_PORT': '99999'}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                UIConfig()
            
            assert 'Invalid port number' in str(exc_info.value)
    
    def test_validation_short_secret_key(self):
        """Test validation with short secret key"""
        with patch.dict(os.environ, {'UI_SECRET_KEY': 'short'}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                UIConfig()
            
            assert 'Secret key is too short' in str(exc_info.value)
    
    def test_validation_auth_without_password(self):
        """Test validation when auth is enabled but no password set"""
        with patch.dict(os.environ, {
            'UI_REQUIRE_AUTH': 'true',
            'UI_AUTH_PASSWORD': ''
        }, clear=True):
            with pytest.raises(ValueError) as exc_info:
                UIConfig()
            
            assert 'Authentication enabled but no password set' in str(exc_info.value)
    
    def test_https_configuration(self):
        """Test HTTPS configuration"""
        # Create temporary certificate files
        with tempfile.NamedTemporaryFile(delete=False) as cert_file:
            cert_path = cert_file.name
        
        with tempfile.NamedTemporaryFile(delete=False) as key_file:
            key_path = key_file.name
        
        try:
            with patch.dict(os.environ, {
                'UI_USE_HTTPS': 'true',
                'UI_SSL_CERT_PATH': cert_path,
                'UI_SSL_KEY_PATH': key_path
            }, clear=True):
                config = UIConfig()
                
                assert config.use_https is True
                assert config.ssl_cert_path == cert_path
                assert config.ssl_key_path == key_path
                
                ssl_context = config.get_ssl_context()
                assert ssl_context == (cert_path, key_path)
        
        finally:
            os.unlink(cert_path)
            os.unlink(key_path)
    
    def test_https_validation_missing_files(self):
        """Test HTTPS validation with missing certificate files"""
        with patch.dict(os.environ, {
            'UI_USE_HTTPS': 'true',
            'UI_SSL_CERT_PATH': '/nonexistent/cert.pem',
            'UI_SSL_KEY_PATH': '/nonexistent/key.pem'
        }, clear=True):
            with pytest.raises(ValueError) as exc_info:
                UIConfig()
            
            error_message = str(exc_info.value)
            assert 'SSL certificate not found' in error_message
            assert 'SSL key not found' in error_message
    
    def test_flask_config_generation(self):
        """Test Flask configuration dictionary generation"""
        with patch.dict(os.environ, {
            'UI_SECRET_KEY': 'test-secret-key',
            'UI_CSRF_ENABLED': 'true',
            'UI_USE_HTTPS': 'true'
        }, clear=True):
            config = UIConfig()
            flask_config = config.get_flask_config()
            
            assert flask_config['SECRET_KEY'] == 'test-secret-key'
            assert flask_config['WTF_CSRF_ENABLED'] is True
            assert flask_config['SESSION_COOKIE_SECURE'] is True
            assert flask_config['SESSION_COOKIE_HTTPONLY'] is True
    
    def test_production_detection(self):
        """Test production mode detection"""
        with patch.dict(os.environ, {'UI_DEBUG': 'true'}, clear=True):
            config = UIConfig()
            assert config.is_production() is False
        
        with patch.dict(os.environ, {'UI_DEBUG': 'false'}, clear=True):
            config = UIConfig()
            assert config.is_production() is True
    
    def test_allowed_hosts_parsing(self):
        """Test allowed hosts parsing"""
        with patch.dict(os.environ, {
            'UI_ALLOWED_HOSTS': 'localhost,127.0.0.1,example.com'
        }, clear=True):
            config = UIConfig()
            
            expected_hosts = ['localhost', '127.0.0.1', 'example.com']
            assert config.allowed_hosts == expected_hosts
    
    def test_database_url_configuration(self):
        """Test database URL configuration"""
        test_db_url = 'sqlite:///test_database.db'
        
        with patch.dict(os.environ, {'DATABASE_URL': test_db_url}, clear=True):
            config = UIConfig()
            
            assert config.database_url == test_db_url
    
    def test_startup_info_output(self, capsys):
        """Test startup information output"""
        with patch.dict(os.environ, {
            'UI_PORT': '8080',
            'UI_DEBUG': 'true'
        }, clear=True):
            config = UIConfig()
            config.print_startup_info()
            
            captured = capsys.readouterr()
            assert 'EMAIL AUTOMATION ADMIN UI' in captured.out
            assert '8080' in captured.out
            assert 'Debug Mode: Enabled' in captured.out
            assert 'DEVELOPMENT MODE' in captured.out

if __name__ == '__main__':
    pytest.main([__file__])