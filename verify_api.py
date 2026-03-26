import os
import django
import asyncio

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_admin.settings")
django.setup()

from asgiref.sync import sync_to_async
from accounts.models import ProductionDatabase
from app import get_databases, app
from request_models import ConnectRequest
from fastapi import Request

class MockRequest:
    def __init__(self):
        self.session = {'username': 'test_admin'}
        self.client = type('Client', (object,), {'host': '127.0.0.1'})()

@sync_to_async
def setup_db():
    prod_db, created = ProductionDatabase.objects.get_or_create(
        host="test.prod.host",
        port=3306,
        defaults={
            'is_production': True,
            'hardcoded_dbs': 'db_prod_1, db_prod_2'
        }
    )
    if not created:
        prod_db.is_production = True
        prod_db.hardcoded_dbs = 'db_prod_1, db_prod_2'
        prod_db.save()
    return prod_db

@sync_to_async
def teardown_db(prod_db):
    prod_db.delete()

async def test_get_databases():
    print("--- Setting up test data ---")
    prod_db = await setup_db()

    print("--- Triggering get_databases ---")
    request = MockRequest()
    body = ConnectRequest(
        host="test.prod.host",
        port=3306,
        user="root",
        password=""    # intentionally empty
    )
    
    response = await get_databases(body, request)
    print("Response:", response)
    
    assert response.get("success") is True, f"Failed: {response}"
    assert response.get("databases") == ['db_prod_1', 'db_prod_2'], f"Wrong DBs: {response}"
    assert 'cred_token' in request.session, "No cred_token in session"
    
    print("--- Test Passed ---")

    await teardown_db(prod_db)

if __name__ == "__main__":
    asyncio.run(test_get_databases())
