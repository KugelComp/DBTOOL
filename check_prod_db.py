import os
import django
from asgiref.sync import sync_to_async

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_admin.settings')
django.setup()

from accounts.models import ProductionDatabase

def check_entries():
    print("--- ProductionDatabase Entries ---")
    entries = ProductionDatabase.objects.all()
    found_wildcard = False
    for entry in entries:
        print(f"Host: {entry.host}, Port: {entry.port}, Name: {entry.name}, Prod: {entry.is_production}")
        if entry.host == "20.40.56.140" and entry.name == "*":
            found_wildcard = True

    if found_wildcard:
        print("\n[OK] Wildcard entry found for demo host (20.40.56.140).")
    else:
        print("\n[WARNING] Wildcard entry MISSING for demo host (20.40.56.140).")

if __name__ == "__main__":
    check_entries()
