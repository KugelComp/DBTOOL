import delete_temp_db
import config
import json
import contextlib
import asyncio
import re
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.wsgi import WSGIMiddleware
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from starlette.middleware.sessions import SessionMiddleware
from datetime import datetime, date
import config
import export_dump
import import_dump
import os
import shutil
import tempfile
import uuid
import logging
import threading
import obscure
import mysql.connector
import auth
from file_utils import safe_rmtree
from session_logger import get_session_logger
from asgiref.sync import sync_to_async
from accounts.models import ProductionDatabase, OperationRequest
from django.contrib.auth.models import User
from security import (
    CREDENTIAL_STORE, export_limiter,
    error_response, ok_response,
    sanitize_identifier, sanitize_host
)
from request_models import (
    LoginRequest, ConnectRequest,
    StartExportRequest, DownloadRequest,
    AddUserRequest, DeleteUserRequest, ResetPasswordRequest,
    ExportControlRequest, RetryExportRequest
)

# Import Django WSGI Application
import django_admin.wsgi
django_app = django_admin.wsgi.application


# ---------------------------------------------------------------------------
# Thread-Safe Job Registry
# Replaces bare ACTIVE_EXPORTS / EXPORT_JOBS dicts.
# Every operation is protected by an RLock so concurrent async handlers
# and background export threads can't corrupt shared state.
# ---------------------------------------------------------------------------

# Maximum concurrent active jobs a single user may have at one time.
MAX_JOBS_PER_USER = 3

class JobRegistry:
    """
    Centralised, thread-safe store for all export/migration jobs.

    Active jobs  — in progress or awaiting download.
    Retry jobs   — completed with partial failures, awaiting retry decision.
    """

    def __init__(self):
        self._lock = threading.RLock()   # Re-entrant so one thread can call multiple methods
        self._active: dict = {}          # job_id -> job dict  (replaces ACTIVE_EXPORTS)
        self._retry:  dict = {}          # job_id -> job dict  (replaces EXPORT_JOBS)

    # --- Active jobs ---

    def create_active(self, job_id: str, data: dict, owner: str) -> None:
        """Register a new active job, stamping the owner."""
        with self._lock:
            data['owner'] = owner
            data['created_at'] = data.get('created_at', datetime.now())
            self._active[job_id] = data

    def get_active(self, job_id: str) -> dict | None:
        with self._lock:
            return self._active.get(job_id)

    def update_active(self, job_id: str, key: str, value) -> None:
        """Atomically set a single key on an active job record."""
        with self._lock:
            if job_id in self._active:
                self._active[job_id][key] = value

    def delete_active(self, job_id: str) -> dict | None:
        """Remove and return an active job record (e.g., after download)."""
        with self._lock:
            return self._active.pop(job_id, None)

    def get_active_if_owner(self, job_id: str, username: str, is_admin: bool = False) -> dict | None:
        """Return the job only if the caller owns it (or is admin/superuser)."""
        with self._lock:
            job = self._active.get(job_id)
            if job is None:
                return None
            if is_admin or job.get('owner') == username:
                return job
            return False      # Exists but not owner — signals 403

    def count_active_for_user(self, username: str) -> int:
        """Count running/starting jobs for a specific user."""
        with self._lock:
            running_statuses = {'Starting', 'Exporting', 'Importing',
                                'Zipping', 'Cloning Database...', 'Obscuring Data...'}
            return sum(
                1 for job in self._active.values()
                if job.get('owner') == username
                and job.get('control', {}).get('status') in running_statuses
            )

    def all_active_snapshot(self) -> list:
        """Return a safe copy of all active jobs (for cleanup loop)."""
        with self._lock:
            return [(jid, dict(job)) for jid, job in self._active.items()]

    def get_all_active_for_user(self, username: str) -> list:
        """Return a safe copy of all active jobs owned by the user."""
        with self._lock:
            jobs = []
            for jid, job in self._active.items():
                if job.get('owner') == username:
                    # Strip out sensitive credentials or very massive arrays before sending
                    start_val = job.get('start_time') or job.get('created_at')
                    if isinstance(start_val, datetime):
                        start_val = start_val.isoformat()
                    
                    safe_job = {
                        'job_id': jid,
                        'status': job.get('control', {}).get('status', 'Unknown'),
                        'start_time': start_val or '',
                        'target_host': job.get('params', {}).get('target_host', ''),
                        'database': job.get('params', {}).get('database', ''),
                        'operation_type': 'Migration' if job.get('is_migration') else 'Export',
                        'progress': job.get('control', {}).get('progress', {'current': 0, 'total': 0})
                    }
                    jobs.append(safe_job)
            return jobs

    # --- Retry jobs ---

    def create_retry(self, job_id: str, data: dict, owner: str) -> None:
        with self._lock:
            data['owner'] = owner
            data['created_at'] = data.get('created_at', datetime.now())
            self._retry[job_id] = data

    def get_retry(self, job_id: str) -> dict | None:
        with self._lock:
            return self._retry.get(job_id)

    def get_retry_if_owner(self, job_id: str, username: str, is_admin: bool = False) -> dict | None:
        with self._lock:
            job = self._retry.get(job_id)
            if job is None:
                return None
            if is_admin or job.get('owner') == username:
                return job
            return False

    def delete_retry(self, job_id: str) -> dict | None:
        with self._lock:
            return self._retry.pop(job_id, None)

    def all_retry_snapshot(self) -> list:
        with self._lock:
            return [(jid, dict(job)) for jid, job in self._retry.items()]


JOB_REGISTRY = JobRegistry()

# NOTE: All job reads/writes must go through JOB_REGISTRY methods to keep
#       RLock protection intact. Direct dict access is intentionally removed.


# ---------------------------------------------------------------------------
# Rate Limiter — thread-safe with explicit lock
# ---------------------------------------------------------------------------

class RateLimiter:
    def __init__(self, max_attempts=5, window_seconds=300):
        self._lock = threading.Lock()
        self.attempts: dict = {}   # {ip: [timestamp, ...]}
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds

    def is_allowed(self, ip: str) -> bool:
        with self._lock:
            now = datetime.now().timestamp()
            if ip not in self.attempts:
                self.attempts[ip] = []

            # Evict old timestamps
            self.attempts[ip] = [t for t in self.attempts[ip] if now - t < self.window_seconds]

            if len(self.attempts[ip]) >= self.max_attempts:
                return False

            self.attempts[ip].append(now)
            return True

login_limiter = RateLimiter(max_attempts=5, window_seconds=300)


# ---------------------------------------------------------------------------
# Cleanup + Lifespan (must be defined before FastAPI() is constructed)
# ---------------------------------------------------------------------------

async def cleanup_old_jobs():
    """Periodically remove old export/retry jobs to prevent memory and disk leaks."""
    _cleanup_logger = logging.getLogger('cleanup')
    while True:
        try:
            now = datetime.now()
            cutoff = 3600  # 1 hour

            for job_id, job in JOB_REGISTRY.all_active_snapshot():
                created_at = job.get('created_at')
                if created_at and (now - created_at).total_seconds() > cutoff:
                    temp_dir = job.get('temp_dir')
                    if temp_dir and os.path.exists(temp_dir):
                        safe_rmtree(temp_dir)
                    JOB_REGISTRY.delete_active(job_id)
                    _cleanup_logger.info(f"Cleanup: removed expired active job {job_id} (owner={job.get('owner')})")

            for job_id, job in JOB_REGISTRY.all_retry_snapshot():
                created_at = job.get('created_at')
                if created_at and (now - created_at).total_seconds() > cutoff:
                    temp_dir = job.get('temp_dir')
                    if temp_dir and os.path.exists(temp_dir):
                        safe_rmtree(temp_dir)
                    JOB_REGISTRY.delete_retry(job_id)
                    _cleanup_logger.info(f"Cleanup: removed expired retry job {job_id} (owner={job.get('owner')})")

        # Purge expired credential store entries
            purged = CREDENTIAL_STORE.purge_expired()
            if purged:
                _cleanup_logger.info(f"Cleanup: purged {purged} expired credential store entries")

            # --- Auto-delete audit logs older than 4 days from Django DB ---
            try:
                from django.utils import timezone
                from datetime import timedelta
                from logs.models import LogEntry
                from django.contrib.admin.models import LogEntry as DjangoAdminLogEntry
                
                log_cutoff = timezone.now() - timedelta(days=4)
                
                # Prune Custom App Logs
                deleted_logs, _ = await sync_to_async(LogEntry.objects.filter(timestamp__lt=log_cutoff).delete)()
                if deleted_logs:
                    _cleanup_logger.info(f"Cleanup: auto-purged {deleted_logs} custom application log entries older than 4 days")
                    
                # Prune Native Django Admin History
                deleted_admin_logs, _ = await sync_to_async(DjangoAdminLogEntry.objects.filter(action_time__lt=log_cutoff).delete)()
                if deleted_admin_logs:
                    _cleanup_logger.info(f"Cleanup: auto-purged {deleted_admin_logs} Django Admin History logs older than 4 days")
                    
            except Exception as log_e:
                _cleanup_logger.error(f"Cleanup: failed to purge old log entries: {log_e}")

        except Exception as e:
            logging.getLogger('cleanup').error(f"Cleanup error: {e}")

        # --- ORPHAN SCAN: catch temp dirs not in the registry ---
        # This handles the case where the server was restarted mid-export,
        # or a job crashed before cleanup ran. Those folders are never in
        # JOB_REGISTRY so they'd survive forever.  We delete any tmp* folder
        # in the OS temp directory that is older than 2 hours and not currently
        # referenced by any live job.
        try:
            import tempfile
            now = datetime.now()
            orphan_cutoff_seconds = 7200  # 2 hours

            # Build set of ALL temp dirs currently known to the registry
            known_temp_dirs = set()
            for _, job in JOB_REGISTRY.all_active_snapshot():
                td = job.get('temp_dir')
                if td: known_temp_dirs.add(os.path.normpath(td))
            for _, job in JOB_REGISTRY.all_retry_snapshot():
                td = job.get('temp_dir')
                if td: known_temp_dirs.add(os.path.normpath(td))

            tmp_root = tempfile.gettempdir()
            orphans_deleted = 0
            for entry in os.scandir(tmp_root):
                # Only consider folders whose names start with "tmp" (created by tempfile.mkdtemp)
                if not entry.is_dir() or not entry.name.startswith('tmp'):
                    continue
                norm_path = os.path.normpath(entry.path)
                # Skip anything still tracked by the registry
                if norm_path in known_temp_dirs:
                    continue
                try:
                    mtime = entry.stat().st_mtime
                    age_seconds = (now - datetime.fromtimestamp(mtime)).total_seconds()
                    if age_seconds > orphan_cutoff_seconds:
                        safe_rmtree(entry.path)
                        orphans_deleted += 1
                except Exception:
                    pass  # Skip any folder we can't stat/delete

            if orphans_deleted:
                logging.getLogger('cleanup').info(
                    f"Orphan scan: removed {orphans_deleted} un-tracked temp dir(s) "
                    f"older than {orphan_cutoff_seconds//3600}h from {tmp_root}"
                )
        except Exception as orphan_err:
            logging.getLogger('cleanup').error(f"Orphan scan error: {orphan_err}")

        await asyncio.sleep(600)  # Run every 10 minutes



