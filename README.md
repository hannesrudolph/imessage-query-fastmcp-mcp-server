[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/hannesrudolph-imessage-query-fastmcp-mcp-server-badge.png)](https://mseep.ai/app/hannesrudolph-imessage-query-fastmcp-mcp-server)

# iMessage Query MCP Server

An MCP server that provides safe access to your iMessage database through Model Context Protocol (MCP). This server is built with the FastMCP framework and the imessagedb library, enabling LLMs to query and analyze iMessage conversations with proper phone number validation and automatic macOS permission handling.

## 📋 System Requirements

- macOS (required for iMessage database access)
- Python 3.12+ (required for modern type hints)
- **uv** (modern Python package manager)
- **Full Disk Access permission** for your MCP client (Claude Desktop, Cursor, VS Code, etc.)

## 📦 Dependencies

### Install uv (Required)

This project uses `uv` for fast, reliable Python package management. Install it first:

```bash
# Install uv using Homebrew (recommended)
brew install uv

# Or install using the official installer
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Python Dependencies

The script automatically manages its dependencies using the embedded metadata. No separate installation needed! Dependencies include:

- **fastmcp**: Framework for building Model Context Protocol servers
- **imessagedb**: Python library for accessing and querying the macOS Messages database
- **phonenumbers**: Google's phone number handling library for proper number validation and formatting

All dependencies are automatically installed when the script runs via `uv`.

## 📑 Table of Contents
- [System Requirements](#-system-requirements)
- [Dependencies](#-dependencies)
- [MCP Tools](#%EF%B8%8F-mcp-tools)
- [Getting Started](#-getting-started)
- [Installation Options](#-installation-options)
  - [Claude Desktop](#option-1-install-for-claude-desktop)
  - [Cline VSCode Plugin](#option-2-install-for-cline-vscode-plugin)
- [macOS Permissions Setup](#-macos-permissions-setup)
- [Safety Features](#-safety-features)
- [Development Documentation](#-development-documentation)
- [Environment Variables](#%EF%B8%8F-environment-variables)

## 🛠️ MCP Tools

The server exposes the following tools to LLMs:

### get_chat_transcript
Retrieve message history for a specific phone number with optional date filtering.

**Parameters:**
- `phone_number` (required): Phone number in any format (E.164 format preferred)
- `start_date` (optional): Start date in ISO format (YYYY-MM-DD)
- `end_date` (optional): End date in ISO format (YYYY-MM-DD)

**Features:**
- Automatic phone number validation and formatting
- Message text and timestamps
- Attachment information with missing file detection
- Date range filtering (defaults to last 7 days if no dates specified)
- Sender identification (is_from_me flag)

## 🚀 Getting Started

Clone the repository:

```bash
git clone https://github.com/hannesrudolph/imessage-query-fastmcp-mcp-server.git
cd imessage-query-fastmcp-mcp-server
```

## 📦 Installation Options

You can install this MCP server in Claude Desktop, Cline VSCode plugin, or any other MCP client. Choose the option that best suits your needs.

### Option 1: Claude Desktop

1. **Find your Claude Desktop config file:**
   - **Location**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Create the file if it doesn't exist

2. **Add the server configuration:**

```json
{
  "mcpServers": {
    "imessage-query": {
      "command": "/full/path/to/imessage-query-server.py"
    }
  }
}
```

3. **Replace the path** with the full path to your cloned repository (e.g., `/Users/username/Projects/imessage-query-fastmcp-mcp-server/imessage-query-server.py`)

4. **Restart Claude Desktop** completely (Cmd+Q, then relaunch)

### Option 2: Cline VSCode Plugin

To use this server with the [Cline VSCode plugin](http://cline.bot):

1. In VSCode, click the server icon (☰) in the Cline plugin sidebar
2. Click the "Edit MCP Settings" button (✎)
3. Add the following configuration to the settings file:

```json
{
  "imessage-query": {
    "command": "/full/path/to/imessage-query-server.py"
  }
}
```

4. **Replace the path** with the full path to your cloned repository

### Option 3: Other MCP Clients

For other MCP clients, use the direct script path as the command:

```
/full/path/to/imessage-query-server.py
```

The script's shebang (`#!/usr/bin/env -S uv run --script`) handles dependency management automatically.

> **Note**: This simplified configuration replaces the previous FastMCP installation method. The script is now self-contained and manages its own dependencies through `uv`.

## 🔐 macOS Permissions Setup

This server requires **Full Disk Access** permission to read the iMessage database. The server includes intelligent permission detection and will guide you through the setup process.

### Automatic Permission Detection

When you first use the server, it will:
1. **Detect your MCP client** (Claude Desktop, Cursor, VS Code, etc.)
2. **Check for Full Disk Access** permission
3. **Automatically open System Preferences** to the correct settings panel
4. **Provide step-by-step instructions** specific to your application

### Manual Permission Setup

If automatic detection doesn't work, follow these steps:

1. **Open System Preferences** → **Privacy & Security** → **Full Disk Access**
2. **Click the lock icon** and enter your password to make changes
3. **Click the '+' button** to add an application
4. **Navigate to and select your MCP client:**
   - **Claude Desktop**: `/Applications/Claude.app`
   - **Cursor**: `/Applications/Cursor.app`
   - **VS Code**: `/Applications/Visual Studio Code.app`
5. **Restart your MCP client** completely (Cmd+Q, then relaunch)

### Common Issues

- **Permission denied errors**: Make sure you've restarted your MCP client after granting permission
- **"uv" instead of app name**: The server will auto-detect your actual MCP client and provide correct instructions
- **Database not found**: Ensure you've used the Messages app and iMessage is enabled

### Security Note

This server only requires **read access** to your iMessage database. It cannot modify, delete, or send messages.

## 🔒 Safety Features

- **Read-only access** to the iMessage database (cannot modify, delete, or send messages)
- **Phone number validation** using Google's phonenumbers library with proper E.164 formatting
- **Safe attachment handling** with missing file detection and metadata extraction
- **Date range validation** to prevent invalid queries
- **Progress output suppression** for clean JSON responses in MCP protocol
- **Intelligent permission detection** with automatic System Preferences navigation
- **MCP client identification** for accurate permission guidance

## 📚 Development Documentation

The repository includes comprehensive documentation for development:

- `dev_docs/imessagedb-documentation.txt`: Complete documentation about the iMessage database structure and the imessagedb library's capabilities
- `dev_docs/fastmcp-documentation.txt`: FastMCP framework details and MCP tool development
- `dev_docs/mcp-documentation.txt`: Model Context Protocol specification

This documentation serves as context when developing features and can be used with LLMs to assist in development.

## ⚙️ Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SQLITE_DB_PATH` | Custom path to iMessage database | `~/Library/Messages/chat.db` |

The server automatically locates the iMessage database in the default macOS location. The environment variable is only needed for custom database locations.

## 🔧 Advanced Usage

### Custom Database Path

If you need to use a custom database path:

```bash
export SQLITE_DB_PATH="/path/to/custom/chat.db"
```

### Testing the Server

Test the server directly using mcptools (github.com/f/mcptools):

```bash
# Navigate to the repository directory
cd /path/to/imessage-query-fastmcp-mcp-server

# List available tools
mcp tools ./imessage-query-server.py

# Test a tool call
mcp call get_chat_transcript ./imessage-query-server.py -p '{"phone_number": "+1234567890"}'
```

The script will automatically handle dependency installation via `uv` when first run.

## 🐛 Troubleshooting

### Common Error Messages

**"❌ Full Disk Access permission required"**
- Follow the [macOS Permissions Setup](#-macos-permissions-setup) section
- Ensure you've restarted your MCP client after granting permission

**"Messages database not found"**
- Make sure you've used the Messages app at least once
- Verify iMessage is enabled in Messages preferences

**"Invalid phone number"**
- Phone numbers are validated using Google's phonenumbers library
- Try using E.164 format (e.g., "+1234567890")
- US numbers without country code will be assumed to be US numbers

### Getting Help

If you encounter issues:
1. Check the error message for specific guidance
2. Ensure your MCP client has Full Disk Access permission
3. Verify the Messages app has been used and iMessage is enabled
4. Try testing the server directly with mcptools (see Advanced Usage)
