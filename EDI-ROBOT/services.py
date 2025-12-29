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
        while not self.stop_event.is_set():
            try:
                pending_files = data_manager.get_pending_files(db_path)
                if not pending_files:
                    self.stop_event.wait(5)
                    continue
                for record_id, file_path, retry_count in pending_files:
                    if self.stop_event.is_set(): break
                    self._process_file(record_id, file_path, retry_count)
            except Exception as e:
                self.logger.error(f"Critical error in processor loop: {e}", exc_info=True)
                self.stop_event.wait(10)
        self.logger.info("File processor stopped.")

    def _process_file(self, record_id, file_path, retry_count):
        raise NotImplementedError("Each processor must implement its own _process_file method.")

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
                            data_manager.add_file_to_queue(db_path, entry.path, status='pending')
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
                            
                            data_manager.add_file_to_queue(db_path, local_dest_path, status='pending', original_path=remote_filepath)
                            self.logger.info(f"File '{attr.filename}' added to queue.")

            except Exception as e:
                self.logger.error(f"Error in SFTP watcher: {e}", exc_info=True)
                self.alert_manager.send(
                    "WARNING", 
                    f"Erro no Watcher SFTP - Perfil: {self.config['name']}",
                    f"Ocorreu um erro ao tentar conectar ou listar arquivos em {username}@{host}. O watcher tentará novamente. Erro: {e}"
                )
            
            self.stop_event.wait(scan_interval)
        self.logger.info("SFTP watcher stopped.")

