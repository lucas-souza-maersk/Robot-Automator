import sqlite3
import logging
import os

def initialize_database(db_path):
    """Inicializa um ficheiro de banco de dados no caminho especificado."""
    try:
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # --- CORREÇÃO CRÍTICA AQUI ---
        # A query CREATE TABLE que estava em falta foi restaurada.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS queue (
                id INTEGER PRIMARY KEY,
                file_path TEXT UNIQUE,
                status TEXT DEFAULT 'pending',
                retry_count INTEGER DEFAULT 0,
                file_hash TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP
            )
        ''')
        # --- FIM DA CORREÇÃO ---

        conn.commit()
        logging.info(f"Banco de dados '{os.path.basename(db_path)}' verificado com sucesso.")
    except Exception as e:
        logging.error(f"Falha na inicialização do banco de dados '{db_path}': {e}")
    finally:
        if conn:
            conn.close()

def get_known_filepaths(db_path):
    """Retorna um conjunto (set) de todos os file_path já registados no banco especificado."""
    if not os.path.exists(db_path): return set()
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT file_path FROM queue")
        return {row[0] for row in cursor.fetchall()}
    except Exception as e:
        if "no such table" in str(e): return set()
        logging.error(f"Falha ao buscar caminhos de arquivos conhecidos de '{db_path}': {e}")
        return set()
    finally:
        if conn:
            conn.close()

def hash_exists(db_path, file_hash):
    """Verifica se um hash já existe na tabela com um status que impede reprocessamento."""
    if not os.path.exists(db_path): return False
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM queue WHERE file_hash = ? AND status IN ('sent', 'duplicate', 'ignored')", (file_hash,))
        return cursor.fetchone() is not None
    except Exception as e:
        if "no such table" in str(e): return False
        logging.error(f"Falha ao verificar se o hash '{file_hash}' existe em '{db_path}': {e}")
        return True
    finally:
        if conn:
            conn.close()

def add_file_to_queue(db_path, file_path, status='pending'):
    """Adiciona um ficheiro à fila no banco de dados especificado."""
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO queue (file_path, status) VALUES (?, ?)", (file_path, status))
        conn.commit()
    except Exception as e:
        logging.error(f"Falha ao adicionar o ficheiro '{file_path}' à fila em '{db_path}': {e}")
    finally:
        if conn:
            conn.close()

def get_pending_files(db_path, limit=10):
    """Busca ficheiros pendentes do banco de dados de um perfil."""
    if not os.path.exists(db_path): return []
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, file_path, retry_count FROM queue WHERE status = 'pending' AND retry_count < 5 ORDER BY added_at ASC LIMIT ?", (limit,))
        return cursor.fetchall()
    except Exception as e:
        if "no such table" in str(e): return []
        logging.error(f"Falha ao buscar ficheiros pendentes de '{db_path}': {e}")
        return []
    finally:
        if conn:
            conn.close()

def update_file_status(db_path, file_id, new_status, increment_retry=False, file_hash=None):
    """Atualiza o status de um ficheiro no banco de dados de um perfil."""
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
        logging.error(f"Falha ao atualizar status para o ID {file_id} em '{db_path}': {e}")
    finally:
        if conn:
            conn.close()

def get_queue_stats(db_path):
    """Obtém as estatísticas da fila para um perfil específico."""
    stats = {'pending': 0, 'sent': 0, 'failed': 0, 'duplicate': 0, 'ignored': 0}
    if not os.path.exists(db_path): return stats
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for status in stats.keys():
            cursor.execute(f"SELECT COUNT(*) FROM queue WHERE status = '{status}'")
            count = cursor.fetchone()
            if count:
                stats[status] = count[0]
        return stats
    except Exception as e:
        if "no such table" in str(e): return stats
        logging.error(f"Falha ao obter estatísticas de '{db_path}': {e}")
        return stats
    finally:
        if conn:
            conn.close()

def get_all_queue_items(db_path):
    """Obtém todos os itens da fila de um perfil."""
    if not os.path.exists(db_path): return []
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, file_path, status, retry_count, added_at, processed_at, file_hash FROM queue ORDER BY added_at DESC")
        return cursor.fetchall()
    except Exception as e:
        if "no such table" in str(e): return []
        logging.error(f"Falha ao obter todos os itens de '{db_path}': {e}")
        return []
    finally:
        if conn:
            conn.close()

def reset_failed_items(db_path, item_ids):
    """Redefine o status de itens com falha para um perfil."""
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
        logging.error(f"Falha ao redefinir itens em '{db_path}': {e}")
    finally:
        if conn:
            conn.close()