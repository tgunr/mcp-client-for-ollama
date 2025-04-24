#!/usr/bin/env python
"""Command-line interface for the MCP Client for Ollama."""

import asyncio
from .client import main

def run_cli():
    """Run the MCP Client for Ollama command-line interface."""
    asyncio.run(main())

if __name__ == "__main__":
    run_cli()
