"""
Tests for route handlers
"""

import pytest
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestDashboardRoutes:
    """Test cases for dashboard routes"""
    
    @pytest.fixture
    def app(self):
        """Create Flask app for testing"""
        from app import create_app
        
        app = create_app()
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()
    
    @patch('routes.dashboard.ui_db')
    def test_dashboard_index_success(self, mock_ui_db, client):
        """Test dashboard index with successful data loading"""
        from database import DashboardMetrics
        from datetime import datetime
        
        # Mock database response
        mock_metrics = DashboardMetrics(
            total_recipients=10,
            active_recipients=5,
            replied_recipients=2,
            pending_recipients=3,
            scheduler_running=True,
            last_updated=datetime.now()
        )
        
        mock_ui_db.db_manager = MagicMock()
        mock_ui_db.get_dashboard_metrics = AsyncMock(return_value=mock_metrics)
        
        response = client.get('/')
        
        assert response.status_code == 200
        assert b'Email Automation Dashboard' in response.data
        assert b'10' in response.data  # Total recipients
        assert b'5' in response.data   # Active recipients
    
    @patch('routes.dashboard.ui_db')
    def test_dashboard_index_error(self, mock_ui_db, client):
        """Test dashboard index with database error"""
        mock_ui_db.db_manager = None
        mock_ui_db.initialize = AsyncMock(side_effect=Exception("Database error"))
        
        response = client.get('/')
        
        assert response.status_code == 200
        # Should still render page but with error message
        assert b'Dashboard' in response.data

class TestRecipientsRoutes:
    """Test cases for recipients routes"""
    
    @pytest.fixture
    def app(self):
        """Create Flask app for testing"""
        from app import create_app
        
        app = create_app()
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()
    
    @patch('routes.recipients.ui_db')
    def test_recipients_list_success(self, mock_ui_db, client):
        """Test recipients list with successful data loading"""
        from database import RecipientStatus
        from datetime import datetime
        
        # Mock recipients data
        mock_recipients = [
            RecipientStatus(
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
                last_activity=datetime.now()
            )
        ]
        
        mock_ui_db.db_manager = MagicMock()
        mock_ui_db.get_recipients_with_status = AsyncMock(return_value=mock_recipients)
        
        response = client.get('/recipients/')
        
        assert response.status_code == 200
        assert b'Recipients Overview' in response.data
        assert b'John' in response.data
        assert b'Acme Corp' in response.data
        assert b'john@acme.com' in response.data
    
    @patch('routes.recipients.ui_db')
    def test_recipients_list_empty(self, mock_ui_db, client):
        """Test recipients list with no recipients"""
        mock_ui_db.db_manager = MagicMock()
        mock_ui_db.get_recipients_with_status = AsyncMock(return_value=[])
        
        response = client.get('/recipients/')
        
        assert response.status_code == 200
        assert b'No Recipients Found' in response.data
    
    def test_add_recipient_form_get(self, client):
        """Test GET request to add recipient form"""
        response = client.get('/recipients/new')
        
        assert response.status_code == 200
        assert b'Add New Recipient' in response.data
        assert b'First Name' in response.data
        assert b'Company' in response.data
        assert b'Email' in response.data
    
    @patch('routes.recipients.ui_db')
    def test_add_recipient_form_post_success(self, mock_ui_db, client):
        """Test successful POST to add recipient form"""
        mock_ui_db.db_manager = MagicMock()
        mock_ui_db.add_recipient = AsyncMock(return_value=(True, "Successfully added john@acme.com"))
        
        form_data = {
            'first_name': 'John',
            'company': 'Acme Corp',
            'role': 'CEO',
            'email': 'john@acme.com'
        }
        
        response = client.post('/recipients/new', data=form_data, follow_redirects=True)
        
        assert response.status_code == 200
        # Should redirect to recipients list
        mock_ui_db.add_recipient.assert_called_once()
    
    @patch('routes.recipients.ui_db')
    def test_add_recipient_form_post_validation_error(self, mock_ui_db, client):
        """Test POST to add recipient form with validation errors"""
        form_data = {
            'first_name': '',  # Missing required field
            'company': 'Acme Corp',
            'role': 'CEO',
            'email': 'invalid-email'  # Invalid email
        }
        
        response = client.post('/recipients/new', data=form_data)
        
        assert response.status_code == 200
        # Should stay on form page with errors
        assert b'Add New Recipient' in response.data
        # Should not call database
        mock_ui_db.add_recipient.assert_not_called()

