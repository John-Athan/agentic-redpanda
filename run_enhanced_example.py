#!/usr/bin/env python3
"""Script to run the enhanced agent example."""

import asyncio
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from examples.enhanced_agent_example import main

if __name__ == "__main__":
    asyncio.run(main())
