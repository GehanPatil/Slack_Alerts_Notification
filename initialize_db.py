import sqlite3

def create_db():
    conn = sqlite3.connect('alerts.db')  # Connect to SQLite database
    cursor = conn.cursor()

    # Create the alerts table with the trigger_function column
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            frequency TEXT NOT NULL,
            time TEXT NOT NULL,
            days TEXT,
            date TEXT,
            user_id TEXT,
            email TEXT,
            recurring BOOLEAN NOT NULL,
            trigger_function TEXT NOT NULL -- Store selected trigger function
        )
    ''')

    conn.commit()
    conn.close()
    print("Database and table created successfully!")

if __name__ == "__main__":
    create_db()
