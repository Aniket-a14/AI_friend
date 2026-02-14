"""
Pytest configuration for AI Friend Sovereign Mesh tests.
Configures Python path and test fixtures.
"""

import sys
import os

# Add the backend directory to Python path so tests can import app modules
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
