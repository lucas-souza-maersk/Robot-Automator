import logging
import time
import os
import shutil
import hashlib
import fnmatch
import pysftp
import keyring
import re
from threading import Thread, Event
from datetime import datetime, date, timedelta

import data_manager
import logger_setup
import alert_manager
import edi_parser 

# --- FUNÇÃO AUXILIAR NOVA ---
def _extract_event_date(file_path):
    """
    Lê o arquivo, usa o EDI Parser para achar a data da transação
    e retorna no formato SQL (YYYY-MM-DD HH:MM:SS) ou None.
    """
    try:
        # Se arquivo vazio ou inexistente, aborta
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            return None

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            parser = edi_parser.EdiParser(content)
            
            # Pega a data da primeira transação encontrada
            if parser.transactions:
                raw_date = parser.transactions[0].get('date') # Ex: "28/01/2026 13:34"
                if raw_date:
                    try:
                        # Tenta converter o formato DD/MM/YYYY HH:MM para SQL
                        dt_obj = datetime.strptime(raw_date, '%d/%m/%Y %H:%M')
                        return dt_obj.strftime('%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        pass # Formato inesperado, retorna None
    except Exception:
        pass # Qualquer erro de leitura (permissão, encoding)
    return None

class BaseWatcher(Thread):
    def __init__(self, profile_config, stop_event, logger, alert_manager):
        super().__init__()
        self.config = profile_config
        self.stop_event = stop_event
        self.logger = logger
        self.alert_manager = alert_manager 
        self.daemon = True

    def run(self):
        raise NotImplementedError("Each watcher must implement its own run method.")

    def _get_date_limit(self):
        age_config = self.config['settings'].get('file_age', {})
        age_value = age_config.get('value', 0)
        age_unit = age_config.get('unit', 'Days')

        if age_unit == "No Limit":
            return None

        days_to_subtract = age_value
        if age_unit == "Months": days_to_subtract *= 30
        elif age_unit == "Years": days_to_subtract *= 365
        return date.today() - timedelta(days=days_to_subtract)

    def _get_scan_interval(self):
        interval_config = self.config['settings'].get('scan_interval', {})
        scan_value = interval_config.get('value', 5)
        scan_unit = interval_config.get('unit', 's')
        
        if scan_unit == 'min': return scan_value * 60
        if scan_unit == 'hr': return scan_value * 3600
        return scan_value

class BaseProcessor(Thread):
    def __init__(self, profile_config, stop_event, logger, alert_manager):
        super().__init__()
        self.config = profile_config
        self.stop_event = stop_event
        self.logger = logger
        self.alert_manager = alert_manager 
        self.daemon = True

    def run(self):
        db_path = self.config['settings']['db_path']
        self.logger.info("File processor started.")
        
        # Config Auto-Resend
        auto_resend = self.config.get("auto_resend", {})
        auto_resend_enabled = auto_resend.get("enabled", False)
        auto_resend_interval = auto_resend.get("interval_minutes", 60)
        last_auto_check = 0

        while not self.stop_event.is_set():
            try:
                # 1. Processa Pendentes
                pending_files = data_manager.get_pending_files(db_path)
                if pending_files:
                    for record_id, file_path, retry_count, original_path in pending_files:
                        if self.stop_event.is_set(): break
                        self._process_file(record_id, file_path, retry_count, original_path)
                
                # 2. Check Auto-Resend (Evita spam, roda a cada 1 minuto)
                if auto_resend_enabled and (time.time() - last_auto_check > 60):
                    self._check_auto_resend(db_path, int(auto_resend_interval))
                    last_auto_check = time.time()

                if not pending_files:
                    self.stop_event.wait(5)

            except Exception as e:
                self.logger.error(f"Critical error in processor loop: {e}", exc_info=True)
                self.stop_event.wait(10)
        self.logger.info("File processor stopped.")

    def _process_file(self, record_id, file_path, retry_count, original_path):
        raise NotImplementedError("Each processor must implement its own _process_file method.")

    def _check_auto_resend(self, db_path, interval):
        """Verifica arquivos antigos para reenviar."""
        try:
            resend_list = data_manager.get_files_for_auto_resend(db_path, interval)
            for item in resend_list:
                rid, fpath, opath, status = item
                # Reutiliza lógica de processamento, mas força modo sender
                self.logger.info(f"[AUTO-RESEND] Triggering resend for file ID {rid}")
                # Passa retry_count=-1 para forçar o envio (lógica do override)
                self._process_file(rid, fpath, -1, opath)
                
                # Atualiza timestamp para não reenviar imediatamente
                data_manager.update_file_status(db_path, rid, 'sent', update_resend_time=True)
        except Exception as e:
            self.logger.error(f"Auto-resend check failed: {e}")

    def _calculate_hash(self, file_path):
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except FileNotFoundError:
            return None

class LocalWatcher(BaseWatcher):
    def run(self):
        source_dir = self.config['source']['path']
        db_path = self.config['settings']['db_path']
        patterns = [p.strip() for p in self.config['settings']['file_format'].split(',') if p.strip()]
        date_limit = self._get_date_limit()
        scan_interval = self._get_scan_interval()

        self.logger.info(f"Local watcher started. Monitoring: {source_dir}")
        while not self.stop_event.is_set():
            try:
                if not os.path.isdir(source_dir):
                    self.logger.error(f"Source directory not found: {source_dir}. Pausing watcher.")
                    self.stop_event.wait(60)
                    continue

                known_files = data_manager.get_known_filepaths(db_path)
                with os.scandir(source_dir) as entries:
                    for entry in entries:
                        if not entry.is_file() or entry.path in known_files:
                            continue
                        if not any(fnmatch.fnmatch(entry.name, pattern) for pattern in patterns):
                            continue
                        
                        mod_date = date.fromtimestamp(entry.stat().st_mtime)
                        if date_limit is None or mod_date >= date_limit:
                            
                            # AQUI A MUDANÇA: Lê a data do evento antes de salvar
                            event_date = _extract_event_date(entry.path)

                            data_manager.add_file_to_queue(
                                db_path, 
                                entry.path, 
                                status='pending', 
                                original_path=entry.path,
                                event_date=event_date # Passa a data extraída
                            )
                            self.logger.info(f"New file '{entry.name}' added to queue.")
            except Exception as e:
                self.logger.error(f"Error in local watcher: {e}", exc_info=True)

            self.stop_event.wait(scan_interval)
        self.logger.info("Local watcher stopped.")

class SftpWatcher(BaseWatcher):
    def run(self):
        source_cfg = self.config['source']
        db_path = self.config['settings']['db_path']
        patterns = [p.strip() for p in self.config['settings']['file_format'].split(',') if p.strip()]
        date_limit = self._get_date_limit()
        scan_interval = self._get_scan_interval()
        
        host = source_cfg.get('host')
        username = source_cfg.get('username')
        remote_path = source_cfg.get('remote_path', '/')
        local_download_path = os.path.join(os.getcwd(), "sftp_downloads", self.config['name'])
        os.makedirs(local_download_path, exist_ok=True)

        self.logger.info(f"SFTP watcher started for {username}@{host}:{remote_path}")

        while not self.stop_event.is_set():
            try:
                password = keyring.get_password(f"robot_automator::{host}", username)
                if not password:
                    raise ValueError(f"Password for {username}@{host} not found in keyring.")

                cnopts = pysftp.CnOpts()
                cnopts.hostkeys = None

                with pysftp.Connection(host, username=username, password=password, port=source_cfg.get('port', 22), cnopts=cnopts) as sftp:
                    sftp.cwd(remote_path)
                    known_files = data_manager.get_known_filepaths(db_path)

                    for attr in sftp.listdir_attr():
                        remote_filepath = f"{remote_path}/{attr.filename}".replace("//", "/")
                        if not sftp.isfile(attr.filename) or remote_filepath in known_files:
                            continue
                        if not any(fnmatch.fnmatch(attr.filename, p) for p in patterns):
                            continue
                            
                        mod_date = date.fromtimestamp(attr.st_mtime)
                        if date_limit is None or mod_date >= date_limit:
                            local_dest_path = os.path.join(local_download_path, attr.filename)
                            self.logger.info(f"Downloading new file: {attr.filename}")
                            sftp.get(attr.filename, local_dest_path)
                            
                            # AQUI A MUDANÇA: Lê a data do evento do arquivo baixado
                            event_date = _extract_event_date(local_dest_path)

                            data_manager.add_file_to_queue(
                                db_path, 
                                local_dest_path, 
                                status='pending', 
                                original_path=remote_filepath,
                                event_date=event_date # Passa a data extraída
                            )
                            self.logger.info(f"File '{attr.filename}' added to queue.")

            except Exception as e:
                self.logger.error(f"Error in SFTP watcher: {e}", exc_info=True)
                self.alert_manager.send(
                    "WARNING", 
                    f"SFTP Watcher Error - Profile: {self.config['name']}",
                    f"Error connecting or listing files at {username}@{host}. Error: {e}"
                )
            
            self.stop_event.wait(scan_interval)
        self.logger.info("SFTP watcher stopped.")

class FileProcessor(BaseProcessor):
    def _extract_and_index_containers(self, record_id, file_path):
        db_path = self.config['settings']['db_path']
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Usa o novo parser SMDG robusto
            parser = edi_parser.EdiParser(content)
            containers = [t.get('container') for t in parser.transactions if t.get('container')]
            
            if containers:
                data_manager.add_containers_to_index(db_path, record_id, containers)
                self.logger.info(f"Indexed {len(set(containers))} units for file ID {record_id}.")
        except Exception as e:
            self.logger.warning(f"Could not extract units from {file_path}: {e}")

    def _handle_backup(self, file_path):
        backup_cfg = self.config['settings'].get('backup', {})
        enabled = backup_cfg.get('enabled')
        path = backup_cfg.get('path')

        if enabled and path:
            try:
                backup_dir = path.strip().replace('"', '') 
                if not os.path.isdir(backup_dir):
                    os.makedirs(backup_dir, exist_ok=True)
                
                filename = os.path.basename(file_path)
                backup_dest = os.path.join(backup_dir, filename)
                
                # Só copia se não existir (evita IO desnecessário)
                if not os.path.exists(backup_dest):
                    shutil.copy2(file_path, backup_dest)
                    self.logger.info(f"Backup created: {filename}")
            except Exception as e:
                self.logger.warning(f"Failed to create backup for '{file_path}': {e}")

    def _resolve_missing_file(self, original_path, file_path):
        """Tenta encontrar o arquivo no Backup ou Destino se sumiu da origem."""
        filename = os.path.basename(original_path or file_path or "unknown")
        
        # 1. Tenta Backup
        backup_cfg = self.config['settings'].get('backup', {})
        if backup_cfg.get('enabled') and backup_cfg.get('path'):
            backup_path = os.path.join(backup_cfg['path'].strip().replace('"', ''), filename)
            if os.path.exists(backup_path):
                self.logger.info(f"Recovered missing file from backup: {backup_path}")
                return backup_path

        # 2. Tenta Destino Local (se aplicável)
        dest_cfg = self.config.get('destination', {})
        if dest_cfg.get('type') == 'local':
            dest_path = os.path.join(dest_cfg.get('path', ''), filename)
            if os.path.exists(dest_path):
                self.logger.info(f"Recovered missing file from destination: {dest_path}")
                return dest_path
        
        return None

    def _process_file(self, record_id, file_path, retry_count, original_path):
        db_path = self.config['settings']['db_path']
        action = self.config.get('action', 'copy')
        dest_cfg = self.config.get('destination', {})
        dest_type = dest_cfg.get('type', 'local')
        mode = self.config.get('mode', 'sender') # Novo: Sender vs Visualizer
        
        # Usa original_path se disponível (para lógica de reenvio/queue)
        current_path = original_path if (original_path and os.path.exists(original_path)) else file_path
        filename = os.path.basename(current_path or "N/A")
        profile_name = self.config['name']
        is_recovered_file = False

        try:
            # Recuperação de arquivo perdido
            if not os.path.exists(current_path):
                recovered_path = self._resolve_missing_file(original_path, file_path)
                if recovered_path:
                    current_path = recovered_path
                    is_recovered_file = True
                else:
                    raise FileNotFoundError(f"File to process not found at source, backup or dest: {filename}")

            file_hash = self._calculate_hash(current_path)
            
            # -1 indica override manual (Forçar Envio)
            is_forced = (retry_count == -1)

            # Verifica duplicata se não for forçado
            if not is_forced and data_manager.hash_exists(db_path, file_hash):
                self.logger.warning(f"Duplicate file detected: {filename}. Marking as duplicate.")
                data_manager.update_file_status(db_path, record_id, 'duplicate', file_hash=file_hash)
                return

            self._extract_and_index_containers(record_id, current_path)

            effective_mode = 'sender' if is_forced else mode
            
            if effective_mode == 'visualizer':
                # Só backup e marca como monitorado
                if not is_recovered_file: self._handle_backup(current_path)
                data_manager.update_file_status(db_path, record_id, 'monitored', file_hash=file_hash)
                self.logger.info(f"File {filename} monitored (Visualizer Mode).")
            
            else:
                # Modo Sender (envia)
                if dest_type == 'local':
                    self._handle_local_destination(record_id, current_path, file_hash, is_forced)
                elif dest_type == 'SFTP':
                    self._handle_sftp_destination(record_id, current_path, file_hash)
                else:
                    raise NotImplementedError(f"Destination type '{dest_type}' is not supported.")

                # Backup sempre (se sender)
                if not is_recovered_file: self._handle_backup(current_path)

                # Ação Pós-Envio (Move) - Só se não for recuperado/backup
                if action == 'move' and not is_recovered_file and not is_forced:
                    try:
                        os.remove(current_path)
                    except Exception as e:
                        self.logger.warning(f"Could not remove source file after move: {e}")

        except Exception as e:
            self.logger.error(f"Failed to process file ID {record_id} ({filename}): {e}", exc_info=True)
            
            new_retry = 0 if retry_count < 0 else retry_count + 1
            if new_retry >= 5:
                data_manager.update_file_status(db_path, record_id, 'failed', increment_retry=True)
                self.alert_manager.send("CRITICAL", f"File Failure - {profile_name}", f"File '{filename}' failed 5 times. Error: {e}")
            else:
                data_manager.update_file_status(db_path, record_id, 'pending', increment_retry=True)

    def _handle_local_destination(self, record_id, file_path, file_hash, is_forced):
        db_path = self.config['settings']['db_path']
        dest_dir = self.config['destination']['path']
        action = self.config.get('action', 'copy')
        filename = os.path.basename(file_path)
        
        if not os.path.isdir(dest_dir): os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, filename)

        # Se forçado ou copy, usa copy2. Se move, usa move.
        if action == 'move' and not is_forced:
            shutil.move(file_path, dest_path)
        else:
            shutil.copy2(file_path, dest_path)
        
        self.logger.info(f"File ID {record_id} processed to local dest.")
        data_manager.update_file_status(db_path, record_id, 'sent', file_hash=file_hash)

    def _handle_sftp_destination(self, record_id, file_path, file_hash):
        db_path = self.config['settings']['db_path']
        dest_cfg = self.config['destination']
        host, username = dest_cfg.get('host'), dest_cfg.get('username')
        remote_path = dest_cfg.get('remote_path', '/')
        filename = os.path.basename(file_path)
        
        password = keyring.get_password(f"robot_automator::{host}", username)
        if not password: raise ValueError(f"Password for {username}@{host} not found.")

        cnopts = pysftp.CnOpts(); cnopts.hostkeys = None
        with pysftp.Connection(host, username=username, password=password, port=dest_cfg.get('port', 22), cnopts=cnopts) as sftp:
            sftp.cwd(remote_path)
            remote_dest = f"{remote_path}/{filename}".replace("//", "/")
            sftp.put(file_path, remote_dest)
        
        self.logger.info(f"File ID {record_id} uploaded to SFTP.")
        data_manager.update_file_status(db_path, record_id, 'sent', file_hash=file_hash)

