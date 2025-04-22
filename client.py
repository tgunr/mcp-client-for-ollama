import argparse
import asyncio
import os
from contextlib import AsyncExitStack
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters, Tool
from mcp.client.stdio import stdio_client
import ollama
from ollama import ChatResponse
from rich import print as rprint
from rich.columns import Columns
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text
from typing import Optional, List, Dict

load_dotenv()  # load environment variables from .env

class MCPClient:
    def __init__(self, model: str = "qwen2.5:latest"):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.ollama = ollama.AsyncClient()
        self.model = model
        self.available_tools: List[Tool] = []
        self.enabled_tools: Dict[str, bool] = {}
        self.console = Console()
        self.chat_history = []  # Add chat history list to store interactions

    def clear_console(self):
        """Clear the console screen"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def display_available_tools(self):
        """Display available tools with their enabled/disabled status"""
        self.console.print("\n[green]Available Tools:[/green]")
        
        # Create a list of styled tool names
        tool_texts = []
        for tool in self.available_tools:
            status = "[green]✓[/green]" if self.enabled_tools.get(tool.name, True) else "[red]✗[/red]"
            tool_texts.append(f"{status} {tool.name}")
        
        # Display tools in columns for better readability
        if tool_texts:
            columns = Columns(tool_texts, equal=True, expand=True)
            self.console.print(Panel(columns, title="Available Tools", border_style="green"))
        else:
            self.console.print("[yellow]No tools available from the server[/yellow]")

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server

        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        self.available_tools = response.tools
        # Initialize all tools as enabled by default
        for tool in self.available_tools:
            self.enabled_tools[tool.name] = True
        
        # Display the available tools
        self.display_available_tools()

    def select_tools(self):
        """Let the user select which tools to enable using interactive prompts"""
        # Save the original tool states in case the user cancels
        original_states = self.enabled_tools.copy()
        show_descriptions = False  # Default: don't show descriptions
        
        # Clear the console to create a "new console" effect
        self.clear_console()
        
        while True:
            # Show the tool selection interface
            self.console.print(Panel("[bold]Tool Selection Interface[/bold]", border_style="green", expand=False))
            
            for i, tool in enumerate(self.available_tools):
                status = "[green]✓[/green]" if self.enabled_tools[tool.name] else "[red]✗[/red]"
                self.console.print(f"{i+1}. {status} [bold blue]{tool.name}[/bold blue]")
                if show_descriptions and hasattr(tool, 'description') and tool.description:
                    description = Text.from_markup(f"{tool.description}")
                    self.console.print(f"   {description}")
                        
            self.console.print(Panel("[bold yellow]Commands[/bold yellow]", expand=False))
            self.console.print(f"• Enter [bold magenta]numbers[/bold magenta][bold yellow] separated by commas[/bold yellow] to toggle tools (e.g. [bold]1,3,5[/bold])")
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
                self.display_available_tools()
                return
            
            if selection in ['q', 'quit']:
                # Restore original tool states
                self.enabled_tools = original_states.copy()
                self.clear_console()
                self.console.print("[yellow]Tool changes cancelled.[/yellow]")
                
                # Display chat history before returning to chat interface
                self._display_chat_history()
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
            
            try:
                selections = [int(x.strip()) for x in selection.split(',') if x.strip()]
                valid_toggle = False
                
                for idx in selections:
                    if 1 <= idx <= len(self.available_tools):
                        tool_name = self.available_tools[idx-1].name
                        self.enabled_tools[tool_name] = not self.enabled_tools[tool_name]
                        valid_toggle = True
                    else:
                        self.console.print(f"[red]Invalid number: {idx}. Must be between 1 and {len(self.available_tools)}[/red]")
                
                if valid_toggle:
                    # Only clear the console if at least one valid tool was toggled
                    self.clear_console()
            
            except ValueError:
                self.clear_console()
                self.console.print("[red]Invalid input. Please enter numbers separated by commas.[/red]")
                
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

                # Execute tool call
                self.console.print(Panel(f"[bold]Calling tool[/bold]: [blue]{tool_name}[/blue]", 
                                       subtitle=f"[dim]{tool_args}[/dim]", 
                                       expand=True))
                self.console.print()
                
                with self.console.status(f"[cyan]Running {tool_name}...[/cyan]"):
                    result = await self.session.call_tool(tool_name, tool_args)
                
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

    async def chat_loop(self):
        """Run an interactive chat loop"""
        self.console.print(Panel.fit("[bold green]MCP Client Started![/bold green]"))
        self.console.print(f"Using Ollama model: [bold blue]{self.model}[/bold blue]")
        self.print_help()

        while True:
            try:
                query = Prompt.ask("\n[bold green]Query[/bold green]")

                if query.lower() in ['quit', 'q']:
                    self.console.print("[yellow]Exiting...[/yellow]")
                    break
                
                if query.lower() in ['tools', 't']:
                    self.select_tools()
                    continue
                    
                if query.lower() in ['help', 'h']:
                    self.print_help()
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
            "• Type [bold]quit[/bold] or [bold]q[/bold] to exit", 
            title="Help", border_style="yellow", expand=False))

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()


async def main():
    parser = argparse.ArgumentParser(description="MCP Client")
    parser.add_argument("--mcp-server", required=True, help="Path to the server script (.py or .js)")
    parser.add_argument("--model", default="qwen2.5:latest", help="Ollama model to use for API calls")
    args = parser.parse_args()

    client = MCPClient(model=args.model)
    try:
        await client.connect_to_server(args.mcp_server)
        await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