@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background tasks on boot; shut them down gracefully."""
    cleanup_task = asyncio.create_task(cleanup_old_jobs())
    try:
        yield
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass

# ---------------------------------------------------------------------------
# In production (APP_ENV=production) API docs are hidden to prevent
# unauthenticated users from browsing the full endpoint schema.
# ---------------------------------------------------------------------------
_IS_PRODUCTION = os.environ.get("APP_ENV", "development").lower() == "production"
_docs_url   = None if _IS_PRODUCTION else "/api/docs"
_redoc_url  = None

app = FastAPI(
    title="DB Tool",
    description="Database Export / Import / Migration Utility",
    docs_url=None if getattr(config, 'APP_ENV', 'development') == 'production' else '/api/docs',
    redoc_url=None if getattr(config, 'APP_ENV', 'development') == 'production' else '/api/redoc',
)

# Mount Django Admin at /admin
app.mount("/admin", WSGIMiddleware(django_app))

# Static files
app.mount("/static/admin", StaticFiles(directory="static/admin_root"), name="static_admin")

# --- Session ---
# In production: cookie is HTTPS-only (https_only=True) and SameSite=lax.
# In development: relaxed so localhost without TLS still works.
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET_KEY,
    https_only=_IS_PRODUCTION,          # Sends cookie only over HTTPS in production
    same_site="lax",                    # Protects against CSRF from cross-site navigations
    max_age=config.SESSION_TIMEOUT_HOURS * 3600,
)


# --- Global 422 Validation Error Handler ---
# Returns a clean, uniform error envelope instead of FastAPI's verbose default.
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        field = " -> ".join(str(l) for l in err.get("loc", []))
        errors.append(f"{field}: {err['msg']}")
    return JSONResponse(
        status_code=422,
        content={"error": True, "message": "Validation failed", "detail": errors}
    )


templates = Jinja2Templates(directory="templates")

_APP_START_TIME = datetime.now()


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["infra"])
async def health_check():
    """
    Health check endpoint — used by load balancers, Docker HEALTHCHECK,
    and monitoring systems (Prometheus, Datadog, etc.).
    Returns 200 while the service is up.
    """
    uptime_seconds = int((datetime.now() - _APP_START_TIME).total_seconds())
    active_jobs = len(JOB_REGISTRY._active)
    retry_jobs  = len(JOB_REGISTRY._retry)

    return {
        "status": "ok",
        "uptime_seconds": uptime_seconds,
        "active_jobs":  active_jobs,
        "retry_jobs":   retry_jobs,
        "version": "1.0.0",
    }



# Helper function to get logger from session
def get_logger(request: Request):
    """Get or create session logger"""
    if 'logger' not in request.session:
        # Re-instantiate if missing object but have session info
        if 'logger_session_id' in request.session and 'username' in request.session:
             return get_session_logger(
                 request.session['logger_session_id'], 
                 request.session['username'],
                 client_ip=request.client.host
             )
        return None
    return request.session.get('logger')


# Helper function to check if user is authenticated
def get_current_user(request: Request):
    """Get current authenticated user from session"""
    return request.session.get('username')


def require_auth(request: Request):
    """Require authentication, redirect to login if not authenticated"""
    username = get_current_user(request)
    if not username:
        return None
    return username


async def require_role(request: Request, allowed_roles=('ADMIN', 'SUPERUSER')):
    """
    Require authentication AND a specific role (checked against UserHierarchy).
    Returns (username, None) if allowed, or (None, JSONResponse) if denied.
    """
    username = get_current_user(request)
    if not username:
        return None, JSONResponse(status_code=401, content={"error": "Authentication required"})

    try:
        user = await sync_to_async(User.objects.get)(username=username)
        hierarchy = await sync_to_async(lambda: getattr(user, 'hierarchy', None))()
        if hierarchy and hierarchy.role in allowed_roles:
            return username, None
        # Also allow Django superusers
        if user.is_superuser:
            return username, None
    except User.DoesNotExist:
        pass

    return None, JSONResponse(status_code=403, content={"error": "Access denied: insufficient permissions"})


async def _is_admin(username: str) -> bool:
    """Return True if the given user is an Admin, Superuser, or Django superuser."""
    try:
        user = await sync_to_async(User.objects.get)(username=username)
        if user.is_superuser:
            return True
        hierarchy = await sync_to_async(lambda: getattr(user, 'hierarchy', None))()
        if hierarchy and hierarchy.role in ('ADMIN', 'SUPERUSER'):
            return True
    except User.DoesNotExist:
        pass
    return False


@app.get('/login', response_class=HTMLResponse)
async def login_page(request: Request):
    """Display login page"""
    # If already logged in, redirect to home
    if get_current_user(request):
        return RedirectResponse(url='/', status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})


@app.post('/login')
async def login(body: LoginRequest, request: Request):
    """Handle login — rate-limited per IP, validated via Pydantic"""
    client_ip = request.client.host
    if not login_limiter.is_allowed(client_ip):
        return JSONResponse(status_code=429, content={
            "success": False,
            "error": "Too many login attempts. Please try again in 5 minutes."
        })

    username = body.username
    password = body.password

    is_authenticated = await sync_to_async(auth.authenticate_user)(username, password)
    if is_authenticated:
        session_token = auth.generate_session_token()
        request.session['username']         = username
        request.session['session_id']       = session_token
        request.session['authenticated']    = True
        request.session['logger_session_id'] = session_token

        logger = get_session_logger(session_token, username, client_ip=client_ip)
        logger.info("User logged in successfully", action="LOGIN_SUCCESS")

        return {"success": True, "message": "Login successful"}
    else:
        temp_logger = get_session_logger("audit_trail", "system", client_ip=client_ip)
        temp_logger.warning(f"Login failed for user: {username}", action="LOGIN_FAILED")
        return {"success": False, "error": "Invalid username or password"}



@app.get('/logout')
async def logout(request: Request):
    """Handle logout — also purges server-side credentials"""
    username = get_current_user(request)

    if username and 'logger_session_id' in request.session:
        logger = get_session_logger(request.session['logger_session_id'], username, client_ip=request.client.host)
        logger.info("User logged out", action="LOGOUT")
        logger.close()

    # Remove server-side DB credentials for this session
    cred_token = request.session.get('cred_token')
    if cred_token:
        CREDENTIAL_STORE.delete(cred_token)

    request.session.clear()
    return RedirectResponse(url='/login', status_code=302)



@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    """Main application page - requires authentication"""
    username = require_auth(request)
    if not username:
        return RedirectResponse(url='/login', status_code=302)
    
    # Check permissions
    is_staff = False
    try:
        user = await sync_to_async(User.objects.get)(username=username)
        # Check hierarchy or is_staff flag directly
        # UserHierarchy logic:
        # is_staff = user.hierarchy.is_admin() or user.hierarchy.is_superuser()
        # But we can also rely on Django's builtin is_staff if UserHierarchy syncs it.
        # Let's check UserHierarchy explicity for safety
        hierarchy = await sync_to_async(lambda: getattr(user, 'hierarchy', None))()
        if hierarchy and (hierarchy.role in ['ADMIN', 'SUPERUSER']):
            is_staff = True
    except User.DoesNotExist:
        pass

    return templates.TemplateResponse("index.html", {
        "request": request,
        "username": username,
        "is_staff": is_staff
    })

@app.get('/get-hosts')
async def get_hosts(request: Request):
    """Return available predefined hosts - requires authentication"""
    username = require_auth(request)
    if not username:
        return {"error": "Authentication required"}
    
    # Log the request
    if 'logger_session_id' in request.session:
        logger = get_session_logger(request.session['logger_session_id'], username, client_ip=request.client.host)
        # Only log if it's not a common polling action
        # logger.info("Fetched available hosts", action="FETCH_HOSTS")
    
    # Read active hosts from DB (primary source)
    # Falls back to config.HOSTS if the table is empty — safe during first deploy
    try:
        from accounts.models import DatabaseHost, ProductionDatabase
        
        db_hosts = await sync_to_async(
            lambda: list(DatabaseHost.objects.filter(is_active=True).values('label', 'ip', 'port', 'db_username', 'db_password'))
        )()
        
        prod_ips = await sync_to_async(
            lambda: list(ProductionDatabase.objects.filter(is_production=True).values_list('host', flat=True))
        )()
        
        if db_hosts:
            hosts = {}
            for h in db_hosts:
                # If this is a production host, scrub the password so it isn't leaked to the UI
                # and isn't automatically used during the migration request payload
                is_prod = h['ip'] in prod_ips
                hosts[h['label']] = {
                    'ip': h['ip'],
                    'port': h['port'],
                    'user': h['db_username'],
                    'password': '' if is_prod else h['db_password']
                }
        else:
            hosts = config.HOSTS  # fallback
    except Exception:
        hosts = config.HOSTS  # fallback if DB/migration issue

    return {"hosts": hosts}





@app.get('/users', response_class=HTMLResponse)
async def admin_users_page(request: Request):
    """User Management Page - Admin only"""
    username = require_auth(request)
    if not username:
        return RedirectResponse(url='/login', status_code=302)
    
    try:
        # Load users asynchronously
        users_dict = await sync_to_async(auth.load_users)()
        
        # Convert dict to list for template
        users_list = []
        for uname, info in users_dict.items():
            users_list.append({
                "username": uname,
                "created_at": info.get("created_at", "N/A"),
                "is_superuser": info.get("is_superuser", False)
            })
            
        return templates.TemplateResponse("admin_users.html", {
            "request": request,
            "username": username,
            "users": users_list
        })
    except Exception as e:
         return HTMLResponse(content=f"Error loading users: {str(e)}", status_code=500)


@app.post('/users/add')
async def add_user_api(body: AddUserRequest, request: Request):
    """Add new user — Admin/Superuser only, validated via Pydantic"""
    username, err = await require_role(request)
    if err: return err

    try:
        success = await sync_to_async(auth.add_user)(body.username, body.password)
        if success:
            if 'logger_session_id' in request.session:
                logger = get_session_logger(request.session['logger_session_id'], username, client_ip=request.client.host)
                logger.info(f"User '{body.username}' created by '{username}'", action="USER_CREATE")
            return {"success": True}
        else:
            return error_response(409, "User already exists or could not be created")
    except Exception as e:
        return error_response(500, "Failed to add user", str(e))



@app.post('/users/delete')
async def delete_user_api(body: DeleteUserRequest, request: Request):
    """Delete user — Admin/Superuser only"""
    username, err = await require_role(request)
    if err: return err

    if body.username == 'admin':
        return error_response(400, "Cannot delete the system admin account")

    try:
        success = await sync_to_async(auth.remove_user)(body.username)
        if success:
            if 'logger_session_id' in request.session:
                logger = get_session_logger(request.session['logger_session_id'], username, client_ip=request.client.host)
                logger.info(f"User '{body.username}' deleted by '{username}'", action="USER_DELETE")
            return {"success": True}
        else:
            return error_response(404, "User not found")
    except Exception as e:
        return error_response(500, "Failed to delete user", str(e))


@app.post('/users/reset-password')
async def reset_password_api(body: ResetPasswordRequest, request: Request):
    """Reset user password — Admin/Superuser only, validated via Pydantic"""
    username, err = await require_role(request)
    if err: return err

    try:
        success = await sync_to_async(auth.change_password)(body.username, body.new_password)
        if success:
            if 'logger_session_id' in request.session:
                logger = get_session_logger(request.session['logger_session_id'], username, client_ip=request.client.host)
                logger.info(f"Password reset for '{body.username}' by '{username}'", action="PASSWORD_RESET")
            return {"success": True}
        else:
            return error_response(404, "User not found")
    except Exception as e:
        return error_response(500, "Failed to reset password", str(e))



@app.get('/logs')
async def logs_page(request: Request):
    """Redirect legacy /logs URL to Django Admin log viewer."""
    username = require_auth(request)
    if not username:
        return RedirectResponse(url='/login', status_code=302)
    return RedirectResponse(url='/admin/logs/logentry/', status_code=302)


@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    """Return an empty response for favicon to stop browser 404 console errors."""
    from fastapi.responses import Response
    return Response(status_code=204)


@app.get('/csrf-token')
async def csrf_token_view(request: Request):
    """
    Return the current CSRF token as JSON for use by AJAX POST requests.
    starlette-csrf sets the 'csrftoken' cookie on every GET response;
    this endpoint lets the JS read it reliably without cookie-parsing edge cases.
    """
    token = request.cookies.get('csrftoken', '')
    return {"csrf_token": token}


@app.get('/api/logs')
async def get_logs(request: Request, page: int = 1, page_size: int = 100):
    """
    Fetch audit logs (JSON) — Admin/Superuser only, paginated.
    Reads from Django DB (logs.LogEntry) — no flat-file dependency.
    """
    username, err = await require_role(request)
    if err: return err

    try:
        from logs.models import LogEntry

        total   = await sync_to_async(LogEntry.objects.count)()
        offset  = (page - 1) * page_size

        entries = await sync_to_async(
            lambda: list(
                LogEntry.objects
                .order_by('-timestamp')
                .values('timestamp', 'level', 'message', 'module', 'line',
                        'client_ip', 'user', 'session_id', 'action', 'exception')
                [offset: offset + page_size]
            )
        )()

        # Serialise datetime to ISO string for JSON
        for entry in entries:
            if entry.get('timestamp'):
                entry['timestamp'] = entry['timestamp'].isoformat()

        return {
            "logs":        entries,
            "total":       total,
            "page":        page,
            "page_size":   page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }

    except Exception as e:
        logging.getLogger('api').error(f"/api/logs error: {e}")
        return JSONResponse(status_code=500, content={"error": "Failed to retrieve logs"})

@app.post('/get-databases')
async def get_databases(body: ConnectRequest, request: Request):
    """
    Connect to a MySQL server and return the list of databases.
    DB credentials are stored server-side (CREDENTIAL_STORE);
    only a token is stored in the session cookie.
    """
    username = require_auth(request)
    if not username:
        return error_response(401, "Authentication required")

    # Sanitize host before use
    safe_host = sanitize_host(body.host)
    if not safe_host:
        return error_response(400, "Invalid hostname or IP address")

    # --- NEW: Check if this is a production host with hardcoded DBs ---
    try:
        prod_db = await sync_to_async(ProductionDatabase.objects.get)(host=safe_host, port=body.port)
        if prod_db.is_production and prod_db.hardcoded_dbs:
            # Bypass real connection, rely on hardcoded list
            databases = [db.strip() for db in prod_db.hardcoded_dbs.split(',') if db.strip()]
            
            # We store what we got (password is likely empty from the UI)
            # The migration background process will get the REAL password from the approval step
            cred_token = str(uuid.uuid4())
            CREDENTIAL_STORE.put(cred_token, {
                'host':     safe_host,
                'port':     body.port,
                'user':     body.user,
                'password': body.password,
            })
            old_token = request.session.get('cred_token')
            if old_token:
                CREDENTIAL_STORE.delete(old_token)

            request.session['cred_token'] = cred_token
            return {"success": True, "databases": databases}
    except Exception as e:
        pass # fallback to actual connection if not found

    try:
        conn = await sync_to_async(mysql.connector.connect)(
            host=safe_host,
            port=body.port,
            user=body.user,
            password=body.password
        )
        cursor = conn.cursor()
        cursor.execute("SHOW DATABASES")
        system_dbs = {'information_schema', 'mysql', 'performance_schema', 'sys'}
        databases = [row[0] for row in cursor.fetchall() if row[0].lower() not in system_dbs]
        cursor.close()
        conn.close()

    except mysql.connector.Error as e:
        return {"success": False, "error": f"Connection failed: {e.msg}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

    # --- Store credentials SERVER-SIDE ---
    # The session cookie will only hold a token, never the raw password.
    cred_token = str(uuid.uuid4())
    CREDENTIAL_STORE.put(cred_token, {
        'host':     safe_host,
        'port':     body.port,
        'user':     body.user,
        'password': body.password,
    })
    # Invalidate any previous cred_token for this session
    old_token = request.session.get('cred_token')
    if old_token:
        CREDENTIAL_STORE.delete(old_token)

    request.session['cred_token'] = cred_token
    # Also keep non-sensitive session state for display purposes
    request.session['host']       = safe_host
    request.session['port']       = body.port
    request.session['user']       = body.user
    # NOTE: password is NO LONGER stored in the session cookie

    return {"success": True, "databases": databases}


# --- ASYNC EXPORT LOGIC ---


def run_async_export(job_id, params, job_control, logger=None, reuse_temp_dir=None, tables_to_dump=None):
    """Background thread to run the export with pause/resume support"""
    temp_dir = None
    try:
        host = params['host']
        port = params['port']
        user = params['user']
        password = params['password']
        database = params['database']
        dump_mode = params.get('dump_mode', 'Plain')
        
        # Create or Reuse temp dir
        if reuse_temp_dir:
             temp_dir = reuse_temp_dir
             JOB_REGISTRY.update_active(job_id, 'temp_dir', temp_dir)
             if logger: logger.info(f"Async Export Retrying: {database} (Reuse Dir: {temp_dir})", action="RETRY_START")
        else:
             temp_dir = tempfile.mkdtemp()
             JOB_REGISTRY.update_active(job_id, 'temp_dir', temp_dir)
             if logger: logger.info(f"Async Export Started: {database} (Mode: {dump_mode})", action="EXPORT_START")

        # --- OBSCURE / PREP LOGIC (Mirrors download_database) ---\r\n
        dumped_db_name = database
        obscured_db = params.get('obscured_db') # Allow passing existing obscured DB name
        target_db_name_export = None # For Tenant Change

        # Prepare Mode Flags
        dump_modes = params.get('dump_modes', [])
        # Backwards compatibility check
        if 'dump_mode' in params and params['dump_mode'] not in dump_modes:
             if params['dump_mode'] != 'Plain':
                dump_modes.append(params['dump_mode'])
        if not dump_modes: dump_modes = ['Plain']

        dumped_db_name = database
        obscured_db = params.get('obscured_db') 
        
        # Determine the name to use in the exported SQL
        # If tenant change is requested, use that, otherwise use original DB name
        target_db_name_export = params.get('new_tenant_name') or database

        is_obscure_needed = "Obscure" in dump_modes
        is_service_off_needed = "Service Off" in dump_modes
        
        is_migration = bool(params.get('target_host'))
        
        # --- NEW APPROACH: Use Default Target Instead of Cloning ---
        # For normal backups with Obscure/Service Off, we use a migration-like approach
        # instead of cloning the source database (which is slow)
        
        use_default_target = False
        auto_target_db_name = None
        
        if (is_obscure_needed or is_service_off_needed) and not obscured_db and not is_migration:
            # Check if default target is enabled
            if config.DEFAULT_TARGET_ENABLED:
                use_default_target = True
                
                # Check if user specified a tenant name (for tenant change exports)
                user_specified_name = params.get('target_database_name')
                
                if user_specified_name:
                    # User wants tenant change - use their specified name
                    auto_target_db_name = user_specified_name
                    if logger:
                        logger.info(f"Using default target with user-specified name: {auto_target_db_name}", action="DEFAULT_TARGET_TENANT_CHANGE")
                else:
                    # Auto-generate unique database name on target
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    auto_target_db_name = f"backup_{database}_{timestamp}"
                    if logger:
                        logger.info(f"Using default target approach (no cloning). Target DB: {auto_target_db_name}", action="DEFAULT_TARGET_BACKUP")
                
                # Set target parameters (convert this to a migration)
                params['target_host'] = config.DEFAULT_TARGET_HOST
                params['target_port'] = config.DEFAULT_TARGET_PORT
                params['target_user'] = config.DEFAULT_TARGET_USER
                params['target_password'] = config.DEFAULT_TARGET_PASSWORD
                params['target_database_name'] = auto_target_db_name  # Use determined name
                params['_auto_cleanup_target'] = True  # Flag to cleanup after export
                
                # CRITICAL FIX: SQL files must embed USE `auto_target_db_name` (the backup DB),
                # NOT USE `source_db_name`. Without this, mysql -D backup_db switches back
                # to the source DB via the USE statement in each SQL file, causing the SOURCE
                # to be modified by the import and subsequently by obscure/service_off.
                target_db_name_export = auto_target_db_name
                
                # Update is_migration flag
                is_migration = True
                
            else:
                # Fallback to old cloning approach if default target is disabled
                job_control['status'] = "Cloning Database..."
                if logger: logger.info(f"Cloning database for modification (Modes: {dump_modes})...")
                obscured_db = obscure.create_temp_db.clone_db(host, user, password, database, logger=logger, job_control=job_control)
                
                if not obscured_db:
                    raise Exception("Failed to clone database for options")
                    
                JOB_REGISTRY.update_active(job_id, 'obscured_db', obscured_db)
                dumped_db_name = obscured_db
                
                # Apply Service Off
                if is_service_off_needed:
                     job_control['status'] = "Applying Service Off..."
                     service_off_file = config.service_off_file
                     if not os.path.exists(service_off_file):
                          raise Exception(f"{service_off_file} file not found")
                     if logger: logger.info("Applying Service Off scripts...")
                     if not obscure.apply_sql_to_db(host, user, password, obscured_db, service_off_file, logger=logger):
                          raise Exception("Failed to apply Service Off SQL")

                # Apply Obscure
                if is_obscure_needed:
                     job_control['status'] = "Obscuring Data..."
                     if logger: logger.info("Applying Data Obscuration...")
                     obscure_file = config.obscure_file
                     if not obscure.apply_sql_to_db(host, user, password, obscured_db, obscure_file, logger=logger):
                          raise Exception("Failed to apply Obscure SQL")

        elif obscured_db:
             # Retry case or pre-existing
             dumped_db_name = obscured_db
             target_db_name_export = database


        # 2. Tenant Change (Renaming)
        if "Tenant Change" in dump_modes:
            new_tenant_name = params.get('new_tenant_name')
            if not new_tenant_name:
                raise Exception("New Tenant Name required")
            target_db_name_export = new_tenant_name
            # Set in params so default target logic uses this name instead of auto-generating
            params['target_database_name'] = new_tenant_name


        # --- PERFORM DUMP ---
        # If we are reusing a temp dir and have no tables to dump (e.g. Ignore mode proceeded),
        # we might want to skip perform_dump or pass empty list?
        # If tables_to_dump is None, perform_dump dumps ALL.
        # If I want to dump NOTHING (skip), I should prevent calling perform_dump or pass empty list.
        
        success = True
        failed_tables = []
        message = "Skipped Dump"

        include_routines = "Dump Routines" in dump_modes
        include_events = "Dump Events" in dump_modes
        include_triggers = "Dump Triggers" in dump_modes
        include_views = "Dump Views" in dump_modes
        
        # Legacy fallback for entire "Include Structure"
        if "Include Structure" in dump_modes:
             include_routines = True
             include_events = True
             include_triggers = True
             include_views = True

        should_dump = True
        if reuse_temp_dir and tables_to_dump is not None and len(tables_to_dump) == 0:
             should_dump = False # Ignore mode, just proceed to zip
        
        # 3. Export Database
        # Initialize success, message, failed_tables for cases where perform_dump is skipped
        success, message, failed_tables = True, "Success", [] 
        # retry_mode is not defined in the original code, assuming it's not intended to be used here
        # if not retry_mode or retry_mode == 'retry': 
        if should_dump: # Use the existing should_dump logic
            if logger: logger.info(f"Starting Export... (Modes: {dump_modes})")
            success, message, failed_tables = export_dump.perform_dump(
                host=host, port=port, user=user, password=password,
                database=dumped_db_name, # Use dumped_db_name as per original logic
                target_database_name=target_db_name_export,
                dump_path=temp_dir,
                tables_to_dump=tables_to_dump,
                include_views=include_views, # Use the determined include_views
                include_routines=include_routines, # Use the determined include_routines
                include_events=include_events, # Use the determined include_events
                include_triggers=include_triggers, # Use the determined include_triggers
                job_control=job_control,
                logger=logger
            )
        
        # Capture the ACTUAL folder name created by perform_dump BEFORE overwriting dumped_db_name.
        # perform_dump always names its output folder after the 'database' arg it received,
        # which is dumped_db_name at call time (the real source DB, e.g. fineract_rkp).
        # Line below would clobber that with the session 'database' variable (e.g. fineract_rikalp)
        # causing source_database to be wrong and the USE-statement rewrite to never fire,
        # producing ERROR 1049: Unknown database on every import file.
        actual_export_db_name = dumped_db_name  # Save real source DB name used as folder name
        dumped_db_name = database if not obscured_db else obscured_db
        dump_subdir = os.path.join(temp_dir, actual_export_db_name)

        # Check for Cancellation (moved up to handle immediately after dump attempt)
        if message == "Export Cancelled by User":
             job_control['status'] = 'Cancelled'
             safe_rmtree(temp_dir, logger=logger)
             if obscured_db:
                  try: delete_temp_db.drop_temp_database(host, user, password, obscured_db)
                  except: pass
             return

        # --- HANDLE COMPLETION ---
        if success:
             
             # Debugging Migration Import Skip
             if logger:
                 logger.info(f"Export Success. Checking for Import/Migration... Keys: {list(params.keys())}")
                 logger.info(f"Target Host in params: '{params.get('target_host')}'")
             
             # --- MIGRATION (IMPORT) PHASE ---
             # IMPORTANT: We check target_host INDEPENDENTLY of should_dump.
             # should_dump = False means "skip re-exporting failed tables, use what we have".
             # But we MUST still import + apply Obscure/Service Off to the target.
             # Previously, `and should_dump` here caused Obscure/Service Off to be silently
             # skipped whenever the user chose "Proceed with Failures".
             if params.get('target_host'):

                 # IGNORE MODE + import already ran once: skip re-import.
                 # The successful tables are already in the target DB.
                 # Just apply Obscure/Service Off then zip.
                 _skip_import = (not should_dump) and params.get('import_already_ran', False)

                 # Reset progress counter for import phase
                 job_control['progress']['current'] = 0
                 job_control['status'] = 'Importing'
                 if logger: logger.info(f"Starting Import Phase to {params['target_host']}")
                 
                 # Folder name might vary. If we renamed it? No, not yet.
                 # dumped_db_name holds the folder name.
                 dump_subdir = os.path.join(temp_dir, actual_export_db_name)
                 
                 if _skip_import:
                     import_success, import_msg, import_errors = True, 'Skipped (proceed-with-failures, import already ran)', []
                     job_control['status'] = 'Applying Modifications...'
                     if logger: logger.info("Import skipped — target DB already has data from previous run. Applying modifications only.", action="IMPORT_SKIPPED")

                 else:
                     if 'target_password' not in params:
                           raise Exception(
                               "Target password is missing — the credential was lost, likely due to a server restart "
                               "between approval and execution. Please have the Operations Director re-approve this request."
                           )

                     import_success, import_msg, import_errors = import_dump.perform_import(
                    host=params['target_host'],
                    port=params.get('target_port', 3306),
                    user=params['target_user'],
                    password=params['target_password'],
                    database=params.get('target_database_name', dumped_db_name), # Fallback if missing
                    dump_path=dump_subdir,
                    source_database=actual_export_db_name,  # Real source DB name embedded in SQL USE statements
                    job_control=job_control,
                    # Merge: tables that failed in a previous run + tables that failed THIS run
                    # (the "Proceed with Failures" case means failed_tables were never dumped,
                    #  so they must also be excluded from import or mysql will error on missing files)
                    exclude_tables=list(set(params.get('export_failed_tables', []) + failed_tables)),
                    # KEY FIX: on retry, only import the tables that were just re-exported.
                    # tables_to_dump is None on first run (import all), or a list of failed
                    # tables on retry (import only those — not the full 630 again).
                    import_only_tables=tables_to_dump if tables_to_dump else None,
                 )

                 
                 # --- POST-IMPORT MODIFICATIONS (Migration Mode) ---
                 # Check for NEW import failures (not export failures we already know about)
                 export_failed_for_check = set(params.get('export_failed_tables', []))
                 import_failed_for_check = set([e['file'].replace('.sql', '') for e in import_errors]) if import_errors else set()
                 new_failures_for_check = import_failed_for_check - export_failed_for_check
                 
                 # Apply modifications as long as import succeeded, even if some tables failed
                 if import_success:
                     target_db = params.get('target_database_name', dumped_db_name)
                     t_host = params['target_host']
                     t_user = params['target_user']
                     t_pass = params['target_password']
                     
                     # Log if we're applying despite failures
                     if new_failures_for_check and logger:
                         logger.warning(f"Applying modifications despite {len(new_failures_for_check)} table import failures", action="IMPORT_PARTIAL_MODIFICATIONS")
                     
                     if is_service_off_needed:
                          job_control['status'] = "Applying Service Off to Target..."
                          service_off_file = config.service_off_file
                          if os.path.exists(service_off_file):
                              print(f"[DEBUG][SERVICE_OFF] host={t_host} db={target_db}")
                              if logger: logger.info(f"Applying Service Off to Target {t_host} DB={target_db}...")
                              if not obscure.apply_sql_to_db(t_host, t_user, t_pass, target_db, service_off_file, logger=logger):
                                   if logger: logger.error("Failed to apply Service Off on Target")
                          else:
                              if logger: logger.warning(f"{service_off_file} missing, skipping")

                     if is_obscure_needed:
                          job_control['status'] = "Obscuring Target Data..."
                          obscure_file = config.obscure_file
                          print(f"[DEBUG][OBSCURE] host={t_host} db={target_db}")
                          if logger: logger.info(f"Applying Obscure to database '{target_db}' on host '{t_host}'...")
                          print(f"[INFO] Applying Obscure to database: {target_db} on {t_host}")
                          if not obscure.apply_sql_to_db(t_host, t_user, t_pass, target_db, obscure_file, logger=logger):
                               if logger: logger.error(f"Failed to apply Obscure on Target database: {target_db}")

                     # --- RE-EXPORT TARGET DATABASE (Default Target Approach) ---
                     # If this is a default target backup, we need to export the modified target database
                     if params.get('_auto_cleanup_target'):
                          # Reset progress counter for re-export phase
                          job_control['progress']['current'] = 0
                          job_control['status'] = "Exporting modified target database..."
                          if logger: logger.info(f"Re-exporting target database {target_db} for download...")
                         
                          # Create new temp dir for target export
                          target_export_dir = tempfile.mkdtemp()
                         
                          # Export the modified target database
                          target_success, target_message, target_failed = export_dump.perform_dump(
                              host=t_host,
                              port=params.get('target_port', 3306),
                              user=t_user,
                              password=t_pass,
                              database=target_db,
                              dump_path=target_export_dir,
                              target_database_name=database,  # Use original database name in dump files
                              job_control=job_control,
                              include_views="Dump Views" in dump_modes,
                              include_routines="Dump Routines" in dump_modes,
                              include_events="Dump Events" in dump_modes,
                              include_triggers="Dump Triggers" in dump_modes,
                              logger=logger
                          )
                         
                          if not target_success or target_failed:
                              raise Exception(f"Failed to export target database: {target_message}")
                         
                          # Replace temp_dir with target export dir
                          # Clean up old import dir
                          if os.path.exists(temp_dir):
                              safe_rmtree(temp_dir, logger=logger)
                         
                          temp_dir = target_export_dir
                          JOB_REGISTRY.update_active(job_id, 'temp_dir', temp_dir)
                          dumped_db_name = target_db  # Use actual folder name created by export
                         
                          # Cleanup target database
                          try:
                              if logger: logger.info(f"Cleaning up target database {target_db}...")
                              delete_temp_db.drop_temp_database(t_host, t_user, t_pass, target_db)
                          except Exception as cleanup_err:
                              if logger: logger.warning(f"Failed to cleanup target DB {target_db}: {cleanup_err}")


                 
                 if not import_success:
                      # If success is False, it's a failure.
                      # Check if it is a "Partial Failure" (with specific file errors)
                      if import_errors:
                          # Separate export failures from import failures
                          export_failed = set(params.get('export_failed_tables', []))
                          import_failed_files = [e['file'].replace('.sql', '') for e in import_errors]
                          import_failed = set(import_failed_files)
                          new_failures = import_failed - export_failed
                          failed_list = list(new_failures)

                          # Build per-table {table, reason} details for UI display.
                          # The error text comes directly from MySQL's stderr, stripped of
                          # the noisy password-warning header inside import_dump.py.
                          failure_details = [
                              {
                                  'table': e['file'].replace('.sql', ''),
                                  'reason': (e.get('error') or 'Unknown error').strip()
                              }
                              for e in import_errors
                              if e['file'].replace('.sql', '') in new_failures
                          ]

                          # Compute tables that PASSED this attempt but failed last time.
                          # On the first pass _prev_failed_tables is empty, so now_passed=[]
                          # On a user-triggered retry it contains the previous failed_list.
                          prev_failed_set = set(params.get('_prev_failed_tables', []))
                          now_passed = sorted(prev_failed_set - new_failures)

                          if failed_list:
                               job_control['status'] = 'Partial Failure'
                               if logger: logger.warning(
                                   f"Import Partial Failure: {len(failed_list)} new table(s) failed"
                                   + (f"; {len(now_passed)} recovered" if now_passed else ""),
                                   action="IMPORT_PARTIAL_FAILURE"
                               )
                               active_job = JOB_REGISTRY._active.get(job_id)
                               owner = active_job.get('owner', 'admin') if active_job else 'admin'
                               JOB_REGISTRY.create_retry(job_id, {
                                  'temp_dir': temp_dir,
                                  'db_name': dumped_db_name,
                                  'failed_tables': failed_list,
                                  'table_failure_details': failure_details,
                                  'now_passed': now_passed,
                                  'export_failed_tables': list(export_failed),
                                  'dump_mode': dump_mode,
                                  'obscured_db_to_cleanup': obscured_db,
                                  'params': params,
                                  'created_at': datetime.now(),
                                  'import_already_ran': True,
                                  'naming_info': {
                                      'tenant': params.get('new_tenant_name', database),
                                      'host_key': params.get('host_key', 'unknown')
                                  }
                               }, owner=owner)
                               # Stop here — the frontend Partial Failure modal takes over
                               return
                          else:
                               # Only known export failures occurred, proceed as success logic
                               pass
                      
                      else:
                          # Critical Failure (No specific files, e.g. Connection Error, No files found)
                          job_control['status'] = 'Failed' 
                          JOB_REGISTRY.update_active(job_id, 'error', f"Import Failed: {import_msg}")
                          if logger: logger.error(f"Import Critical Failure: {import_msg}", action="IMPORT_FAILED")
                          return


             # --- ZIPPING (Common) ---
             # Even if migrated, we might want to allow download, or just mark completed.
             # Standard flow: Zip it.
             job_control['status'] = 'Zipping'
             
             # Naming Logic (Simplified version of download_database)
             tenant = params.get('new_tenant_name') or database
             host_key = params.get('host_key') or 'unknown'
             environment = host_key[3:] if host_key.startswith('db_') else host_key
             export_type = "plain" if dump_mode == "Tenant Change" else dump_mode.lower().replace(" ", "_")
             timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
             
             try:
                 final_name = f"{tenant}_{environment}_{export_type}_{timestamp}"
                 final_path = os.path.join(temp_dir, final_name)
                 
                 # Move folder
                 source_folder = os.path.join(temp_dir, dumped_db_name)
                 
                 # Defensive validation: ensure folder exists before renaming
                 if not os.path.exists(source_folder):
                      # Log available folders for debugging
                      available = os.listdir(temp_dir) if os.path.exists(temp_dir) else []
                      error_msg = f"Expected folder '{dumped_db_name}' not found in temp_dir. Available: {available}"
                      if logger: logger.error(error_msg, action="EXPORT_ERROR")
                      raise FileNotFoundError(error_msg)
                 
                 os.rename(source_folder, final_path)
                 
                 # Zip - archive from parent dir so zip contains final_name/*.sql
                 # (MySQL Workbench Dump Project Folder expects files inside a named subfolder)
                 zip_base = os.path.join(temp_dir, final_name)
                 shutil.make_archive(zip_base, 'zip', temp_dir, final_name)
                 zip_file = f"{zip_base}.zip"
                 
                 JOB_REGISTRY.update_active(job_id, 'result', zip_file)
                 job_control['status'] = 'Completed'
                 
                 action_type = "MIGRATION_SUCCESS" if params.get('target_host') else "EXPORT_SUCCESS"
                 if logger: logger.info(f"Async Job Completed: {zip_file}", action=action_type)
             except Exception as zip_e:
                 job_control['status'] = 'Failed'
                 JOB_REGISTRY.update_active(job_id, 'error', f"Zipping failed: {str(zip_e)}")
                 if logger: logger.error(f"Zipping Exception: {str(zip_e)}", action="EXPORT_ERROR")
             
             # Cleanup obscured handled in finally or by download endpoint cleanup?
             # We should cleanup obscured DB now, keep file for download.
             if obscured_db:
                  try: delete_temp_db.drop_temp_database(host, user, password, obscured_db)
                  except: pass

        else:
            # Failure or Partial Failure
            if failed_tables:
                job_control['status'] = 'Partial Failure'
                
                # Populate retry flow
                active_job = JOB_REGISTRY._active.get(job_id)
                owner = active_job.get('owner', 'admin') if active_job else 'admin'
                JOB_REGISTRY.create_retry(job_id, {
                    'temp_dir': temp_dir,
                    'db_name': dumped_db_name,
                    'failed_tables': failed_tables,
                    'dump_mode': dump_mode,
                    'obscured_db_to_cleanup': obscured_db,
                    'params': params,
                    'created_at': datetime.now(),
                    'naming_info': {
                        'tenant': params.get('new_tenant_name', database),
                        'host_key': params.get('host_key', 'unknown')
                    }
                }, owner=owner)
                if logger: logger.warning(f"Async Export Partial Failure: {failed_tables}", action="EXPORT_PARTIAL_FAILURE")
            else:
                job_control['status'] = 'Failed'
                JOB_REGISTRY.update_active(job_id, 'error', message)
                safe_rmtree(temp_dir, logger=logger) # Cleanup
                if logger: logger.error(f"Async Export Failed: {message}", action="EXPORT_FAILED")

    except Exception as e:
        job_control['status'] = 'Failed'
        JOB_REGISTRY.update_active(job_id, 'error', str(e))
        if logger: logger.error(f"Async Export Exception: {e}", action="EXPORT_ERROR")
        if temp_dir and os.path.exists(temp_dir):
             safe_rmtree(temp_dir, logger=logger)

@app.post('/start-export')
async def start_export(request: Request):
    """Start an async export job"""
    try:
        body = await request.json()
        # validate body... similar to download
        database = body.get('database')
        if not database: return {"error": "Database required"}
        
        username = require_auth(request)
        if not username: return {"error": "Auth required"}
        
        # Get creds from server-side store
        cred_token = request.session.get('cred_token')
        creds = CREDENTIAL_STORE.get(cred_token) if cred_token else None
        
        host = creds.get('host') if creds else request.session.get('host')
        user = creds.get('user') if creds else request.session.get('user')
        port = creds.get('port', 3306) if creds else request.session.get('port', 3306)
        password = creds.get('password', '') if creds else ''
        
        dump_modes = body.get('dump_modes', [])
        # Fallback
        if not dump_modes and body.get('dump_mode'):
             dump_modes = [body.get('dump_mode')]
        if not dump_modes: dump_modes = ['Plain']

        if not host:
             return {"error": "Session expired. Please reconnect to the database."}


        params = {
            'host': host, 'port': port, 'user': user, 'password': password,
            'database': database,
            'dump_modes': dump_modes,
            'dump_mode': body.get('dump_mode') or 'Plain',
            'new_tenant_name': body.get('new_tenant_name') or None,
            'host_key': body.get('host_key') or 'unknown'
        }
        
        # --- APPROVAL CHECK ---
        needs_approval = await sync_to_async(check_approval_needed_sync)('EXPORT', host, port, database, username)
        if needs_approval:
            req_id = await sync_to_async(create_approval_request_sync)('EXPORT', database, params, username)
            return {
                "status": "pending_approval", 
                "request_id": req_id, 
                "message": "Export from PRODUCTION database requires approval."
            }
        
        # --- PER-USER JOB LIMIT ---
        active_count = JOB_REGISTRY.count_active_for_user(username)
        if active_count >= MAX_JOBS_PER_USER:
            return JSONResponse(status_code=429, content={
                "error": f"You already have {active_count} active export job(s). "
                         f"Please wait for them to complete before starting a new one."
            })

        job_id = str(uuid.uuid4())
        job_control = {
            'pause_event': threading.Event(),
            'cancel_event': threading.Event(),
            'progress': {'total': 0, 'current': 0},
            'status': 'Starting'
        }
        job_control['pause_event'].set()  # Start running

        JOB_REGISTRY.create_active(job_id, {
            'control': job_control,
            'status': 'Starting',
            'params': params,
        }, owner=username)
        
        logger = None
        if 'logger_session_id' in request.session:
            logger = get_session_logger(request.session['logger_session_id'], username, client_ip=request.client.host)
            
        t = threading.Thread(target=run_async_export, args=(job_id, params, job_control, logger))
        t.start()
        
        return {"job_id": job_id, "status": "started"}
        
    except Exception as e:
        return {"error": str(e)}

@app.get('/export-status/{job_id}')
async def export_status(job_id: str, request: Request):
    username = require_auth(request)
    if not username:
        return JSONResponse(status_code=401, content={"error": "Authentication required"})

    # Check ownership (admins can see all jobs)
    is_admin = await _is_admin(username)
    result = JOB_REGISTRY.get_active_if_owner(job_id, username, is_admin=is_admin)
    if result is None:
        return JSONResponse(status_code=404, content={"error": "Job not found"})
    if result is False:
        return JSONResponse(status_code=403, content={"error": "Access denied: this job belongs to another user"})

    job = result
    ctrl = job['control']
    response = {
        "job_id": job_id,
        "status": ctrl['status'],
        "progress": ctrl['progress'],
        "paused": not ctrl['pause_event'].is_set(),
        "error": job.get('error'),
        "result": job.get('result') is not None
    }

    retry_job = JOB_REGISTRY.get_retry(job_id)
    if retry_job:
        response['failed_tables']         = retry_job.get('failed_tables', [])
        response['table_failure_details'] = retry_job.get('table_failure_details', [])
        response['now_passed']            = retry_job.get('now_passed', [])

    return response

@app.post('/export-control/{job_id}')
async def export_control(job_id: str, request: Request):
    """Pause/resume/cancel an active export — auth + owner-only"""
    username = require_auth(request)
    if not username:
        return JSONResponse(status_code=401, content={"error": "Authentication required"})

    is_admin = await _is_admin(username)
    result = JOB_REGISTRY.get_active_if_owner(job_id, username, is_admin=is_admin)
    if result is None:
        return JSONResponse(status_code=404, content={"error": "Job not found"})
    if result is False:
        return JSONResponse(status_code=403, content={"error": "Access denied: this job belongs to another user"})

    body = await request.json()
    action = body.get('action')
    ctrl = result['control']

    if action == 'pause':
        ctrl['pause_event'].clear()
        return {"status": "paused"}
    elif action == 'resume':
        ctrl['pause_event'].set()
        return {"status": "resumed"}
    elif action == 'cancel':
        ctrl['cancel_event'].set()
        ctrl['pause_event'].set()  # Unpause so thread can exit
        return {"status": "cancelling"}

    return {"error": "Invalid action"}

@app.get('/download-artifact/{job_id}')
async def download_artifact(job_id: str, request: Request, background_tasks: BackgroundTasks):
    """Download completed export zip — auth + owner-only"""
    username = require_auth(request)
    if not username:
        return JSONResponse(status_code=401, content={"error": "Authentication required"})

    is_admin = await _is_admin(username)
    result = JOB_REGISTRY.get_active_if_owner(job_id, username, is_admin=is_admin)
    if result is None:
        return JSONResponse(status_code=404, content={"error": "Job not found"})
    if result is False:
        return JSONResponse(status_code=403, content={"error": "Access denied: this job belongs to another user"})

    job = result
    zip_path = job.get('result')

    if not zip_path or not os.path.exists(zip_path):
        return JSONResponse(status_code=404, content={"error": "File not ready or missing"})

    # Atomically remove from registry before streaming
    JOB_REGISTRY.delete_active(job_id)

    background_tasks.add_task(cleanup_temp_files, job.get('temp_dir', ''), zip_path)

    filename = os.path.basename(zip_path)
    return FileResponse(
        path=zip_path,
        filename=filename,
        media_type='application/zip',
        headers={"X-Filename": filename}
    )


def cleanup_temp_files(folder_path, file_path, host=None, user=None, password=None, obscured_db=None):
    """Cleanup temporary files and obscured DB clone after download"""
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        if folder_path and os.path.exists(folder_path):
            safe_rmtree(folder_path)
    except Exception as e:
        logging.getLogger(__name__).error(f"Error cleaning up temp files: {e}")
    # Drop the temporary obscured/service-off clone DB if it exists
    if obscured_db and host and user:
        try:
            delete_temp_db.drop_temp_database(host, user, password or '', obscured_db)
        except Exception as e:
            logging.getLogger(__name__).error(f"Error dropping temp clone DB {obscured_db}: {e}")


@app.post('/download')
async def download_database(request: Request, background_tasks: BackgroundTasks):
    """Download database dump - creates a zip file and streams it for download"""
    
    # Get JSON body
    try:
        body = await request.json()
        database = body.get('database')
        dump_mode = body.get('dump_mode', 'Plain')
    except Exception as e:
        return {"error": f"Invalid request format: {str(e)}"}
    
    if not database:
        return {"error": "Database name is required"}
    
    # Check authentication
    username = require_auth(request)
    if not username:
        return {"error": "Authentication required"}
    
    # Get logger
    logger = None
    if 'logger_session_id' in request.session:
        logger = get_session_logger(request.session['logger_session_id'], username, client_ip=request.client.host)
    
    # Retrieve credentials from server-side store
    cred_token = request.session.get('cred_token')
    creds = CREDENTIAL_STORE.get(cred_token) if cred_token else None
    
    host = creds.get('host') if creds else request.session.get('host')
    port = creds.get('port', 3306) if creds else request.session.get('port', 3306)
    user = creds.get('user') if creds else request.session.get('user')
    password = creds.get('password', '') if creds else ''
    
    if not host or not user or not creds:
        if logger:
            logger.error("Session expired - no database credentials found")
        return {"error": "Session expired. Please reconnect to the database."}
    
    # Use a temporary directory for the dump
    temp_dir = tempfile.mkdtemp()
    obscured_db = None  # Track temp DB for cleanup
    dumped_db_name = database  # Track which database name was actually dumped
    
    if logger:
        logger.info(f"Starting database export: database={database}, mode={dump_mode}, host={host}", action="EXPORT_START")
    
    # --- APPROVAL CHECK (Sync Download) ---
    # Check if this operation requires approval
    needs_approval = await sync_to_async(check_approval_needed_sync)('EXPORT', host, port, database, username)
    if needs_approval:
        # Create parameters for the request
        params = {
            'host': host, 'port': port, 'user': user, 'password': password,
            'database': database,
            'dump_mode': dump_mode,
            'new_tenant_name': body.get('new_tenant_name') or None,
            'host_key': body.get('host_key') or 'unknown'
        }
        
        req_id = await sync_to_async(create_approval_request_sync)('EXPORT', database, params, username)
        
        if logger:
             logger.info(f"Export blocked: Approval required for {database} on {host}", action="EXPORT_BLOCKED")
             
        return JSONResponse(status_code=202, content={
            "status": "pending_approval", 
            "request_id": req_id, 
            "message": "Export from PRODUCTION database requires approval. Request submitted."
        })
    
    try:
        if dump_mode == "Plain":
            # Perform dump with session credentials (thread-safe)
            success, message, failed_tables = export_dump.perform_dump(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
                dump_path=temp_dir
            )
            
            # Handle failure cases
            if not success or failed_tables:
                 # Check if it's a partial failure (we have a failed_tables list)
                 if failed_tables:
                     # Create a job ID for retry
                     job_id = str(uuid.uuid4())
                     active_job = JOB_REGISTRY._active.get(job_id)
                     owner = active_job.get('owner', 'admin') if active_job else 'admin'
                     JOB_REGISTRY.create_retry(job_id, {
                         'temp_dir': temp_dir,
                         'db_name': dumped_db_name,
                         'failed_tables': failed_tables,
                         'dump_mode': dump_mode,
                         'params': {
                             'host': host, 'port': port, 'user': user, 'password': password,
                             'database': database,
                             'target_database_name': None 
                         },
                         'created_at': datetime.now()
                     }, owner=owner)
                     if logger:
                         logger.warning(f"Export partial failure. Job ID: {job_id}, Failed: {failed_tables}", action="EXPORT_PARTIAL_FAILURE")
                     
                     return JSONResponse(status_code=200, content={
                         "status": "partial_failure", 
                         "failed_tables": failed_tables,
                         "job_id": job_id,
                         "message": message
                     })
                 
                 # Complete failure
                 safe_rmtree(temp_dir, logger=logger)
                 return JSONResponse(status_code=500, content={"error": message})

        elif dump_mode == "Obscure":
            # Use default obscure.sql
            obscured_db = obscure.obscure_data(host, user, password, database)
            
            if not obscured_db:
                if logger:
                    logger.error("Obscure mode failed: Could not obscure data")
                safe_rmtree(temp_dir, logger=logger)
                return JSONResponse(status_code=500, content={"error": "Failed to obscure data. Check server logs for details."})
            
            # Log that temporary database was created
            if logger:
                logger.info(f"Created temporary obscured database: {obscured_db} (will be dropped after export)")
            
            # Track the obscured database name
            dumped_db_name = obscured_db
            
            # Perform dump on obscured temp database
            success, message, failed_tables = export_dump.perform_dump(
                host=host,
                port=port,
                user=user,
                password=password,
                database=obscured_db,
                dump_path=temp_dir,
                target_database_name=database # Use original name in export files
            )
            
            if not success or failed_tables:
                 if failed_tables:
                     job_id = str(uuid.uuid4())
                     active_job = JOB_REGISTRY._active.get(job_id)
                     owner = active_job.get('owner', 'admin') if active_job else 'admin'
                     JOB_REGISTRY.create_retry(job_id, {
                         'temp_dir': temp_dir,
                         'db_name': dumped_db_name,
                         'failed_tables': failed_tables,
                         'dump_mode': dump_mode,
                         'obscured_db_to_cleanup': obscured_db, # Need to cleanup this DB later!
                         'params': {
                             'host': host,
                             'user': user,
                             'password': password,
                             'database': obscured_db,
                             'target_database_name': database # Preserve original name for retry
                         },
                         'created_at': datetime.now()
                     }, owner=owner)
                     return JSONResponse(status_code=200, content={
                         "status": "partial_failure", 
                         "failed_tables": failed_tables,
                         "job_id": job_id,
                         "message": message
                     })

                 # Cleanup if full failure
                 safe_rmtree(temp_dir, logger=logger)
                 return JSONResponse(status_code=500, content={"error": message})

        elif dump_mode == "Service Off":
            # Use config.service_off_file
            service_off_file = config.service_off_file
            if not os.path.exists(service_off_file):
                 return JSONResponse(status_code=500, content={"error": f"{service_off_file} file not found"})

            # We reuse the obscure_data function but pass a different SQL file
            # It clones the DB and runs the SQL
            obscured_db = obscure.obscure_data(host, user, password, database, sql_file_path=service_off_file)
            
            if not obscured_db:
                if logger:
                    logger.error("Service Off mode failed: Could not apply service off SQL")
                safe_rmtree(temp_dir, logger=logger)
                return JSONResponse(status_code=500, content={"error": "Failed to apply Service Off queries. Check server logs."})
            
            if logger:
                logger.info(f"Created temporary Service Off database: {obscured_db}")
            
            dumped_db_name = obscured_db
            
            success, message, failed_tables = export_dump.perform_dump(
                host=host,
                user=user,
                password=password,
                database=obscured_db,
                dump_path=temp_dir,
                target_database_name=database # Use original name in export files
            )
            
            if not success or failed_tables:
                 if failed_tables:
                     job_id = str(uuid.uuid4())
                     active_job = JOB_REGISTRY._active.get(job_id)
                     owner = active_job.get('owner', 'admin') if active_job else 'admin'
                     JOB_REGISTRY.create_retry(job_id, {
                         'temp_dir': temp_dir,
                         'db_name': dumped_db_name,
                         'failed_tables': failed_tables,
                         'dump_mode': dump_mode,
                         'obscured_db_to_cleanup': obscured_db,
                         'params': {
                             'host': host,
                             'user': user,
                             'password': password,
                             'database': obscured_db,
                             'target_database_name': database # Preserve original name for retry
                         },
                         'created_at': datetime.now()
                     }, owner=owner)
                     return JSONResponse(status_code=200, content={
                         "status": "partial_failure", 
                         "failed_tables": failed_tables,
                         "job_id": job_id,
                         "message": message
                     })

                 safe_rmtree(temp_dir, logger=logger)
                 return JSONResponse(status_code=500, content={"error": message})
        
        elif dump_mode == "Tenant Change":
            # Tenant Change - Rename the database in the export
            new_tenant_name = body.get('new_tenant_name')
            if not new_tenant_name:
                safe_rmtree(temp_dir, logger=logger)
                return JSONResponse(status_code=400, content={"error": "New Tenant Name is required for Tenant Change mode."})

            if logger:
                logger.info(f"Tenant Change Mode: Exporting {database} as {new_tenant_name}")

            dumped_db_name = database
            
            # Pass new_tenant_name as target_database_name to rename it in the SQL files
            success, message, failed_tables = export_dump.perform_dump(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
                dump_path=temp_dir,
                target_database_name=new_tenant_name
            )
            
            if not success or failed_tables:
                 if failed_tables:
                     job_id = str(uuid.uuid4())
                     active_job = JOB_REGISTRY._active.get(job_id)
                     owner = active_job.get('owner', 'admin') if active_job else 'admin'
                     JOB_REGISTRY.create_retry(job_id, {
                         'temp_dir': temp_dir,
                         'db_name': dumped_db_name,
                         'failed_tables': failed_tables,
                         'dump_mode': dump_mode,
                         'params': {
                             'host': host,
                             'user': user,
                             'password': password,
                             'database': database,
                             'target_database_name': new_tenant_name
                         },
                         'created_at': datetime.now(),
                          # We need to preserve naming info for the final zip
                         'naming_info': {
                             'tenant': new_tenant_name, # Use new tenant name for zip
                             'host_key': body.get('host_key', 'unknown')
                         }
                     }, owner=owner)
                     return JSONResponse(status_code=200, content={
                         "status": "partial_failure", 
                         "failed_tables": failed_tables,
                         "job_id": job_id,
                         "message": message
                     })

                 safe_rmtree(temp_dir, logger=logger)
                 return JSONResponse(status_code=500, content={"error": message})
        
        else:
            if logger:
                logger.error(f"Invalid dump mode: {dump_mode}")
            safe_rmtree(temp_dir, logger=logger)
            return JSONResponse(status_code=400, content={"error": f"Invalid dump mode: {dump_mode}"})
        
        # Locate the dump folder
        target_dir = os.path.join(temp_dir, dumped_db_name)
        
        if not os.path.exists(target_dir):
            if logger:
                logger.error(f"Dump directory not found: {target_dir}")
            safe_rmtree(temp_dir, logger=logger)
            return JSONResponse(status_code=500, content={"error": f"Dump failed or database directory not found. Looking for: {target_dir}"})

        # --- Naming Convention Logic ---
        # Pattern: <tenant>_<environment>_<export_type>_<timestamp>
        
        # 1. Tenant = Database Name (or New Tenant Name if Tenant Change mode)
        if dump_mode == "Tenant Change":
             tenant = body.get('new_tenant_name', database)
        else:
             tenant = database
        
        # 2. Environment (from host_key)
        # Expecting format like 'db_local', 'db_demo' -> extract 'local', 'demo'
        host_key = body.get('host_key', 'unknown')
        if host_key.startswith('db_'):
            environment = host_key[3:] # remove 'db_' prefix
        else:
            environment = host_key
            
        # 3. Export Type
        if dump_mode == "Tenant Change":
            export_type = "plain"
        else:
            export_type = dump_mode.lower().replace(" ", "_")
        
        # 4. Timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Construct Final Name
        final_dir_name = f"{tenant}_{environment}_{export_type}_{timestamp}"
            
        final_dir_path = os.path.join(temp_dir, final_dir_name)
        os.rename(target_dir, final_dir_path)

        # Zip the directory - archive from parent dir so zip contains final_dir_name/*.sql
        # (MySQL Workbench Dump Project Folder expects files inside a named subfolder)
        zip_filename = f"{final_dir_name}"
        zip_path = os.path.join(temp_dir, zip_filename)
        shutil.make_archive(zip_path, 'zip', temp_dir, final_dir_name)
        zip_file_path = f"{zip_path}.zip"        
        
        if logger:
            logger.info(f"Export completed: {zip_filename}.zip created. Sending to browser.", action="EXPORT_SUCCESS")

        # Add cleanup task (runs after response is sent)
        # Also passes obscured_db so the temp MySQL clone is dropped cleanly
        background_tasks.add_task(
            cleanup_temp_files, temp_dir, zip_file_path,
            host, user, password, obscured_db
        )

        # Return the file as a download
        return FileResponse(
            path=zip_file_path,
            filename=f"{zip_filename}.zip",
            media_type='application/zip',
            headers={"X-Filename": f"{zip_filename}.zip"}
        )

    except Exception as e:
        if logger:
            logger.error(f"Exception during export: {str(e)}")
        safe_rmtree(temp_dir, logger=logger)
        return JSONResponse(status_code=500, content={"error": f"An error occurred: {str(e)}"})
    
    finally:
        # Always cleanup temp database if it was created
        if obscured_db:
            try:
                # Wait a moment
                import time
                time.sleep(1)
                
                if logger:
                    logger.info(f"Cleaning up temporary database: {obscured_db}")
                
                delete_temp_db.drop_temp_database(host, user, password, obscured_db)
                
                if logger:
                    logger.info(f"Successfully dropped temporary database: {obscured_db}")
                
            except Exception as e:
                error_msg = f"Failed to cleanup temp database {obscured_db}: {e}"
                if logger:
                    logger.error(error_msg)


@app.post('/retry-export')
async def retry_export(request: Request, background_tasks: BackgroundTasks):
    """Handle retry of failed or full export"""
    try:
        # Create logger if possible
        username = require_auth(request)
        logger = None
        if username and 'logger_session_id' in request.session:
            logger = get_session_logger(request.session['logger_session_id'], username)

        body = await request.json()
        job_id = body.get('job_id')
        retry_mode = body.get('retry_mode') # 'failed' or 'full'
        
        if not job_id or not JOB_REGISTRY.get_retry(job_id):
            return JSONResponse(status_code=404, content={"error": "Retry session expired or invalid. Please start over."})
        
        job = JOB_REGISTRY.get_retry(job_id)
        temp_dir = job['temp_dir']
        params = job['params']
        
        # Determine tables to dump
        tables_to_dump = None
        if retry_mode == 'failed':
            tables_to_dump = job['failed_tables']
            if not tables_to_dump:
                return JSONResponse(status_code=400, content={"error": "No failed tables to retry."})
        elif retry_mode == 'ignore':
            # Ignore failures, proceed to zip what we have
            if logger: logger.info(f"User chose to ignore failures and proceed. Failed tables ignored: {job['failed_tables']}")
            tables_to_dump = [] # Dump nothing new
        
        # --- ASYNC RETRY ---
        # Create a NEW Async Job for the retry attempt
        retry_job_id = str(uuid.uuid4())
        
        job_control = {
            'pause_event': threading.Event(),
            'cancel_event': threading.Event(),
            'progress': {'total': len(tables_to_dump) if tables_to_dump else 0, 'current': 0}, 
            # Note: Total is only new tables. If ignore, total 0.
            'status': 'Starting Retry'
        }
        job_control['pause_event'].set()

        # Update metadata to include 'obscured_db' if it exists in old job params (or we need to pass it)
        # We need to make sure 'obscured_db' is passed so `run_async_export` knows it exists.
        # But `run_async_export` logic I just added looks at params['obscured_db'].
        # Does job['params'] have it? No. `params` usually assumes input params.
        # But we can inject it.
        # Wait, obscured db name was generated inside run_async_export. 
        # Did we store it in job? 
        # In `run_async_export` (original): `ACTIVE_EXPORTS[job_id]['obscured_db'] = obscured_db`
        # So the OLD job has it in `ACTIVE_EXPORTS[old_job_id]['obscured_db']`.
        # SYNCHRONOUS `retry_export` used EXPORT_JOBS. 
        # Ideally we should unify retry and active.
        # For now, let's assume active might be gone if the server restarted?
        # But retry persists? No, they are both in-memory.
        # If user retries, retry[old_job_id] exists.
        
        # Let's try to get obscured_db from the old job if present
        obscured_db = job.get('obscured_db')
        if obscured_db:
            params['obscured_db'] = obscured_db

        # When user chose "Proceed with Failures" (ignore mode), tables_to_dump = []
        # We must carry the known failed tables into params so the import phase
        # can exclude them (they were never exported → no .sql file for them).
        if retry_mode == 'ignore':
            params['export_failed_tables'] = job.get('failed_tables', [])
            # Carry the import_already_ran flag so run_async_export can skip re-import
            if job.get('import_already_ran'):
                params['import_already_ran'] = True
            if logger:
                logger.info(
                    f"Proceed-with-failures: {len(params['export_failed_tables'])} tables will be excluded from import",
                    action="RETRY_IGNORE"
                )

        # Carry the previous failed-tables list into params so run_async_export can
        # diff it against the new failures and compute which tables "recovered".
        if retry_mode == 'failed':
            params['_prev_failed_tables'] = job.get('failed_tables', [])

        JOB_REGISTRY.create_active(retry_job_id, {
            'control': job_control,
            'status': 'Starting Retry',
            'params': params,
            'temp_dir': temp_dir, # We will point to this, but run_async_export updates it too
            'created_at': datetime.now()
        }, owner=username)

        # Start Thread
        thread = threading.Thread(
            target=run_async_export,
            args=(retry_job_id, params, job_control, logger, temp_dir, tables_to_dump)
        )
        thread.start()

        return {"job_id": retry_job_id, "status": "started"}

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        with open("last_error.txt", "w") as f:
            f.write(f"Error: {str(e)}\n\nTraceback:\n{tb}")

        if logger:
            logger.error(f"Retry Logic Exception: {str(e)}")
            logger.error(tb)

        return JSONResponse(status_code=500, content={"error": f"Retry error: {str(e)}"})




# --- APPROVAL SYSTEM HELPERS ---

def check_approval_needed_sync(op_type, host, port, database, username):
    """
    Check if an operation requires approval.
    All migrations (IMPORT) require approval so the target password can be securely entered.
    For EXPORT, SUPERUSER bypasses the approval queue entirely.
    """
    # All migrations MUST go through approval to capture the target password
    if op_type == 'IMPORT':
        return True

    try:
        user = User.objects.get(username=username)
        # Django-level superuser bypass
        if user.is_superuser:
            return False
        # Application-level UserHierarchy SUPERUSER bypass
        try:
            if user.hierarchy.role == 'SUPERUSER':
                return False
        except Exception:
            pass
    except User.DoesNotExist:
        pass

    if op_type == 'EXPORT':
        try:
            q_port = int(port) if port else 3306
            q_host = str(host).strip()
            prod_db = ProductionDatabase.objects.get(host=q_host, port=q_port)
            return prod_db.is_production
        except ProductionDatabase.DoesNotExist:
            return False
        except Exception:
            return False

    return False

def create_approval_request_sync(op_type, target_db, params, username):
    """
    Create a PENDING OperationRequest, storing the requester's group
    so the correct group Admin can see and endorse it.
    """
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return None

    # Resolve the requester's group (USER and ADMIN belong to a group; SUPERUSER does not)
    requester_group = None
    try:
        requester_group = user.hierarchy.group
    except Exception:
        pass

    req = OperationRequest.objects.create(
        operation_type=op_type,
        target_db=target_db,
        params=params,
        requested_by=user,
        requester_group=requester_group,
        status='PENDING'
    )
    return req.id

def get_request_sync(request_id):
    try:
        return OperationRequest.objects.get(id=request_id)
    except OperationRequest.DoesNotExist:
        return None

def get_request_status_sync(request_id):
    try:
        req = OperationRequest.objects.get(id=request_id)
        return {
            "status": req.status,
            "admin_approved": req.admin_approved,
            "superuser_approved": req.superuser_approved,
            "reviewed_by": req.reviewed_by.username if req.reviewed_by else None
        }
    except OperationRequest.DoesNotExist:
        return None

def get_my_requests_sync(username):
    from django.utils import timezone
    from datetime import timedelta
    
    try:
        user = User.objects.get(username=username)
        # Fetch all non-executed and non-rejected requests for this user
        time_threshold = timezone.now() - timedelta(days=1)
        requests = OperationRequest.objects.filter(
            requested_by=user,
            requested_at__gte=time_threshold
        ).exclude(status__in=['EXECUTED', 'REJECTED']).order_by('-requested_at')
        
        results = []
        for req in requests:
            # Safely mask password when sending to frontend
            display_params = dict(req.params) if isinstance(req.params, dict) else {}
            if 'password' in display_params: display_params['password'] = '********'
            if 'source_password' in display_params: display_params['source_password'] = '********'
            if 'target_password' in display_params: display_params['target_password'] = '********'

            results.append({
                "id": req.id,
                "operation_type": req.operation_type,
                "target_db": req.target_db,
                "status": req.status,
                "requested_at": req.requested_at.strftime("%Y-%m-%d %H:%M:%S") if req.requested_at else None,
                "admin_approved": req.admin_approved,
                "superuser_approved": req.superuser_approved,
                "params": display_params
            })
        return results
    except User.DoesNotExist:
        return []

def mark_executed_sync(request_id):
    OperationRequest.objects.filter(id=request_id).update(status='EXECUTED')


@app.post('/execute-operation/{request_id}')
async def execute_approved_operation(request_id: int, request: Request):
    """
    Execute an operation after it has been approved.
    """
    username = require_auth(request)
    if not username: return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    # Fetch request
    op_request = await sync_to_async(get_request_sync)(request_id)
    if not op_request:
        return JSONResponse(status_code=404, content={"error": "Request not found"})
        
    # Validation
    # Validation
    if op_request.status != 'APPROVED':
        return JSONResponse(status_code=400, content={"error": f"Request is not APPROVED (Current status: {op_request.status})"})
        
    # --- MAKER CHECKER LOGIC ---
    is_safe_to_execute = False
    rejection_reason = "Unauthorized approval."
    
    # STRICT POLICY: Only Superuser approval allows execution.
    if op_request.superuser_approved:
        is_safe_to_execute = True
    else:
        is_safe_to_execute = False
        rejection_reason = "All operations require mandatory SUPERUSER approval."

    # Legacy Admin logic removed as requested.
            
    if not is_safe_to_execute:
         return JSONResponse(status_code=400, content={"error": rejection_reason})

    # Execute
    try:
        params = op_request.params
        
        # Inject transient passwords securely from RAM
        import credential_store
        creds = credential_store.get_credentials(request_id, remove=True)
        if creds:
            if creds.get('target_password'):
                 params['target_password'] = creds['target_password']
            if creds.get('source_password'):
                 params['password'] = creds['source_password']
                 
        job_id = str(uuid.uuid4())
        
        # Prepare Job Control
        job_control = {
            'pause_event': threading.Event(),
            'cancel_event': threading.Event(),
            'progress': {'total': 0, 'current': 0},
            'status': 'Starting Approved Operation'
        }
        job_control['pause_event'].set()

        # Get Logger
        logger = None
        if 'logger_session_id' in request.session:
            logger = get_session_logger(request.session['logger_session_id'], username, client_ip=request.client.host)
            
        if logger:
            logger.info(f"Executing approved operation (ID: {request_id}): {op_request.operation_type} on {op_request.target_db}", action="EXECUTE_APPROVED")

        # Register Active Job
        JOB_REGISTRY.create_active(job_id, {
            'control': job_control,
            'status': 'Starting',
            'params': params,
            'created_at': datetime.now(),
            'approval_request_id': request_id
        }, owner=username)
        
        # Mark as Executed in DB
        await sync_to_async(mark_executed_sync)(request_id)
        
        # Start Thread
        t = threading.Thread(target=run_async_export, args=(job_id, params, job_control, logger))
        t.start()
        
        return {"success": True, "job_id": job_id, "message": "Operation started successfully"}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get('/check-request-status/{request_id}')
async def check_request_status(request_id: int, request: Request):
    """
    Check the status of an approval request.
    Used by frontend polling to detect when approval is granted.
    Requires authentication.
    """
    username = require_auth(request)
    if not username:
        return JSONResponse(status_code=401, content={"error": "Authentication required"})

    status_data = await sync_to_async(get_request_status_sync)(request_id)
    if not status_data:
        return JSONResponse(status_code=404, content={"error": "Request not found"})

    return status_data

@app.get('/my-pending-requests')
async def my_pending_requests(request: Request):
    """
    Returns a list of all pending or approved requests for the logged-in user.
    """
    username = require_auth(request)
    if not username:
        return JSONResponse(status_code=401, content={"error": "Authentication required"})

    requests_data = await sync_to_async(get_my_requests_sync)(username)
    return {"success": True, "requests": requests_data}

@app.get('/my-active-jobs')
async def my_active_jobs(request: Request):
    """
    Returns a safe summary of all ongoing jobs (and retries) for the user.
    """
    username = require_auth(request)
    if not username:
        return JSONResponse(status_code=401, content={"error": "Authentication required"})
        
    active_jobs = JOB_REGISTRY.get_all_active_for_user(username)
    # Could similarly fetch from _retry if we want to show jobs paused on partial failure
    
    return {"success": True, "active_jobs": active_jobs}





@app.post('/migrate')
async def migrate_database(request: Request, background_tasks: BackgroundTasks):
    """
    Handle direct database migration (Export -> Import)
    Now ASYNCHRONOUS to allow Pause/Resume support.
    """
    # Get logger
    username = request.session.get('username', 'unknown')
    logger = None
    if 'logger_session_id' in request.session:
        logger = get_session_logger(request.session['logger_session_id'], username, client_ip=request.client.host)

    try:
        body = await request.json()
        
        # We pass the entire body as params to run_async_export
        # It contains source_* and target_* keys.
        # run_async_export expects: 'host', 'port', 'user', 'password', 'database' (Source)
        # But body has 'source_host' etc.
        # We need to map them back to standard 'host' keys for export_dump compatibility.
        
        params = body.copy()
        
        # Map source_* to standard keys for export logic
        params['host'] = body.get('source_host')
        params['port'] = body.get('source_port', 3306)
        params['user'] = body.get('source_user')
        params['password'] = body.get('source_password')
        params['database'] = body.get('database') # This is source db
        
        # --- SERVER-SIDE VALIDATION ---
        # Never rely on frontend-only checks. Validate all required fields here.
        missing = []
        if not params.get('host'):     missing.append('source host')
        if not params.get('user'):     missing.append('source user')
        if not params.get('database'): missing.append('source database')
        if not body.get('target_host'):     missing.append('target host')
        if not body.get('target_user'):     missing.append('target username')
        
        if missing:
            return JSONResponse(
                status_code=400,
                content={"error": f"Missing required migration fields: {', '.join(missing)}"}
            )
        
        # Target keys are already target_host etc.
        
        # --- APPROVAL CHECK ---
        # SUPERUSER bypasses approval and starts the job immediately.
        # ADMIN and USER always need SUPERUSER approval for migrations.
        needs_approval = await sync_to_async(check_approval_needed_sync)(
            'IMPORT', params.get('host'), params.get('port'), params.get('database'), username
        )
        
        if not needs_approval:
            # SUPERUSER — start migration immediately without queuing
            job_id = str(uuid.uuid4())
            job_control = {
                'pause_event': threading.Event(),
                'cancel_event': threading.Event(),
                'progress': {'total': 0, 'current': 0},
                'status': 'Starting Migration'
            }
            job_control['pause_event'].set()
            JOB_REGISTRY.create_active(job_id, {
                'status': 'Starting',
                'params': params,
                'control': job_control,
            }, owner=username)
            if logger: logger.info(f"SUPERUSER migration started directly (no approval): job_id={job_id}")
            t = threading.Thread(target=run_async_export, args=(job_id, params, job_control, logger))
            t.start()
            return {"success": True, "job_id": job_id, "message": "Migration started directly (superuser)."}
        
        # Non-superuser — queue for approval
        target_display = f"{body.get('new_tenant_name') or params['database']} -> {params.get('target_host')}"
        req_id = await sync_to_async(create_approval_request_sync)('IMPORT', target_display, params, username)
        
        return {
            "status": "pending_approval",
            "request_id": req_id,
            "message": "Migration/Import operation requires approval."
        }

    except Exception as e:
        if logger: logger.error(f"Migration Start Failed: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})




# --- ADMIN USER MANAGEMENT ---

def require_admin(request: Request):
    """Ensure user is logged in and is 'admin'"""
    user = require_auth(request)
    if not user: return None
    if user != "admin":
        return None # or raise exception
    return user

@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(request: Request):
    user = require_auth(request)
    if not user: return RedirectResponse(url='/login')
    if user != "admin":
        return HTMLResponse("Access Denied: Admins only", status_code=403)
        
    users_dict = auth.load_users()
    # Convert dict to list for template
    users_list = []
    for u, data in users_dict.items():
        users_list.append({
            "username": u,
            "created_at": data.get("created_at", "N/A")
        })
    
    return templates.TemplateResponse("admin_users.html", {
        "request": request, 
        "user": user,
        "users": users_list
    })

@app.post("/admin/users/add")
async def admin_add_user(request: Request):
    user = require_auth(request)
    if user != "admin": return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=403)
    
    data = await request.json()
    new_user = data.get("username")
    new_pass = data.get("password")
    
    if not new_user or not new_pass:
        return JSONResponse({"success": False, "error": "Username and Password required"})
        
    if auth.add_user(new_user, new_pass):
        if logger: logger.info(f"Admin added user: {new_user}", action="USER_MGMT")
        return JSONResponse({"success": True})
    else:
        return JSONResponse({"success": False, "error": "User already exists"})

@app.post("/admin/users/delete")
async def admin_delete_user(request: Request):
    user = require_auth(request)
    if user != "admin": return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=403)
    
    data = await request.json()
    target_user = data.get("username")
    
    if target_user == "admin":
        return JSONResponse({"success": False, "error": "Cannot delete admin"})
        
    if auth.remove_user(target_user):
        if logger: logger.info(f"Admin deleted user: {target_user}", action="USER_MGMT")
        return JSONResponse({"success": True})
    else:
        return JSONResponse({"success": False, "error": "User not found"})

@app.post("/admin/users/reset-password")
async def admin_reset_password(request: Request):
    user = require_auth(request)
    if user != "admin": return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=403)
    
    data = await request.json()
    target_user = data.get("username")
    new_pass = data.get("new_password")
    
    if not target_user or not new_pass:
         return JSONResponse({"success": False, "error": "Missing fields"})

    if auth.change_password(target_user, new_pass):
        if logger: logger.info(f"Admin reset password for: {target_user}", action="USER_MGMT")
        return JSONResponse({"success": True})
    else:
         return JSONResponse({"success": False, "error": "User not found"})
