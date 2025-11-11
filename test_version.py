#!/usr/bin/env python3
"""Test script to verify dynamic versioning works."""



# Test the system route function directly
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from unittest.mock import Mock

from api.server.routes.system import root

# Mock request
mock_request = Mock()
mock_request.app.routes = []

# Call the root function
result = root(mock_request)

