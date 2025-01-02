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
            # Extract text from attributed_body
            text_data = attributed_body.split(b'NSNumber')[0]
            text_data = text_data.split(b'NSString')[1]
            text_data = text_data.split(b'NSDictionary')[0]
            text_data = text_data[6:-12]
            
            # Handle various text encodings
            if b'\x01' in text_data:
                text_data = text_data.split(b'\x01')[1]
            if b'\x02' in text_data:
                text_data = text_data.split(b'\x02')[1]
            if b'\x00' in text_data:
                text_data = text_data.split(b'\x00')[1]
            if b'\x86' in text_data:
                text_data = text_data.split(b'\x86')[0]
                
            return text_data.decode('utf-8', errors='replace')
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
            
            # Filter messages by date if specified
            filtered_messages = []
            for msg in messages.message_list:
                # Parse message date as local time and convert to UTC
                msg_dt = datetime.strptime(msg.date, "%Y-%m-%d %H:%M:%S").astimezone(timezone.utc)
                msg_date = msg_dt.date()
                
                if start_date:
                    start_dt = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
                    if msg_date < start_dt.date():
                        continue
                        
                if end_date:
                    end_dt = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)
                    if msg_date > end_dt.date():
                        continue
                        
                # Handle attachments
                attachments = []
                if msg.attachments:
                    downloads_dir = Path.home() / "Downloads"
                    for att in msg.attachments:
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
                    "text": msg.text,
                    "date": msg_dt.strftime("%Y-%m-%d %H:%M:%SZ"),
                    "is_from_me": msg.is_from_me,
                    "has_attachments": bool(attachments),
                    "attachments": attachments
                })
            
            return {
                "messages": filtered_messages,
                "total_count": len(filtered_messages)
            }

