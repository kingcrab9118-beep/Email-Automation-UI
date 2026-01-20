"""
Backend integration utilities for Admin UI
Provides safe access to existing email automation components
"""

import asyncio
import logging
import sys
import os
from typing import Optional, Dict, Any, Tuple
from contextlib import asynccontextmanager

# Add parent directory to path for email_automation imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

class BackendIntegration:
    """Safe integration with existing email automation backend"""
    
    def __init__(self):
        self._config = None
        self._db_manager = None
        self._scheduler = None
        self._reply_tracker = None
        self._app_instance = None
    
    @asynccontextmanager
    async def get_config(self):
        """Get configuration with proper error handling"""
        try:
            if not self._config:
                from email_automation.config import Config
                self._config = Config()
            yield self._config
        except Exception as e:
            logger.error(f"Error getting configuration: {e}")
            raise
    
    @asynccontextmanager
    async def get_database_manager(self):
        """Get database manager with proper lifecycle management"""
        db_manager = None
        try:
            from email_automation.db.database import DatabaseManager
            from email_automation.config import Config
            
            config = Config()
            db_manager = DatabaseManager(config.database_url)
            await db_manager.initialize()
            yield db_manager
            
        except Exception as e:
            logger.error(f"Error with database manager: {e}")
            raise
        finally:
            if db_manager:
                try:
                    await db_manager.close()
                except Exception as e:
                    logger.warning(f"Error closing database manager: {e}")
    
    async def get_scheduler_status(self) -> Dict[str, Any]:
        """Get scheduler status safely"""
        try:
            async with self.get_database_manager() as db_manager:
                from email_automation.scheduler.scheduler import SequenceScheduler
                from email_automation.config import Config
                
                config = Config()
                scheduler = SequenceScheduler(config, db_manager)
                return await scheduler.get_scheduler_status()
                
        except Exception as e:
            logger.error(f"Error getting scheduler status: {e}")
            return {'scheduler_running': False, 'error': str(e)}
    
    async def start_scheduler(self) -> Tuple[bool, str]:
        """Start the scheduler safely"""
        try:
            if not self._app_instance:
                await self._initialize_app()
            
            if self._scheduler:
                self._scheduler.start()
                return True, "Scheduler started successfully"
            else:
                return False, "Scheduler not available"
                
        except Exception as e:
            logger.error(f"Error starting scheduler: {e}")
            return False, f"Error starting scheduler: {str(e)}"
    
    async def stop_scheduler(self) -> Tuple[bool, str]:
        """Stop the scheduler safely"""
        try:
            if not self._app_instance:
                await self._initialize_app()
            
            if self._scheduler:
                self._scheduler.shutdown()
                return True, "Scheduler stopped successfully"
            else:
                return False, "Scheduler not available"
                
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")
            return False, f"Error stopping scheduler: {str(e)}"
    
    async def process_due_emails(self) -> Tuple[bool, str]:
        """Process due emails safely"""
        try:
            if not self._app_instance:
                await self._initialize_app()
            
            if self._scheduler:
                await self._scheduler.process_due_emails()
                return True, "Email processing completed"
            else:
                return False, "Scheduler not available"
                
        except Exception as e:
            logger.error(f"Error processing emails: {e}")
            return False, f"Error processing emails: {str(e)}"
    
    async def scan_for_replies(self) -> Tuple[bool, str]:
        """Scan for replies safely"""
        try:
            if not self._app_instance:
                await self._initialize_app()
            
            if self._reply_tracker:
                await self._reply_tracker.scan_inbox()
                return True, "Reply scanning completed"
            else:
                return False, "Reply tracker not available"
                
        except Exception as e:
            logger.error(f"Error scanning replies: {e}")
            return False, f"Error scanning replies: {str(e)}"
    
    async def _initialize_app(self):
        """Initialize the backend application components"""
        try:
            from email_automation.main import EmailAutomationApp
            from email_automation.config import Config
            
            config = Config()
            self._app_instance = EmailAutomationApp(config)
            await self._app_instance.initialize()
            
            self._scheduler = self._app_instance.scheduler
            self._reply_tracker = self._app_instance.reply_tracker
            
            logger.info("Backend application initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing backend application: {e}")
            raise
    
    async def cleanup(self):
        """Cleanup backend resources"""
        try:
            if self._app_instance:
                await self._app_instance.cleanup()
            
            self._config = None
            self._db_manager = None
            self._scheduler = None
            self._reply_tracker = None
            self._app_instance = None
            
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")

# Global backend integration instance
backend = BackendIntegration()

def run_async_safely(coro):
    """Run async function safely in sync context"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Error running async function: {e}")
        raise

def handle_backend_error(func):
    """Decorator for handling backend integration errors"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Backend integration error in {func.__name__}: {e}")
            from flask import flash
            flash(f"System error: {str(e)}", 'error')
            return None
    return wrapper