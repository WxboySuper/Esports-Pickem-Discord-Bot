"""Test suite initialization for Esports Pick'em Discord Bot"""
import os
import sys

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Clear the log file before running tests
log_file = 'logs/app.log'
if os.path.exists(log_file):
    with open(log_file, 'w') as f:
        f.write('')  # Clear the log file
    print(f"Log file cleared: {log_file}")
