import os
import django
from asgiref.sync import sync_to_async

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_admin.settings')
django.setup()

from accounts.models import ProductionDatabase

def remove_wildcard():
    host = "20.40.56.140"
    print(f"Checking for wildcard protection on {host}...")
    
    entries = ProductionDatabase.objects.filter(host=host, name="*")
    count = entries.count()
    
    if count > 0:
        entries.delete()
        print(f"SUCCESS: Removed {count} wildcard entry/entries for {host}.")
        print("Exports from this host will no longer be globally blocked (unless specific DBs are listed).")
    else:
        print("No wildcard entry found.")

if __name__ == "__main__":
    remove_wildcard()
