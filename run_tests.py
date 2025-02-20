import coverage
import unittest
import sys
import logging


def run_tests():
    """
    Runs all unit tests and generates coverage reports.
    This function performs the following steps:
    1. Starts code coverage tracking
    2. Discovers and executes all tests in the 'Tests' directory
    3. Exits with code 1 if any tests fail
    4. Generates coverage reports in both console and HTML format
    Returns:
        None
    Raises:
        SystemExit: If any tests fail (with exit code 1)
    Notes:
        - Tests are discovered automatically from the 'Tests' directory
        - HTML coverage report is generated in 'coverage_html' directory
        - Requires the 'coverage' module to be installed
    """
    # Configure logging for tests
    logger = logging.getLogger(__name__)

    logger.info("Starting test run")

    try:
        # Start coverage tracking
        cov = coverage.Coverage()
        cov.start()
    except coverage.CoverageException as e:
        logger.error("Failed to start coverage tracking: %s", str(e))
        sys.exit(1)

    # Discover and run tests
    loader = unittest.TestLoader()
    tests = loader.discover('tests')
    runner = unittest.TextTestRunner()
    test_result = runner.run(tests)
    if not test_result.wasSuccessful():
        sys.exit(1)

    try:
        # Stop coverage tracking
        cov.stop()
        cov.save()

        # Generate coverage report
        cov.report()
        # Generate HTML report
        cov.html_report(directory='coverage_html')
        # Generate XML report for CI
        cov.xml_report()
    except coverage.CoverageException as e:
        logger.error("Failed to generate coverage report: %s", str(e))
        sys.exit(1)

    logger.info("Test run completed. Success: %s", test_result.wasSuccessful())


if __name__ == '__main__':
    run_tests()
