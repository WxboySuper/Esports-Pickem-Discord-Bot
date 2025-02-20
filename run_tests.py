import unittest
import coverage
import sys
import logging
from logging.handlers import RotatingFileHandler
import asyncio
from pathlib import Path
from typing import Tuple

def setup_logging() -> logging.Logger:
    """Configure logging for test runner with rotating file handler"""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Set up rotating file handler
    log_file = Path(__file__).parent / 'logs' / 'test_runner.log'
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5*1024*1024,  # 5MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    # Remove any existing handlers and add our new one
    logger.handlers.clear()
    logger.addHandler(file_handler)

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
    """Run all tests and generate coverage"""
    logger = setup_logging()

    try:
        # Initialize coverage
        cov = coverage.Coverage(
            config_file='.coveragerc',
            source=['src'],
            branch=True,
            omit=[
                '*/site-packages/*',
                '*/tests/*',
                '*/__init__.py',
                '*/path_helper.py',
                'run_tests.py'
            ]
        )

        # Start coverage
        logger.info("Starting coverage tracking")
        cov.start()

        # Set up test environment
        test_dir = Path(__file__).parent / 'tests'
        test_loader = unittest.TestLoader()

        # Run tests
        logger.info("Running tests...")

        # Handle both sync and async tests
        policy = asyncio.get_event_loop_policy()
        loop = policy.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result, success = run_test_suite(test_loader, test_dir)
        finally:
            # Clean up async resources
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()

            group = asyncio.gather(*pending, return_exceptions=True)
            loop.run_until_complete(group)
            loop.close()
            asyncio.set_event_loop(None)

        # Stop and save coverage
        logger.info("Stopping coverage tracking")
        cov.stop()
        cov.save()

        # Generate reports
        generate_coverage_report(cov, logger)

        logger.info("Test run complete")
        sys.exit(not success)

    except coverage.CoverageException as ce:
        logger.error(f"Coverage error: {ce}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error running tests: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Ensure everything is cleaned up
        try:
            cov.stop()
            cov.save()
        except Exception:
            pass

if __name__ == '__main__':
    run_tests()
