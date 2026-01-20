"""
Tests for security utilities
"""

import pytest
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from security import (
    InputValidator, FormValidator, CSRFProtection, XSSProtection,
    SecurityMiddleware, rate_limiter
)

class TestInputValidator:
    """Test cases for InputValidator class"""
    
    def test_validate_email_valid(self):
        """Test email validation with valid emails"""
        valid_emails = [
            'test@example.com',
            'user.name@domain.co.uk',
            'user+tag@example.org',
            'firstname.lastname@company.com'
        ]
        
        for email in valid_emails:
            valid, error = InputValidator.validate_email(email)
            assert valid is True, f"Email {email} should be valid"
            assert error == ""
    
    def test_validate_email_invalid(self):
        """Test email validation with invalid emails"""
        invalid_emails = [
            '',
            'invalid',
            '@domain.com',
            'user@',
            'user@domain',
            'user name@domain.com',
            'user@domain..com'
        ]
        
        for email in invalid_emails:
            valid, error = InputValidator.validate_email(email)
            assert valid is False, f"Email {email} should be invalid"
            assert error != ""
    
    def test_validate_name_valid(self):
        """Test name validation with valid names"""
        valid_names = [
            'John',
            'Mary Jane',
            "O'Connor",
            'Jean-Pierre',
            'Smith Jr.'
        ]
        
        for name in valid_names:
            valid, error = InputValidator.validate_name(name)
            assert valid is True, f"Name {name} should be valid"
            assert error == ""
    
    def test_validate_name_invalid(self):
        """Test name validation with invalid names"""
        invalid_names = [
            '',
            '   ',
            'John123',
            'Name@domain',
            'A' * 101  # Too long
        ]
        
        for name in invalid_names:
            valid, error = InputValidator.validate_name(name)
            assert valid is False, f"Name {name} should be invalid"
            assert error != ""
    
    def test_validate_company_valid(self):
        """Test company validation with valid company names"""
        valid_companies = [
            'Acme Corp',
            'Smith & Associates',
            'Tech Solutions Inc.',
            'ABC-123 Company',
            'Global Corp (USA)'
        ]
        
        for company in valid_companies:
            valid, error = InputValidator.validate_company(company)
            assert valid is True, f"Company {company} should be valid"
            assert error == ""
    
    def test_validate_company_invalid(self):
        """Test company validation with invalid company names"""
        invalid_companies = [
            '',
            '   ',
            'A' * 201  # Too long
        ]
        
        for company in invalid_companies:
            valid, error = InputValidator.validate_company(company)
            assert valid is False, f"Company {company} should be invalid"
            assert error != ""
    
    def test_validate_role_optional(self):
        """Test role validation (optional field)"""
        # Empty role should be valid
        valid, error = InputValidator.validate_role('')
        assert valid is True
        assert error == ""
        
        # Valid roles
        valid_roles = ['CEO', 'Marketing Director', 'VP Sales & Marketing']
        for role in valid_roles:
            valid, error = InputValidator.validate_role(role)
            assert valid is True, f"Role {role} should be valid"
            assert error == ""

class TestFormValidator:
    """Test cases for FormValidator class"""
    
    def test_validate_recipient_form_valid(self):
        """Test form validation with valid recipient data"""
        form_data = {
            'first_name': 'John',
            'company': 'Acme Corp',
            'role': 'CEO',
            'email': 'john@acme.com'
        }
        
        validator = FormValidator(form_data)
        assert validator.validate_recipient_form() is True
        assert len(validator.get_errors()) == 0
        
        cleaned_data = validator.get_cleaned_data()
        assert cleaned_data['first_name'] == 'John'
        assert cleaned_data['email'] == 'john@acme.com'
    
    def test_validate_recipient_form_invalid(self):
        """Test form validation with invalid recipient data"""
        form_data = {
            'first_name': '',
            'company': 'Acme Corp',
            'role': 'CEO',
            'email': 'invalid-email'
        }
        
        validator = FormValidator(form_data)
        assert validator.validate_recipient_form() is False
        
        errors = validator.get_errors()
        assert len(errors) >= 2  # At least first_name and email errors
        assert any('First name is required' in error for error in errors)
        assert any('Invalid email format' in error for error in errors)

