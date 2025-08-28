#!/usr/bin/env python3
import sqlite3
import os

print("Starting database migration for sources...")

# Connect to the database
db_path = 'instance/citadel.db'
if not os.path.exists(db_path):
    print(f"Database file {db_path} not found!")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check if source table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='source'")
if not cursor.fetchone():
    print("Creating source table...")
    cursor.execute('''
    CREATE TABLE source (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        source_type TEXT NOT NULL,
        path TEXT NOT NULL,
        ssh_host TEXT,
        ssh_port INTEGER DEFAULT 22,
        ssh_user TEXT,
        ssh_key_path TEXT,
        user_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES user (id)
    )
    ''')
    print("Source table created successfully.")
else:
    print("Source table already exists.")

# Check if job table has source_id column
cursor.execute("PRAGMA table_info(job)")
columns = cursor.fetchall()
column_names = [column['name'] for column in columns]

if 'source_id' not in column_names:
    print("Adding source_id column to job table...")
    
    # SQLite doesn't support ALTER TABLE ADD COLUMN with foreign key constraints
    # So we need to recreate the table with the new schema
    
    # 1. Get current job table schema without the source_id column
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='job'")
    table_schema = cursor.fetchone()[0]
    
    # 2. Create a new temporary table with the old schema
    cursor.execute("CREATE TABLE job_backup AS SELECT * FROM job")
    
    # 3. Drop the old table
    cursor.execute("DROP TABLE job")
    
    # 4. Create a new job table with source_id column
    cursor.execute('''
    CREATE TABLE job (
        id INTEGER PRIMARY KEY,
        job_type TEXT NOT NULL,
        status TEXT NOT NULL,
        repository_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        archive_name TEXT,
        source_path TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        log_output TEXT,
        source_id INTEGER,
        FOREIGN KEY (repository_id) REFERENCES repository (id),
        FOREIGN KEY (user_id) REFERENCES user (id),
        FOREIGN KEY (source_id) REFERENCES source (id)
    )
    ''')
    
    # 5. Copy data from backup table to new table
    cursor.execute('''
    INSERT INTO job (id, job_type, status, repository_id, user_id, archive_name, source_path, timestamp, completed_at, log_output)
    SELECT id, job_type, status, repository_id, user_id, archive_name, source_path, timestamp, completed_at, log_output FROM job_backup
    ''')
    
    # 6. Drop the backup table
    cursor.execute("DROP TABLE job_backup")
    
    print("Migration completed: source_id column added to job table.")
else:
    print("source_id column already exists in job table.")

# Commit the changes
conn.commit()
conn.close()

print("Database migration completed successfully!")
