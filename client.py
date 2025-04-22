import argparse
import asyncio
import json
import os
import shutil
from contextlib import AsyncExitStack
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters, Tool
from mcp.client.stdio import stdio_client
import ollama
from ollama import ChatResponse
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from rich import print as rprint
from rich.columns import Columns
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text
from typing import Optional, List, Dict, Any
import aiohttp
from datetime import datetime
import dateutil.parser

load_dotenv()  # load environment variables from .env

# Default Claude config file location
DEFAULT_CLAUDE_CONFIG = os.path.expanduser("~/Library/Application Support/Claude/claude_desktop_config.json")

class MCPClient:
    def __init__(self, model: str = "qwen2.5:latest"):
        # Initialize session and client objects
        self.sessions = {}  # Dict to store multiple sessions
        self.exit_stack = AsyncExitStack()
        self.ollama = ollama.AsyncClient()
        self.model = model
        self.available_tools: List[Tool] = []
        self.enabled_tools: Dict[str, bool] = {}
        self.console = Console()
        self.chat_history = []  # Add chat history list to store interactions
        self.prompt_session = PromptSession()
        self.prompt_style = Style.from_dict({
            'prompt': 'ansibrightyellow bold',
        })
        
    async def check_ollama_running(self) -> bool:
        """Check if Ollama is running by making a request to its API
        
        Returns:
            bool: True if Ollama is running, False otherwise
        """
        try:
            # Try to make a simple request to the Ollama API
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:11434/api/tags") as response:
                    if response.status == 200:
                        return True
                    return False
        except Exception:
            return False
            
    async def list_ollama_models(self) -> List[Dict[str, Any]]:
        """Get a list of available Ollama models
        
        Returns:
            List[Dict[str, Any]]: List of model objects each with name and other metadata
        """
        try:
            # Get models from Ollama API
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:11434/api/tags") as response:
                    if response.status == 200:
                        data = await response.json()
                        if "models" in data:
                            return data["models"]
                        return []
                    else:
                        self.console.print(f"[red]Error getting models from Ollama API: {response.status}[/red]")
                        return []
        except Exception as e:
            self.console.print(f"[red]Error getting models from Ollama: {str(e)}[/red]")
            return []
            
    def display_current_model(self):
        """Display the currently selected model"""
        self.console.print(Panel(f"[bold blue]Current model:[/bold blue] [green]{self.model}[/green]", 
                               border_style="blue", expand=False))
                               
    async def select_model(self):
        """Let the user select an Ollama model from the available ones"""
        # Check if Ollama is running first
        if not await self.check_ollama_running():
            self.console.print(Panel(
                "[bold red]Ollama is not running![/bold red]\n\n"
                "Please start Ollama before trying to list or switch models.\n"
                "You can start Ollama by running the 'ollama serve' command in a terminal.",
                title="Error", border_style="red", expand=False
            ))
            return
        
        # Save the current model in case the user cancels
        original_model = self.model
            
        # Get available models
        with self.console.status("[cyan]Getting available models from Ollama...[/cyan]"):
            models = await self.list_ollama_models()
            
        if not models:
            self.console.print("[yellow]No models available. Try pulling a model with 'ollama pull <model>'[/yellow]")
            return
            
        # Clear console for a clean interface
        self.clear_console()
        
        # Display model selection interface
        self.console.print(Panel("[bold]Model Selection[/bold]", border_style="blue", expand=False))
        
        # Sort models by name for easier reading
        models.sort(key=lambda x: x.get("name", ""))
        
        # Show current model with an indicator
        self.console.print(f"Current model: [bold green]{self.model}[/bold green]\n")
        
        # Display available models
        for i, model in enumerate(models):
            model_name = model.get("name", "Unknown")
            is_current = model_name == self.model
            status = "[green]→[/green] " if is_current else "  "
            size = model.get("size", 0)
            size_str = f"{size/(1024*1024):.1f} MB" if size else "Unknown size"
            
            # Format the date if available
            modified_at = model.get("modified_at", "Unknown")
            if modified_at != "Unknown":
                try:
                    modified_at = dateutil.parser.parse(modified_at).strftime("%Y-%m-%d %H:%M:%S")                                        
                except Exception as e:
                    self.console.print(f"[red]Error parsing date: {str(e)}[/red]")
                    modified_at = "Unknown date"
            
            # Debug: Print raw model data if name is not found
            if model_name == "Unknown":
                self.console.print(f"[dim]Debug - Model data: {model}[/dim]")
                # Try alternative fields that might contain the name
                for key in ["name", "model", "tag", "id"]:
                    if key in model and model[key]:
                        model_name = model[key]
                        break
            
            self.console.print(f"{i+1}. {status} [bold blue]{model_name}[/bold blue] [dim]({size_str}, {modified_at})[/dim]")

        self.console.print(Panel("[bold yellow]Commands[/bold yellow]", expand=False))
        self.console.print("• Enter [bold magenta]number[/bold magenta] to select a model")
        self.console.print("• [bold]s[/bold] or [bold]save[/bold] - Save model selection and return")
        self.console.print("• [bold]q[/bold] or [bold]quit[/bold] - Cancel and return")
        
        selection = Prompt.ask("> ")
        selection = selection.strip().lower()
        
        if selection in ['s', 'save']:
            # Keep the current model selection
            self.clear_console()
            self.console.print("[green]Model selection saved![/green]")
            # Display the current model
            self.display_current_model()
            # Display available tools
            self.display_available_tools()
            # Display chat history before returning to chat interface
            self._display_chat_history()
            return
        
        if selection in ['q', 'quit']:
            # Restore original model
            self.model = original_model
            self.clear_console()
            self.console.print("[yellow]Model selection cancelled.[/yellow]")
            # Display the current model
            self.display_current_model()
            # Display available tools
            self.display_available_tools()
            # Display chat history before returning to chat interface
            self._display_chat_history()
            return
            
        try:
            idx = int(selection) - 1
            if 0 <= idx < len(models):
                # Update the model
                model_data = models[idx]
                # Try multiple fields that might contain the model name
                for key in ["name", "model", "tag", "id"]:
                    if key in model_data and model_data[key]:
                        new_model = model_data[key]
                        old_model = self.model
                        self.model = new_model
                        self.clear_console()
                        self.console.print(f"[green]Model changed from [bold]{old_model}[/bold] to [bold]{new_model}[/bold]![/green]")
                        # Show a message that changes need to be saved
                        self.console.print("[yellow]Use 's' to save this selection or 'q' to cancel[/yellow]")
                        return await self.select_model()  # Return to model selection to save/cancel
                
                # If we couldn't find a name, inform the user
                self.clear_console()
                self.console.print("[red]Error: Could not determine the model name from the API response.[/red]")
                # Return to model selection
                return await self.select_model()
            else:
                self.clear_console()
                self.console.print(f"[red]Invalid number: {idx + 1}. Must be between 1 and {len(models)}[/red]")
                # Return to model selection
                return await self.select_model()
        except ValueError:
            self.clear_console()
            self.console.print("[red]Invalid input. Please enter a number.[/red]")
            # Return to model selection
            return await self.select_model()

    def clear_console(self):
        """Clear the console screen"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def display_available_tools(self):
        """Display available tools with their enabled/disabled status"""
        
        # Create a list of styled tool names
        tool_texts = []
        enabled_count = 0
        for tool in self.available_tools:
            is_enabled = self.enabled_tools.get(tool.name, True)
            if is_enabled:
                enabled_count += 1
            status = "[green]✓[/green]" if is_enabled else "[red]✗[/red]"
            tool_texts.append(f"{status} {tool.name}")
        
        # Display tools in columns for better readability
        if tool_texts:
            columns = Columns(tool_texts, equal=True, expand=True)
            subtitle = f"{enabled_count}/{len(self.available_tools)} tools enabled"
            self.console.print(Panel(columns, title="Available Tools", subtitle=subtitle, border_style="green"))
        else:
            self.console.print("[yellow]No tools available from the server[/yellow]")

    @staticmethod
    def load_server_config(config_path: str) -> Dict[str, Any]:
        """Load and parse a server configuration file
        
        Args:
            config_path: Path to the JSON config file
            
        Returns:
            Dictionary containing server configurations
        """
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            return config.get('mcpServers', {})
        except Exception as e:
            raise ValueError(f"Error loading server config from {config_path}: {str(e)}")

    @staticmethod
    def directory_exists(args_list):
        """Check if a directory specified in args exists
        
        Looks for a --directory argument followed by a path and checks if that path exists
        
        Args:
            args_list: List of command line arguments
            
        Returns:
            tuple: (directory_exists, directory_path or None)
        """
        if not args_list:
            return True, None
            
        for i, arg in enumerate(args_list):
            if arg == "--directory" and i + 1 < len(args_list):
                directory = args_list[i + 1]
                if not os.path.exists(directory):
                    return False, directory
        
        return True, None

    async def connect_to_servers(self, server_paths=None, config_path=None):
        """Connect to one or more MCP servers
        
        Args:
            server_paths: List of paths to server scripts (.py or .js)
            config_path: Path to JSON config file with server configurations
        """
        all_servers = []
        
        # Add individual server paths if provided
        if server_paths:
            if isinstance(server_paths, str):
                server_paths = [server_paths]
                
            for path in server_paths:
                all_servers.append({
                    "type": "script",
                    "path": path,
                    "name": os.path.basename(path).split('.')[0]  # Use filename without extension as name
                })
        
        # Add servers from config file if provided
        if config_path:
            server_configs = self.load_server_config(config_path)
            for name, config in server_configs.items():
                # Skip disabled servers
                if config.get('disabled', False):
                    continue
                
                # Check if required directory exists
                args = config.get("args", [])
                dir_exists, missing_dir = self.directory_exists(args)
                
                if not dir_exists:
                    self.console.print(f"[yellow]Warning: Server '{name}' specifies a directory that doesn't exist: {missing_dir}[/yellow]")
                    self.console.print(f"[yellow]Skipping server '{name}'[/yellow]")
                    continue
                    
                all_servers.append({
                    "type": "config",
                    "name": name,
                    "config": config
                })
        
        if not all_servers:
            raise ValueError("No servers specified. Please provide server paths or a config file.")
            
        # Connect to each server
        for server in all_servers:
            server_name = server["name"]
            self.console.print(f"[cyan]Connecting to server: {server_name}[/cyan]")
            
            if server["type"] == "script":
                # Handle direct script path
                path = server["path"]
                is_python = path.endswith('.py')
                is_js = path.endswith('.js')
                
                if not (is_python or is_js):
                    self.console.print(f"[yellow]Warning: Server script {path} must be a .py or .js file. Skipping.[/yellow]")
                    continue
                    
                command = "python" if is_python else "node"
                server_params = StdioServerParameters(
                    command=command,
                    args=[path],
                    env=None
                )
            else:
                # Handle config-based server
                server_config = server["config"]
                command = server_config.get("command")
                
                # Validate the command exists in PATH
                if not shutil.which(command):
                    self.console.print(f"[yellow]Warning: Command '{command}' for server '{server_name}' not found in PATH. Skipping.[/yellow]")
                    continue
                    
                args = server_config.get("args", [])
                env = server_config.get("env")
                
                server_params = StdioServerParameters(
                    command=command,
                    args=args,
                    env=env
                )
            
            try:
                # Connect to this server
                stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
                stdio, write = stdio_transport
                session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))
                await session.initialize()
                
                # Store the session
                self.sessions[server_name] = {
                    "session": session,
                    "tools": []
                }
                
                # Get tools from this server
                response = await session.list_tools()
                
                # Store and merge tools, prepending server name to avoid conflicts
                server_tools = []
                for tool in response.tools:
                    # Create a qualified name for the tool that includes the server
                    qualified_name = f"{server_name}.{tool.name}"
                    # Clone the tool but update the name
                    tool_copy = Tool(
                        name=qualified_name,
                        description=f"[{server_name}] {tool.description}" if hasattr(tool, 'description') else f"Tool from {server_name}",
                        inputSchema=tool.inputSchema,
                        outputSchema=tool.outputSchema if hasattr(tool, 'outputSchema') else None
                    )
                    server_tools.append(tool_copy)
                    self.enabled_tools[qualified_name] = True
                
                self.sessions[server_name]["tools"] = server_tools
                self.available_tools.extend(server_tools)
                
                self.console.print(f"[green]Successfully connected to {server_name} with {len(server_tools)} tools[/green]")
                
            except FileNotFoundError as e:
                self.console.print(f"[red]Error connecting to {server_name}: File not found - {str(e)}[/red]")
            except PermissionError:
                self.console.print(f"[red]Error connecting to {server_name}: Permission denied[/red]")
            except Exception as e:
                self.console.print(f"[red]Error connecting to {server_name}: {str(e)}[/red]")
        
        if not self.sessions:
            self.console.print("[bold red]Warning: Could not connect to any MCP servers![/bold red]")
            if config_path:
                self.console.print(f"[yellow]Check if paths in {config_path} exist and are accessible[/yellow]")

    async def connect_to_server(self, server_script_path: str):
        """Connect to a single MCP server (legacy support)"""
        await self.connect_to_servers([server_script_path])

    def select_tools(self):
        """Let the user select which tools to enable using interactive prompts with server-based grouping"""
        # Save the original tool states in case the user cancels
        original_states = self.enabled_tools.copy()
        show_descriptions = False  # Default: don't show descriptions
        
        # Group tools by server
        servers = {}
        for tool in self.available_tools:
            server_name, tool_name = tool.name.split('.', 1) if '.' in tool.name else ("default", tool.name)
            if server_name not in servers:
                servers[server_name] = []
            servers[server_name].append(tool)
        
        # Sort servers by name for consistent display
        sorted_servers = sorted(servers.items(), key=lambda x: x[0])
        
        # Clear the console to create a "new console" effect
        self.clear_console()
        
        while True:
            # Show the tool selection interface
            self.console.print(Panel("[bold]Tool Selection Interface[/bold]", border_style="green", expand=False))
            
            # Display the server groups and their tools
            self.console.print(Panel("[bold]Available Tools[/bold]", border_style="blue", expand=False))
            
            tool_index = 1  # Global tool index across all servers
            
            # Create a mapping of display indices to tools for accurate selection
            index_to_tool = {}
            
            # Calculate and display server stats and tools
            for server_idx, (server_name, server_tools) in enumerate(sorted_servers):
                enabled_count = sum(1 for tool in server_tools if self.enabled_tools[tool.name])
                total_count = len(server_tools)
                
                # Determine server status indicator
                if enabled_count == total_count:
                    server_status = "[green]✓[/green]"  # All enabled
                elif enabled_count == 0:
                    server_status = "[red]✗[/red]"      # None enabled
                else:
                    server_status = "[yellow]~[/yellow]"  # Some enabled
                
                self.console.print(f"S{server_idx+1}. {server_status} [bold blue]{server_name}[/bold blue] ({enabled_count}/{total_count} tools)")
                
                # Display individual tools for this server
                for tool in server_tools:
                    status = "[green]✓[/green]" if self.enabled_tools[tool.name] else "[red]✗[/red]"
                    self.console.print(f"   {tool_index}. {status} {tool.name}")
                    
                    # Store the mapping from display index to tool
                    index_to_tool[tool_index] = tool
                    
                    if show_descriptions and hasattr(tool, 'description') and tool.description:
                        description = Text.from_markup(f"{tool.description}")
                        self.console.print(f"      {description}")
                    
                    tool_index += 1
            
            # Display the command panel
            self.console.print(Panel("[bold yellow]Commands[/bold yellow]", expand=False))
            self.console.print(f"• Enter [bold magenta]numbers[/bold magenta][bold yellow] separated by commas or ranges[/bold yellow] to toggle tools (e.g. [bold]1,3,5-8[/bold])")
            self.console.print(f"• Enter [bold magenta]S + number[/bold magenta] to toggle all tools in a server (e.g. [bold]S1[/bold] or [bold]s2[/bold])")
            self.console.print("• [bold]a[/bold] or [bold]all[/bold] - Enable all tools")
            self.console.print("• [bold]n[/bold] or [bold]none[/bold] - Disable all tools")
            self.console.print(f"• [bold]d[/bold] or [bold]desc[/bold] - {'Hide' if show_descriptions else 'Show'} descriptions")
            self.console.print("• [bold]s[/bold] or [bold]save[/bold] - Save changes and return")
            self.console.print("• [bold]q[/bold] or [bold]quit[/bold] - Cancel and return")
            
            selection = Prompt.ask("> ")
            selection = selection.strip().lower()
            
            if selection in ['s', 'save']:
                self.clear_console()
                self.console.print("[green]Tool changes saved![/green]")
                
                # Display chat history before returning to chat interface
                self._display_chat_history()
                self.display_current_model()
                self.display_available_tools()            
                return
            
            if selection in ['q', 'quit']:
                # Restore original tool states
                self.enabled_tools = original_states.copy()
                self.clear_console()
                self.console.print("[yellow]Tool changes cancelled.[/yellow]")
                
                # Display chat history before returning to chat interface
                self._display_chat_history()
                self.display_current_model()
                self.display_available_tools()
                return
            
            if selection in ['a', 'all']:
                for tool in self.available_tools:
                    self.enabled_tools[tool.name] = True
                self.clear_console()
                self.console.print("[green]All tools enabled![/green]")
                continue
            
            if selection in ['n', 'none']:
                for tool in self.available_tools:
                    self.enabled_tools[tool.name] = False
                self.clear_console()
                self.console.print("[orange3]All tools disabled![/orange3]")
                continue
                
            if selection in ['d', 'desc']:
                show_descriptions = not show_descriptions
                self.clear_console()
                self.console.print(f"[cyan]Descriptions {'shown' if show_descriptions else 'hidden'}![/cyan]")
                continue
            
            # Check for server toggle (S1, S2, etc.)
            if selection.startswith('s') and len(selection) > 1 and selection[1:].isdigit():
                server_idx = int(selection[1:]) - 1
                if 0 <= server_idx < len(sorted_servers):
                    server_name, server_tools = sorted_servers[server_idx]
                    
                    # Check if all tools in this server are currently enabled
                    all_enabled = all(self.enabled_tools[tool.name] for tool in server_tools)
                    
                    # Toggle accordingly: if all are enabled, disable all; otherwise enable all
                    new_state = not all_enabled
                    for tool in server_tools:
                        self.enabled_tools[tool.name] = new_state
                    
                    self.clear_console()
                    status = "enabled" if new_state else "disabled"
                    self.console.print(f"[green]All tools in server '{server_name}' {status}![/green]")
                else:
                    self.clear_console()
                    self.console.print(f"[red]Invalid server number: S{server_idx+1}. Must be between S1 and S{len(sorted_servers)}[/red]")
                continue
            
            # Process individual tool selections and ranges
            try:
                valid_toggle = False
                
                # Split the input by commas to handle multiple selections
                parts = [part.strip() for part in selection.split(',') if part.strip()]
                selections = []
                
                for part in parts:
                    # Check if this part is a range (e.g., "5-8")
                    if '-' in part:
                        try:
                            start, end = map(int, part.split('-', 1))
                            selections.extend(range(start, end + 1))
                        except ValueError:
                            self.console.print(f"[red]Invalid range: {part}[/red]")
                    else:
                        # Otherwise, treat as a single number
                        try:
                            selections.append(int(part))
                        except ValueError:
                            self.console.print(f"[red]Invalid selection: {part}[/red]")
                
                # Process the selections using our accurate mapping
                for idx in selections:
                    if idx in index_to_tool:
                        tool = index_to_tool[idx]
                        self.enabled_tools[tool.name] = not self.enabled_tools[tool.name]
                        valid_toggle = True
                    else:
                        self.console.print(f"[red]Invalid number: {idx}. Must be between 1 and {len(index_to_tool)}[/red]")
                
                if valid_toggle:
                    self.clear_console()
                    self.console.print("[green]Tools toggled successfully![/green]")
                else:
                    self.clear_console()
                    self.console.print("[yellow]No valid tool numbers provided.[/yellow]")
            
            except ValueError:
                self.clear_console()
                self.console.print("[red]Invalid input. Please enter numbers, ranges, or server designators.[/red]")

    def _display_chat_history(self):
        """Display chat history when returning to the main chat interface"""
        if self.chat_history:
            self.console.print(Panel("[bold]Chat History[/bold]", border_style="blue", expand=False))
            
            # Display the last few conversations (limit to keep the interface clean)
            max_history = 3
            history_to_show = self.chat_history[-max_history:]
            
            for i, entry in enumerate(history_to_show):
                # Calculate query number starting from 1 for the first query
                query_number = len(self.chat_history) - len(history_to_show) + i + 1
                self.console.print(f"[bold green]Query {query_number}:[/bold green]")
                self.console.print(Text(entry["query"].strip(), style="green"))
                self.console.print(f"[bold blue]Response:[/bold blue]")
                self.console.print(Markdown(entry["response"].strip()))
                self.console.print()
                
            if len(self.chat_history) > max_history:
                self.console.print(f"[dim](Showing last {max_history} of {len(self.chat_history)} conversations)[/dim]")

    async def process_query(self, query: str) -> str:
        """Process a query using Ollama and available tools"""
        messages = [
            {
                "role": "user",
                "content": query
            }
        ]

        # Filter tools based on user selection
        enabled_tool_objects = [tool for tool in self.available_tools if self.enabled_tools.get(tool.name, False)]
        
        if not enabled_tool_objects:
            self.console.print("[yellow]Warning: No tools are enabled. Model will respond without tool access.[/yellow]")
        
        available_tools = [{
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema
            }
        } for tool in enabled_tool_objects]        

        # Initial Ollama API call
        with self.console.status("[cyan]Thinking...[/cyan]"):
            response: ChatResponse = await self.ollama.chat(
                model=self.model,
                messages=messages,
                tools=available_tools,
                options={"num_predict": 1000}
            )

        # Process response and handle tool calls
        final_text = []
        
        if hasattr(response.message, 'content') and response.message.content:
            final_text.append(response.message.content)            

        elif response.message.tool_calls:
            for tool in response.message.tool_calls:
                tool_name = tool.function.name
                tool_args = tool.function.arguments

                # Parse server name and actual tool name from the qualified name
                server_name, actual_tool_name = tool_name.split('.', 1) if '.' in tool_name else (None, tool_name)
                
                if not server_name or server_name not in self.sessions:
                    self.console.print(f"[red]Error: Unknown server for tool {tool_name}[/red]")
                    continue
                
                # Execute tool call
                self.console.print(Panel(f"[bold]Calling tool[/bold]: [blue]{tool_name}[/blue]", 
                                       subtitle=f"[dim]{tool_args}[/dim]", 
                                       expand=True))
                self.console.print()
                
                with self.console.status(f"[cyan]Running {tool_name}...[/cyan]"):
                    result = await self.sessions[server_name]["session"].call_tool(actual_tool_name, tool_args)
                
                self.console.print()
                
                messages.append({
                    "role": "tool",
                    "content": result.content[0].text,
                    "name": tool_name
                })            

                # Get next response from Ollama with the tool results
                with self.console.status("[cyan]Processing results...[/cyan]"):
                    response = await self.ollama.chat(
                        model=self.model,
                        messages=messages,
                        tools=available_tools,
                    )

                self.console.print() 
                final_text.append(response.message.content)

        # Append query and response to chat history
        self.chat_history.append({"query": query, "response": "\n".join(final_text)})

        return "\n".join(final_text)

    async def get_user_input(self, prompt_text: str = "\nQuery") -> str:
        """Get user input with full keyboard navigation support"""
        try:
            # Use prompt_async instead of prompt
            user_input = await self.prompt_session.prompt_async(
                f"{prompt_text}: ",
                style=self.prompt_style
            )
            return user_input
        except KeyboardInterrupt:
            return "quit"
        except EOFError:
            return "quit"

    async def chat_loop(self):
        """Run an interactive chat loop"""
        self.clear_console()
        self.console.print(Panel.fit("[bold green]MCP Client Started![/bold green]"))
        self.display_current_model()        
        self.display_available_tools()
        self.print_help()

        while True:
            try:
                # Use await to call the async method
                query = await self.get_user_input("Query")

                if query.lower() in ['quit', 'q']:
                    self.console.print("[yellow]Exiting...[/yellow]")
                    break
                
                if query.lower() in ['tools', 't']:
                    self.select_tools()
                    continue
                    
                if query.lower() in ['help', 'h']:
                    self.print_help()
                    continue
                
                if query.lower() in ['model', 'm']:
                    await self.select_model()
                    continue

                # Check if query is too short and not a special command
                if len(query.strip()) < 5:
                    self.console.print("[yellow]Query must be at least 5 characters long.[/yellow]")
                    continue

                response = await self.process_query(query)
                if response:
                    self.console.print(Markdown(response))
                else:
                    self.console.print("[red]No response received.[/red]")

            except Exception as e:
                self.console.print(f"[bold red]Error:[/bold red] {str(e)}")
                self.console.print_exception()
                
    def print_help(self):
        """Print available commands"""
        self.console.print(Panel(
            "[yellow]Available Commands:[/yellow]\n"
            "• Type [bold]help[/bold] or [bold]h[/bold] to show this help message\n"
            "• Type [bold]tools[/bold] or [bold]t[/bold] to configure tools\n"
            "• Type [bold]model[/bold] or [bold]m[/bold] to select a model\n"
            "• Type [bold]quit[/bold] or [bold]q[/bold] to exit", 
            title="Help", border_style="yellow", expand=False))

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()


async def main():
    parser = argparse.ArgumentParser(description="MCP Client")
    
    # Server configuration options
    server_group = parser.add_argument_group("Server Options")
    server_group.add_argument("--mcp-server", help="Path to a server script (.py or .js)", action="append")
    server_group.add_argument("--servers-json", help="Path to a JSON file with server configurations")
    server_group.add_argument("--auto-discovery", action="store_true", default=False,
                            help=f"Auto-discover servers from Claude's config at {DEFAULT_CLAUDE_CONFIG} - Default option")
    # Model options
    model_group = parser.add_argument_group("Model Options")
    model_group.add_argument("--model", default="qwen2.5:latest", help="Ollama model to use. For example: 'qwen2.5:latest'")
    
     # Add a function to modify args after parsing
    def parse_args_with_defaults():
        args = parser.parse_args()
        # If none of the server arguments are provided, enable auto-discovery
        if not (args.mcp_server or args.servers_json or args.auto_discovery):
            args.auto_discovery = True
        return args
    
    args = parse_args_with_defaults()

    console = Console()

    # Create a temporary client to check if Ollama is running
    client = MCPClient(model=args.model)
    if not await client.check_ollama_running():
        console.print(Panel(
            "[bold red]Error: Ollama is not running![/bold red]\n\n"
            "This client requires Ollama to be running to process queries.\n"
            "Please start Ollama by running the 'ollama serve' command in a terminal.",
            title="Ollama Not Running", border_style="red", expand=False
        ))
        return

    # Determine which server config to use
    config_path = None
    if args.auto_discovery:
        if os.path.exists(DEFAULT_CLAUDE_CONFIG):
            config_path = DEFAULT_CLAUDE_CONFIG
        else:
            console.print(f"[yellow]Warning: Claude config not found at {DEFAULT_CLAUDE_CONFIG}[/yellow]")
    elif args.servers_json:
        if os.path.exists(args.servers_json):
            config_path = args.servers_json
        else:
            console.print(f"[bold red]Error: Specified JSON config file not found: {args.servers_json}[/bold red]")
            return

    # Validate that we have at least one server source
    if not args.mcp_server and not config_path:
        parser.error("At least one of --mcp-server, --servers-json, or --auto-discovery must be provided")

    # Validate mcp-server paths exist
    if args.mcp_server:
        for server_path in args.mcp_server:
            if not os.path.exists(server_path):
                console.print(f"[bold red]Error: Server script not found: {server_path}[/bold red]")
                return

    try:
        await client.connect_to_servers(args.mcp_server, config_path)
        # Only proceed to chat loop if we have at least one tool available
        if client.available_tools:
            await client.chat_loop()
        else:
            console.print("[bold red]No tools available. Exiting.[/bold red]")
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
