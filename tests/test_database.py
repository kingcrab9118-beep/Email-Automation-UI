"""
Tests for database integration layer
"""

import pytest
import asyncio
import tempfile
import os
from datetime import datetime
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import UIDatabase, DashboardMetrics, RecipientStatus, AddRecipientForm

class TestUIDatabase:
    """Test cases for UIDatabase class"""
    
    @pytest.fixture
    async def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_db_path = f.name
        
        # Mock the config to use temp database
        with patch('database.Config') as mock_config:
            mock_config.return_value.database_url = f'sqlite:///{temp_db_path}'
            
            db = UIDatabase()
            await db.initialize()
            
            yield db
            
            await db.close()
            os.unlink(temp_db_path)
    
    @pytest.mark.asyncio
    async def test_get_dashboard_metrics_empty_db(self, temp_db):
        """Test dashboard metrics with empty database"""
        metrics = await temp_db.get_dashboard_metrics()
        
        assert isinstance(metrics, DashboardMetrics)
        assert metrics.total_recipients == 0
        assert metrics.active_recipients == 0
        assert metrics.replied_recipients == 0
        assert metrics.pending_recipients == 0
        assert isinstance(metrics.last_updated, datetime)
    
    @pytest.mark.asyncio
    async def test_add_recipient_valid_data(self, temp_db):
        """Test adding recipient with valid data"""
        recipient_data = {
            'first_name': 'John',
            'company': 'Acme Corp',
            'role': 'CEO',
            'email': 'john@acme.com'
        }
        
        success, message = await temp_db.add_recipient(recipient_data)
        
        assert success is True
        assert 'Successfully added' in message
        assert 'john@acme.com' in message
    
    @pytest.mark.asyncio
    async def test_add_recipient_invalid_data(self, temp_db):
        """Test adding recipient with invalid data"""
        recipient_data = {
            'first_name': '',  # Missing required field
            'company': 'Acme Corp',
            'role': 'CEO',
            'email': 'john@acme.com'
        }
        
        success, message = await temp_db.add_recipient(recipient_data)
        
        assert success is False
        assert 'Missing required fields' in message
    
    @pytest.mark.asyncio
    async def test_add_duplicate_recipient(self, temp_db):
        """Test adding duplicate recipient"""
        recipient_data = {
            'first_name': 'John',
            'company': 'Acme Corp',
            'role': 'CEO',
            'email': 'john@acme.com'
        }
        
        # Add first time
        success1, _ = await temp_db.add_recipient(recipient_data)
        assert success1 is True
        
        # Try to add duplicate
        success2, message2 = await temp_db.add_recipient(recipient_data)
        assert success2 is False
        assert 'already exists' in message2
    
    @pytest.mark.asyncio
    async def test_get_recipients_with_status_empty(self, temp_db):
        """Test getting recipients with status from empty database"""
        recipients = await temp_db.get_recipients_with_status()
        
        assert isinstance(recipients, list)
        assert len(recipients) == 0

class TestAddRecipientForm:
    """Test cases for AddRecipientForm validation"""
    
    def test_valid_form_data(self):
        """Test form validation with valid data"""
        form_data = {
            'first_name': 'John',
            'company': 'Acme Corp',
            'role': 'CEO',
            'email': 'john@acme.com'
        }
        
        form = AddRecipientForm(form_data)
        assert form.validate() is True
        assert len(form.errors) == 0
        
        cleaned_data = form.to_dict()
        assert cleaned_data['first_name'] == 'John'
        assert cleaned_data['email'] == 'john@acme.com'
    
    def test_missing_required_fields(self):
        """Test form validation with missing required fields"""
        form_data = {
            'first_name': '',
            'company': '',
            'role': 'CEO',
            'email': ''
        }
        
        form = AddRecipientForm(form_data)
        assert form.validate() is False
        assert len(form.errors) == 3  # first_name, company, email
        
        errors = form.get_errors()
        assert any('First name is required' in error for error in errors)
        assert any('Company is required' in error for error in errors)
        assert any('Email is required' in error for error in errors)
    
    def test_invalid_email_format(self):
        """Test form validation with invalid email"""
        form_data = {
            'first_name': 'John',
            'company': 'Acme Corp',
            'role': 'CEO',
            'email': 'invalid-email'
        }
        
        form = AddRecipientForm(form_data)
        assert form.validate() is False
        
        errors = form.get_errors()
        assert any('Invalid email format' in error for error in errors)
    
    def test_optional_role_field(self):
        """Test that role field is optional"""
        form_data = {
            'first_name': 'John',
            'company': 'Acme Corp',
            'role': '',  # Empty role should be valid
            'email': 'john@acme.com'
        }
        
        form = AddRecipientForm(form_data)
        assert form.validate() is True
        
        cleaned_data = form.to_dict()
        assert cleaned_data['role'] == ''

class TestDashboardMetrics:
    """Test cases for DashboardMetrics data class"""
    
    def test_dashboard_metrics_creation(self):
        """Test creating DashboardMetrics instance"""
        now = datetime.now()
        metrics = DashboardMetrics(
            total_recipients=10,
            active_recipients=5,
            replied_recipients=2,
            pending_recipients=3,
            scheduler_running=True,
            last_updated=now
        )
        
        assert metrics.total_recipients == 10
        assert metrics.active_recipients == 5
        assert metrics.replied_recipients == 2
        assert metrics.pending_recipients == 3
        assert metrics.scheduler_running is True
        assert metrics.last_updated == now

class TestRecipientStatus:
    """Test cases for RecipientStatus data class"""
    
    def test_recipient_status_creation(self):
        """Test creating RecipientStatus instance"""
        now = datetime.now()
        status = RecipientStatus(
            id=1,
            first_name='John',
            company='Acme Corp',
            role='CEO',
            email='john@acme.com',
            first_mail_sent=True,
            reminder1_sent=False,
            reminder2_sent=False,
            has_replied=False,
            current_status='In sequence',
            last_activity=now
        )
        
        assert status.id == 1
        assert status.first_name == 'John'
        assert status.company == 'Acme Corp'
        assert status.role == 'CEO'
        assert status.email == 'john@acme.com'
        assert status.first_mail_sent is True
        assert status.reminder1_sent is False
        assert status.reminder2_sent is False
        assert status.has_replied is False
        assert status.current_status == 'In sequence'
        assert status.last_activity == now

# Integration test fixtures
@pytest.fixture
def app():
    """Create Flask app for testing"""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from app import create_app
    
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
    
    return app

@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()

if __name__ == '__main__':
    pytest.main([__file__])