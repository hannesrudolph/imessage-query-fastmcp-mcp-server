from pathlib import Path
import os
import shutil
import subprocess
from typing import Dict, Any, Optional
from fastmcp import FastMCP
from datetime import datetime, timedelta, timezone
import imessagedb
import phonenumbers
import contextlib
import io
import plistlib

# Initialize FastMCP server
mcp = FastMCP("iMessage Query", dependencies=["imessagedb", "phonenumbers"],
    log_level="CRITICAL")

# Default to Messages database in user's Library
DEFAULT_DB_PATH = Path.home() / "Library" / "Messages" / "chat.db"
DB_PATH = Path(os.environ.get('SQLITE_DB_PATH', DEFAULT_DB_PATH))

def convert_heic_to_jpeg(input_heic: Path, output_jpeg: Path) -> bool:
    """Convert HEIC file to JPEG using ImageMagick."""
    try:
        if not input_heic.exists():
            raise FileNotFoundError(f"Input file {input_heic} not found.")
        
        # Run ImageMagick's convert command
        subprocess.run(
            ["magick", "convert", str(input_heic), str(output_jpeg)],
            check=True,
            capture_output=True,
            text=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error converting HEIC to JPEG: {e.stderr}")
        return False
    except Exception as e:
        print(f"Error converting HEIC to JPEG: {str(e)}")
        return False

def normalize_phone_number(phone: str) -> str:
    """Remove all non-digit characters from a phone number."""
    return ''.join(c for c in phone if c.isdigit())

def extract_message_text(text: str, attributed_body: bytes, message_summary_info: bytes) -> str:
    """Extract message text from various possible storage locations."""
    if text:
        return text
        
    if attributed_body:
        try:
            # Find the NSString marker
            ns_string_idx = attributed_body.find(b'NSString')
            if ns_string_idx == -1:
                return None
                
            # Look for the actual message content after NSString
            content_marker = b'\x01+'
            text_start = attributed_body.find(content_marker, ns_string_idx)
            if text_start == -1:
                return None
                
            # Skip the content marker and any control bytes
            text_start += len(content_marker)
            while text_start < len(attributed_body) and attributed_body[text_start] < 0x20:
                text_start += 1
                
            # Find the end of the text (before the next control sequence)
            text_end = attributed_body.find(b'\x86', text_start)
            if text_end == -1:
                text_end = len(attributed_body)
                
            # Extract and decode the text, removing any remaining control characters
            text_data = attributed_body[text_start:text_end]
            decoded = text_data.decode('utf-8', errors='replace')
            # Clean up any remaining control characters except newlines
            cleaned = ''.join(char for char in decoded if char == '\n' or char >= ' ')
            # Remove replacement characters and image placeholders
            cleaned = cleaned.replace('\ufffd', '').replace('\ufffc', '')
            # Remove any leading/trailing whitespace
            cleaned = cleaned.strip()
            return cleaned if cleaned else None
        except Exception as e:
            print(f"Error extracting text from attributed_body: {e}")
    
    if message_summary_info:
        try:
            # Try to extract text from message_summary_info (edited messages)
            plist = plistlib.loads(message_summary_info)
            if 'ec' in plist and '0' in plist['ec']:
                # Get the most recent edit
                latest_edit = plist['ec']['0'][-1]
                if 't' in latest_edit:
                    edit_text = latest_edit['t']
                    # Extract text from edit data using same method as attributed_body
                    return extract_message_text(None, edit_text, None)
        except Exception as e:
            print(f"Error extracting text from message_summary_info: {e}")
    
    return None

def copy_and_convert_attachment(attachment_path: Path, destination_dir: Path) -> Optional[Path]:
    """
    Copy attachment to destination directory, converting HEIC to jpg if needed.
    
    Args:
        attachment_path: Source path of the attachment
        destination_dir: Destination directory (Downloads folder)
        
    Returns:
        Path to the copied/converted file or None if conversion failed
    """
    if not attachment_path.exists():
        raise FileNotFoundError(f"Attachment not found: {attachment_path}")
        
    # Create destination directory if it doesn't exist
    destination_dir.mkdir(parents=True, exist_ok=True)
    
    # Handle HEIC files
    if attachment_path.suffix.lower() == '.heic':
        dest_name = attachment_path.stem + '.jpeg'
        dest_path = destination_dir / dest_name
        
        # Try to convert HEIC to JPEG
        if convert_heic_to_jpeg(attachment_path, dest_path):
            return dest_path
        return None
    else:
        # Regular file copy for non-HEIC files
        dest_path = destination_dir / attachment_path.name
        shutil.copy2(attachment_path, dest_path)
        return dest_path

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
    identifiers: str,
    start_date: str = None,
    end_date: str = None
) -> Dict[str, Any]:
    """Get chat transcript for one or more identifiers (phone numbers/emails) within a date range.
    
    Args:
        identifiers: Comma-separated list of identifiers (phone numbers in E.164 format preferred, or email addresses)
        start_date: Optional start date in ISO format (YYYY-MM-DD)
        end_date: Optional end date in ISO format (YYYY-MM-DD)
    
    Returns:
        Dictionary containing the chat transcript data
    
    Raises:
        ValueError: If any identifier is invalid
    """
    # Split and clean identifiers
    id_list = [id.strip() for id in identifiers.split(',')]
    normalized_ids = []
    
    # Process each identifier
    for identifier in id_list:
        if '@' in identifier:  # Email address
            normalized_ids.append(identifier)
        else:  # Phone number
            try:
                # Parse assuming US number if no region provided
                parsed_number = phonenumbers.parse(identifier, "US")
                if not phonenumbers.is_valid_number(parsed_number):
                    raise ValueError(f"Invalid phone number: {identifier}")
                # Format to E.164 format
                normalized_ids.append(phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164))
            except phonenumbers.NumberParseException as e:
                raise ValueError(f"Invalid phone number format for {identifier}: {e}")
    
    if not normalized_ids:
        raise ValueError("No valid identifiers provided")
        
    # Validate identifiers exist in database
    with MessageDBConnection() as db:
        invalid_ids = []
        for identifier in normalized_ids:
            db.connection.execute("SELECT COUNT(*) FROM handle WHERE id = ?", (identifier,))
            if db.connection.fetchone()[0] == 0:
                invalid_ids.append(identifier)
                
        if invalid_ids:
            raise ValueError(f"The following identifiers were not found in the database: {', '.join(invalid_ids)}")

    if not DB_PATH.exists():
        raise FileNotFoundError(f"Messages database not found at: {DB_PATH}")

    # Suppress stdout to hide progress bars
    with contextlib.redirect_stdout(io.StringIO()):
        with MessageDBConnection() as db:
            try:
                # Build query for multiple identifiers using UNION approach
                placeholders = ','.join(['?' for _ in normalized_ids])
                query = f"""
                    -- Get messages from direct handle associations
                    SELECT DISTINCT m1.ROWID, m1.guid, m1.text, m1.is_from_me, m1.date, 
                           m1.attributedBody, m1.message_summary_info, m1.handle_id
                    FROM message m1 
                    WHERE m1.handle_id IN (
                        SELECT rowid FROM handle 
                        WHERE id IN ({placeholders})
                    )
                    UNION
                    -- Get messages from chat associations
                    SELECT DISTINCT m2.ROWID, m2.guid, m2.text, m2.is_from_me, m2.date,
                           m2.attributedBody, m2.message_summary_info, m2.handle_id
                    FROM message m2 
                    JOIN chat_message_join cmj ON m2.ROWID = cmj.message_id 
                    JOIN chat c ON cmj.chat_id = c.ROWID 
                    JOIN chat_handle_join chj ON c.ROWID = chj.chat_id 
                    WHERE chj.handle_id IN (
                        SELECT rowid FROM handle 
                        WHERE id IN ({placeholders})
                    )
                    ORDER BY date ASC
                """
                # Execute with normalized_ids twice since we have two placeholders sets
                db.connection.execute(query, normalized_ids + normalized_ids)
                rows = db.connection.fetchall()
                
                # Process messages
                filtered_messages = []
                for row in rows:
                    rowid, guid, text, is_from_me, date, attributed_body, message_summary_info, handle_id = row
                    
                    # Convert database timestamp to datetime
                    msg_dt = datetime.fromtimestamp(date/1000000000 + 978307200).astimezone(timezone.utc)
                    msg_date = msg_dt.date()
                    
                    if start_date:
                        start_dt = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
                        if msg_date < start_dt.date():
                            continue
                            
                    if end_date:
                        end_dt = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)
                        if msg_date > end_dt.date():
                            continue
                            
                    # Set up downloads directory for attachments
                    downloads_dir = Path.home() / "Downloads"
                    
                    # Extract text from various possible locations
                    message_text = extract_message_text(text, attributed_body, message_summary_info)
                    
                    # Get attachments if any
                    attachments = []
                    if rowid in db.attachment_list.message_join:
                        att_list = db.attachment_list.message_join[rowid]
                        for att in att_list:
                            if att in db.attachment_list.attachment_list:
                                attachment = db.attachment_list.attachment_list[att]
                                if not attachment.missing:
                                    try:
                                        # Copy and potentially convert the attachment
                                        src_path = Path(attachment.original_path)
                                        new_path = copy_and_convert_attachment(src_path, downloads_dir)
                                        if new_path:  # Only add if copy/conversion succeeded
                                            attachments.append({
                                                'path': str(new_path),
                                                'mime_type': 'image/jpeg' if src_path.suffix.lower() == '.heic' else attachment.mime_type
                                            })
                                    except Exception as e:
                                        print(f"Failed to copy attachment: {e}")
                    
                    filtered_messages.append({
                        "text": message_text,
                        "date": msg_dt.strftime("%Y-%m-%d %H:%M:%SZ"),
                        "is_from_me": bool(is_from_me),
                        "has_attachments": bool(attachments),
                        "attachments": attachments
                    })
            
                return {
                    "messages": filtered_messages,
                    "total_count": len(filtered_messages)
                }
            except Exception as e:
                # Handle any errors during message retrieval
                print(f"Error retrieving messages: {str(e)}")
                return {
                    "messages": [],
                    "total_count": 0,
                    "error": str(e)
                }

@mcp.tool()
def list_conversations() -> Dict[str, Any]:
    """List all conversations in the Messages database.
    
    Returns:
        Dictionary containing the list of conversations with participant info and last message dates
    """
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Messages database not found at: {DB_PATH}")
        
    # Suppress stdout to hide progress bars
    with contextlib.redirect_stdout(io.StringIO()):
        with MessageDBConnection() as db:
            # Get formatted list of all chats
            conversations = db.chats.get_chats()
            
            # Split into list and count total
            conversation_list = conversations.split('\n')
            
            return {
                "conversations": conversation_list,
                "total_count": len(conversation_list)
            }
