"""
Security utilities for Admin UI
Provides input validation, CSRF protection, and XSS prevention
"""

import re
import logging
from typing import Dict, List, Tuple, Any
from flask import request, session, abort
from flask_wtf.csrf import validate_csrf, ValidationError
from markupsafe import Markup, escape

logger = logging.getLogger(__name__)

class InputValidator:
    """Input validation utilities"""
    
    EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    NAME_REGEX = re.compile(r'^[a-zA-Z\s\-\'\.]{1,100}$')
    COMPANY_REGEX = re.compile(r'^[a-zA-Z0-9\s\-\'\.&,()]{1,200}$')
    
    @classmethod
    def validate_email(cls, email: str) -> Tuple[bool, str]:
        """Validate email address format"""
        if not email:
            return False, "Email is required"
        
        email = email.strip().lower()
        
        if len(email) > 254:
            return False, "Email address is too long"
        
        if not cls.EMAIL_REGEX.match(email):
            return False, "Invalid email format"
        
        return True, ""
    
    @classmethod
    def validate_name(cls, name: str, field_name: str = "Name") -> Tuple[bool, str]:
        """Validate name fields (first name, last name)"""
        if not name:
            return False, f"{field_name} is required"
        
        name = name.strip()
        
        if len(name) < 1:
            return False, f"{field_name} is required"
        
        if len(name) > 100:
            return False, f"{field_name} is too long (max 100 characters)"
        
        if not cls.NAME_REGEX.match(name):
            return False, f"{field_name} contains invalid characters"
        
        return True, ""
    
    @classmethod
    def validate_company(cls, company: str) -> Tuple[bool, str]:
        """Validate company name"""
        if not company:
            return False, "Company is required"
        
        company = company.strip()
        
        if len(company) < 1:
            return False, "Company is required"
        
        if len(company) > 200:
            return False, "Company name is too long (max 200 characters)"
        
        if not cls.COMPANY_REGEX.match(company):
            return False, "Company name contains invalid characters"
        
        return True, ""
    
    @classmethod
    def validate_role(cls, role: str) -> Tuple[bool, str]:
        """Validate role/job title (optional field)"""
        if not role:
            return True, ""  # Role is optional
        
        role = role.strip()
        
        if len(role) > 100:
            return False, "Role is too long (max 100 characters)"
        
        # Allow more flexible characters for job titles
        if not re.match(r'^[a-zA-Z0-9\s\-\'\.&,()\/]{1,100}$', role):
            return False, "Role contains invalid characters"
        
        return True, ""

class FormValidator:
    """Complete form validation for recipient data"""
    
    def __init__(self, form_data: Dict[str, str]):
        self.form_data = form_data
        self.errors = []
        self.cleaned_data = {}
    
    def validate_recipient_form(self) -> bool:
        """Validate add recipient form data"""
        self.errors = []
        self.cleaned_data = {}
        
        # Validate first name
        first_name = self.form_data.get('first_name', '').strip()
        valid, error = InputValidator.validate_name(first_name, "First name")
        if not valid:
            self.errors.append(error)
        else:
            self.cleaned_data['first_name'] = first_name
        
        # Validate company
        company = self.form_data.get('company', '').strip()
        valid, error = InputValidator.validate_company(company)
        if not valid:
            self.errors.append(error)
        else:
            self.cleaned_data['company'] = company
        
        # Validate role (optional)
        role = self.form_data.get('role', '').strip()
        valid, error = InputValidator.validate_role(role)
        if not valid:
            self.errors.append(error)
        else:
            self.cleaned_data['role'] = role
        
        # Validate email
        email = self.form_data.get('email', '').strip().lower()
        valid, error = InputValidator.validate_email(email)
        if not valid:
            self.errors.append(error)
        else:
            self.cleaned_data['email'] = email
        
        return len(self.errors) == 0
    
    def get_errors(self) -> List[str]:
        """Get validation errors"""
        return self.errors
    
    def get_cleaned_data(self) -> Dict[str, str]:
        """Get cleaned and validated data"""
        return self.cleaned_data