class TestXSSProtection:
    """Test cases for XSS protection utilities"""
    
    def test_sanitize_input_basic(self):
        """Test basic input sanitization"""
        test_cases = [
            ('Hello World', 'Hello World'),
            ('<script>alert("xss")</script>', '&lt;script&gt;alert(&#34;xss&#34;)&lt;/script&gt;'),
            ('Normal text with <b>bold</b>', 'Normal text with &lt;b&gt;bold&lt;/b&gt;'),
            ('', ''),
            ('Text with & ampersand', 'Text with &amp; ampersand')
        ]
        
        for input_text, expected in test_cases:
            result = XSSProtection.sanitize_input(input_text)
            assert result == expected, f"Input: {input_text}, Expected: {expected}, Got: {result}"
    
    def test_sanitize_dict(self):
        """Test dictionary sanitization"""
        input_dict = {
            'name': 'John <script>alert("xss")</script>',
            'company': 'Acme & Corp',
            'number': 123,
            'boolean': True
        }
        
        result = XSSProtection.sanitize_dict(input_dict)
        
        assert '&lt;script&gt;' in result['name']
        assert '&amp;' in result['company']
        assert result['number'] == 123  # Non-string values unchanged
        assert result['boolean'] is True

class TestRateLimiter:
    """Test cases for rate limiting"""
    
    def test_rate_limiter_allows_requests(self):
        """Test that rate limiter allows requests under limit"""
        identifier = 'test_user_1'
        
        # Should allow first few requests
        for i in range(5):
            assert rate_limiter.is_allowed(identifier, max_requests=10, window_seconds=300) is True
    
    def test_rate_limiter_blocks_excess_requests(self):
        """Test that rate limiter blocks requests over limit"""
        identifier = 'test_user_2'
        max_requests = 3
        
        # Allow up to max_requests
        for i in range(max_requests):
            assert rate_limiter.is_allowed(identifier, max_requests=max_requests, window_seconds=300) is True
        
        # Should block the next request
        assert rate_limiter.is_allowed(identifier, max_requests=max_requests, window_seconds=300) is False
    
    def test_rate_limiter_different_identifiers(self):
        """Test that rate limiter tracks different identifiers separately"""
        identifier1 = 'test_user_3'
        identifier2 = 'test_user_4'
        max_requests = 2
        
        # Both should be allowed initially
        assert rate_limiter.is_allowed(identifier1, max_requests=max_requests, window_seconds=300) is True
        assert rate_limiter.is_allowed(identifier2, max_requests=max_requests, window_seconds=300) is True
        
        # Fill up identifier1's quota
        assert rate_limiter.is_allowed(identifier1, max_requests=max_requests, window_seconds=300) is True
        assert rate_limiter.is_allowed(identifier1, max_requests=max_requests, window_seconds=300) is False
        
        # identifier2 should still be allowed
        assert rate_limiter.is_allowed(identifier2, max_requests=max_requests, window_seconds=300) is True

class TestCSRFProtection:
    """Test cases for CSRF protection"""
    
    @patch('security.validate_csrf')
    def test_validate_csrf_token_success(self, mock_validate_csrf):
        """Test successful CSRF token validation"""
        mock_validate_csrf.return_value = None  # No exception means success
        
        result = CSRFProtection.validate_csrf_token('valid_token')
        assert result is True
        mock_validate_csrf.assert_called_once_with('valid_token')
    
    @patch('security.validate_csrf')
    def test_validate_csrf_token_failure(self, mock_validate_csrf):
        """Test failed CSRF token validation"""
        from flask_wtf.csrf import ValidationError
        mock_validate_csrf.side_effect = ValidationError('Invalid token')
        
        result = CSRFProtection.validate_csrf_token('invalid_token')
        assert result is False

class TestSecurityMiddleware:
    """Test cases for security middleware"""
    
    @patch('security.request')
    def test_validate_request_size_valid(self, mock_request):
        """Test request size validation with valid size"""
        mock_request.content_length = 1024  # 1KB - should be valid
        
        # Should not raise exception
        SecurityMiddleware.validate_request_size()
    
    @patch('security.request')
    @patch('security.abort')
    def test_validate_request_size_too_large(self, mock_abort, mock_request):
        """Test request size validation with oversized request"""
        mock_request.content_length = 2 * 1024 * 1024  # 2MB - should be rejected
        
        SecurityMiddleware.validate_request_size()
        mock_abort.assert_called_once_with(413)
    
    @patch('security.request')
    def test_validate_request_method_valid(self, mock_request):
        """Test request method validation with valid method"""
        mock_request.method = 'GET'
        
        # Should not raise exception
        SecurityMiddleware.validate_request_method()
    
    @patch('security.request')
    @patch('security.abort')
    def test_validate_request_method_invalid(self, mock_abort, mock_request):
        """Test request method validation with invalid method"""
        mock_request.method = 'DELETE'
        
        SecurityMiddleware.validate_request_method()
        mock_abort.assert_called_once_with(405)

# Integration tests would go here, testing the decorators and middleware
# in the context of actual Flask requests

if __name__ == '__main__':
    pytest.main([__file__])