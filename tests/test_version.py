"""Test version consistency in the package."""

try:
    import mcp_client_for_ollama
except ImportError:
    import os
    import sys
    # Add the parent directory to sys.path so the package can be imported
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import mcp_client_for_ollama


def test_version_exists():
    """Test that the package has a version."""
    assert hasattr(mcp_client_for_ollama, "__version__")
    assert isinstance(mcp_client_for_ollama.__version__, str)
    assert mcp_client_for_ollama.__version__ != ""