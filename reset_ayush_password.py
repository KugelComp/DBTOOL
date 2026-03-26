import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_admin.settings')
django.setup()

from django.contrib.auth.models import User

username = "ayush"
new_password = "ayush-password"

try:
    user = User.objects.get(username=username)
    user.set_password(new_password)
    user.save()
    print(f"SUCCESS: Password for '{username}' has been reset to: {new_password}")
    print(f"You can now log in to /admin with username: {username}")
except User.DoesNotExist:
    print(f"User '{username}' does not exist.")
except Exception as e:
    print(f"Error: {e}")
