#!/usr/bin/env python3
"""Root-level entry point for Docker and direct execution."""

import sys
import os

# Add src/ to path so the package can be imported without pip install
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from roleplaying_dice_mcp.server import main

if __name__ == "__main__":
    main()
