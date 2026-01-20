"""
Operational safety utilities for Admin UI
Provides additional safety checks and user experience enhancements
"""

import logging
from typing import Dict, Any, List, Tuple
from datetime import datetime, timedelta
from flask import request, session, flash

logger = logging.getLogger(__name__)

class OperationalSafety:
    """Operational safety checks and validations"""
    
    @staticmethod
    def validate_email_sending_safety(pending_emails: int, rate_limit_status: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate if it's safe to trigger email sending"""
        
        # Check if there are too many pending emails
        if pending_emails > 100:
            return False, f"Too many pending emails ({pending_emails}). Consider processing in smaller batches."
        
        # Check rate limiting status
        if rate_limit_status.get('near_limit', False):
            return False, "System is near rate limits. Wait before triggering manual email cycle."
        
        # Check if it's outside business hours (optional safety check)
        current_hour = datetime.now().hour
        if current_hour < 8 or current_hour > 18:
            logger.warning(f"Email cycle triggered outside business hours: {current_hour}:00")
        
        return True, "Safe to proceed"
    
    @staticmethod
    def validate_scheduler_operation(action: str, current_status: bool) -> Tuple[bool, str]:
        """Validate scheduler start/stop operations"""
        
        if action == 'start' and current_status:
            return False, "Scheduler is already running"
        
        if action == 'stop' and not current_status:
            return False, "Scheduler is already stopped"
        
        # Check for recent operations to prevent rapid start/stop cycles
        last_operation_key = f'scheduler_last_{action}'
        last_operation = session.get(last_operation_key)
        
        if last_operation:
            last_time = datetime.fromisoformat(last_operation)
            if datetime.now() - last_time < timedelta(minutes=1):
                return False, f"Please wait before {action}ing the scheduler again (minimum 1 minute interval)"
        
        return True, "Operation allowed"
    
    @staticmethod
    def record_scheduler_operation(action: str):
        """Record scheduler operation for safety tracking"""
        session[f'scheduler_last_{action}'] = datetime.now().isoformat()
        logger.info(f"Scheduler {action} operation recorded for user session")
    
    @staticmethod
    def check_system_health() -> Dict[str, Any]:
        """Perform basic system health checks"""
        health_status = {
            'overall_healthy': True,
            'warnings': [],
            'errors': []
        }
        
        try:
            # Check database connectivity
            from database import ui_db
            if not ui_db.db_manager:
                health_status['errors'].append("Database not connected")
                health_status['overall_healthy'] = False
        
        except Exception as e:
            health_status['errors'].append(f"Database check failed: {str(e)}")
            health_status['overall_healthy'] = False
        
        # Add more health checks as needed
        
        return health_status

class UserExperienceEnhancements:
    """User experience enhancements and helpers"""
    
    @staticmethod
    def format_email_status(first_mail: bool, reminder1: bool, reminder2: bool, replied: bool) -> str:
        """Format email status for clear display"""
        if replied:
            return "✅ Replied (sequence stopped)"
        
        status_parts = []
        if first_mail:
            status_parts.append("📧 First mail sent")
        if reminder1:
            status_parts.append("📧 Reminder 1 sent")
        if reminder2:
            status_parts.append("📧 Reminder 2 sent")
        
        if not status_parts:
            return "⏳ Not started"
        
        return " → ".join(status_parts)
    
    @staticmethod
    def get_status_color_class(status: str) -> str:
        """Get CSS class for status display"""
        status_lower = status.lower()
        
        if 'replied' in status_lower:
            return 'status-success'
        elif 'in sequence' in status_lower:
            return 'status-active'
        elif 'not started' in status_lower:
            return 'status-pending'
        elif 'stopped' in status_lower:
            return 'status-stopped'
        else:
            return 'status-unknown'
    
    @staticmethod
    def format_last_activity(last_activity: datetime) -> str:
        """Format last activity timestamp for display"""
        if not last_activity:
            return "Never"
        
        now = datetime.now()
        diff = now - last_activity
        
        if diff.days > 0:
            return f"{diff.days} days ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hours ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minutes ago"
        else:
            return "Just now"
    
    @staticmethod
    def get_dashboard_insights(metrics: Dict[str, int]) -> List[str]:
        """Generate insights for dashboard display"""
        insights = []
        
        total = metrics.get('total_recipients', 0)
        if total == 0:
            insights.append("💡 Add your first recipient to start email sequences")
            return insights
        
        active = metrics.get('active_recipients', 0)
        replied = metrics.get('replied_recipients', 0)
        pending = metrics.get('pending_recipients', 0)
        
        # Reply rate insights
        if total > 0:
            reply_rate = (replied / total) * 100
            if reply_rate > 20:
                insights.append(f"🎉 Excellent reply rate: {reply_rate:.1f}%")
            elif reply_rate > 10:
                insights.append(f"👍 Good reply rate: {reply_rate:.1f}%")
            elif reply_rate > 5:
                insights.append(f"📈 Moderate reply rate: {reply_rate:.1f}%")
            else:
                insights.append(f"📊 Reply rate: {reply_rate:.1f}% - consider reviewing email content")
        
        # Activity insights
        if pending > active:
            insights.append(f"⏳ {pending} recipients waiting to start sequences")
        
        if active > 0:
            insights.append(f"🔄 {active} recipients currently in email sequences")
        
        return insights
    
    @staticmethod
    def validate_recipient_data_ux(data: Dict[str, str]) -> List[str]:
        """User-friendly validation messages for recipient data"""
        messages = []
        
        # Check for common email domain issues
        email = data.get('email', '').lower()
        if email:
            # Check for common typos
            common_domains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']
            domain = email.split('@')[-1] if '@' in email else ''
            
            if domain and domain not in common_domains:
                # Check for common typos
                if 'gmial' in domain or 'gmai' in domain:
                    messages.append("⚠️ Did you mean 'gmail.com'?")
                elif 'yahooo' in domain or 'yaho' in domain:
                    messages.append("⚠️ Did you mean 'yahoo.com'?")
        
        # Check for potential formatting issues
        first_name = data.get('first_name', '')
        if first_name and not first_name[0].isupper():
            messages.append("💡 Consider capitalizing the first name")
        
        company = data.get('company', '')
        if company and len(company) < 2:
            messages.append("⚠️ Company name seems very short")
        
        return messages

class ErrorMessageEnhancer:
    """Enhanced error messaging for better user experience"""
    
    @staticmethod
    def enhance_database_error(error: str) -> str:
        """Convert technical database errors to user-friendly messages"""
        error_lower = error.lower()
        
        if 'unique constraint' in error_lower or 'already exists' in error_lower:
            return "This email address is already in the system. Each recipient can only be added once."
        
        if 'foreign key' in error_lower:
            return "There was a data consistency issue. Please try again or contact support."
        
        if 'connection' in error_lower or 'timeout' in error_lower:
            return "Database connection issue. Please check your connection and try again."
        
        if 'permission' in error_lower or 'access denied' in error_lower:
            return "Database access issue. Please check system permissions."
        
        # Generic fallback
        return "A database error occurred. Please try again or contact support if the problem persists."
    
    @staticmethod
    def enhance_backend_error(error: str) -> str:
        """Convert technical backend errors to user-friendly messages"""
        error_lower = error.lower()
        
        if 'authentication' in error_lower or 'unauthorized' in error_lower:
            return "Authentication issue with Microsoft 365. Please check the system configuration."
        
        if 'rate limit' in error_lower or 'throttled' in error_lower:
            return "Microsoft 365 rate limits reached. Please wait a few minutes before trying again."
        
        if 'network' in error_lower or 'connection refused' in error_lower:
            return "Network connectivity issue. Please check your internet connection."
        
        if 'scheduler' in error_lower and 'not available' in error_lower:
            return "Email scheduler is not available. Please ensure the main email automation system is running."
        
        # Generic fallback
        return "A system error occurred. Please try again or contact support if the problem persists."

def flash_enhanced_message(message: str, category: str = 'info', include_timestamp: bool = True):
    """Enhanced flash message with timestamp and formatting"""
    if include_timestamp:
        timestamp = datetime.now().strftime('%H:%M:%S')
        message = f"[{timestamp}] {message}"
    
    flash(message, category)
    logger.info(f"Flash message: [{category}] {message}")

def get_user_friendly_status_explanation(status: str) -> str:
    """Get detailed explanation of recipient status"""
    explanations = {
        'pending': "This recipient has been added but their email sequence hasn't started yet. The scheduler will begin sending emails according to the configured timing.",
        'active': "This recipient is currently in an email sequence. They will receive follow-up emails according to the schedule unless they reply.",
        'replied': "This recipient has replied to one of the emails. Their sequence has been automatically stopped to prevent further emails.",
        'stopped': "This recipient's sequence has been manually stopped. No further emails will be sent unless manually restarted."
    }
    
    return explanations.get(status.lower(), "Status information not available.")

# Template filters for enhanced display
def register_template_filters(app):
    """Register custom template filters for enhanced display"""
    
    @app.template_filter('format_status')
    def format_status_filter(status):
        return UserExperienceEnhancements.format_email_status(
            status.get('first_mail', False),
            status.get('reminder1', False), 
            status.get('reminder2', False),
            status.get('replied', False)
        )
    
    @app.template_filter('status_class')
    def status_class_filter(status):
        return UserExperienceEnhancements.get_status_color_class(status)
    
    @app.template_filter('time_ago')
    def time_ago_filter(timestamp):
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        return UserExperienceEnhancements.format_last_activity(timestamp)
    
    @app.template_filter('enhance_error')
    def enhance_error_filter(error):
        return ErrorMessageEnhancer.enhance_backend_error(error)