class ServiceManager:
    def __init__(self, profile_config, main_log_queue):
        self.profile_config = profile_config
        self.runner_thread = None
        self.stop_event = Event()
        self.logger = logger_setup.create_profile_logger(
            self.profile_config['settings']['log_path'], 
            main_log_queue
        )
        alert_cfg = self.profile_config.get('settings', {}).get('alerting', {})
        self.alert_manager = alert_manager.TeamsAlertManager(alert_cfg, self.logger)

    def start(self):
        if self.is_running(): return
        self.logger.info("Starting services...")
        self.stop_event.clear()
        data_manager.initialize_database(self.profile_config['settings']['db_path'])
        
        self.runner_thread = ProfileRunner(
            self.profile_config, self.stop_event, self.logger, self.alert_manager
        )
        self.runner_thread.start()
        self.logger.info("Services started.")

    def stop(self):
        if not self.is_running(): return
        self.logger.info("Stopping services...")
        self.stop_event.set()
        if self.runner_thread: self.runner_thread.join(timeout=10)
        self.runner_thread = None
        self.logger.info("Services stopped.")

    def is_running(self):
        return self.runner_thread and self.runner_thread.is_alive()

class ProfileRunner(Thread):
    WATCHER_MAPPING = {'local': LocalWatcher, 'SFTP': SftpWatcher}
    PROCESSOR_MAPPING = {'local': FileProcessor, 'SFTP': FileProcessor}

    def __init__(self, profile_config, stop_event, logger, alert_manager):
        super().__init__()
        self.config = profile_config
        self.stop_event = stop_event
        self.logger = logger
        self.alert_manager = alert_manager
        self.daemon = True

    def run(self):
        source_type = self.config['source']['type']
        WatcherClass = self.WATCHER_MAPPING.get(source_type)
        ProcessorClass = self.PROCESSOR_MAPPING.get(self.config['destination']['type'])

        if not WatcherClass or not ProcessorClass:
            self.logger.error("Invalid Source/Dest type config.")
            return

        watcher = WatcherClass(self.config, self.stop_event, self.logger, self.alert_manager)
        processor = ProcessorClass(self.config, self.stop_event, self.logger, self.alert_manager)

        watcher.start()
        processor.start()
        self.logger.info(f"Profile '{self.config['name']}' threads running.")

        while not self.stop_event.is_set():
            if not watcher.is_alive() or not processor.is_alive():
                self.logger.error("Critical thread died. Restarting profile...")
                self.stop_event.set()
                self.stop_event.wait(5)
            self.stop_event.wait(2)
        
        watcher.join()
        processor.join()