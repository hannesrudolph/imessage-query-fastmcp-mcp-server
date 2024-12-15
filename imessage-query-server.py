from pathlib import Path
import os
from typing import Dict, Any
from fastmcp import FastMCP
from datetime import datetime, timedelta
import imessagedb
import phonenumbers
import contextlib
import io

# Initialize FastMCP server
mcp = FastMCP("iMessage Query", dependencies=["imessagedb", "phonenumbers"])

# Default to Messages database in user's Library
DEFAULT_DB_PATH = Path.home() / "Library" / "Messages" / "chat.db"
DB_PATH = Path(os.environ.get('SQLITE_DB_PATH', DEFAULT_DB_PATH))

class DatabaseContext:
    """Singleton context for managing database connections across tools."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseContext, cls).__new__(cls)
            cls._instance.db_path = DB_PATH
            cls._instance._db = None
        return cls._instance
    
    def get_connection(self):
        """Get an imessagedb connection from the context."""
        if self._db is None:
            self._db = imessagedb.DB(str(self.db_path))
        return self._db

class MessageDBConnection:
    """Context manager for database connections."""
    def __init__(self):
        self.db_context = DatabaseContext()
        self.db = None
        
    def __enter__(self):
        self.db = self.db_context.get_connection()
        return self.db
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        # No need to close imessagedb connection
        pass

@mcp.tool()
def get_chat_transcript(
    phone_number: str,
    start_date: str = None,
    end_date: str = None
) -> Dict[str, Any]:
    """Get chat transcript for a specific phone number within a date range.
    
    Args:
        phone_number: Phone number to get transcript for (E.164 format preferred)
        start_date: Optional start date in ISO format (YYYY-MM-DD)
        end_date: Optional end date in ISO format (YYYY-MM-DD)
    
    Returns:
        Dictionary containing the chat transcript data
    
    Raises:
        ValueError: If the phone number is invalid
    """
    # Validate and format the phone number
    try:
        # Parse assuming US number if no region provided
        parsed_number = phonenumbers.parse(phone_number, "US")
        if not phonenumbers.is_valid_number(parsed_number):
            raise ValueError(f"Invalid phone number: {phone_number}")
        # Format to E.164 format
        phone_number = phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException as e:
        raise ValueError(f"Invalid phone number format: {e}")

    if not DB_PATH.exists():
        raise FileNotFoundError(f"Messages database not found at: {DB_PATH}")

    # Suppress stdout to hide progress bars
    with contextlib.redirect_stdout(io.StringIO()):
        with MessageDBConnection() as db:
            # Create Messages object for the phone number
            messages = db.Messages("person", phone_number, numbers=[phone_number])
            
            # Set default date range to last 7 days if not specified
            if not start_date and not end_date:
                end_dt = datetime.now()
                start_dt = end_dt - timedelta(days=7)
                start_date = start_dt.strftime("%Y-%m-%d")
                end_date = end_dt.strftime("%Y-%m-%d")
            
            # Filter messages by date if specified
            filtered_messages = []
            for msg in messages.message_list:
                msg_date = datetime.strptime(msg.date[:10], "%Y-%m-%d")
                
                if start_date:
                    start_dt = datetime.fromisoformat(start_date)
                    if msg_date < start_dt:
                        continue
                        
                if end_date:
                    end_dt = datetime.fromisoformat(end_date)
                    if msg_date > end_dt:
                        continue
                        
                filtered_messages.append({
                    "text": msg.text,
                    "date": msg.date,
                    "is_from_me": msg.is_from_me,
                    "has_attachments": bool(msg.attachments),
                    "attachments": [
                        {
                            "mime_type": att.mime_type if hasattr(att, 'mime_type') else None,
                            "filename": att.filename if hasattr(att, 'filename') else None,
                            "file_path": att.original_path if hasattr(att, 'original_path') else None,
                            "is_missing": att.missing if hasattr(att, 'missing') else False
                        } for att in msg.attachments if isinstance(att, object)
                    ] if msg.attachments else []
                })
                
            return {
                "messages": filtered_messages,
                "total_count": len(filtered_messages)
            }