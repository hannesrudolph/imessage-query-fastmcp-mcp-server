#!/usr/bin/env -S uv run --script
# ABOUTME: MCP server that provides safe access to macOS iMessage database through the FastMCP framework
# ABOUTME: Exposes iMessage conversation data to LLMs with proper validation and safety measures
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "fastmcp==0.4.1",
#     "imessagedb==1.4.7",
#     "phonenumbers==8.13.52",
# ]
# ///

from pathlib import Path
import os
import subprocess
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

def check_full_disk_access() -> bool:
    """Check if the current application has Full Disk Access."""
    try:
        # Try to read the Messages directory - this requires Full Disk Access
        messages_dir = Path.home() / "Library" / "Messages"
        return os.access(messages_dir, os.R_OK)
    except:
        return False

def open_privacy_settings():
    """Open macOS Privacy & Security settings to grant Full Disk Access."""
    try:
        subprocess.run([
            "open", 
            "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"
        ], check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def request_full_disk_access(app_name: str, bundle_id: str = "") -> bool:
    """Request Full Disk Access permission for the specified application.
    
    Args:
        app_name: Human-readable application name
        bundle_id: macOS bundle identifier (optional)
        
    Returns:
        True if System Preferences was opened successfully, False otherwise
    """
    try:
        # Try to use AppleScript to navigate to Full Disk Access settings
        if bundle_id:
            script = '''
            tell application "System Events"
                tell application "System Preferences" to activate
                tell application "System Preferences"
                    set current pane to pane "com.apple.preference.security"
                end tell
                delay 1
                tell window 1 of application "System Preferences"
                    click button "Privacy" of tab group 1
                    delay 1
                    select row "Full Disk Access" of table 1 of scroll area 1 of tab group 1
                    delay 1
                    click button "+" of group 1 of tab group 1
                    delay 1
                end tell
            end tell
            '''
            
            result = subprocess.run(
                ["osascript", "-e", script], 
                capture_output=True, 
                text=True
            )
            return result.returncode == 0
        else:
            # Fallback to just opening the settings
            return open_privacy_settings()
            
    except:
        # Fallback to just opening the settings
        return open_privacy_settings()

def _create_permission_error_message(app_name: str, bundle_id: str, auto_opened: bool) -> str:
    """Create a detailed permission error message with app-specific guidance."""
    error_msg = (
        f"❌ Full Disk Access permission required for {app_name} to read iMessage database.\n\n"
        f"To grant permission:\n"
        f"1. Open System Preferences → Privacy & Security → Full Disk Access\n"
        f"2. Click the '+' button and add '{app_name}'\n"
        f"3. Restart {app_name} after granting permission\n\n"
    )
    
    # Add app-specific restart guidance
    if app_name in MCP_CLIENTS:
        error_msg += f"Note: You may need to quit {app_name} completely (Cmd+Q) and relaunch."
    
    # Add status of automatic opening
    if auto_opened:
        error_msg += "\n✅ System Preferences opened automatically. Please add the application and restart."
    else:
        error_msg += "\n⚠️  Please manually open System Preferences → Privacy & Security → Full Disk Access"
    
    return error_msg

def _validate_database_access() -> None:
    """Validate database exists and permissions are granted.
    
    Raises:
        FileNotFoundError: If Messages database doesn't exist
        PermissionError: If Full Disk Access permission is not granted
    """
    # Check database exists
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Messages database not found at: {DB_PATH}. "
            "Make sure Messages app has been used and iMessage is enabled."
        )

    # Check for Full Disk Access permission
    if not check_full_disk_access():
        app_name, bundle_id = get_parent_app_name()
        
        # Try to automatically open permission settings
        auto_opened = False
        try:
            auto_opened = request_full_disk_access(app_name, bundle_id)
        except:
            pass
        
        error_msg = _create_permission_error_message(app_name, bundle_id, auto_opened)
        raise PermissionError(error_msg)

# Known MCP client applications with their bundle IDs
MCP_CLIENTS = {
    "Claude Desktop": "com.anthropic.claude",
    "Cursor": "com.todesktop.230313mzl4w4u92", 
    "VS Code": "com.microsoft.VSCode",
}

