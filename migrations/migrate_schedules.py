#!/usr/bin/env python3
import sqlite3
import os

print("Starting database migration for schedules...")

# Connect to the database
db_path = 'instance/towerofborg.db'
if not os.path.exists(db_path):
    print(f"Database file {db_path} not found!")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check if schedule table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schedule'")
if not cursor.fetchone():
    print("Creating schedule table...")
    cursor.execute('''
    CREATE TABLE schedule (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        repository_id INTEGER NOT NULL,
        source_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        archive_prefix TEXT,
        frequency TEXT NOT NULL,
        hour INTEGER DEFAULT 0,
        minute INTEGER DEFAULT 0,
        day_of_week TEXT,
        day_of_month INTEGER,
        keep_daily INTEGER DEFAULT 7,
        keep_weekly INTEGER DEFAULT 4,
        keep_monthly INTEGER DEFAULT 6,
        auto_prune BOOLEAN DEFAULT 1,
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_run TIMESTAMP,
        next_run TIMESTAMP,
        FOREIGN KEY (repository_id) REFERENCES repository (id),
        FOREIGN KEY (source_id) REFERENCES source (id),
        FOREIGN KEY (user_id) REFERENCES user (id)
    )
    ''')
    print("Schedule table created successfully.")
else:
    print("Schedule table already exists.")

# Check if schedule_job table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schedule_job'")
if not cursor.fetchone():
    print("Creating schedule_job table...")
    cursor.execute('''
    CREATE TABLE schedule_job (
        schedule_id INTEGER NOT NULL,
        job_id INTEGER NOT NULL,
        PRIMARY KEY (schedule_id, job_id),
        FOREIGN KEY (schedule_id) REFERENCES schedule (id),
        FOREIGN KEY (job_id) REFERENCES job (id)
    )
    ''')
    print("Schedule_job table created successfully.")
else:
    print("Schedule_job table already exists.")

# Commit the changes
conn.commit()
conn.close()

print("Database migration completed successfully!")
