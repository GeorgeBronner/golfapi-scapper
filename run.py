"""Runner script for local testing."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Override DB_PATH for local testing
os.environ['DB_PATH'] = os.path.join(os.path.dirname(__file__), 'data', 'golf_courses.db')

# Import and run
from src.main import main

if __name__ == "__main__":
    main()
