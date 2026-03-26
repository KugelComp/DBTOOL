import os
import django
from asgiref.sync import sync_to_async

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_admin.settings')
django.setup()

from accounts.models import ProductionDatabase

def check():
    if ProductionDatabase.objects.filter(host="20.40.56.140", name="*").exists():
        print("FOUND")
    else:
        print("MISSING")

if __name__ == "__main__":
    check()
