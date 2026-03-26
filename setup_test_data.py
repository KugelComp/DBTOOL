
import os
import django
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_admin.settings')
django.setup()

from django.contrib.auth.models import User
from accounts.models import UserHierarchy, Group, ProductionDatabase

def setup():
    print("Setting up test data...")
    
    # 1. Create Group
    group, _ = Group.objects.get_or_create(name="TestGroup")
    
    # 2. Create Admin User (testadmin)
    username = "testadmin"
    password = "testpassword123"
    
    if not User.objects.filter(username=username).exists():
        user = User.objects.create_user(username=username, password=password)
        print(f"Created user: {username}")
    else:
        user = User.objects.get(username=username)
        user.set_password(password)
        user.save()
        print(f"Updated user: {username}")
        
    # Set Hierarchy (ADMIN)
    # Check if hierarchy exists
    if hasattr(user, 'hierarchy'):
        h = user.hierarchy
        h.role = "ADMIN"
        h.group = group
        h.save()
    else:
        UserHierarchy.objects.create(user=user, role="ADMIN", group=group)
    print(f"User {username} set as ADMIN in {group.name}")

    # 3. Create Superuser (testsuper) - needed for prod approval tests if we want
    s_user, _ = User.objects.get_or_create(username="testsuper")
    s_user.set_password("superpass123")
    s_user.is_superuser = True
    s_user.save()
    if not hasattr(s_user, 'hierarchy'):
        UserHierarchy.objects.create(user=s_user, role="SUPERUSER")
    print("Ensured testsuper exists")

    # 4. Create Production Database Entry
    # Corresponds to db_test in config.py: "db_test": {"ip": "127.0.0.1", "port": 3306}
    # We will flag it as PRODUCTION for the test
    prod_db, created = ProductionDatabase.objects.get_or_create(
        host="127.0.0.1",
        port=3306,
        name="test_prod_db" 
    )
    prod_db.is_production = True # FORCE PROD
    prod_db.save()
    print(f"Production Database configured: {prod_db}")
    
    # 5. Non-Production Database Entry
    non_prod_db, _ = ProductionDatabase.objects.get_or_create(
        host="127.0.0.1",
        port=3306,
        name="test_non_prod_db"
    )
    non_prod_db.is_production = False
    non_prod_db.save()
    print(f"Non-Production Database configured: {non_prod_db}")

if __name__ == "__main__":
    setup()
