"""
Mental Outline VPN Platform — application entry point.

Bootstrap sequence (Phase 0.5):
  1.  Load environment variables (python-dotenv).
  2.  Load and validate configuration (Settings).
  3.  Initialise logger (setup_logging — must run before any other import).
  4.  Initialise database (Alembic migrations to HEAD).
  5.  Initialise cache (CacheService / MemoryCache).
  6.  Initialise service registry (all Phase 0.x services).
  7.  Load localisation (Translator warm-up).
  8.  Register event bus subscribers.
  9.  Initialise scheduler (APScheduler, no jobs yet).
 10.  Register middlewares (group=-2: request_context; group=-1: auth, language, activity).
 11.  Register handlers (start, admin, error).
 12.  Register global error handler (must be last).
 13.  Run startup health check (all subsystems).
 14.  Transition lifecycle to RUNNING.
 15.  Start Telegram bot (polling).

Graceful shutdown sequence:
  a. Stop accepting new updates (updater.stop).
  b. Finish in-flight handlers (application.stop).
  c. Stop scheduler.
  d. Stop cache background tasks.
  e. Close database.
  f. Flush logs.
  g. Transition lifecycle to STOPPED.
  h. Log shutdown summary.

To add a new handler group:
  - Create app/handlers/my_feature.py with register(application).
  - Import and call it in the "Register handlers" section below.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
import time
from pathlib import Path

# Ensure the bot/ directory is on sys.path when running as `python main.py`
# from inside the bot/ folder or from the repo root.
sys.path.insert(0, str(Path(__file__).parent))

# ── Step 1: Load environment variables ────────────────────────────────────────
# python-dotenv is a soft dependency; the bot runs without a .env file
# when secrets are injected via the environment (Replit Secrets, Docker, etc.).
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass   # dotenv not installed — rely on OS environment.

# ── Step 3 (early): Logger must be ready before any other module uses it. ─────
# Imported at top level so setup_logging() is callable immediately.
from app.utils.logger import setup_logging  # noqa: E402


async def main() -> None:
    """Async application bootstrap — runs the full 15-step startup sequence."""
    _boot_start = time.monotonic()

    # ── Step 2: Configuration ─────────────────────────────────────────────
    from config import settings  # imported after dotenv so env vars are loaded

    # ── Step 3: Logger ────────────────────────────────────────────────────
    setup_logging(
        level=settings.log_level,
        is_development=settings.is_development,
    )
    logger = logging.getLogger(__name__)
    logger.info(
        "━━━ Mental Outline VPN Platform — starting ━━━  env=%s  lang=%s",
        settings.environment,
        settings.default_language,
    )

    # ── Lifecycle: STARTING ───────────────────────────────────────────────
    from app.lifecycle import lifecycle, AppState
    # lifecycle is already in STARTING state at import time.
    logger.info("Lifecycle state: %s", lifecycle.state.value.upper())

    # ── Step 4: Database ──────────────────────────────────────────────────
    logger.info("[4/15] Initialising database…")
    from database import DatabaseManager
    db = DatabaseManager.initialise(settings.database_url)
    await db.init()
    logger.info("       Database ready — scheme=%s", settings.database_url.split("://")[0])

    # ── Step 5: Cache ─────────────────────────────────────────────────────
    logger.info("[5/15] Initialising cache…")
    from app.cache import cache
    cache.start()
    logger.info("       Cache ready — backend=%s", type(cache._backend).__name__)

    # ── Step 6: Service registry ──────────────────────────────────────────
    logger.info("[6/15] Initialising service registry…")
    from app.services.registry import ServiceRegistry
    from app.services import SettingsService
    registry = ServiceRegistry(db)
    registry.initialise_all()
    # Seed default settings and feature flags (safe on every startup).
    settings_service = registry.get(SettingsService)
    await settings_service.seed_defaults()
    logger.info("       Registry ready — %d services", len(registry.list_registered()))

    # ── Step 7: Localisation ──────────────────────────────────────────────
    logger.info("[7/15] Loading localisation…")
    from locales.translator import Translator
    _translator = Translator(settings.default_language)   # warm-up
    logger.info("       Localisation ready — default_lang=%s", settings.default_language)

    # ── Step 8: Event bus ─────────────────────────────────────────────────
    logger.info("[8/15] Registering event bus subscribers…")
    from app.events import bus, EventType

    @bus.on(EventType.APP_STARTED)
    async def _on_app_started(**_: object) -> None:
        logger.info("EventBus: APP_STARTED received")

    @bus.on(EventType.APP_STOPPED)
    async def _on_app_stopped(**_: object) -> None:
        logger.info("EventBus: APP_STOPPED received")

    logger.info("       Event bus ready — 2 core subscriber(s) registered")

    # ── Step 9: Scheduler ─────────────────────────────────────────────────
    logger.info("[9/15] Initialising scheduler…")
    from app.scheduler import Scheduler
    scheduler = Scheduler()
    scheduler.register_jobs(sync_service=registry.get_or_none(__import__("app.services.outline_server_sync_service", fromlist=["OutlineServerSyncService"]).OutlineServerSyncService), reservation_service=registry.get_or_none(__import__("app.services.server_reservation_service", fromlist=["ServerReservationService"]).ServerReservationService), lifecycle_service=registry.get_or_none(__import__("app.services.vpn_lifecycle_service", fromlist=["VPNLifecycleService"]).VPNLifecycleService), job_service=registry.get_or_none(__import__("app.services.background_job_service", fromlist=["BackgroundJobService"]).BackgroundJobService), health_service=registry.get_or_none(__import__("app.services.health_service", fromlist=["HealthService"]).HealthService), order_service=registry.get_or_none(__import__("app.services.order_service", fromlist=["OrderService"]).OrderService), free_trial_upgrade_service=registry.get_or_none(__import__("app.services.free_trial_upgrade_service", fromlist=["FreeTrialUpgradeService"]).FreeTrialUpgradeService))
    scheduler.start()
    registry.inject_scheduler(scheduler)
    logger.info("       Scheduler ready")

    # ── Step 10: Build Telegram application ───────────────────────────────
    from telegram.ext import Application, TypeHandler
    from telegram import Update

    application = (
        Application.builder()
        .token(settings.bot_token)
        .build()
    )

    # Expose shared resources to handlers via bot_data.
    application.bot_data["db"]              = db
    application.bot_data["registry"]        = registry
    application.bot_data["cache"]           = cache
    application.bot_data["scheduler"]       = scheduler
    application.bot_data["settings"]        = settings
    from app.services import (
        CustomerEntryService,
        CustomerNavigationService,
        LanguageService,
        PreferenceService,
        UserService,
    )
    application.bot_data["user_service"] = registry.get(UserService)
    application.bot_data["language_service"] = registry.get(LanguageService)
    application.bot_data["preference_service"] = registry.get(PreferenceService)
    application.bot_data["customer_entry_service"] = registry.get(CustomerEntryService)
    application.bot_data["customer_navigation_service"] = registry.get(CustomerNavigationService)

    # ── Step 10: Register middlewares ─────────────────────────────────────
    logger.info("[10/15] Registering middlewares…")
    from app.middlewares import (
        request_context_middleware_handler,
        auth_middleware_handler,
        language_middleware_handler,
        activity_middleware_handler,
    )

    # PTB executes at most one matching handler per group, so every
    # middleware gets its own group to guarantee deterministic ordering.
    application.add_handler(
        TypeHandler(Update, request_context_middleware_handler), group=-4
    )
    application.add_handler(TypeHandler(Update, auth_middleware_handler),     group=-3)
    application.add_handler(TypeHandler(Update, language_middleware_handler), group=-2)
    application.add_handler(TypeHandler(Update, activity_middleware_handler), group=-1)
    logger.info("       Middlewares registered: request_context, auth, language, activity")

    # ── Step 11: Register handlers ────────────────────────────────────────
    logger.info("[11/15] Registering handlers…")
    from app.handlers import (
        register_start,
        register_customer_navigation,
        register_customer_account,
        register_package_catalog,
        register_customer_keys,
        register_admin,
        register_admin_server,
        register_admin_outline,
        register_error,
    )

    register_start(application)
    register_package_catalog(application)
    register_customer_keys(application)
    register_customer_account(application)
    register_customer_navigation(application)
    register_admin(application)
    register_admin_server(application)
    register_admin_outline(application)
    logger.info("       Handlers registered: start, package_catalog, customer_keys, customer_account, customer_navigation, admin, admin_server, admin_outline")

    # ── Step 12: Global error handler (must be last) ──────────────────────
    logger.info("[12/15] Registering global error handler…")
    register_error(application)
    logger.info("       Error handler registered")

    # ── Step 13: Startup health check ─────────────────────────────────────
    logger.info("[13/15] Running startup health check…")
    from app.utils.startup_checks import run_all_checks, StartupError
    try:
        await run_all_checks(
            settings=settings,
            db=db,
            scheduler=scheduler,
            cache_service=cache,
        )
    except StartupError as exc:
        logger.critical("Startup validation failed: %s", exc)
        await _shutdown(scheduler, cache, db, application, lifecycle, started=False)
        sys.exit(1)
    logger.info("       All health checks passed ✓")

    # ── Step 14: Lifecycle → RUNNING ──────────────────────────────────────
    logger.info("[14/15] Transitioning lifecycle to RUNNING…")
    lifecycle.set_state(AppState.RUNNING)
    await bus.emit(EventType.APP_STARTED, settings=settings)

    # ── Step 15: Run the bot (polling) ────────────────────────────────────
    _boot_ms = (time.monotonic() - _boot_start) * 1000
    logger.info(
        "[15/15] Bot is starting — polling for updates… (boot=%.0fms)",
        _boot_ms,
    )
    try:
        await application.initialize()
        await application.start()

        # Inject bot into registry/HealthService after initialize().
        registry.inject_bot(application.bot)

        await application.updater.start_polling(drop_pending_updates=True)

        logger.info("━━━ Bot is running ━━━  Press Ctrl+C to stop.")
        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()

        def request_shutdown() -> None:
            if not stop_event.is_set():
                logger.info("Shutdown signal received.")
                stop_event.set()

        registered_signals: list[signal.Signals] = []
        for shutdown_signal in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(shutdown_signal, request_shutdown)
                registered_signals.append(shutdown_signal)
            except (NotImplementedError, RuntimeError):
                # Some platforms do not expose event-loop signal handlers.
                # KeyboardInterrupt is still handled by the outer exception path.
                logger.debug("Signal handler unavailable for %s", shutdown_signal.name)

        await stop_event.wait()

        for shutdown_signal in registered_signals:
            loop.remove_signal_handler(shutdown_signal)

    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown signal received.")
    finally:
        lifecycle.set_state(AppState.STOPPING)
        await _shutdown(scheduler, cache, db, application, lifecycle, started=True)


async def _shutdown(
    scheduler,
    cache,
    db,
    application,
    lifecycle,
    *,
    started: bool,
) -> None:
    """
    Execute the graceful shutdown sequence.

    Steps:
      a. Stop accepting new updates (updater.stop / application.stop).
      b. Stop the scheduler (finish running jobs).
      c. Stop cache background tasks.
      d. Close database connections.
      e. Flush logs.
      f. Transition lifecycle to STOPPED.
      g. Log shutdown summary.
    """
    logger = logging.getLogger(__name__)
    _shutdown_start = time.monotonic()

    from app.events import bus, EventType
    from app.lifecycle import AppState

    logger.info("Shutdown: stopping Telegram updater…")
    try:
        if started and application.updater and application.updater.running:
            await application.updater.stop()
        if started:
            await application.stop()
        await application.shutdown()
    except Exception as exc:
        logger.warning("Shutdown: application stop raised: %s", exc)

    logger.info("Shutdown: stopping scheduler…")
    try:
        scheduler.shutdown()
    except Exception as exc:
        logger.warning("Shutdown: scheduler stop raised: %s", exc)

    logger.info("Shutdown: stopping cache…")
    try:
        cache.stop()
    except Exception as exc:
        logger.warning("Shutdown: cache stop raised: %s", exc)

    logger.info("Shutdown: closing database…")
    try:
        await db.close()
    except Exception as exc:
        logger.warning("Shutdown: db close raised: %s", exc)

    # Emit stopped event before flushing logs.
    try:
        await bus.emit(EventType.APP_STOPPED)
    except Exception:
        pass

    _shutdown_ms = (time.monotonic() - _shutdown_start) * 1000
    logger.info(
        "━━━ Bot stopped gracefully ━━━  shutdown took %.0fms", _shutdown_ms
    )

    # Lifecycle → STOPPED.
    try:
        lifecycle.set_state(AppState.STOPPED)
    except Exception:
        pass

    # Flush log handlers.
    logging.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