class TestControlRoutes:
    """Test cases for control routes"""
    
    @pytest.fixture
    def app(self):
        """Create Flask app for testing"""
        from app import create_app
        
        app = create_app()
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()
    
    def test_control_panel_get(self, client):
        """Test GET request to control panel"""
        response = client.get('/control/')
        
        assert response.status_code == 200
        assert b'System Control Panel' in response.data
        assert b'Email Scheduler' in response.data
        assert b'Reply Detection' in response.data
    
    @patch('routes.control.get_backend_instances')
    def test_start_scheduler_success(self, mock_get_backend, client):
        """Test successful scheduler start"""
        mock_scheduler = MagicMock()
        mock_scheduler.start = MagicMock()
        mock_get_backend.return_value = (mock_scheduler, None, None)
        
        response = client.post('/control/start-scheduler', follow_redirects=True)
        
        assert response.status_code == 200
        mock_scheduler.start.assert_called_once()
    
    @patch('routes.control.get_backend_instances')
    def test_start_scheduler_not_available(self, mock_get_backend, client):
        """Test scheduler start when scheduler not available"""
        mock_get_backend.return_value = (None, None, None)
        
        response = client.post('/control/start-scheduler', follow_redirects=True)
        
        assert response.status_code == 200
        # Should show error message about scheduler not available
    
    @patch('routes.control.get_backend_instances')
    def test_stop_scheduler_success(self, mock_get_backend, client):
        """Test successful scheduler stop"""
        mock_scheduler = MagicMock()
        mock_scheduler.shutdown = MagicMock()
        mock_get_backend.return_value = (mock_scheduler, None, None)
        
        response = client.post('/control/stop-scheduler', follow_redirects=True)
        
        assert response.status_code == 200
        mock_scheduler.shutdown.assert_called_once()
    
    @patch('routes.control.get_backend_instances')
    def test_run_email_cycle_success(self, mock_get_backend, client):
        """Test successful email cycle execution"""
        mock_scheduler = MagicMock()
        mock_scheduler.process_due_emails = AsyncMock()
        mock_get_backend.return_value = (mock_scheduler, None, None)
        
        response = client.post('/control/run-email-cycle', follow_redirects=True)
        
        assert response.status_code == 200
    
    @patch('routes.control.get_backend_instances')
    def test_run_reply_check_success(self, mock_get_backend, client):
        """Test successful reply check execution"""
        mock_reply_tracker = MagicMock()
        mock_reply_tracker.scan_inbox = AsyncMock()
        mock_get_backend.return_value = (None, mock_reply_tracker, None)
        
        response = client.post('/control/run-reply-check', follow_redirects=True)
        
        assert response.status_code == 200
    
    @patch('routes.control.get_backend_instances')
    def test_system_status_json(self, mock_get_backend, client):
        """Test system status JSON endpoint"""
        mock_scheduler = MagicMock()
        mock_scheduler.get_scheduler_status = AsyncMock(return_value={
            'scheduler_running': True,
            'pending_emails': 5
        })
        
        mock_reply_tracker = MagicMock()
        mock_reply_tracker.get_monitoring_status = MagicMock(return_value={
            'monitoring_active': True
        })
        
        mock_get_backend.return_value = (mock_scheduler, mock_reply_tracker, None)
        
        response = client.get('/control/system-status')
        
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        
        import json
        data = json.loads(response.data)
        assert 'scheduler_available' in data
        assert 'reply_tracker_available' in data

class TestErrorHandling:
    """Test cases for error handling"""
    
    @pytest.fixture
    def app(self):
        """Create Flask app for testing"""
        from app import create_app
        
        app = create_app()
        app.config['TESTING'] = True
        
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()
    
    def test_404_error(self, client):
        """Test 404 error handling"""
        response = client.get('/nonexistent-page')
        
        assert response.status_code == 404
        # Should render error template
    
    def test_method_not_allowed(self, client):
        """Test 405 error for wrong HTTP method"""
        # Try POST to a GET-only endpoint
        response = client.post('/')
        
        assert response.status_code == 405

if __name__ == '__main__':
    pytest.main([__file__])