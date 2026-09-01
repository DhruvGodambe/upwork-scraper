import os
import sqlite3


def connect_to_db(database_name="upwork_jobs.db"):
    # Get the full path to the database file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)  # Get the parent directory
    database_path = (
        database_name
        if os.path.isabs(str(database_name))
        else os.path.join(parent_dir, str(database_name))
    )
    # Connect to database
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()
    return conn, cursor


def create_db(conn, cursor):
    # Create the `jobs` table (if it doesn't exist)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            job_url TEXT,
            job_title TEXT NOT NULL,
            posted_date DATETIME,
            job_description TEXT NOT NULL,
            job_tags TEXT,
            job_proposals TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
