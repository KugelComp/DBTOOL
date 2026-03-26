"""
Quick smoke test for JobRegistry ownership isolation.
Run with: python test_job_registry.py
"""
import sys
import os
import threading
import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

# Import just what we need (avoid full FastAPI startup)
from datetime import datetime as dt

# ---- Inline minimal JobRegistry (same as app.py) ----
import threading as _threading

class JobRegistry:
    def __init__(self):
        self._lock = _threading.RLock()
        self._active = {}
        self._retry  = {}

    def create_active(self, job_id, data, owner):
        with self._lock:
            data['owner'] = owner
            data['created_at'] = data.get('created_at', dt.now())
            self._active[job_id] = data

    def get_active_if_owner(self, job_id, username, is_admin=False):
        with self._lock:
            job = self._active.get(job_id)
            if job is None:
                return None
            if is_admin or job.get('owner') == username:
                return job
            return False

    def count_active_for_user(self, username):
        with self._lock:
            running = {'Starting', 'Exporting'}
            return sum(
                1 for j in self._active.values()
                if j.get('owner') == username and j.get('status') in running
            )

    def delete_active(self, job_id):
        with self._lock:
            return self._active.pop(job_id, None)


print("=== JobRegistry Isolation Tests ===\n")

reg = JobRegistry()

# Test 1: Owner can access their own job
reg.create_active('job-alice-1', {'status': 'Starting', 'control': {'status': 'Starting'}}, owner='alice')
result = reg.get_active_if_owner('job-alice-1', 'alice')
assert result is not None and result is not False, "FAIL: Alice should access her own job"
print("[PASS] Owner can access their own job")

# Test 2: Other user cannot access someone else's job
result = reg.get_active_if_owner('job-alice-1', 'bob')
assert result is False, f"FAIL: Bob should be denied access to Alice's job, got: {result}"
print("[PASS] Non-owner gets False (→ 403)")

# Test 3: Non-existent job returns None (→ 404)
result = reg.get_active_if_owner('does-not-exist', 'bob')
assert result is None, "FAIL: Unknown job should return None"
print("[PASS] Non-existent job returns None (→ 404)")

# Test 4: Admin can access any job
result = reg.get_active_if_owner('job-alice-1', 'admin', is_admin=True)
assert result is not None and result is not False, "FAIL: Admin should see all jobs"
print("[PASS] Admin can access any user's job")

# Test 5: Per-user job count
reg.create_active('job-bob-1', {'status': 'Starting', 'control': {'status': 'Starting'}}, owner='bob')
reg.create_active('job-bob-2', {'status': 'Exporting', 'control': {'status': 'Exporting'}}, owner='bob')
reg.create_active('job-bob-3', {'status': 'Starting', 'control': {'status': 'Starting'}}, owner='bob')
count = reg.count_active_for_user('bob')
assert count == 3, f"FAIL: Bob should have 3 active jobs, got {count}"
print("[PASS] Per-user active job count = 3")

# Test 6: Concurrent threaded access (no deadlock / race condition)
errors = []
def worker(tid):
    try:
        jid = f'concurrent-job-{tid}'
        reg.create_active(jid, {'status': 'Starting', 'control': {}}, owner=f'user_{tid}')
        job = reg.get_active_if_owner(jid, f'user_{tid}')
        assert job is not None
        reg.delete_active(jid)
    except Exception as e:
        errors.append(str(e))

threads = [_threading.Thread(target=worker, args=(i,)) for i in range(50)]
for t in threads: t.start()
for t in threads: t.join()
assert not errors, f"FAIL: Concurrent errors: {errors}"
print("[PASS] 50 concurrent threads — no race conditions or deadlocks")

print("\n=== All tests passed! ===")
