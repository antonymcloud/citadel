"""Migration script to add email, created_at and preferences to User model."""

import sys
import os
import sqlite3
from datetime import datetime

# Add the parent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def migrate():
    """Add email, created_at and preferences_json columns to User model."""
    # Get the database path
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'instance', 'citadel.db'))
    
    if not os.path.exists(db_path):
        print(f"Database file not found at {db_path}")
        sys.exit(1)
    
    print(f"Using database at {db_path}")
    
    # Connect directly to the SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Start a transaction
        conn.execute('BEGIN TRANSACTION')
        
        # Get the list of columns in the user table
        cursor.execute("PRAGMA table_info(user)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        # Add email column if it doesn't exist
        if 'email' not in column_names:
            print("Adding email column to User model...")
            cursor.execute('ALTER TABLE user ADD COLUMN email TEXT')
        
        # Add created_at column if it doesn't exist
        if 'created_at' not in column_names:
            print("Adding created_at column to User model...")
            cursor.execute('ALTER TABLE user ADD COLUMN created_at TIMESTAMP')
            
            # Set default value for existing users
            now = datetime.utcnow().isoformat()
            print(f"Setting default created_at ({now}) for existing users...")
            cursor.execute("UPDATE user SET created_at = ?", (now,))
        
        # Add preferences_json column if it doesn't exist
        if 'preferences_json' not in column_names:
            print("Adding preferences_json column to User model...")
            cursor.execute('ALTER TABLE user ADD COLUMN preferences_json TEXT')
        
        # Commit the transaction
        conn.commit()
        print("Migration completed successfully!")
        
    except Exception as e:
        # Rollback the transaction in case of error
        conn.rollback()
        print(f"Error during migration: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
