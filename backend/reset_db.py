#!/usr/bin/env python3
"""
reset_db.py — Wipe all nodes and sessions from the database.
Run from inside the backend folder:
  python reset_db.py
"""
import sqlite3, os, sys

DB_PATH = os.getenv("DATABASE_PATH", "./proofgraph.db")

if not os.path.exists(DB_PATH):
    print(f"No database at {DB_PATH} — nothing to reset.")
    sys.exit(0)

conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()

cur.execute("SELECT COUNT(*) FROM nodes");    n = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM sessions"); s = cur.fetchone()[0]
print(f"Database: {DB_PATH}")
print(f"  Nodes:    {n}")
print(f"  Sessions: {s}")
print()

choice = input("Wipe everything for a clean start? (yes/no): ").strip().lower()
if choice != "yes":
    print("Cancelled.")
    sys.exit(0)

cur.execute("DELETE FROM nodes")
cur.execute("DELETE FROM sessions")
cur.execute("DELETE FROM citations")
conn.commit()
conn.close()

print(f"✅ Database cleared. Restart the backend.")
