"""
import_dump.py — Import SQL dump files into a target MySQL database.

Key design decisions:
  - Sequential import (not parallel) to avoid lock contention on the target.
  - Per-table auto-retry (3 attempts, 5 s / 10 s back-off) for transient
    InnoDB/network errors that self-heal when server pressure eases.
  - lock_wait_timeout / innodb_lock_wait_timeout set to 600 s (was 60 s).
    The old 60 s value caused "fails first time, passes on retry" because the
    server was under load with 600+ tables streaming in.  600 s gives plenty
    of room without ever blocking the hard per-file 3 600 s ceiling.
"""

import os
import subprocess
import threading
import time
import uuid
import logging

import mysql.connector
from debug_logger import log_debug

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Transient error substrings — safe to auto-retry, caused by server pressure.
# ---------------------------------------------------------------------------
_TRANSIENT_ERRORS = (
    "lock wait timeout",
    "innodb_lock_wait_timeout",
    "deadlock found",
    "try restarting transaction",
    "lost connection to mysql",
    "mysql server has gone away",
    "can't connect to mysql",
    "connection refused",
    "error reading communication packets",
)

# Maximum per-table retry attempts and delays (seconds) before each attempt.
_MAX_ATTEMPTS = 3
_RETRY_DELAYS = (0, 5, 10)  # attempt 1 → immediate, attempt 2 → 5 s, attempt 3 → 10 s


def _is_transient(error_text: str) -> bool:
    """Return True if the MySQL error message looks like a transient server issue."""
    lowered = error_text.lower()
    return any(kw in lowered for kw in _TRANSIENT_ERRORS)


