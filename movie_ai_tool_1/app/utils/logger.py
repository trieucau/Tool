"""
Centralized logging configuration for Movie AI Tool.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


def setup_logger(
    name: str,
    log_file: Optional[Path] = None,
    level: int = logging.DEBUG,
) -> logging.Logger:
    """
    Create and configure a logger with console and optional file handlers.

    Args:
        name: Logger name (usually __name__).
        log_file: Optional path for log file output.
        level: Logging level.

    Returns:
        Configured Logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # Console handler
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File handler — auto-rotate at 1MB, keep 0 backups (just truncate & restart)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        from logging.handlers import RotatingFileHandler
        fh = RotatingFileHandler(
            log_file, mode="a", maxBytes=1 * 1024 * 1024,
            backupCount=0, encoding="utf-8"
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


# Track whether the log file has been cleared for this session
_session_log_cleared = False


def get_logger(name: str) -> logging.Logger:
    """Get or create a logger for the given module name.
    
    Log file is cleared once per app session (on first call),
    so logs never accumulate across restarts.
    """
    global _session_log_cleared
    from app.config import config

    log_dir = config.paths.root / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "movie_ai.log"

    # Clear the log file once at the start of each session
    if not _session_log_cleared:
        try:
            if log_file.exists():
                log_file.write_text("", encoding="utf-8")
        except Exception:
            pass
        _session_log_cleared = True

    return setup_logger(name, log_file)
