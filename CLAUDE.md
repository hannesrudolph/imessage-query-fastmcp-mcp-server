# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an MCP (Model Context Protocol) server that provides safe access to macOS iMessage database through the FastMCP framework. The server exposes iMessage conversation data to LLMs with proper validation and safety measures.

### Architecture

- **Single-file MCP server**: `imessage-query-server.py` contains the entire server implementation
- **FastMCP framework**: Uses `@mcp.tool()` decorators to expose functions as MCP tools
- **Database access**: Uses `imessagedb` library to read from macOS Messages database (`~/Library/Messages/chat.db`)
- **Phone number validation**: Leverages Google's `phonenumbers` library for proper number formatting and validation
- **Singleton database context**: `DatabaseContext` class manages database connections across tool calls

### Key Components

- `DatabaseContext`: Singleton pattern for managing database connections
- `MessageDBConnection`: Context manager for safe database access
- `get_chat_transcript`: Main MCP tool for retrieving message history with date filtering

## Development Commands

### Installation and Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Install as MCP server for Claude Desktop
fastmcp install imessage-query-server.py --name "iMessage Query"

# Run directly for testing
python imessage-query-server.py
```

### Testing the Server
```bash
# Test with FastMCP development tools
fastmcp dev imessage-query-server.py
```

## Implementation Guidelines

### MCP Tool Development
- Use `@mcp.tool()` decorator to expose functions
- Always include comprehensive docstrings with Args/Returns/Raises sections
- Handle database connections through `MessageDBConnection` context manager
- Suppress stdout using `contextlib.redirect_stdout(io.StringIO())` to prevent progress output

### Phone Number Handling
- Always validate phone numbers using `phonenumbers.parse()` and `phonenumbers.is_valid_number()`
- Format to E.164 format using `phonenumbers.format_number()`
- Default to "US" region for parsing when no region specified

### Database Operations
- Use singleton `DatabaseContext` for connection management
- Access database through `MessageDBConnection` context manager
- Database path defaults to `~/Library/Messages/chat.db` but can be overridden with `SQLITE_DB_PATH` environment variable
- Always check database file existence before operations

### Safety Considerations
- Server provides read-only access to iMessage database
- All attachments are handled safely with missing file detection
- Date range validation prevents invalid queries
- Progress output is suppressed for clean JSON responses

## Development Documentation

Reference files in `dev_docs/` contain comprehensive documentation:
- `imessagedb-documentation.txt`: iMessage database structure and library capabilities
- `fastmcp-documentation.txt`: FastMCP framework details
- `mcp-documentation.txt`: Model Context Protocol specification