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
    3. Exits with code 1 if any tests fail (ignoring coverage)
    4. Generates coverage reports for informational purposes only
    """
    # Configure logging
    logger = setup_logging()

    logger.info("Starting test run")

    try:
        # Start coverage tracking
        cov = coverage.Coverage(source=['src'])
        cov.start()

        # Set up event loop for async tests
        policy = asyncio.get_event_loop_policy()
        loop = policy.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Discover and run tests
            loader = unittest.TestLoader()
            tests = loader.discover('tests')
            runner = unittest.TextTestRunner(verbosity=2)

            # Run tests and capture result
            test_result = runner.run(tests)

            # Print test summary
            logger.info("\nTest Summary:")
            logger.info("Ran %d tests", test_result.testsRun)
            logger.info("Failures: %d", len(test_result.failures))
            logger.info("Errors: %d", len(test_result.errors))

            # Log any errors or failures
            if test_result.errors:
                logger.error("\nTest Errors:")
                for test, error in test_result.errors:
                    logger.error("%s:\n%s", test, error)
                    
            if test_result.failures:
                logger.error("\nTest Failures:")
                for test, failure in test_result.failures:
                    logger.error("%s:\n%s", test, failure)
                    
        finally:
            # Clean up async resources
            try:
                pending = asyncio.all_tasks(loop)
                if pending:
                    # Cancel all pending tasks
                    for task in pending:
                        task.cancel()
                    # Wait for cancellation to complete
                    try:
                        loop.run_until_complete(
                            asyncio.wait_for(
                                asyncio.gather(*pending, return_exceptions=True),
                                timeout=10.0  # 10 seconds timeout
                            )
                        )
                    except asyncio.TimeoutError:
                        logger.error("Async cleanup timed out after 10 seconds")
            except Exception as e:
                logger.error("Error during async cleanup: %s", str(e))
            finally:
                loop.close()
                asyncio.set_event_loop(None)

        # Stop coverage and generate reports
        cov.stop()
        cov.save()

        # Generate coverage reports (for information only)
        generate_coverage_report(cov, logger)

        # Exit based on test success only, ignoring coverage percentage
        successful = test_result.wasSuccessful()
        logger.info("\nTest run %s", "successful" if successful else "failed")
        sys.exit(0 if successful else 1)

    except Exception as e:
        logger.error("Error during test execution: %s", str(e), exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    run_tests()
