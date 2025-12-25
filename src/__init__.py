import atexit
import logging

logger = logging.getLogger(__name__)


def _cleanup_bot_session():
	"""Close bot HTTP session if present.

	This function intentionally does lazy imports to avoid import-time
	side-effects when the package is imported.
	"""
	try:
		from .bot_instance import get_bot_instance
		bot = get_bot_instance()
		if bot is None:
			return
		sess = getattr(bot, "session", None)
		if sess is None:
			return
		try:
			# close() is safe to call; prefer sync close to avoid
			# requiring an event loop at shutdown
			sess.close()
		except Exception:
			logger.debug("Failed to close bot session", exc_info=True)
	except Exception:
		logger.debug("Error during bot session cleanup", exc_info=True)


def _shutdown_scheduler():
	"""Shutdown any background scheduler if available."""
	try:
		from . import scheduler
		if hasattr(scheduler, "shutdown"):
			try:
				scheduler.shutdown(wait=False)
			except Exception:
				logger.debug("Failed to shutdown scheduler", exc_info=True)
	except Exception:
		logger.debug("Scheduler cleanup not available", exc_info=True)


def _dispose_db_engines():
	"""Dispose sync and async DB engines if present."""
	def _safe_dispose(obj, label: str) -> None:
		"""Call dispose() on obj if available, swallowing exceptions and
		logging any failures with the provided label.
		"""
		if obj is None:
			return
		try:
			dispose_fn = getattr(obj, "dispose", None)
			if callable(dispose_fn):
				dispose_fn()
		except Exception:
			logger.debug(f"Failed to dispose {label}", exc_info=True)

	try:
		from . import db
	except Exception:
		logger.debug("DB cleanup not available", exc_info=True)
		return

	# Dispose sync engine if present
	_safe_dispose(getattr(db, "engine", None), "sync engine")

	# Dispose async engine's underlying sync engine, or the async engine itself
	async_engine = getattr(db, "async_engine", None)
	if async_engine is None:
		return

	# Prefer disposing the underlying sync_engine if exposed
	sync_engine = getattr(async_engine, "sync_engine", None)
	if sync_engine is not None:
		_safe_dispose(sync_engine, "async engine (sync_engine)")
	else:
		_safe_dispose(async_engine, "async engine")


def _cleanup():
	"""Attempt to cleanly shutdown background resources on process exit.

	This helps test runners and manual runs exit without hanging due to
	background schedulers, DB connections, or aiohttp sessions.
	"""

	# Execute cleanup steps. Keeping these as separate functions reduces the
	# cyclomatic complexity of this wrapper and improves readability.
	_cleanup_bot_session()
	_shutdown_scheduler()
	_dispose_db_engines()


atexit.register(_cleanup)

