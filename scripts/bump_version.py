#!/usr/bin/env python3
"""
Version bumper for MCP Client for Ollama

This script bumps the version number in both the main package and the CLI package,
ensuring they stay in sync.
"""

import argparse
import os
import re
from pathlib import Path


def read_version(file_path):
    """Read the current version from a pyproject.toml file."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Use regex to find the version line
    match = re.search(r'version\s*=\s*"([^"]+)"', content)
    if match:
        return match.group(1)
    else:
        raise ValueError(f"Could not find version in {file_path}")


def bump_version(version, bump_type):
    """Bump a version number based on semantic versioning."""
    major, minor, patch = map(int, version.split('.'))
    
    if bump_type == 'major':
        major += 1
        minor = 0
        patch = 0
    elif bump_type == 'minor':
        minor += 1
        patch = 0
    else:  # patch
        patch += 1
        
    return f"{major}.{minor}.{patch}"


def update_version_in_file(file_path, new_version):
    """Update the version in a pyproject.toml file."""
    with open(file_path, 'r') as f:
        content = f.read()
        
    # Replace version in the version line - using a lambda for safe replacement
    version_pattern = re.compile(r'(version\s*=\s*)"([^"]+)"')
    updated_content = version_pattern.sub(lambda m: f'{m.group(1)}"{new_version}"', content)
    
    # Also update any dependency on the main package (for the CLI package)
    dep_pattern = re.compile(r'("mcp-client-for-ollama==)([^"]+)"')
    updated_content = dep_pattern.sub(lambda m: f'{m.group(1)}{new_version}"', updated_content)
    
    with open(file_path, 'w') as f:
        f.write(updated_content)


def update_version_in_init(init_path, new_version):
    """Update the __version__ in __init__.py files."""
    if os.path.exists(init_path):
        with open(init_path, 'r') as f:
            content = f.read()
        
        # Replace version in __version__ = "x.y.z" - using lambda for safe replacement
        version_pattern = re.compile(r'(__version__\s*=\s*)"([^"]+)"')
        updated_content = version_pattern.sub(lambda m: f'{m.group(1)}"{new_version}"', content)
        
        with open(init_path, 'w') as f:
            f.write(updated_content)


def main():
    parser = argparse.ArgumentParser(description="Bump version for MCP Client for Ollama packages")
    parser.add_argument(
        "bump_type", 
        choices=["patch", "minor", "major", "custom"],
        help="The type of version bump to perform following semantic versioning, or 'custom' to specify a specific version"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--version", 
        help="Custom version to set when using the 'custom' bump type"
    )
    args = parser.parse_args()
    
    # Get repo root directory
    repo_root = Path(__file__).parent.parent.absolute()
    
    # Define paths
    main_pyproject = repo_root / "pyproject.toml"
    cli_pyproject = repo_root / "cli-package" / "pyproject.toml"
    main_init = repo_root / "mcp_client_for_ollama" / "__init__.py"
    cli_init = repo_root / "cli-package" / "ollmcp" / "__init__.py"
    
    # Read current version
    current_version = read_version(main_pyproject)
    print(f"Current version: {current_version}")
    
    # Calculate new version
    if args.bump_type == "custom":
        if not args.version:
            parser.error("--version is required when using 'custom' bump type")
        new_version = args.version
        # Check if version is valid
        if not re.match(r'^\d+\.\d+\.\d+$', new_version):
            parser.error(f"Invalid version format: {new_version}. Expected format: X.Y.Z")
    else:
        new_version = bump_version(current_version, args.bump_type)
    
    print(f"New version: {new_version}")
    
    if args.dry_run:
        print("Dry run - no changes made.")
        return
    
    # Update versions
    print(f"Updating main package version in {main_pyproject}")
    update_version_in_file(main_pyproject, new_version)
    
    print(f"Updating CLI package version in {cli_pyproject}")
    update_version_in_file(cli_pyproject, new_version)
    
    # Update __version__ in __init__.py files if they exist
    print(f"Checking for __init__.py files...")
    update_version_in_init(main_init, new_version)
    update_version_in_init(cli_init, new_version)
    
    print(f"Version bump complete! {current_version} -> {new_version}")
    print("\nNext steps:")
    print(f"1. Commit the changes: git commit -am \"Bump version to {new_version}\"")
    print("2. Create a tag: git tag -a v{new_version} -m \"Version {new_version}\"")
    print("3. Push changes: git push && git push --tags")
    print("4. Build and publish the packages")


if __name__ == "__main__":
    main()
