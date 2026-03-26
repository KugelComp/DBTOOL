import os
import django
from asgiref.sync import sync_to_async

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_admin.settings')
django.setup()

from accounts.models import ProductionDatabase

def add_protection():
    host = "20.40.56.140"
    print(f"Adding Wildcard Protection for {host}...")
    
    # Check if exists
    if ProductionDatabase.objects.filter(host=host, name="*").exists():
        print("Already exists.")
        return

    ProductionDatabase.objects.create(
        host=host,
        port=3306,
        name="*",
        is_production=True
    )
    print("SUCCESS: Added wildcard protection entry.")

if __name__ == "__main__":
    add_protection()
