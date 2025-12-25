import atexit
import logging

logger = logging.getLogger(__name__)


def _cleanup_bot_session():
	"""
	Close the bot's HTTP session if one exists.
	
	Performs a lazy import to obtain the bot instance and, if the instance exposes a `session` attribute, calls its `close()` method. Any exceptions raised during lookup or closing are swallowed and logged at debug level.
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
	"""
	Dispose available database engines to help avoid hanging background resources at process exit.
	
	Attempts a lazy import of the package's `db` module; if present, disposes `db.engine` (sync) and then disposes either `db.async_engine.sync_engine` (if exposed) or `db.async_engine` itself. All disposal attempts swallow exceptions and log failures at the debug level to avoid raising during shutdown.
	"""
	def _safe_dispose(obj, label: str) -> None:
		"""
		Dispose an object if it exposes a callable `dispose` method, logging failures without raising.
		
		If `obj` is None nothing is done. If `obj` has a callable `dispose` attribute it will be called; any exception raised during disposal is caught and logged at debug level using `label` to identify the resource.
		
		Parameters:
			obj: The object to dispose (may be None or not implement `dispose`).
			label (str): Human-readable name for the object used in debug log messages.
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