class FileProcessor(BaseProcessor):
    def _extract_and_index_containers(self, record_id, file_path):
        db_path = self.config['settings']['db_path']
        try:
            with open(file_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
                content = f.read()
            
            containers = re.findall(r'[A-Z]{4}[0-9]{7}', content)
            if containers:
                data_manager.add_containers_to_index(db_path, record_id, containers)
                self.logger.info(f"Indexed {len(set(containers))} units for file ID {record_id}.")
        except Exception as e:
            self.logger.warning(f"Could not extract units from {file_path}: {e}")

    def _process_file(self, record_id, file_path, retry_count):
        db_path = self.config['settings']['db_path']
        action = self.config.get('action', 'copy')
        dest_cfg = self.config.get('destination', {})
        dest_type = dest_cfg.get('type', 'local')
        
        filename = os.path.basename(file_path or "N/A")
        profile_name = self.config['name']

        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File to process not found: {file_path}")

            file_hash = self._calculate_hash(file_path)
            if data_manager.hash_exists(db_path, file_hash):
                self.logger.warning(f"Duplicate file detected by hash: {filename}. Marking as duplicate.")
                data_manager.update_file_status(db_path, record_id, 'duplicate', file_hash=file_hash)
                self.alert_manager.send(
                    "WARNING",
                    f"Arquivo Duplicado - Perfil: {profile_name}",
                    f"O arquivo '{filename}' foi detectado como duplicado (baseado no hash) e não será processado."
                )
                return

            self._extract_and_index_containers(record_id, file_path)

            if dest_type == 'local':
                self._handle_local_destination(record_id, file_path, file_hash)
            elif dest_type == 'SFTP':
                self._handle_sftp_destination(record_id, file_path, file_hash)
            else:
                raise NotImplementedError(f"Destination type '{dest_type}' is not supported.")

            if action == 'move':
                try:
                    os.remove(file_path)
                except Exception as e:
                    self.logger.warning(f"Could not remove source file after move: {e}")

        except Exception as e:
            self.logger.error(f"Failed to process file ID {record_id} ({filename}): {e}", exc_info=True)
            if retry_count + 1 >= 5:
                data_manager.update_file_status(db_path, record_id, 'failed', increment_retry=True)
                self.alert_manager.send(
                    "CRITICAL",
                    f"Falha Permanente de Arquivo - Perfil: {profile_name}",
                    f"O arquivo '{filename}' falhou o processamento 5 vezes e foi movido para 'failed'. Último Erro: {e}"
                )
            else:
                data_manager.update_file_status(db_path, record_id, 'pending', increment_retry=True)
                self.alert_manager.send(
                    "WARNING",
                    f"Falha de Processamento - Perfil: {profile_name}",
                    f"O arquivo '{filename}' falhou na tentativa {retry_count + 1}/5. Será tentado novamente. Erro: {e}"
                )

    def _handle_local_destination(self, record_id, file_path, file_hash):
        db_path = self.config['settings']['db_path']
        action = self.config.get('action', 'copy')
        dest_dir = self.config['destination']['path']
        filename = os.path.basename(file_path)
        
        if not os.path.isdir(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
            
        dest_path = os.path.join(dest_dir, filename)

        if action == 'move' and self.config['source']['type'] == 'local':
            shutil.move(file_path, dest_path)
        else:
            shutil.copy(file_path, dest_path)
        
        self.logger.info(f"File ID {record_id} successfully processed to local destination.")
        data_manager.update_file_status(db_path, record_id, 'sent', file_hash=file_hash)
        
        self.alert_manager.send(
            "INFO",
            f"Arquivo Processado - Perfil: {self.config['name']}",
            f"O arquivo '{filename}' foi processado com sucesso para o destino local: {dest_dir}"
        )

    def _handle_sftp_destination(self, record_id, file_path, file_hash):
        db_path = self.config['settings']['db_path']
        dest_cfg = self.config['destination']
        host = dest_cfg.get('host')
        username = dest_cfg.get('username')
        remote_path = dest_cfg.get('remote_path', '/')
        filename = os.path.basename(file_path)
        
        password = keyring.get_password(f"robot_automator::{host}", username)
        if not password:
            raise ValueError(f"Password for {username}@{host} not found in keyring.")

        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None

        with pysftp.Connection(host, username=username, password=password, port=dest_cfg.get('port', 22), cnopts=cnopts) as sftp:
            sftp.cwd(remote_path)
            remote_dest_path = f"{remote_path}/{filename}".replace("//", "/")
            sftp.put(file_path, remote_dest_path)
        
        self.logger.info(f"File ID {record_id} successfully uploaded to SFTP destination.")
        data_manager.update_file_status(db_path, record_id, 'sent', file_hash=file_hash)

        self.alert_manager.send(
            "INFO",
            f"Arquivo Enviado (SFTP) - Perfil: {self.config['name']}",
            f"O arquivo '{filename}' foi enviado com sucesso para sftp://{username}@{host}{remote_dest_path}"
        )

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
        if self.is_running():
            self.logger.warning("Attempted to start services that are already running.")
            return
        
        self.logger.info("Starting services...")
        self.stop_event.clear()
        
        db_path = self.profile_config['settings']['db_path']
        data_manager.initialize_database(db_path)
        
        self.runner_thread = ProfileRunner(
            self.profile_config, 
            self.stop_event, 
            self.logger, 
            self.alert_manager
        )
        self.runner_thread.start()
        self.logger.info("Services started successfully.")

    def stop(self):
        if not self.is_running():
            return
        
        self.logger.info("Stopping services...")
        self.stop_event.set()
        if self.runner_thread:
            self.runner_thread.join(timeout=10) 
        self.runner_thread = None
        self.logger.info("Services stopped successfully.")

    def is_running(self):
        return self.runner_thread and self.runner_thread.is_alive()

class ProfileRunner(Thread):
    WATCHER_MAPPING = {
        'local': LocalWatcher,
        'SFTP': SftpWatcher,
    }
    PROCESSOR_MAPPING = {
        'local': FileProcessor,
        'SFTP': FileProcessor,
    }

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

        if not WatcherClass:
            self.logger.error(f"No watcher found for source type '{source_type}'. Stopping profile.")
            return
        if not ProcessorClass:
            self.logger.error(f"No processor found for destination type '{self.config['destination']['type']}'. Stopping profile.")
            return

        watcher = WatcherClass(self.config, self.stop_event, self.logger, self.alert_manager)
        processor = ProcessorClass(self.config, self.stop_event, self.logger, self.alert_manager)

        watcher.start()
        processor.start()
        
        self.logger.info(f"Profile '{self.config['name']}' is now running.")

        while not self.stop_event.is_set():
            if not watcher.is_alive() or not processor.is_alive():
                self.logger.error("A critical thread has died. Stopping profile.")
                thread_name = "Watcher" if not watcher.is_alive() else "Processor"
                self.alert_manager.send(
                    "CRITICAL",
                    f"Crash de Thread - Perfil: {self.config['name']}",
                    f"A thread crítica '{thread_name}' morreu inesperadamente. O perfil '{self.config['name']}' será interrompido e reiniciado pelo serviço principal."
                )
                self.stop_event.set()
            self.stop_event.wait(5)
        
        watcher.join()
        processor.join()
        self.logger.info(f"Profile '{self.config['name']}' has been stopped.")