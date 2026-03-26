import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_admin.settings")
django.setup()

from accounts.models import DatabaseHost, ProductionDatabase

def run_tests():
    # 1. Create a DatabaseHost with a password
    test_ip = "192.168.99.99"
    host, _ = DatabaseHost.objects.get_or_create(
        label="test_host_wipe",
        ip=test_ip,
        port=3306,
        defaults={'db_password': 'secret_password_123', 'db_username': 'root'}
    )
    
    # Ensure it saved before test
    if not host.db_password:
        host.db_password = 'secret_password_123'
        host.save()
        
    host.refresh_from_db()
    print(f"Before creating ProdDB -> Password is: '{host.db_password}'")
    assert host.db_password == "secret_password_123", "Setup failed, password not saved."

    # 2. Add it to ProductionDatabase
    print("Creating ProductionDatabase record for this IP...")
    prod_db, _ = ProductionDatabase.objects.get_or_create(
        host=test_ip,
        port=3306,
        defaults={'is_production': True}
    )
    # Re-save to trigger the override in case it existed
    prod_db.is_production = True
    prod_db.save()

    # 3. Verify DatabaseHost password was wiped
    host.refresh_from_db()
    print(f"After creating ProdDB -> Password is: '{host.db_password}'")
    assert host.db_password == "", "Failed: DatabaseHost password was not wiped by ProductionDatabase save!"

    # 4. Attempt to save password back to DatabaseHost directly
    print("Attempting to explicitly update DatabaseHost with a new password...")
    host.db_password = "new_secret_password_456"
    host.save()

    host.refresh_from_db()
    print(f"After explicit save -> Password is: '{host.db_password}'")
    assert host.db_password == "", "Failed: DatabaseHost allowed saving a password for a Production IP!"

    print("--- All tests passed! ---")
    
    # Clean up
    host.delete()
    prod_db.delete()

if __name__ == "__main__":
    run_tests()
