import unittest
import sys
from pathlib import Path
import logging

# Add src directory to path
src_path = Path(__file__).parent.parent / 'src'
sys.path.append(str(src_path))

logging.basicConfig(level=logging.INFO)
bot_logger = logging.getLogger('bot')  # Changed from logger to bot_logger

def run_tests():
    """Run all tests and return True if all pass"""
    # Discover and run all tests
    test_dir = Path(__file__).parent.parent / 'tests'
    loader = unittest.TestLoader()
    suite = loader.discover(str(test_dir))
    
    # Run tests
    runner = unittest.TextTestRunner()
    result = runner.run(suite)
    
    # Return True if all tests passed
    return result.wasSuccessful()

if __name__ == "__main__":
    bot_logger.info("Running pre-deployment tests...")
    success = run_tests()
    
    if success:
        bot_logger.info("All tests passed!")
        sys.exit(0)
    else:
        bot_logger.error("Tests failed!")
        sys.exit(1)
