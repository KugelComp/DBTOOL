import os
import django
from django.db.models import Count

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_admin.settings')
django.setup()

from accounts.models import ProductionDatabase

def deduplicate():
    print("--- Deduplicating ProductionDatabase Entries ---")
    
    # 1. Identify duplicates based on Host and Port
    duplicates = (
        ProductionDatabase.objects.values('host', 'port')
        .annotate(count=Count('id'))
        .filter(count__gt=1)
    )
    
    if not duplicates:
        print("No duplicates found. Safe to migrate.")
        return

    print(f"Found {duplicates.count()} host(s) with multiple entries.")
    
    for item in duplicates:
        host = item['host']
        port = item['port']
        print(f"\nProcessing Host: {host}:{port}")
        
        entries = ProductionDatabase.objects.filter(host=host, port=port)
        
        # Check if ANY are marked as production
        is_prod = entries.filter(is_production=True).exists()
        
        # We will keep the first one and update its status
        keep = entries.first()
        to_delete = entries.exclude(id=keep.id)
        
        count_deleted = to_delete.count()
        to_delete.delete()
        
        # Update the kept entry to be True if any were True
        if is_prod:
            keep.is_production = True
            keep.save()
            print(f"  - Consolidated to single entry (PROD). Deleted {count_deleted} others.")
        else:
            print(f"  - Consolidated to single entry (NON-PROD). Deleted {count_deleted} others.")

if __name__ == "__main__":
    deduplicate()
