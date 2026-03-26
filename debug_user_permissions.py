import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_admin.settings')
django.setup()

from django.contrib.auth.models import User
from accounts.models import UserHierarchy

username = "ayush"

try:
    user = User.objects.get(username=username)
    print(f"User: {user.username}")
    print(f"Django is_superuser: {user.is_superuser}")
    print(f"Django is_staff: {user.is_staff}")
    
    try:
        hierarchy = user.hierarchy
        print(f"UserHierarchy Role: {hierarchy.role}")
        print(f"UserHierarchy Group: {hierarchy.group}")
        print(f"UserHierarchy.is_superuser(): {hierarchy.is_superuser()}")
    except UserHierarchy.DoesNotExist:
        print("UserHierarchy: MISSING")
        
except User.DoesNotExist:
    print(f"User '{username}' does not exist.")
