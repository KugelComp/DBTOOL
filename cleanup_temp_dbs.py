"""Drops all leftover temp_ and backup_ databases left by previous obscure/clone runs."""
import mysql.connector
from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv(dotenv_path=Path(__file__).parent / ".env")
host = os.environ.get("DEFAULT_TARGET_HOST", "localhost")
user = os.environ.get("DEFAULT_TARGET_USER", "root")
pw   = os.environ.get("DEFAULT_TARGET_PASSWORD", "")

conn = mysql.connector.connect(host=host, user=user, password=pw)
c = conn.cursor()
c.execute("SHOW DATABASES")
dbs = [row[0] for row in c.fetchall()]
temp_dbs = [db for db in dbs if db.startswith("temp_") or db.startswith("backup_")]

if not temp_dbs:
    print("No leftover temp/backup DBs found — all clean.")
else:
    for db in temp_dbs:
        print(f"Dropping: {db}")
        c.execute(f"DROP DATABASE IF EXISTS `{db}`")
        conn.commit()
        print(f"  -> DROPPED")

conn.close()
print("Done.")
