import sqlite3
import logging
import os

def initialize_database(db_path):
    try:
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS queue (
                id INTEGER PRIMARY KEY,
                file_path TEXT UNIQUE,
                status TEXT DEFAULT 'pending',
                retry_count INTEGER DEFAULT 0,
                file_hash TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                original_path TEXT
            )
        ''')

        try:
            cursor.execute("ALTER TABLE queue ADD COLUMN original_path TEXT")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                raise

        conn.commit()
        logging.info(f"Database '{os.path.basename(db_path)}' successfully verified.")
    except Exception as e:
        logging.error(f"Failed to initialize database '{db_path}': {e}")
    finally:
        if conn:
            conn.close()

def get_known_filepaths(db_path):
    if not os.path.exists(db_path): return set()
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT file_path FROM queue WHERE file_path IS NOT NULL")
        paths = {row[0] for row in cursor.fetchall()}
        cursor.execute("SELECT original_path FROM queue WHERE original_path IS NOT NULL")
        paths.update(row[0] for row in cursor.fetchall())
        return paths
    except Exception as e:
        if "no such table" in str(e): return set()
        logging.error(f"Failed to fetch known file paths from '{db_path}': {e}")
        return set()
    finally:
        if conn:
            conn.close()

def hash_exists(db_path, file_hash):
    if not os.path.exists(db_path): return False
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM queue WHERE file_hash = ? AND status IN ('sent', 'duplicate', 'ignored')", (file_hash,))
        return cursor.fetchone() is not None
    except Exception as e:
        if "no such table" in str(e): return False
        logging.error(f"Failed to check if hash '{file_hash}' exists in '{db_path}': {e}")
        return True
    finally:
        if conn:
            conn.close()

def add_file_to_queue(db_path, file_path, status='pending', original_path=None):
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO queue (file_path, status, original_path) VALUES (?, ?, ?)",
            (file_path, status, original_path)
        )
        conn.commit()
    except Exception as e:
        logging.error(f"Failed to add file '{file_path}' to the queue in '{db_path}': {e}")
    finally:
        if conn:
            conn.close()

def get_pending_files(db_path, limit=10):
    if not os.path.exists(db_path): return []
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, file_path, retry_count FROM queue WHERE status = 'pending' AND retry_count < 5 ORDER BY added_at ASC LIMIT ?", (limit,))
        return cursor.fetchall()
    except Exception as e:
        if "no such table" in str(e): return []
        logging.error(f"Failed to fetch pending files from '{db_path}': {e}")
        return []
    finally:
        if conn:
            conn.close()

def update_file_status(db_path, file_id, new_status, increment_retry=False, file_hash=None):
    if not os.path.exists(db_path): return
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        if new_status == 'sent' and file_hash:
            cursor.execute("UPDATE queue SET status = ?, processed_at = CURRENT_TIMESTAMP, file_hash = ? WHERE id = ?", (new_status, file_hash, file_id))
        elif increment_retry:
            cursor.execute("UPDATE queue SET status = ?, processed_at = CURRENT_TIMESTAMP, retry_count = retry_count + 1 WHERE id = ?", (new_status, file_id))
        else:
            cursor.execute("UPDATE queue SET status = ?, processed_at = CURRENT_TIMESTAMP WHERE id = ?", (new_status, file_id))
        conn.commit()
    except Exception as e:
        logging.error(f"Failed to update status for ID {file_id} in '{db_path}': {e}")
    finally:
        if conn:
            conn.close()

def get_queue_stats(db_path):
    stats = {'pending': 0, 'sent': 0, 'failed': 0, 'duplicate': 0, 'ignored': 0}
    if not os.path.exists(db_path): return stats
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for status in stats.keys():
            cursor.execute(f"SELECT COUNT(*) FROM queue WHERE status = ?", (status,))
            count = cursor.fetchone()
            if count:
                stats[status] = count[0]
        return stats
    except Exception as e:
        if "no such table" in str(e): return stats
        logging.error(f"Failed to get statistics from '{db_path}': {e}")
        return stats
    finally:
        if conn:
            conn.close()

def get_all_queue_items(db_path):
    if not os.path.exists(db_path): return []
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, status, retry_count, file_path, file_hash, added_at, processed_at, original_path FROM queue ORDER BY added_at DESC")
        return cursor.fetchall()
    except Exception as e:
        if "no such table" in str(e): return []
        logging.error(f"Failed to get all items from '{db_path}': {e}")
        return []
    finally:
        if conn:
            conn.close()

def reset_failed_items(db_path, item_ids):
    if not item_ids or not os.path.exists(db_path): return
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        placeholders = ','.join('?' for _ in item_ids)
        query = f"UPDATE queue SET status = 'pending', retry_count = 0 WHERE id IN ({placeholders})"
        cursor.execute(query, item_ids)
        conn.commit()
    except Exception as e:
        logging.error(f"Failed to reset items in '{db_path}': {e}")
    finally:
        if conn:
            conn.close()