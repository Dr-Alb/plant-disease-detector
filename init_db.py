import sqlite3

# Connect to SQLite DB
with sqlite3.connect("database.db") as conn:
    cursor = conn.cursor()

    # Create users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        email TEXT UNIQUE,
        phone_number TEXT,
        password TEXT
    )
    """)

    # Create scans table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        image_path TEXT,
        result TEXT,
        solution TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Create alerts table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        scheduled_time TEXT,
        is_sent INTEGER DEFAULT 0
    )
    """)

    conn.commit()

print("✅ Database initialized successfully.")