class CSRFProtection:
    """CSRF protection utilities"""
    
    @staticmethod
    def validate_csrf_token(token: str = None) -> bool:
        """Validate CSRF token from request"""
        try:
            if token is None:
                token = request.form.get('csrf_token')
            
            validate_csrf(token)
            return True
            
        except ValidationError as e:
            logger.warning(f"CSRF validation failed: {e}")
            return False
        except Exception as e:
            logger.error(f"CSRF validation error: {e}")
            return False
    
    @staticmethod
    def require_csrf():
        """Decorator to require CSRF token validation"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                if request.method == 'POST':
                    if not CSRFProtection.validate_csrf_token():
                        logger.warning(f"CSRF validation failed for {request.endpoint}")
                        abort(403)
                return func(*args, **kwargs)
            wrapper.__name__ = func.__name__
            return wrapper
        return decorator

class XSSProtection:
    """XSS prevention utilities"""
    
    @staticmethod
    def sanitize_input(text: str) -> str:
        """Sanitize user input to prevent XSS"""
        if not text:
            return ""
        
        # Flask's escape function handles XSS prevention
        return str(escape(text))
    
    @staticmethod
    def sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize all string values in a dictionary"""
        sanitized = {}
        for key, value in data.items():
            if isinstance(value, str):
                sanitized[key] = XSSProtection.sanitize_input(value)
            else:
                sanitized[key] = value
        return sanitized

class SecurityMiddleware:
    """Security middleware for request processing"""
    
    @staticmethod
    def validate_request_size():
        """Validate request content length"""
        max_content_length = 1024 * 1024  # 1MB
        
        if request.content_length and request.content_length > max_content_length:
            logger.warning(f"Request too large: {request.content_length} bytes")
            abort(413)  # Request Entity Too Large
    
    @staticmethod
    def validate_request_method():
        """Validate allowed request methods"""
        allowed_methods = ['GET', 'POST']
        
        if request.method not in allowed_methods:
            logger.warning(f"Method not allowed: {request.method}")
            abort(405)  # Method Not Allowed
    
    @staticmethod
    def log_security_event(event_type: str, details: str):
        """Log security-related events"""
        logger.warning(f"Security event - {event_type}: {details} | IP: {request.remote_addr} | User-Agent: {request.headers.get('User-Agent', 'Unknown')}")

def secure_form_handler(form_validator_class):
    """Decorator for secure form handling"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Validate request
            SecurityMiddleware.validate_request_size()
            SecurityMiddleware.validate_request_method()
            
            # CSRF protection for POST requests
            if request.method == 'POST':
                if not CSRFProtection.validate_csrf_token():
                    SecurityMiddleware.log_security_event("CSRF_FAILURE", f"Endpoint: {request.endpoint}")
                    abort(403)
            
            # Form validation
            if request.method == 'POST' and form_validator_class:
                validator = form_validator_class(request.form.to_dict())
                if hasattr(validator, 'validate_recipient_form'):
                    if not validator.validate_recipient_form():
                        from flask import flash
                        for error in validator.get_errors():
                            flash(error, 'error')
                        return func(*args, **kwargs)
                    
                    # Add cleaned data to request context
                    request.cleaned_data = validator.get_cleaned_data()
            
            return func(*args, **kwargs)
        
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator

# Rate limiting (simple implementation)
class RateLimiter:
    """Simple rate limiting for form submissions"""
    
    def __init__(self):
        self.requests = {}
    
    def is_allowed(self, identifier: str, max_requests: int = 10, window_seconds: int = 300) -> bool:
        """Check if request is allowed based on rate limiting"""
        import time
        
        current_time = time.time()
        
        if identifier not in self.requests:
            self.requests[identifier] = []
        
        # Clean old requests
        self.requests[identifier] = [
            req_time for req_time in self.requests[identifier]
            if current_time - req_time < window_seconds
        ]
        
        # Check if under limit
        if len(self.requests[identifier]) >= max_requests:
            return False
        
        # Add current request
        self.requests[identifier].append(current_time)
        return True

# Global rate limiter instance
rate_limiter = RateLimiter()

def rate_limit(max_requests: int = 10, window_seconds: int = 300):
    """Rate limiting decorator"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            identifier = request.remote_addr
            
            if not rate_limiter.is_allowed(identifier, max_requests, window_seconds):
                SecurityMiddleware.log_security_event("RATE_LIMIT_EXCEEDED", f"IP: {identifier}")
                abort(429)  # Too Many Requests
            
            return func(*args, **kwargs)
        
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator