# iMessage Query MCP Server

An MCP server that provides safe access to your iMessage database through Model Context Protocol (MCP). This server is built with the FastMCP framework and the imessagedb library, enabling LLMs to query and analyze iMessage conversations with proper phone number validation and attachment handling.

## 📋 System Requirements

- macOS (required for iMessage database access)
- Python 3.6+

## 📦 Dependencies

Install all required dependencies:

```bash
# Using pip
pip install -r requirements.txt
```

### Required Packages
- **fastmcp**: Framework for building Model Context Protocol servers
- **imessagedb**: Python library for accessing and querying the macOS Messages database
- **phonenumbers**: Google's phone number handling library for proper number validation and formatting

All dependencies are specified in `requirements.txt` for easy installation.

## 📑 Table of Contents
- [System Requirements](#-system-requirements)
- [Dependencies](#-dependencies)
- [MCP Tools](#%EF%B8%8F-mcp-tools)
- [Getting Started](#-getting-started)
- [Installation Options](#-installation-options)
  - [Claude Desktop](#option-1-install-for-claude-desktop)
  - [Cline VSCode Plugin](#option-2-install-for-cline-vscode-plugin)
- [Safety Features](#-safety-features)
- [Development Documentation](#-development-documentation)
- [Environment Variables](#%EF%B8%8F-environment-variables)

## 🛠️ MCP Tools

The server exposes the following tools to LLMs:

### get_chat_transcript
Retrieve message history for a specific phone number with optional date filtering. Includes:
- Message text and timestamps
- Attachment information (if any)
- Proper phone number validation
- Date range filtering

## 🚀 Getting Started

Clone the repository:

```bash
git clone https://github.com/hannesrudolph/imessage-query-fastmcp-mcp-server.git
cd imessage-query-fastmcp-mcp-server
```

## 📦 Installation Options

You can install this MCP server in either Claude Desktop or the Cline VSCode plugin. Choose the option that best suits your needs.

### Option 1: Install for Claude Desktop

Install using FastMCP:

```bash
fastmcp install imessage-query-server.py --name "iMessage Query"
```

### Option 2: Install for Cline VSCode Plugin

To use this server with the [Cline VSCode plugin](http://cline.bot):

1. In VSCode, click the server icon (☰) in the Cline plugin sidebar
2. Click the "Edit MCP Settings" button (✎)
3. Add the following configuration to the settings file:

```json
{
  "imessage-query": {
    "command": "uv",
    "args": [
      "run",
      "--with",
      "fastmcp",
      "fastmcp",
      "run",
      "/path/to/repo/imessage-query-server.py"
    ]
  }
}
```

Replace `/path/to/repo` with the full path to where you cloned this repository (e.g., `/Users/username/Projects/imessage-query-fastmcp-mcp-server`)

## 🔒 Safety Features

- Read-only access to the iMessage database
- Phone number validation using the phonenumbers library
- Safe attachment handling with missing file detection
- Date range validation
- Progress output suppression for clean JSON responses

## 📚 Development Documentation

The repository includes documentation files for development:

- `dev_docs/imessagedb-documentation.txt`: Contains comprehensive documentation about the iMessage database structure and the imessagedb library's capabilities.

This documentation serves as context when developing features and can be used with LLMs to assist in development.

## ⚙️ Environment Variables

No environment variables are required as the server automatically locates the iMessage database in the default macOS location.