"""
Scheduler package.

Houses all background / periodic tasks.

Powered by APScheduler (async job scheduler).
The scheduler instance is created once in main.py and passed here.

Planned jobs (Phase 4+):
  • subscription_expiry_checker  — Revoke keys for expired subscriptions.
  • server_health_monitor        — Ping all registered servers every 5 min.
  • daily_stats_report           — Send usage summary to admins each morning.
"""

from .base import Scheduler

__all__ = ["Scheduler"]