TERMINAL_APPS = {
    "Terminal": "com.apple.Terminal",
    "iTerm2": "com.googlecode.iterm2",
    "kitty": "net.kovidgoyal.kitty",
    "Alacritty": "org.alacritty",
    "Warp": "dev.warp.Warp-Stable",
    "Hyper": "co.zeit.hyper"
}

def _find_running_mcp_clients() -> tuple[str, str] | None:
    """Scan running processes for known MCP clients."""
    try:
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
        if result.returncode != 0:
            return None
            
        processes = result.stdout.lower()
        
        # Check for each known MCP client
        if "claude" in processes and ".app" in processes:
            return ("Claude Desktop", MCP_CLIENTS["Claude Desktop"])
        elif "cursor" in processes and ".app" in processes:
            return ("Cursor", MCP_CLIENTS["Cursor"])
        elif ("visual studio code" in processes or "code" in processes) and ".app" in processes:
            return ("VS Code", MCP_CLIENTS["VS Code"])
            
        return None
    except:
        return None

def _walk_process_tree() -> tuple[str, str]:
    """Walk up the process tree to identify the parent application."""
    try:
        parent_pid = os.getppid()
        fallback_name = ("unknown application", "")
        
        # Check up to 5 levels up the process tree
        for level in range(5):
            if level == 0:
                pid_to_check = parent_pid
            else:
                # Get parent process ID
                result = subprocess.run([
                    "ps", "-p", str(pid_to_check), "-o", "ppid="
                ], capture_output=True, text=True)
                if result.returncode != 0:
                    break
                try:
                    pid_to_check = int(result.stdout.strip())
                except ValueError:
                    break
            
            # Get process name and command
            result = subprocess.run([
                "ps", "-p", str(pid_to_check), "-o", "comm=,command="
            ], capture_output=True, text=True)
            if result.returncode != 0 or not result.stdout.strip():
                continue
                
            parts = result.stdout.strip().split(None, 1)
            if len(parts) < 2:
                continue
                
            app_name, command = parts[0], parts[1]
            
            # Check for MCP clients in command path
            command_lower = command.lower()
            if "claude" in command_lower and ".app" in command_lower:
                return ("Claude Desktop", MCP_CLIENTS["Claude Desktop"])
            elif "cursor" in command_lower and ".app" in command_lower:
                return ("Cursor", MCP_CLIENTS["Cursor"])
            elif ("visual studio code" in command_lower or "code" in command_lower) and ".app" in command_lower:
                return ("VS Code", MCP_CLIENTS["VS Code"])
            
            # Check known applications by process name
            all_apps = {**MCP_CLIENTS, **TERMINAL_APPS}
            for app_display_name, bundle_id in all_apps.items():
                if app_name.lower() in app_display_name.lower().replace(" ", ""):
                    if level == 0:  # Save first-level fallback
                        fallback_name = (app_display_name, bundle_id)
                    if app_display_name in MCP_CLIENTS:
                        return (app_display_name, bundle_id)
        
        return fallback_name
    except:
        return ("unknown application", "")

def get_parent_app_name() -> tuple[str, str]:
    """Get the name and bundle ID of the parent application (MCP client or terminal).
    
    Returns:
        Tuple of (app_name, bundle_id) where app_name is human-readable 
        and bundle_id is the macOS bundle identifier.
    """
    # First, try to find running MCP clients directly
    mcp_client = _find_running_mcp_clients()
    if mcp_client:
        return mcp_client
    
    # Fallback: Walk up the process tree
    return _walk_process_tree()


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
        # Parameters are required by context manager protocol but unused
        del exc_type, exc_val, exc_tb

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

    # Validate database access and permissions
    _validate_database_access()

    # Suppress stdout to hide progress bars
    with contextlib.redirect_stdout(io.StringIO()):
        try:
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
        except Exception as e:
            # Check if this is a permission-related database error
            error_str = str(e).lower()
            if "unable to open database file" in error_str or "operation not permitted" in error_str:
                app_name, bundle_id = get_parent_app_name()
                error_msg = _create_permission_error_message(app_name, bundle_id, False)
                error_msg += f"\n\nOriginal error: {e}"
                raise PermissionError(error_msg)
            else:
                # Re-raise other exceptions as-is
                raise

# Run the server
if __name__ == "__main__":
    mcp.run()
