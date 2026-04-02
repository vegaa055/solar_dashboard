"""
tests/conftest.py
Shared pytest fixtures and test configuration.
"""
import sys
import os

# Make sure the project root is on the path so imports resolve
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
