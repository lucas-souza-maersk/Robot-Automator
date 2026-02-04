import sqlite3
import logging
import os
from datetime import datetime

# --- CONFIGURAÇÃO DE TIMEOUT E MODO WAL ---
TIMEOUT_SEC = 30 

def get_db_connection(db_path):
    conn = sqlite3.connect(db_path, timeout=TIMEOUT_SEC)
    conn.execute("PRAGMA journal_mode=WAL;") 
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def initialize_database(db_path):
    try:
        db_dir = os.path.dirname(db_path)
        if db_dir: os.makedirs(db_dir, exist_ok=True)

        conn = get_db_connection(db_path)
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
                last_auto_resend TIMESTAMP,
                event_date TIMESTAMP  -- NOVA COLUNA: Data extraída do conteúdo do EDI
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

        # Migrations
        migrations = [
            "ALTER TABLE queue ADD COLUMN original_path TEXT",
            "ALTER TABLE queue ADD COLUMN last_auto_resend TIMESTAMP",
            "ALTER TABLE queue ADD COLUMN event_date TIMESTAMP" # Migration da nova coluna
        ]
        
        for mig in migrations:
            try: cursor.execute(mig)
            except sqlite3.OperationalError: pass

        # Índices
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_added_at ON queue(added_at)",
            "CREATE INDEX IF NOT EXISTS idx_event_date ON queue(event_date)", # Índice para filtrar rápido!
            "CREATE INDEX IF NOT EXISTS idx_status ON queue(status)",
            "CREATE INDEX IF NOT EXISTS idx_file_path ON queue(file_path)",
            "CREATE INDEX IF NOT EXISTS idx_container_queue ON container_index(queue_id)",
            "CREATE INDEX IF NOT EXISTS idx_container_number ON container_index(container_number)"
        ]
        
        for idx in indices:
            cursor.execute(idx)

        conn.commit()
    except Exception as e:
        logging.error(f"Failed to initialize database '{db_path}': {e}")
    finally:
        if conn: conn.close()

def get_known_filepaths(db_path):
    if not os.path.exists(db_path): return set()
    conn = None
    try:
        conn = get_db_connection(db_path)
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
        conn = get_db_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM queue WHERE file_hash = ? AND status IN ('sent', 'duplicate', 'monitored')", (file_hash,))
        return cursor.fetchone() is not None
    except: return False
    finally: 
        if conn: conn.close()

# ATUALIZADO: Recebe event_date opcional
def add_file_to_queue(db_path, file_path, status='pending', original_path=None, event_date=None):
    conn = None
    try:
        conn = get_db_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO queue (file_path, status, original_path, event_date) VALUES (?, ?, ?, ?)",
            (file_path, status, original_path, event_date)
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
        conn = get_db_connection(db_path)
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
        conn = get_db_connection(db_path)
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
    if not os.path.exists(db_path): return []
    conn = None
    try:
        conn = get_db_connection(db_path)
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
        conn = get_db_connection(db_path)
        cursor = conn.cursor()
        for status in stats.keys():
            cursor.execute(f"SELECT COUNT(*) FROM queue WHERE status = ?", (status,))
            res = cursor.fetchone()
            if res: stats[status] = res[0]
        return stats
    except: return stats
    finally: 
        if conn: conn.close()

# ATUALIZADO: Filtro de datas agora busca em event_date (se existir) OU added_at
def get_all_queue_items(db_path, container_filter=None, date_start=None, date_end=None, limit=100):
    if not os.path.exists(db_path): return []
    conn = None
    try:
        conn = get_db_connection(db_path)
        cursor = conn.cursor()
        
        # event_date é o index 9
        query = '''
            SELECT q.id, q.status, q.retry_count, q.file_path, q.file_hash, q.added_at, q.processed_at, q.original_path,
            COALESCE((SELECT GROUP_CONCAT(container_number, ', ') FROM container_index WHERE queue_id = q.id), 'NOT EDI') as units,
            q.event_date
            FROM queue q
        '''
        
        params = []
        where_clauses = []
        joins = []

        if container_filter:
            if isinstance(container_filter, list) and len(container_filter) > 0:
                joins.append("JOIN container_index ci ON q.id = ci.queue_id")
                placeholders = ','.join('?' for _ in container_filter)
                where_clauses.append(f"ci.container_number IN ({placeholders})")
                params.extend(container_filter)
            elif isinstance(container_filter, str):
                joins.append("JOIN container_index ci ON q.id = ci.queue_id")
                where_clauses.append("ci.container_number LIKE ?")
                params.append(f"%{container_filter}%")

        # LOGICA DO FILTRO DE DATA
        # Se tiver event_date, usa ele. Se não, fallback para added_at (comentado abaixo, vamos focar no event_date se o usuário quer "Data Real")
        # Mas como vamos preencher o event_date, vamos usar COALESCE pra garantir
        
        date_col = "COALESCE(q.event_date, q.added_at)" 
        # Ou se você quiser forçar filtrar SÓ pela data real quando ela existe:
        # date_col = "q.event_date" (mas aí arquivos sem data somem)
        
        if date_start:
            where_clauses.append(f"{date_col} >= ?")
            params.append(f"{date_start} 00:00:00")
        
        if date_end:
            where_clauses.append(f"{date_col} <= ?")
            params.append(f"{date_end} 23:59:59")

        if joins:
            query += " " + " ".join(joins)

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        
        if joins:
            query = query.replace("SELECT", "SELECT DISTINCT", 1)

        # Ordenar pela data do evento é o mais lógico agora
        query += f" ORDER BY {date_col} DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        return cursor.fetchall()
    except Exception as e:
        logging.error(f"Error fetching queue items: {e}")
        return []
    finally: 
        if conn: conn.close()

def force_resend_items(db_path, item_ids):
    if not item_ids or not os.path.exists(db_path): return
    conn = None
    try:
        conn = get_db_connection(db_path)
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
        conn = get_db_connection(db_path)
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
        conn = get_db_connection(db_path)
        cursor = conn.cursor()
        # Adicionado event_date no final
        cursor.execute("SELECT id, status, retry_count, file_path, file_hash, added_at, processed_at, original_path, last_auto_resend, event_date FROM queue WHERE id = ?", (file_id,))
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
                "event_date": row[9],
                "units": units
            }
        return None
    except: return None
    finally: 
        if conn: conn.close()