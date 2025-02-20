import unittest
import coverage
import sys
import logging
from pathlib import Path

def run_tests():
    """Run all tests and generate coverage"""
    # Configure logging for tests
    logger = logging.getLogger(__name__)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.info("Starting test run")

    try:
        # Start coverage tracking
        cov = coverage.Coverage()
        cov.start()
    except coverage.CoverageException as e:
        logger.error("Failed to start coverage tracking: %s", str(e))
        sys.exit(1)

    # Find and load tests
    test_loader = unittest.TestLoader()
    test_dir = Path(__file__).parent / 'tests'

    # Discover tests pattern
    pattern = 'test_*.py'

    try:
        # Discover and load tests
        suite = test_loader.discover(str(test_dir), pattern=pattern)

        if not list(suite):
            logger.error(f"No tests found in {test_dir} with pattern {pattern}")
            sys.exit(1)

        # Run tests
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)

        # Stop coverage and generate reports
        cov.stop()
        cov.save()

        logger.info("\nCoverage Report:")
        cov.report()

        # Generate HTML report
        html_dir = Path('coverage_html')
        html_dir.mkdir(exist_ok=True)
        cov.html_report(directory=str(html_dir))

        # Generate XML report for CI
        cov.xml_report()

        logger.info(f"\nDetailed HTML coverage report: {html_dir}/index.html")

        sys.exit(not result.wasSuccessful())

    except Exception as e:
        logger.error(f"Error running tests: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    run_tests()
