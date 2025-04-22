# MCP Client for Ollama

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
![Tool Terminal Interface](https://img.shields.io/badge/Tool-Terminal%20Interface-red.svg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)


A powerful Python client for interacting with Model Context Protocol (MCP) servers using Ollama models, enabling tool use for local LLMs.



## Overview

This project provides a robust Python-based client that connects to one or more Model Context Protocol (MCP) servers and uses Ollama to process queries with tool use capabilities. The client establishes connections to MCP servers, sends queries to Ollama models, and handles the tool calls the model makes.

This implementation was adapted from the [Model Context Protocol quickstart guide](https://modelcontextprotocol.io/quickstart/client) and customized to work with Ollama, providing a user-friendly interface for interacting with LLMs that support function calling.

## Key Features

- 🌐 **Multi-Server Support**: Connect to multiple MCP servers simultaneously
- 🎨 **Rich Terminal Interface**: Colorful, interactive console UI with Rich library
- 🛠️ **Tool Management**: Enable/disable specific tools or entire servers during a session
- 🧠 **Context Management**: Control conversation memory with configurable context retention
- 🔄 **Cross-Language Support**: Work with Python and JavaScript MCP servers
- 🔍 **Auto-Discovery**: Automatically find and use Claude's existing MCP server configurations
- 🔄 **Model Switching**: List and switch between any installed Ollama model during a session
- 💾 **Configuration Management**: Save and load tool configurations between sessions
- 📊 **Context Statistics**: Track token usage and conversation history

## Requirements

- **Python 3.8+** (Python 3.10 recommended)
- **Ollama** running locally ([Installation guide](https://ollama.com/download))
- **UV package manager** ([Installation guide](https://github.com/astral-sh/uv))

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/jonigl/mcp-client-for-ollama.git
   cd mcp-client-for-ollama
   ```

2. Create and activate a virtual environment with UV:
   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install the package:
   ```bash
   uv pip install .
   ```

4. Ensure Ollama is running:
   ```bash
   ollama serve
   ```

## Usage

Run the client with:

```bash
uv run client.py [options]
```

If you don't provide any options, the client will use auto-discovery mode to find MCP servers from Claude's configuration.

### Command-line Arguments

#### Server Options:
- `--mcp-server`: Path to one or more MCP server scripts (.py or .js). Can be specified multiple times.
- `--servers-json`: Path to a JSON file with server configurations.
- `--auto-discovery`: Auto-discover servers from Claude's default config file (default behavior if no other options provided).

#### Model Options:
- `--model`: Ollama model to use (default: "qwen2.5:latest")

### Usage Examples

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

## Interactive Commands

During the chat session, the following commands are available:

| Command | Shortcut | Description |
|---------|----------|-------------|
| `help` | `h` | Display help and available commands |
| `tools` | `t` | Open the tool selection interface |
| `model` | `m` | List and select a different Ollama model |
| `context` | `c` | Toggle context retention (on/off) |
| `clear` | `cc` | Clear conversation history and context |
| `contextinfo` | `ci` | Toggle displaying context statistics after each message |
| `cls` | `clear-screen` | Clear the terminal screen |
| `save-config` | `sc` | Save current tool and model configuration to a file |
| `load-config` | `lc` | Load tool and model configuration from a file |
| `reset-config` | `rc` | Reset configuration to defaults (all tools enabled) |
| `quit` | `q` | Exit the client |

### Tool Selection Interface

The tool selection interface allows you to enable or disable specific tools:

- Enter **numbers** separated by commas (e.g. `1,3,5`) to toggle specific tools
- Enter **ranges** of numbers (e.g. `5-8`) to toggle multiple consecutive tools
- Enter **S + number** (e.g. `S1`) to toggle all tools in a specific server
- `a` or `all` - Enable all tools
- `n` or `none` - Disable all tools
- `d` or `desc` - Show/hide tool descriptions
- `s` or `save` - Save changes and return to chat
- `q` or `quit` - Cancel changes and return to chat

### Model Selection Interface

The model selection interface shows all available models in your Ollama installation:

- Enter the **number** of the model you want to use
- `s` or `save` - Save the model selection and return to chat
- `q` or `quit` - Cancel the model selection and return to chat

## Configuration Management

The client supports saving and loading tool configurations between sessions:

- When using `save-config`, you can provide a name for the configuration or use the default
- Configurations are stored in `~/.config/mcp-client-for-ollama/` directory
- The default configuration is saved as `~/.config/mcp-client-for-ollama/config.json`
- Named configurations are saved as `~/.config/mcp-client-for-ollama/{name}.json`

The configuration saves:
- Current model selection
- Enabled/disabled status of all tools
- Context retention settings

## Server Configuration Format

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

## Context Management

The client provides several ways to manage conversation context:

- **Context Retention**: Toggle with the `context` command to enable/disable conversation memory
- **Context Statistics**: View token usage and conversation history with the `contextinfo` command
- **Context Clearing**: Clear the conversation history with the `clear` command

## Advanced Usage

### Creating Custom MCP Servers

You can create your own MCP server by:
1. Creating a Python or JavaScript file that implements the MCP protocol
2. Adding it to the client with `--mcp-server` or through a JSON configuration

Example Python MCP server:

```python
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("weather")

# Register a tool
@mcp.tool()
async def get_forecast(city: str) -> str:
    """Get weather forecast for a location.

    Args:
        city: str: The name of the city.
    """    
    # Simulate a weather forecast
    forecast = f"The weather in {city} is sunny with a high of 25°C."
    return forecast

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')
```

### How Tool Calls Work

1. The client sends your query to Ollama with a list of available tools
2. If Ollama decides to use a tool, the client:
   - Extracts the tool name and arguments
   - Calls the appropriate MCP server with these arguments
   - Sends the tool result back to Ollama
   - Shows the final response

### Compatible Ollama Models

Models that work well with tool use include:
- llama3
- qwen2.5
- mistral
- llava

Make sure your model is recent enough to support the function calling API.

## Troubleshooting

### Common Issues

- **"Ollama is not running"**: Start Ollama with `ollama serve`
- **"Model not found"**: Pull the model with `ollama pull <model-name>`
- **"No tools available"**: Check that your MCP server paths are correct
- **"Connection Error"**: Ensure the MCP server script is executable and free of syntax errors

### Debugging

For more detailed logs, you can run the client in debug mode:

```bash
PYTHONPATH=. LOGLEVEL=DEBUG uv run client.py --mcp-server /path/to/server.py
```

## Contributing

Contributions are welcome! Feel free to submit pull requests or open issues for bugs and feature requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [Model Context Protocol](https://modelcontextprotocol.io/) for the specification and examples
- [Ollama](https://ollama.com/) for the local LLM runtime
- [Rich](https://rich.readthedocs.io/) for the terminal user interface
