"""
Database integration layer for Admin UI
Provides read-only and transactional database access
"""

import os
import sys
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

# Add parent directory to path for email_automation imports
email_automation_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if email_automation_path not in sys.path:
    sys.path.insert(0, email_automation_path)

# Also add email_automation directory itself
email_automation_dir = os.path.join(email_automation_path, 'email_automation')
if email_automation_dir not in sys.path:
    sys.path.insert(0, email_automation_dir)

# Import UI config (not email_automation config)
from ui_config import ui_config

# Import email_automation database classes and config
from db.database import DatabaseManager
from db.models import Recipient, EmailSequence, RecipientRepository, EmailSequenceRepository
from config import Config

@dataclass
class DashboardMetrics:
    """Dashboard statistics"""
    total_recipients: int
    active_recipients: int
    replied_recipients: int
    pending_recipients: int
    scheduler_running: bool
    last_updated: datetime

@dataclass
class RecipientStatus:
    """UI representation of recipient with email status"""
    id: int
    first_name: str
    company: str
    role: str
    email: str
    first_mail_sent: bool
    reminder1_sent: bool
    reminder2_sent: bool
    has_replied: bool
    current_status: str
    last_activity: Optional[datetime]

class UIDatabase:
    """Database integration layer for the admin UI"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Use UI config which has the correct database path
        self.database_url = ui_config.database_url
        self.db_manager = None
        self.recipient_repo = None
        self.sequence_repo = None
        
        # Load email automation config for sequence timing
        self.email_config = Config()
    
    async def initialize(self):
        """Initialize database connections and repositories"""
        try:
            self.logger.info(f"Initializing UI database with: {self.database_url}")
            self.db_manager = DatabaseManager(self.database_url)
            await self.db_manager.initialize()
            
            self.recipient_repo = RecipientRepository(self.db_manager)
            self.sequence_repo = EmailSequenceRepository(self.db_manager)
            
            self.logger.info("UI Database layer initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize UI database layer: {e}")
            raise
    
    async def get_dashboard_metrics(self) -> DashboardMetrics:
        """Calculate dashboard statistics from database"""
        try:
            # Query for recipient counts by status
            query = """
            SELECT 
                COUNT(*) as total_recipients,
                COUNT(CASE WHEN status = 'active' THEN 1 END) as active_recipients,
                COUNT(CASE WHEN status = 'replied' THEN 1 END) as replied_recipients,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_recipients
            FROM recipients
            """
            
            results = await self.db_manager.execute_query(query)
            
            if results:
                row = results[0]
                return DashboardMetrics(
                    total_recipients=row[0] or 0,
                    active_recipients=row[1] or 0,
                    replied_recipients=row[2] or 0,
                    pending_recipients=row[3] or 0,
                    scheduler_running=False,  # Will be updated by scheduler status check
                    last_updated=datetime.now()
                )
            else:
                return DashboardMetrics(0, 0, 0, 0, False, datetime.now())
                
        except Exception as e:
            self.logger.error(f"Error getting dashboard metrics: {e}")
            return DashboardMetrics(0, 0, 0, 0, False, datetime.now())
    
    async def get_recipients_with_status(self, page: int = 1, per_page: int = 20) -> Tuple[List[RecipientStatus], int]:
        """Get recipients with their email sequence status (paginated)
        
        Returns:
            Tuple of (recipients list, total count)
        """
        try:
            # Get total count first
            count_query = "SELECT COUNT(*) FROM recipients"
            count_result = await self.db_manager.execute_query(count_query)
            total_count = count_result[0][0] if count_result else 0
            
            # Calculate offset
            offset = (page - 1) * per_page
            
            # Complex query to get recipients with email status in one query
            query = """
            SELECT 
                r.id, r.first_name, r.company, r.role, r.email, r.status,
                MAX(CASE WHEN es.step = 1 AND es.sent_at IS NOT NULL THEN 1 ELSE 0 END) as first_mail_sent,
                MAX(CASE WHEN es.step = 2 AND es.sent_at IS NOT NULL THEN 1 ELSE 0 END) as reminder1_sent,
                MAX(CASE WHEN es.step = 3 AND es.sent_at IS NOT NULL THEN 1 ELSE 0 END) as reminder2_sent,
                MAX(CASE WHEN es.replied = 1 THEN 1 ELSE 0 END) as has_replied,
                MAX(es.sent_at) as last_activity
            FROM recipients r
            LEFT JOIN email_sequence es ON r.id = es.recipient_id
            GROUP BY r.id, r.first_name, r.company, r.role, r.email, r.status
            ORDER BY r.created_at ASC
            LIMIT ? OFFSET ?
            """
            
            results = await self.db_manager.execute_query(query, (per_page, offset))
            
            recipients = []
            for row in results:
                # Parse last_activity from string to datetime if it exists
                last_activity = None
                if row[10]:
                    try:
                        # SQLite stores datetime as string, parse it
                        last_activity = datetime.fromisoformat(row[10].replace(' ', 'T'))
                    except (ValueError, AttributeError):
                        # If parsing fails, leave as None
                        last_activity = None
                
                recipients.append(RecipientStatus(
                    id=row[0],
                    first_name=row[1],
                    company=row[2],
                    role=row[3],
                    email=row[4],
                    first_mail_sent=bool(row[6]),
                    reminder1_sent=bool(row[7]),
                    reminder2_sent=bool(row[8]),
                    has_replied=bool(row[9]),
                    current_status=self._calculate_status(row[5], bool(row[9])),
                    last_activity=last_activity
                ))
            
            return recipients, total_count
            
        except Exception as e:
            self.logger.error(f"Error getting recipients with status: {e}")
            return [], 0
    
    def _calculate_status(self, recipient_status: str, has_replied: bool) -> str:
        """Calculate human-readable status from database values"""
        if has_replied:
            return "Replied (sequence stopped)"
        elif recipient_status == 'active':
            return "In sequence"
        elif recipient_status == 'pending':
            return "Not started"
        elif recipient_status == 'stopped':
            return "Stopped manually"
        else:
            return "Unknown"
    
    async def add_recipient(self, recipient_data: Dict[str, str]) -> Tuple[bool, str]:
        """Add new recipient with email sequence initialization"""
        try:
            # Validate input data
            if not all([recipient_data.get('first_name'), 
                       recipient_data.get('company'), 
                       recipient_data.get('email')]):
                return False, "Missing required fields"
            
            # Check for duplicate email
            existing = await self.recipient_repo.get_by_email(recipient_data['email'])
            if existing:
                return False, f"Recipient with email {recipient_data['email']} already exists"
            
            # Create recipient
            recipient = Recipient(
                first_name=recipient_data['first_name'].strip(),
                company=recipient_data['company'].strip(),
                role=recipient_data.get('role', '').strip(),
                email=recipient_data['email'].strip().lower(),
                status='pending'
            )
            
            if not recipient.validate():
                return False, "Invalid recipient data"
            
            # Insert recipient
            recipient_id = await self.recipient_repo.create(recipient)
            
            # Note: We only create the recipient here with 'pending' status.
            # The scheduler will automatically detect pending recipients and create
            # the email sequence with proper timing when it processes them.
            # This avoids conflicts with the scheduler's sequence creation logic.
            
            self.logger.info(f"Added recipient {recipient.email} with ID {recipient_id}")
            return True, f"Successfully added {recipient.email}"
            
        except Exception as e:
            self.logger.error(f"Error adding recipient: {e}")
            return False, f"Database error: {str(e)}"
    
    async def get_recipient_count(self) -> int:
        """Get total number of recipients"""
        try:
            query = "SELECT COUNT(*) FROM recipients"
            results = await self.db_manager.execute_query(query)
            return results[0][0] if results else 0
        except Exception as e:
            self.logger.error(f"Error getting recipient count: {e}")
            return 0
    
    async def close(self):
        """Close database connections"""
        if self.db_manager:
            await self.db_manager.close()
    
    async def get_recipient_by_id(self, recipient_id: int) -> Optional[Recipient]:
        """Get recipient by ID"""
        try:
            recipient = await self.recipient_repo.get_by_id(recipient_id)
            return recipient
        except Exception as e:
            self.logger.error(f"Error getting recipient by ID: {e}")
            return None
    
    async def update_recipient(self, recipient_id: int, recipient_data: Dict[str, str]) -> Tuple[bool, str]:
        """Update existing recipient"""
        try:
            # Validate input data
            if not all([recipient_data.get('first_name'), 
                       recipient_data.get('company'), 
                       recipient_data.get('email')]):
                return False, "Missing required fields"
            
            # Get existing recipient
            existing = await self.recipient_repo.get_by_id(recipient_id)
            if not existing:
                return False, f"Recipient with ID {recipient_id} not found"
            
            # Check if email is being changed and if new email already exists
            new_email = recipient_data['email'].strip().lower()
            if new_email != existing.email:
                email_check = await self.recipient_repo.get_by_email(new_email)
                if email_check and email_check.id != recipient_id:
                    return False, f"Email {new_email} is already used by another recipient"
            
            # Update recipient fields
            existing.first_name = recipient_data['first_name'].strip()
            existing.company = recipient_data['company'].strip()
            existing.role = recipient_data.get('role', '').strip()
            existing.email = new_email
            
            if not existing.validate():
                return False, "Invalid recipient data"
            
            # Update in database
            await self.recipient_repo.update(existing)
            
            self.logger.info(f"Updated recipient {existing.email} with ID {recipient_id}")
            return True, f"Successfully updated {existing.email}"
            
        except Exception as e:
            self.logger.error(f"Error updating recipient: {e}")
            return False, f"Database error: {str(e)}"
    
    async def delete_recipient(self, recipient_id: int) -> Tuple[bool, str]:
        """Delete recipient and associated email sequences"""
        try:
            # Get recipient first
            recipient = await self.recipient_repo.get_by_id(recipient_id)
            if not recipient:
                return False, f"Recipient with ID {recipient_id} not found"
            
            # Delete associated email sequences first
            delete_sequences_query = "DELETE FROM email_sequence WHERE recipient_id = ?"
            await self.db_manager.execute_update(delete_sequences_query, (recipient_id,))
            
            # Delete recipient
            await self.recipient_repo.delete(recipient_id)
            
            self.logger.info(f"Deleted recipient {recipient.email} with ID {recipient_id}")
            return True, f"Successfully deleted {recipient.email}"
            
        except Exception as e:
            self.logger.error(f"Error deleting recipient: {e}")
            return False, f"Database error: {str(e)}"

class AddRecipientForm:
    """Form validation for adding recipients"""
    
    def __init__(self, form_data: Dict[str, str]):
        self.first_name = form_data.get('first_name', '').strip()
        self.company = form_data.get('company', '').strip()
        self.role = form_data.get('role', '').strip()
        self.email = form_data.get('email', '').strip().lower()
        self.errors = []
    
    def validate(self) -> bool:
        """Validate form data and populate errors list"""
        self.errors = []
        
        if not self.first_name:
            self.errors.append('First name is required')
        
        if not self.company:
            self.errors.append('Company is required')
        
        if not self.email:
            self.errors.append('Email is required')
        elif '@' not in self.email or '.' not in self.email:
            self.errors.append('Invalid email format')
        
        return len(self.errors) == 0
    
    def to_dict(self) -> Dict[str, str]:
        """Convert form data to dictionary"""
        return {
            'first_name': self.first_name,
            'company': self.company,
            'role': self.role,
            'email': self.email
        }

# Global database instance
ui_db = UIDatabase()