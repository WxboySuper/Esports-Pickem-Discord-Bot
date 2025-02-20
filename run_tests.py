import unittest
import coverage
import sys
import logging
import asyncio
from pathlib import Path
from typing import Tuple

def setup_logging() -> logging.Logger:
    """Configure logging for test runner with rotating file handler"""
    # Set up logs directory
    logs_dir = Path(__file__).parent / 'logs'
    logs_dir.mkdir(exist_ok=True)

    # Configure root logger first - this affects all loggers
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Set up file handler for test runner
    log_file = logs_dir / 'test_runner.log'
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    )
    root_logger.addHandler(file_handler)

    # Get the logger for the test runner
    logger = logging.getLogger(__name__)
    return logger

def run_test_suite(test_loader: unittest.TestLoader, test_dir: Path) -> Tuple[unittest.TestResult, bool]:
    """Run the test suite and return results"""
    suite = test_loader.discover(str(test_dir), pattern='test_*.py')
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result, result.wasSuccessful()

def generate_coverage_report(cov: coverage.Coverage, logger: logging.Logger) -> None:
    """Generate and display coverage reports"""
    logger.info("\nGenerating coverage reports...")

    # Console report
    logger.info("\nCoverage Summary:")
    total = cov.report(show_missing=True)
    logger.info(f"Total coverage: {total:.2f}%")

    # HTML report
    html_dir = Path('coverage_html')
    html_dir.mkdir(exist_ok=True)
    cov.html_report(directory=str(html_dir))
    logger.info(f"HTML report generated: {html_dir}/index.html")

    # XML report
    xml_file = Path('coverage.xml')
    cov.xml_report(outfile=str(xml_file))
    logger.info(f"XML report generated: {xml_file}")

def run_tests():
    """
    Runs all unit tests and generates coverage reports.
    This function performs the following steps:
    1. Starts code coverage tracking
    2. Discovers and executes all tests in the 'tests' directory
    3. Exits with code 1 if any tests fail
    4. Generates coverage reports in both console and HTML format
    """
    # Configure logging
    logger = setup_logging()

    logger.info("Starting test run")

    try:
        # Start coverage tracking
        cov = coverage.Coverage(source=['src'])
        cov.start()
    except coverage.CoverageException as e:
        logger.error("Failed to start coverage tracking: %s", str(e))
        sys.exit(1)

    # Set up event loop for async tests
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # Discover and run tests
        loader = unittest.TestLoader()
        tests = loader.discover('tests')
        runner = unittest.TextTestRunner(verbosity=2)
        test_result = runner.run(tests)
    finally:
        # Clean up async resources
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()

        group = asyncio.gather(*pending, return_exceptions=True)
        loop.run_until_complete(group)
        loop.close()
        asyncio.set_event_loop(None)

    try:
        # Stop coverage tracking
        cov.stop()
        cov.save()

        # Generate coverage report
        logger.info("\nCoverage Summary:")
        cov.report(show_missing=True)

        # Generate HTML report
        html_dir = Path('coverage_html')
        html_dir.mkdir(exist_ok=True)
        cov.html_report(directory=str(html_dir))

        # Generate XML report for CI
        cov.xml_report()

        logger.info("Test run completed. Success: %s", test_result.wasSuccessful())

        if not test_result.wasSuccessful():
            sys.exit(1)

    except coverage.CoverageException as e:
        logger.error("Failed to generate coverage report: %s", str(e))
        sys.exit(1)

if __name__ == '__main__':
    run_tests()
