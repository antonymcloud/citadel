#!/usr/bin/env python3
import sqlite3
from datetime import datetime

# Connect to the database
conn = sqlite3.connect('instance/towerofborg.db')
cursor = conn.cursor()

# Create the source table
cursor.execute('''
CREATE TABLE IF NOT EXISTS source (
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

# Add the source_id column to the job table
try:
    cursor.execute('ALTER TABLE job ADD COLUMN source_id INTEGER')
    cursor.execute('ALTER TABLE job ADD FOREIGN KEY (source_id) REFERENCES source (id)')
except sqlite3.OperationalError:
    # Column might already exist
    pass

print("Database schema updated successfully")

# Commit the changes
conn.commit()
conn.close()
