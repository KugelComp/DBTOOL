"""
session_logger.py — Structured audit logger that writes exclusively to the
                    Django Database (logs.LogEntry model).

File-based logging has been removed. All audit records are visible in
Django Admin at /admin/logs/logentry/.

Auto-deletion of records older than 4 days is handled by the background
cleanup task in app.py (purge_old_log_entries).
"""

import logging
from typing import Optional


class DjangoDbHandler(logging.Handler):
    """Writes log records directly to the Django LogEntry model."""

    def emit(self, record):
        try:
            # Background threads (export/import workers) don't share the main
            # thread's DB connection. Close any stale connection first so Django
            # opens a fresh one for this thread automatically.
            from django.db import connection as _db_conn
            try:
                _db_conn.ensure_connection()
            except Exception:
                _db_conn.close()   # Force a fresh connection on next query

            from logs.models import LogEntry
            LogEntry.objects.create(
                level=record.levelname,
                message=record.getMessage(),
                module=record.module,
                line=record.lineno,
                client_ip=getattr(record, 'client_ip', None),
                user=getattr(record, 'user', None),
                session_id=getattr(record, 'session_id', None),
                action=getattr(record, 'action', None),
                exception=self.formatException(record.exc_info) if record.exc_info else None,
            )
        except Exception:
            self.handleError(record)



class SessionLogger:
    """
    Per-session audit logger.

    Writes to the Django Database only — no log files are created.
    Records are visible in Django Admin and auto-purged after 4 days.
    """

    def __init__(self, session_id: str, username: str, client_ip: str = "unknown", log_dir: str = "logs"):
        self.session_id = session_id
        self.username = username
        self.client_ip = client_ip
        # log_dir kept for API compatibility but no longer used for file output

        self.logger = logging.getLogger(f"session_{session_id}")
        self.logger.setLevel(logging.INFO)
        self.logger.handlers = []   # Clear any residual handlers
        self.logger.propagate = False

        # Single handler — Django DB only
        handler = DjangoDbHandler()
        self.logger.addHandler(handler)

        # Context injected into every log record
        self.extra = {
            'user': self.username,
            'session_id': self.session_id[:8],
            'client_ip': self.client_ip,
        }

    def info(self, message: str, action: str = None):
        extra = {**self.extra, **({"action": action} if action else {})}
        self.logger.info(message, extra=extra)

    def warning(self, message: str, action: str = None):
        extra = {**self.extra, **({"action": action} if action else {})}
        self.logger.warning(message, extra=extra)

    def error(self, message: str, action: str = None):
        extra = {**self.extra, **({"action": action} if action else {})}
        self.logger.error(message, extra=extra)

    def close(self):
        """Flush and remove handlers."""
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)


def get_session_logger(session_id: str, username: str, client_ip: str = "unknown", **kwargs) -> SessionLogger:
    """Factory function — extra kwargs (e.g. log_dir) accepted but ignored."""
    return SessionLogger(session_id, username, client_ip)
