import unittest
import sys
import os
from pathlib import Path
import logging

# Add src directory to path
src_path = Path(__file__).parent.parent / 'src'
sys.path.append(str(src_path))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    logger.info("Running pre-deployment tests...")
    success = run_tests()
    
    if success:
        logger.info("All tests passed!")
        sys.exit(0)
    else:
        logger.error("Tests failed!")
        sys.exit(1)
