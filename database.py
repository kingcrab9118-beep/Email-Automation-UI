"""
Database integration layer for Admin UI
Provides read-only and transactional database access
"""

import os
import sys
import sqlite3
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

# Add parent directory to path for email_automation imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from email_automation.config import Config
from email_automation.db.database import DatabaseManager
from email_automation.db.models import Recipient, EmailSequence, RecipientRepository, EmailSequenceRepository

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
        self.config = Config()
        self.db_manager = None
        self.recipient_repo = None
        self.sequence_repo = None
    
    async def initialize(self):
        """Initialize database connections and repositories"""
        try:
            self.db_manager = DatabaseManager(self.config.database_url)
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
    
    async def get_recipients_with_status(self) -> List[RecipientStatus]:
        """Get all recipients with their email sequence status"""
        try:
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
            ORDER BY r.created_at DESC
            """
            
            results = await self.db_manager.execute_query(query)
            
            recipients = []
            for row in results:
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
                    last_activity=row[10]
                ))
            
            return recipients
            
        except Exception as e:
            self.logger.error(f"Error getting recipients with status: {e}")
            return []
    
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
            
            # Initialize email sequence entries (but don't schedule them yet)
            # This creates the sequence records but they won't be sent until scheduled
            for step in [1, 2, 3]:
                sequence = EmailSequence(
                    recipient_id=recipient_id,
                    step=step,
                    scheduled_at=datetime.now()  # Will be updated when actually scheduled
                )
                await self.sequence_repo.create(sequence)
            
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