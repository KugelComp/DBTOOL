import os
import django
import uuid
from typing import Dict

# Ensure Django is setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_admin.settings')
django.setup()

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.hashers import check_password

# USERS_FILE is likely deprecated but kept for compatibility logic if needed
USERS_FILE = os.path.join(os.path.dirname(__file__), "users.json")
SESSION_TIMEOUT_HOURS = 24


def load_users() -> Dict:
    """
    Load users from Django DB.
    Returns format expected by existing app logic: {username: {created_at, ...}}
    """
    User = get_user_model()
    users = {}
    for u in User.objects.all():
        users[u.username] = {
            "created_at": str(u.date_joined),
            "is_superuser": u.is_superuser
        }
    return users


def authenticate_user(username: str, password: str) -> bool:
    """Authenticate a user against Django DB"""
    User = get_user_model()
    try:
        user = User.objects.get(username=username)
        # We manually check password to avoid Django session creation overhead here
        # or use authenticate() if we wanted full Django session integration
        return user.check_password(password)
    except User.DoesNotExist:
        return False



def generate_session_token() -> str:
    """Generate a random session token"""
    return uuid.uuid4().hex

# The following functions (add_user, remove_user, etc.) are now handled by Django Admin
# But we keep them as wrappers or no-ops to prevent import errors if used elsewhere
# Or ideally, redirect them to Django ORM.

def add_user(username: str, password: str) -> bool:
    """Add a new user via Django ORM"""
    User = get_user_model()
    if User.objects.filter(username=username).exists():
        return False
    User.objects.create_user(username=username, password=password)
    return True

def remove_user(username: str) -> bool:
    """Remove a user via Django ORM"""
    User = get_user_model()
    try:
        user = User.objects.get(username=username)
        user.delete()
        return True
    except User.DoesNotExist:
        return False

def change_password(username: str, new_password: str) -> bool:
    """Change password via Django ORM"""
    User = get_user_model()
    try:
        user = User.objects.get(username=username)
        user.set_password(new_password)
        user.save()
        return True
    except User.DoesNotExist:
        return False
