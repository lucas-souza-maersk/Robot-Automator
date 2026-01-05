import sqlite3
import os
from auth_utils import get_password_hash

DB_FILE = "users.db"

def init_user_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            hashed_password TEXT,
            role TEXT,
            full_name TEXT
        )
    ''')
    conn.commit()
    conn.close()
    create_default_admin()

def get_user(username: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT username, hashed_password, role, full_name FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"username": row[0], "hashed_password": row[1], "role": row[2], "full_name": row[3]}
    return None

def get_all_users():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT username, role, full_name FROM users")
    rows = cursor.fetchall()
    conn.close()
    return [{"username": r[0], "role": r[1], "full_name": r[2]} for r in rows]

def create_user(username, password, role="viewer", full_name=""):
    if get_user(username):
        return False
    hashed = get_password_hash(password)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (username, hashed_password, role, full_name) VALUES (?, ?, ?, ?)", 
                   (username, hashed, role, full_name))
    conn.commit()
    conn.close()
    return True

def delete_user(username):
    if username == "admin": return False # Protege o admin principal
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    return True

def create_default_admin():
    if not get_user("admin"):
        create_user("admin", "admin123", role="admin", full_name="System Administrator")
        print("Default admin created: user='admin', pass='admin123'")

if __name__ == "__main__":
    init_user_db()