import threading
import time

# Thread-safe in-memory store for transient credentials
# No passwords will ever be written to disk or the database.
_store_lock = threading.Lock()
CREDENTIAL_STORE = {}

def store_credentials(request_id, target_password, source_password=None):
    with _store_lock:
        CREDENTIAL_STORE[str(request_id)] = {
            'target_password': target_password,
            'source_password': source_password,
            'timestamp': time.time()
        }

def get_credentials(request_id, remove=True):
    with _store_lock:
        if remove:
            return CREDENTIAL_STORE.pop(str(request_id), None)
        else:
            return CREDENTIAL_STORE.get(str(request_id), None)

def clean_expired_credentials(max_age_seconds=86400):
    """Optionally clean up old credentials periodically to prevent memory leaks."""
    with _store_lock:
        current_time = time.time()
        expired_keys = [
            k for k, v in CREDENTIAL_STORE.items() 
            if current_time - v.get('timestamp', 0) > max_age_seconds
        ]
        for k in expired_keys:
            del CREDENTIAL_STORE[k]
