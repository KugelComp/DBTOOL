import sqlite3
import json

conn = sqlite3.connect('db.sqlite3')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute('SELECT * FROM accounts_operationrequest ORDER BY id DESC LIMIT 5')
rows = cur.fetchall()
for row in rows:
    print(f"ID: {row['id']} | Status: {row['status']}")
    print(f"Error Message: {row['error_message']}")