@mcp.tool()
def get_chat_transcript_beta(
    phone_number: str,
    start_date: str = None,
    end_date: str = None
) -> Dict[str, Any]:
    """Get chat transcript for a specific phone number within a date range.
    
    Args:
        phone_number: Phone number to get transcript for (raw input)
        start_date: Optional start date in ISO format (YYYY-MM-DD)
        end_date: Optional end date in ISO format (YYYY-MM-DD)
    
    Returns:
        Dictionary containing the chat transcript data
    """
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Messages database not found at: {DB_PATH}")

    # Suppress stdout to hide progress bars
    with contextlib.redirect_stdout(io.StringIO()):
        with MessageDBConnection() as db:
            # First try direct database query to check if messages exist
            cursor = db.connection
            query = """
            SELECT COUNT(*) 
            FROM message m 
            JOIN handle h ON m.handle_id = h.ROWID 
            WHERE h.id = ?
            """
            cursor.execute(query, (phone_number,))
            count = cursor.fetchone()[0]
            
            debug_info = {
                "direct_query_count": count,
                "handle_search": {}
            }
            
            # Normalize input phone number
            normalized_input = normalize_phone_number(phone_number)
            debug_info["normalized_input"] = normalized_input
            
            # Initialize matching handles list
            matching_handles = []
            
            # Validate and normalize phone number
            try:
                parsed_number = phonenumbers.parse(phone_number, "US")
                if not phonenumbers.is_valid_number(parsed_number):
                    return {
                        "messages": [],
                        "total_count": 0,
                        "error": f"Invalid phone number: {phone_number}",
                        "debug": debug_info
                    }
                # Format to E.164 format
                formatted_number = phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)
                debug_info["formatted_number"] = formatted_number
            except phonenumbers.NumberParseException as e:
                return {
                    "messages": [],
                    "total_count": 0,
                    "error": f"Invalid phone number format: {e}",
                    "debug": debug_info
                }

            # Only match phone number handles (no email addresses)
            for number, handles in db.handles.numbers.items():
                try:
                    # Check if handle is a valid phone number
                    parsed_handle = phonenumbers.parse(number, "US")
                    if phonenumbers.is_valid_number(parsed_handle):
                        handle_e164 = phonenumbers.format_number(parsed_handle, phonenumbers.PhoneNumberFormat.E164)
                        if handle_e164 == formatted_number:
                            matching_handles.extend(handles)
                            debug_info["handle_search"]["exact_match"] = number
                except phonenumbers.NumberParseException:
                    # Skip handles that aren't valid phone numbers
                    continue
            
            if not matching_handles:
                return {
                    "messages": [],
                    "total_count": 0,
                    "error": f"No matching handles found for: {phone_number}",
                    "debug": debug_info
                }
            
            # Get unique handle IDs and their numbers
            handle_numbers = []
            seen = set()
            for handle in matching_handles:
                if handle.number not in seen:
                    handle_numbers.append(handle.number)
                    seen.add(handle.number)
            
            debug_info["handle_numbers"] = handle_numbers
            
            # Try direct message query first
            messages = []
            for handle_id in handle_numbers:
                query = """
                SELECT m.ROWID, m.guid,
                       datetime(m.date/1000000000 + strftime('%s', '2001-01-01'),'unixepoch') as date,
                       m.is_from_me, m.handle_id, m.text, m.attributedBody, m.message_summary_info
                FROM message m 
                JOIN handle h ON m.handle_id = h.ROWID 
                WHERE h.id = ?
                ORDER BY m.date ASC
                """
                cursor.execute(query, (handle_id,))
                rows = cursor.fetchall()
                for row in rows:
                    # Extract message text from various possible storage locations
                    text = extract_message_text(row[5], row[6], row[7])
                    
                    messages.append({
                        "rowid": row[0],
                        "guid": row[1],
                        "date": row[2],
                        "is_from_me": bool(row[3]),
                        "handle_id": row[4],
                        "text": text
                    })
            
            debug_info["direct_messages_count"] = len(messages)
            
            # Set default date range to last 7 days if not specified
            if not start_date and not end_date:
                end_dt = datetime.now(timezone.utc)
                start_dt = end_dt - timedelta(days=7)
                start_date = start_dt.strftime("%Y-%m-%d")
                end_date = end_dt.strftime("%Y-%m-%d")

            # Filter messages by date if specified
            filtered_messages = []
            for msg in messages:
                # Parse message date as UTC since we removed localtime from SQL query
                msg_dt = datetime.strptime(msg["date"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                msg_date = msg_dt.date()
                
                if start_date:
                    start_dt = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
                    if msg_date < start_dt.date():
                        continue
                        
                if end_date:
                    end_dt = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)
                    if msg_date > end_dt.date():
                        continue
                
                # Get handle info
                handle_info = None
                if msg["handle_id"] and msg["handle_id"] in db.handles.handles:
                    handle = db.handles.handles[msg["handle_id"]]
                    handle_info = {
                        'id': handle.number,
                        'name': handle.name if handle.name != handle.number else None
                    }
                
                # Get attachments for this message
                attachments = []
                query = """
                SELECT a.filename, a.mime_type, a.transfer_name
                FROM attachment a
                JOIN message_attachment_join maj ON a.ROWID = maj.attachment_id
                WHERE maj.message_id = ?
                """
                cursor.execute(query, (msg["rowid"],))
                attachment_rows = cursor.fetchall()
                
                if attachment_rows:
                    downloads_dir = Path.home() / "Downloads"
                    for att_row in attachment_rows:
                        if att_row[0]:  # If filename exists
                            try:
                                src_path = Path(att_row[0])
                                if src_path.exists():
                                    new_path = copy_and_convert_attachment(src_path, downloads_dir)
                                    if new_path:  # Only add if copy/conversion succeeded
                                        attachments.append({
                                            'path': str(new_path),
                                            'mime_type': 'image/jpeg' if src_path.suffix.lower() == '.heic' else att_row[1],
                                            'transfer_name': att_row[2]
                                        })
                            except Exception as e:
                                print(f"Failed to copy attachment: {e}")

                filtered_messages.append({
                    "text": msg["text"],
                    "date": msg_dt.strftime("%Y-%m-%d %H:%M:%SZ"),
                    "is_from_me": msg["is_from_me"],
                    "handle": handle_info,
                    "has_attachments": bool(attachments),
                    "attachments": attachments,
                    "rowid": msg["rowid"]
                })
            
            return {
                "messages": filtered_messages,
                "total_count": len(filtered_messages),
                "matched_handles": [
                    {
                        'id': h.number,
                        'name': h.name if h.name != h.number else None
                    }
                    for h in matching_handles
                ],
                "debug": debug_info
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
