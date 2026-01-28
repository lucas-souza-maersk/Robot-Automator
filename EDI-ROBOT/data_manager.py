import sqlite3
import logging
import os
from datetime import datetime

def initialize_database(db_path):
    try:
        db_dir = os.path.dirname(db_path)
        if db_dir: os.makedirs(db_dir, exist_ok=True)

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
                original_path TEXT,
                last_auto_resend TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS container_index (
                id INTEGER PRIMARY KEY,
                queue_id INTEGER,
                container_number TEXT,
                FOREIGN KEY (queue_id) REFERENCES queue (id)
            )
        ''')

        try: cursor.execute("ALTER TABLE queue ADD COLUMN original_path TEXT")
        except sqlite3.OperationalError: pass
        
        try: cursor.execute("ALTER TABLE queue ADD COLUMN last_auto_resend TIMESTAMP")
        except sqlite3.OperationalError: pass

        conn.commit()
    except Exception as e:
        logging.error(f"Failed to initialize database '{db_path}': {e}")
    finally:
        if conn: conn.close()

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
    except: return set()
    
    finally: 
        if conn: conn.close()

def hash_exists(db_path, file_hash):
    if not os.path.exists(db_path): return False
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM queue WHERE file_hash = ? AND status IN ('sent', 'duplicate', 'monitored')", (file_hash,))
        return cursor.fetchone() is not None
    except: return False
    
    finally: 
        if conn: conn.close()

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
        logging.error(f"DB Error adding file: {e}")
    finally: 
        if conn: conn.close()

def get_pending_files(db_path, limit=10):
    if not os.path.exists(db_path): return []
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, file_path, retry_count, original_path FROM queue WHERE status = 'pending' AND retry_count < 5 ORDER BY added_at ASC LIMIT ?", (limit,))
        return cursor.fetchall()
    except: return []
    finally: 
        if conn: conn.close()

def update_file_status(db_path, file_id, new_status, increment_retry=False, file_hash=None, update_resend_time=False):
    if not os.path.exists(db_path): return
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        updates = ["status = ?"]
        params = [new_status]
        
        if new_status in ['sent', 'monitored']:
            updates.append("processed_at = CURRENT_TIMESTAMP")
        
        if file_hash:
            updates.append("file_hash = ?")
            params.append(file_hash)
            
        if increment_retry:
            updates.append("retry_count = retry_count + 1")
            
        if update_resend_time:
            updates.append("last_auto_resend = CURRENT_TIMESTAMP")

        params.append(file_id)
        
        query = f"UPDATE queue SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, params)
        conn.commit()
    except Exception as e:
        logging.error(f"DB Update Error: {e}")
    finally: 
        if conn: conn.close()

def get_files_for_auto_resend(db_path, interval_minutes):
    """Busca arquivos elegíveis para reenvio automático."""
    if not os.path.exists(db_path): return []
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        query = f'''
            SELECT id, file_path, original_path, status 
            FROM queue 
            WHERE status IN ('sent', 'monitored')
            AND (
                last_auto_resend IS NULL 
                OR 
                (strftime('%s', 'now') - strftime('%s', last_auto_resend)) / 60 >= ?
            )
            AND (
                (strftime('%s', 'now') - strftime('%s', processed_at)) / 60 >= ?
            )
        '''
        cursor.execute(query, (interval_minutes, interval_minutes))
        return cursor.fetchall()
    except: return []
    finally: 
        if conn: conn.close()

def get_queue_stats(db_path):
    stats = {'pending': 0, 'sent': 0, 'failed': 0, 'duplicate': 0, 'monitored': 0}
    if not os.path.exists(db_path): return stats
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for status in stats.keys():
            cursor.execute(f"SELECT COUNT(*) FROM queue WHERE status = ?", (status,))
            res = cursor.fetchone()
            if res: stats[status] = res[0]
        return stats
    except: return stats
    finally: 
        if conn: conn.close()

def get_all_queue_items(db_path, container_filter=None):
    if not os.path.exists(db_path): return []
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        query = '''
            SELECT q.id, q.status, q.retry_count, q.file_path, q.file_hash, q.added_at, q.processed_at, q.original_path,
            COALESCE((SELECT GROUP_CONCAT(container_number, ', ') FROM container_index WHERE queue_id = q.id), 'NOT EDI') as units
            FROM queue q
        '''
        
        if container_filter:
            query += " JOIN container_index ci ON q.id = ci.queue_id WHERE ci.container_number LIKE ?"
            cursor.execute(query + " ORDER BY q.added_at DESC", (f"%{container_filter}%",))
        else:
            cursor.execute(query + " ORDER BY q.added_at DESC")
            
        return cursor.fetchall()
    except: return []
    finally: 
        if conn: conn.close()

def force_resend_items(db_path, item_ids):
    if not item_ids or not os.path.exists(db_path): return
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        placeholders = ','.join('?' for _ in item_ids)
        query = f"UPDATE queue SET status = 'pending', retry_count = -1, file_hash = NULL WHERE id IN ({placeholders})"
        cursor.execute(query, item_ids)
        conn.commit()
    except: pass
    
    finally: 
        if conn: conn.close()

def add_containers_to_index(db_path, queue_id, container_list):
    if not container_list: return
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        data = [(queue_id, c) for c in set(container_list)]
        cursor.executemany("INSERT INTO container_index (queue_id, container_number) VALUES (?, ?)", data)
        conn.commit()
    except: pass
    finally: 
        if conn: conn.close()

def get_file_details(db_path, file_id):
    if not os.path.exists(db_path): return None
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, status, retry_count, file_path, file_hash, added_at, processed_at, original_path, last_auto_resend FROM queue WHERE id = ?", (file_id,))
        row = cursor.fetchone()
        
        units = "N/A"
        try:
            cursor.execute("SELECT GROUP_CONCAT(container_number, ', ') FROM container_index WHERE queue_id = ?", (file_id,))
            u_row = cursor.fetchone()
            if u_row and u_row[0]: units = u_row[0]
        except: pass

        if row:
            return {
                "id": row[0],
                "status": row[1],
                "retries": row[2],
                "file_path": row[3],
                "hash": row[4],
                "added_at": row[5],
                "processed_at": row[6],
                "original_path": row[7],
                "last_resend": row[8],
                "units": units
            }
        return None
    except: return None
    finally: 
        if conn: conn.close()