def _strip_mysql_warning(text: str) -> str:
    """Remove the noisy 'mysql: [Warning] Using a password…' prefix from stderr."""
    import re
    return re.sub(
        r"mysql:\s*\[Warning\]\s*Using a password on the command line interface can be insecure\.?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()


def perform_import(
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    dump_path: str,
    source_database: str = None,
    job_control: dict = None,
    exclude_tables: list = None,
    import_only_tables: list = None,
):
    """
    Import every SQL file found in *dump_path* into *database* on *host*.

    Import order (always sequential):
      1. ``00_*.sql``  — CREATE DATABASE / schema init
      2. ``<table>.sql`` — one file per table, with per-table auto-retry
      3. ``01_*.sql``, ``02_*.sql`` — routines, triggers, post-scripts

    Parameters
    ----------
    source_database:
        Original DB name written into the SQL files' USE statement.  When it
        differs from *database* (e.g. tenant-change migration) every occurrence
        is replaced so the import targets the correct schema.
    exclude_tables:
        Table names to skip entirely (they failed during export and have no
        corresponding .sql file).
    import_only_tables:
        When set, restrict the table stage to only these names.  Used on retry
        so we don't re-import all 630 tables when only 20 need a second chance.

    Returns
    -------
    (success: bool, message: str, errors: list[dict])
        *errors* contains ``{"file": "<name>.sql", "error": "<mysql stderr>"}``
        entries for every file that ultimately could not be imported.
    """

    # ------------------------------------------------------------------
    # 1. Ensure target database exists
    # ------------------------------------------------------------------
    try:
        conn = mysql.connector.connect(
            host=host, port=port, user=user, password=password,
            connection_timeout=30,
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database}`")
        conn.commit()
        cursor.close()
        conn.close()
    except mysql.connector.Error as exc:
        return False, f"Failed to connect / create target database: {exc}", []

    # ------------------------------------------------------------------
    # 2. Discover and categorise SQL files
    # ------------------------------------------------------------------
    try:
        all_files = sorted(f for f in os.listdir(dump_path) if f.endswith(".sql"))
    except Exception as list_exc:
        return False, f"Dump directory not found: {dump_path} ({list_exc})", []

    if not all_files:
        return False, "No SQL files found to import.", []

    init_files  = [f for f in all_files if f.startswith("00_")]
    post_files  = [f for f in all_files if f.startswith("01_") or f.startswith("02_")]
    table_files = [f for f in all_files if f not in init_files and f not in post_files]

    # Retry filter — only process the re-exported subset
    if import_only_tables is not None:
        only_set = {f"{t}.sql" for t in import_only_tables}
        table_files = [f for f in table_files if f in only_set]
        log_debug(f"[IMPORT] Retry mode: restricting to {len(table_files)} table(s)")

    # Exclude tables that failed during export (no .sql file → would error)
    if exclude_tables:
        exclude_set = set(exclude_tables)
        before = len(table_files)
        table_files = [f for f in table_files if f.replace(".sql", "") not in exclude_set]
        skipped = before - len(table_files)
        if skipped:
            log_debug(f"[IMPORT] Skipping {skipped} table(s) that failed during export")

    table_files.sort()

    # ------------------------------------------------------------------
    # 3. Initialise progress counter
    # ------------------------------------------------------------------
    total = len(init_files) + len(table_files) + len(post_files)
    if job_control:
        job_control["progress"]["total"]   = total
        job_control["progress"]["current"] = 0

    # ------------------------------------------------------------------
    # 4. Shared state for status display
    # ------------------------------------------------------------------
    active_set  = set()     # files currently being processed
    status_lock = threading.Lock()

    def _update_status_start(label: str):
        if not job_control:
            return
        with status_lock:
            active_set.add(label)
            _refresh_status()

    def _update_status_finish(label: str):
        if not job_control:
            return
        with status_lock:
            active_set.discard(label)
            _refresh_status()
        job_control["progress"]["current"] += 1

    def _refresh_status():
        """Must be called while holding status_lock."""
        if not job_control:
            return
        items   = list(active_set)[:2]
        extra   = len(active_set) - 2
        text    = f"Importing: {', '.join(items)}" if items else "Processing…"
        if extra > 0:
            text += f" + {extra} more…"
        job_control["status"] = text

    # ------------------------------------------------------------------
    # 5. Per-file import worker
    # ------------------------------------------------------------------
    def _import_file(sql_file: str):
        """
        Import a single SQL file.  Returns None on success, or a dict
        ``{"file": sql_file, "error": <message>}`` on permanent failure.
        """
        full_path  = os.path.join(dump_path, sql_file)
        start_time = time.monotonic()

        # --- cancel / pause ---
        if job_control and job_control["cancel_event"].is_set():
            return {"file": sql_file, "error": "Cancelled by user"}
        if job_control:
            job_control["pause_event"].wait()

        # --- size label (for status display) ---
        size_label = ""
        try:
            mb = os.path.getsize(full_path) / (1024 * 1024)
            size_label = f"{mb:.1f} MB" if mb < 1024 else f"{mb/1024:.2f} GB"
        except OSError:
            pass

        display_label = f"{sql_file} ({size_label})" if size_label else sql_file
        _update_status_start(display_label)

        # --- Read file once; shared across all retry attempts ---
        try:
            with open(full_path, "r", encoding="utf-8") as fh:
                raw_sql = fh.read()
        except OSError as exc:
            _update_status_finish(display_label)
            return {"file": sql_file, "error": f"Cannot read file: {exc}"}

        # --- Prepend session settings ---
        # lock_wait_timeout / innodb_lock_wait_timeout raised to 600 s.
        # The old value (60 s) caused legitimate tables to fail on the first
        # bulk pass when the server was under memory/lock pressure; on an
        # explicit retry (20 tables) the server had recovered and they passed.
        session_preamble = (
            "SET SESSION FOREIGN_KEY_CHECKS=0;\n"
            "SET SESSION UNIQUE_CHECKS=0;\n"
            "SET SESSION lock_wait_timeout=600;\n"
            "SET SESSION innodb_lock_wait_timeout=600;\n"
        )

        sql_content = session_preamble + raw_sql

        # --- Tenant-change: rewrite database name in USE / CREATE statements ---
        # Fixes ERROR 1049 (Unknown database) when the export embedded the
        # source DB name but the target has a different name.
        # --- Tenant-change: rewrite database name in USE / CREATE statements ---
        # Fixes ERROR 1049 (Unknown database) when the export embedded the
        # source DB name but the target has a different name.
        if source_database and source_database != database:
            import re
            
            # Step 1: Replace backticked/quoted exact matches everywhere
            sql_content = (
                sql_content
                .replace(f"`{source_database}`", f"`{database}`")
                .replace(f"'{source_database}'",  f"'{database}'")
                .replace(f'"{source_database}"',  f'"{database}"')
            )
            
            # Step 2: Catch unquoted USE statements (e.g. "USE fineract_rkp;")
            # The regex \b ensures we match the exact db name, not a substring.
            pattern_use = re.compile(rf"(?i)(USE\s+){re.escape(source_database)}(\s*;)")
            sql_content = pattern_use.sub(rf"\g<1>{database}\g<2>", sql_content)
            
            # Step 3: Catch unquoted CREATE DATABASE (e.g. "CREATE DATABASE IF NOT EXISTS fineract_rkp;")
            pattern_create = re.compile(rf"(?i)(CREATE\s+DATABASE(?:\s+IF\s+NOT\s+EXISTS)?\s+){re.escape(source_database)}(\s*;|\s+)")
            sql_content = pattern_create.sub(rf"\g<1>{database}\g<2>", sql_content)


        # --- Build mysql CLI command ---
        cmd = ["mysql", "-h", host, "-P", str(port), "-u", user]
        if password:
            cmd.append(f"-p{password}")
        cmd.extend(["-D", database, "--max_allowed_packet=1G"])

        last_error   = "Unknown error"
        env          = os.environ.copy()

        # ---------------------------------------------------------------
        # Retry loop
        # ---------------------------------------------------------------
        for attempt in range(_MAX_ATTEMPTS):
            delay = _RETRY_DELAYS[attempt]
            if delay:
                log_debug(f"[IMPORT] Retry {sql_file} attempt {attempt+1}/{_MAX_ATTEMPTS} "
                          f"after {delay} s (prev error: {last_error[:80]})")
                time.sleep(delay)

            # Re-check cancel between attempts
            if job_control and job_control["cancel_event"].is_set():
                _update_status_finish(display_label)
                return {"file": sql_file, "error": "Cancelled by user"}

            err_path = os.path.join(
                os.path.dirname(dump_path) or ".",
                f"import_err_{uuid.uuid4().hex}.log",
            )

            try:
                # Open the error log file and keep it open for the ENTIRE duration of the
                # subprocess so MySQL can write its error messages to it.
                # Previously the `with` block closed err_fh right after Popen() returned,
                # BEFORE proc.stdin.write() was called — on Windows this caused MySQL's
                # stderr output (e.g. "Access denied", "Unknown database") to be lost,
                # leaving only the password warning in the file and making every failure
                # appear as a silent permanent error with an empty error string.
                err_fh = open(err_path, "w", encoding="utf-8")
                try:
                    proc = subprocess.Popen(
                        cmd,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.DEVNULL,
                        stderr=err_fh,
                        env=env,
                        # DON'T USE text=True on Windows because stdin defaults to cp1252!
                        # This silently crashes Python with UnicodeEncodeError when writing
                        # SQL that contains emojis or foreign characters, killing the whole job.
                        text=False,
                    )
                    try:
                        # Write pure UTF-8 bytes to MySQL directly
                        proc.stdin.write(sql_content.encode("utf-8"))
                        proc.stdin.close()
                    except OSError as stdin_exc:
                        # If MySQL dies early (e.g. syntax error), the pipe closes, causing Errno 22 / Broken Pipe.
                        # We catch it so we can drop down and read the ACTUAL error from stderr log below.
                        pass
                finally:
                    err_fh.close()  # Close AFTER stdin is submitted; stderr fd stays valid in child

                # Poll loop — check cancel/timeout while mysql runs
                hard_timeout = 3600  # 1-hour absolute ceiling per file
                while proc.poll() is None:
                    if job_control and job_control["cancel_event"].is_set():
                        proc.terminate()
                        try:
                            proc.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                        _update_status_finish(display_label)
                        _safe_remove(err_path)
                        return {"file": sql_file, "error": "Cancelled by user"}

                    if time.monotonic() - start_time > hard_timeout:
                        proc.terminate()
                        try:
                            proc.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                        _update_status_finish(display_label)
                        _safe_remove(err_path)
                        return {"file": sql_file, "error": f"Hard timeout ({hard_timeout} s)"}

                    time.sleep(0.5)

                # --- Process finished ---
                if proc.returncode == 0:
                    # SUCCESS
                    _update_status_finish(display_label)
                    _safe_remove(err_path)
                    if attempt > 0:
                        log_debug(f"[IMPORT] {sql_file} recovered on attempt {attempt+1}")
                    else:
                        log_debug(f"[IMPORT] OK: {sql_file}")
                    return None

                # Non-zero exit: read MySQL's stderr
                try:
                    with open(err_path, "r", encoding="utf-8") as rfh:
                        raw_err = rfh.read()
                except OSError:
                    raw_err = f"mysql exited with code {proc.returncode}"

                last_error = _strip_mysql_warning(raw_err) or raw_err.strip()
                _safe_remove(err_path)

                if _is_transient(last_error) and attempt < _MAX_ATTEMPTS - 1:
                    log_debug(f"[IMPORT] Transient error on {sql_file} (attempt {attempt+1}): "
                              f"{last_error[:120]} — will retry")
                    continue   # back to top of retry loop

                # Permanent failure or last attempt
                _update_status_finish(display_label)
                log_debug(f"[IMPORT] FAILED {sql_file} after {attempt+1} attempt(s): {last_error[:200]}")
                return {"file": sql_file, "error": last_error}

            except OSError as exc:
                # e.g. error opening the err log file
                last_error = str(exc)
                _safe_remove(err_path)
                if attempt < _MAX_ATTEMPTS - 1:
                    continue
                _update_status_finish(display_label)
                return {"file": sql_file, "error": last_error}

        # Safety net — should never be reached
        _update_status_finish(display_label)
        return {"file": sql_file, "error": last_error}

    # ------------------------------------------------------------------
    # 6. Execute stages
    # ------------------------------------------------------------------
    errors = []

    # Stage 1 — init / schema
    for f in init_files:
        log_debug(f"[IMPORT] Stage 1 — init: {f}")
        result = _import_file(f)
        if result:
            # Init failure is fatal — target schema is broken
            return False, f"Init file '{f}' failed: {result['error']}", [result]

    # Stage 2 — tables (with per-table auto-retry)
    log_debug(f"[IMPORT] Stage 2 — importing {len(table_files)} table(s) "
              f"(up to {_MAX_ATTEMPTS} attempts each)")
    for f in table_files:
        result = _import_file(f)
        if result:
            errors.append(result)

    # Stage 3 — routines / triggers / post-scripts
    for f in post_files:
        log_debug(f"[IMPORT] Stage 3 — post: {f}")
        result = _import_file(f)
        if result:
            errors.append(result)

    # ------------------------------------------------------------------
    # 7. Final result
    # ------------------------------------------------------------------
    if errors:
        return False, f"Import completed with {len(errors)} error(s).", errors

    return True, "Import successful.", []


def _safe_remove(path: str):
    """Delete a file, silently ignoring errors (e.g. already deleted)."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
