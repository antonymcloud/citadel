"""
Migration script to add job_metadata column to Job table.
This will be a JSON column to store additional job information like statistics.
"""
import sqlite3
import os
import json

# Get database path
db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance/towerofborg.db')

def migrate():
    # Check if database exists
    if not os.path.exists(db_path):
        print(f"Database file not found at {db_path}")
        print("The column will be added when the database is created.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check all tables first
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print(f"Available tables: {[t[0] for t in tables]}")
    
    # Look for a table name that matches our job model (it might be capitalized differently)
    job_table_name = None
    for table in tables:
        if table[0].lower() == 'job':
            job_table_name = table[0]
    
    if not job_table_name:
        print("Job table not found in the database.")
        print("The column will be added when the database is initialized.")
        conn.close()
        return
    
    # Check if job_metadata column already exists
    cursor.execute(f"PRAGMA table_info({job_table_name})")
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]
    
    if 'job_metadata' not in column_names:
        print(f"Adding job_metadata column to {job_table_name} table...")
        cursor.execute(f"ALTER TABLE {job_table_name} ADD COLUMN job_metadata TEXT")
        conn.commit()
        print("Done!")
    else:
        print("job_metadata column already exists in Job table.")
    
    conn.close()

if __name__ == "__main__":
    migrate()
