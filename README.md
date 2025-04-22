# MCP Client for Ollama

A simple Python client implementation for interacting with Model Context Protocol (MCP) servers using Ollama models.

## Overview

This project provides a Python-based client that connects to an MCP server and uses Ollama to process queries, enabling tool use capabilities. The client establishes a connection to one or more MCP servers, sends queries to Ollama, and handles any tool calls that the model might make.

This client was created by adapting the Python example for MCP client from the [Model Context Protocol quickstart guide](https://modelcontextprotocol.io/quickstart/client) and modifying it to work with Ollama instead of the Anthropic SDK.

## Key Features

- Connect to multiple MCP servers simultaneously
- Interactive colorful terminal interface using Rich
- Tool selection and management during chat
- Chat history tracking
- Support for both Python and JavaScript MCP servers
- Auto-discovery of servers from Claude's configuration
- List and switch Ollama models during a session

## Requirements

- Python 3.8+
- Ollama running locally
- UV package manager

## Installation

```bash
uv venv
source .venv/bin/activate
uv pip install .
```

## Usage

Run the client with:

```bash
uv run client.py [options]
```

### Command-line Arguments

#### Server Options:
- `--mcp-server`: Path to one or more MCP server scripts (.py or .js). Can be specified multiple times.
- `--servers-json`: Path to a JSON file with server configurations
- `--auto-discovery`: Auto-discover servers from Claude's default config file

#### Model Options:
- `--model`: Ollama model to use (default: "qwen2.5:latest")

### Examples

Connect to a single server:
```bash
uv run client.py --mcp-server /path/to/weather.py --model llama3:latest
```

Connect to multiple servers:
```bash
uv run client.py --mcp-server /path/to/weather.py --mcp-server /path/to/filesystem.js --model qwen2:latest
```

Use a JSON configuration file:
```bash
uv run client.py --servers-json /path/to/servers.json --model llama3:latest
```

Use Claude's default server configuration:
```bash
uv run client.py --auto-discovery --model llama3:latest
```

### Interactive Commands

During the chat session, the following commands are available:

| Command | Shortcut | Description |
|---------|----------|-------------|
| `help` | `h` | Display help and available commands |
| `tools` | `t` | Open the tool selection interface |
| `model` | `m` | List and select a different Ollama model |
| `quit` | `q` | Exit the client |

In the tool selection interface:
- Enter numbers separated by commas (e.g. `1,3,5`) to toggle specific tools
- `a` or `all` - Enable all tools
- `n` or `none` - Disable all tools
- `d` or `desc` - Show/hide tool descriptions
- `s` or `save` - Save changes and return to chat
- `q` or `quit` - Cancel changes and return to chat

In the model selection interface:
- Enter the number of the model you want to use
- `q` or `quit` - Cancel and return to chat

### Server Configuration Format

The JSON configuration file should follow this format:

```json
{
  "mcpServers": {
    "server-name": {
      "command": "command-to-run",
      "args": ["arg1", "arg2", "..."],
      "env": {
        "ENV_VAR1": "value1",
        "ENV_VAR2": "value2"
      },
      "disabled": false
    }
  }
}
```

Claude's configuration file is typically located at:
`~/Library/Application Support/Claude/claude_desktop_config.json`

## Development

### How Tool Calls Work

1. The client sends your query to Ollama with a list of available tools
2. If Ollama decides to use a tool, the client:
   - Extracts the tool name and arguments
   - Calls the appropriate MCP server with these arguments
   - Sends the tool result back to Ollama
   - Shows the final response

### Adding Custom MCP Servers

You can create your own MCP server by:
1. Creating a Python or JavaScript file that implements the MCP protocol
2. Adding it to the client with `--mcp-server` or through a JSON configuration

For MCP server development, refer to the MCP specification.
