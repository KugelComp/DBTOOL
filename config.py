"""
config.py — Application configuration loaded from environment variables.
All secrets and machine-specific paths must be set in a .env file
(see .env.example). Never hardcode credentials here.
"""
import os
from pathlib import Path

# Load .env file if python-dotenv is available (preferred in development).
# In production, set environment variables directly via your OS / container.
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).parent / ".env")
except ImportError:
    pass  # dotenv not installed — env vars must be set externally

# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------
SESSION_SECRET_KEY = os.environ.get(
    "SESSION_SECRET_KEY",
    "insecure-fallback-do-not-use-in-production"
)
SESSION_TIMEOUT_HOURS = int(os.environ.get("SESSION_TIMEOUT_HOURS", "24"))

# ---------------------------------------------------------------------------
# Predefined database hosts
# ---------------------------------------------------------------------------
HOSTS = {
    "db_local": {"ip": "localhost", "port": 3306},
    "db_demo":  {"ip": "20.40.56.140", "port": 3306},
    "db_test":  {"ip": "127.0.0.1",   "port": 3306},
}

# ---------------------------------------------------------------------------
# Dump modes
# ---------------------------------------------------------------------------
Types_of_dump = {
    "full_dump": "full_dump",
    "partial":   "partial",
}

Dump_Modes = {
    "Plain":      "Plain",
    "Obscure":    "Obscure",
    "SERVICE OFF": "SERVICE OFF",
    "TENANT NAME": "TENANT NAME",
}

# ---------------------------------------------------------------------------
# File paths — relative by default so they work on any machine
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent

obscure_file = os.environ.get("OBSCURE_FILE", str(BASE_DIR / "obscure.sql"))
service_off_file = os.environ.get("SERVICE_OFF_FILE", str(BASE_DIR / "service_off.sql"))
dump_path    = os.environ.get("DUMP_PATH", str(BASE_DIR / "dumps"))
Output_file  = ""

# ---------------------------------------------------------------------------
# Default Target Database for Obscure / Service-Off exports
# (avoids slow DB cloning by using a migration-like approach instead)
# ---------------------------------------------------------------------------
DEFAULT_TARGET_ENABLED  = os.environ.get("DEFAULT_TARGET_ENABLED", "true").lower() == "true"
DEFAULT_TARGET_HOST     = os.environ.get("DEFAULT_TARGET_HOST", "localhost")
DEFAULT_TARGET_PORT     = int(os.environ.get("DEFAULT_TARGET_PORT", "3306"))
DEFAULT_TARGET_USER     = os.environ.get("DEFAULT_TARGET_USER", "root")
DEFAULT_TARGET_PASSWORD = os.environ.get("DEFAULT_TARGET_PASSWORD", "")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_DIR = os.environ.get("LOG_DIR", str(BASE_DIR / "logs"))
