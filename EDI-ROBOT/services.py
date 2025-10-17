import logging
import time
import os
import shutil
import hashlib
from threading import Thread, Event
from datetime import datetime, date, timedelta
import fnmatch

import data_manager
import logger_setup

class ServiceManager:
    """Gere os serviços (FileWatcher, FileProcessor) para um único perfil."""
    def __init__(self, profile_config, main_log_queue):
        self.profile_config = profile_config
        self.watcher_thread = None
        self.processor_thread = None
        self.stop_event = Event()
        self.logger = logger_setup.create_profile_logger(profile_config['log_path'], main_log_queue)

    def start(self):
        if self.is_running():
            self.logger.warning("Tentativa de iniciar serviços que já estão em execução.")
            return
        self.logger.info("Iniciando serviços...")
        self.stop_event.clear()
        data_manager.initialize_database(self.profile_config['db_path'])
        self.watcher_thread = FileWatcher(self.profile_config, self.stop_event, self.logger)
        self.processor_thread = FileProcessor(self.profile_config, self.stop_event, self.logger)
        self.watcher_thread.start()
        self.processor_thread.start()
        self.logger.info("Serviços iniciados com sucesso.")

    def stop(self):
        if not self.is_running():
            return
        self.logger.info("Parando serviços...")
        self.stop_event.set()
        if self.watcher_thread:
            self.watcher_thread.join()
        if self.processor_thread:
            self.processor_thread.join()
        self.logger.info("Serviços parados com sucesso.")

    def is_running(self):
        return (self.watcher_thread and self.watcher_thread.is_alive()) or \
               (self.processor_thread and self.processor_thread.is_alive())

class FileWatcher(Thread):
    def __init__(self, profile_config, stop_event, logger):
        super().__init__()
        self.config = profile_config
        self.stop_event = stop_event
        self.logger = logger
        self.daemon = True

    def _get_date_limit(self):
        age_config = self.config.get('file_age', {})
        if isinstance(age_config, dict):
            age_value = age_config.get('value', 0)
            age_unit = age_config.get('unit', 'Days')
        else: 
            self.logger.warning("Configuração de 'idade de arquivo' em formato antigo. Usando padrão.")
            age_value = 0
            age_unit = 'Days'

        # CORREÇÃO: Lógica ajustada para usar estritamente os valores em Inglês da UI
        if age_unit == "No Limit":
            return None

        days_to_subtract = 0
        if age_unit == "Days":
            days_to_subtract = age_value
        elif age_unit == "Months":
            days_to_subtract = age_value * 30
        elif age_unit == "Years":
            days_to_subtract = age_value * 365

        return date.today() - timedelta(days=days_to_subtract)

    def run(self):
        source_dir = self.config['source_path']
        db_path = self.config['db_path']
        patterns = [p.strip() for p in self.config['file_format'].split(',') if p.strip()]
        date_limit = self._get_date_limit()

        interval_config = self.config.get('scan_interval', {})
        if isinstance(interval_config, dict):
            scan_value = interval_config.get('value', 5)
            scan_unit = interval_config.get('unit', 's')
        else: 
            self.logger.warning("Configuração de 'tempo de scan' em formato antigo. Usando padrão.")
            scan_value = interval_config or 5
            scan_unit = 's'

        # CORREÇÃO: Lógica ajustada para usar estritamente os valores em Inglês da UI
        scan_interval_seconds = scan_value
        if scan_unit == 'min':
            scan_interval_seconds *= 60
        elif scan_unit == 'hr':
            scan_interval_seconds *= 3600

        self.logger.info(f"Monitor iniciado. Vigiando: {source_dir}")
        while not self.stop_event.is_set():
            try:
                if not os.path.isdir(source_dir):
                    self.logger.error(f"Pasta de origem não encontrada: {source_dir}. Pausando monitor.")
                    self.stop_event.wait(60)
                    continue
                known_files = data_manager.get_known_filepaths(db_path)
                with os.scandir(source_dir) as entries:
                    for entry in entries:
                        if not entry.is_file() or entry.path in known_files:
                            continue
                        if not any(fnmatch.fnmatch(entry.name, pattern) for pattern in patterns):
                            continue
                        try:
                            mod_date = date.fromtimestamp(entry.stat().st_mtime)
                            if date_limit is None or mod_date >= date_limit:
                                data_manager.add_file_to_queue(db_path, entry.path, status='pending')
                                self.logger.info(f"Novo arquivo: '{entry.name}' adicionado à fila.")
                            else:
                                mod_date_str = mod_date.strftime('%d/%m/%Y')
                                self.logger.warning(f"Arquivo antigo ignorado: '{entry.name}' (data: {mod_date_str}).")
                                data_manager.add_file_to_queue(db_path, entry.path, status='ignored')
                        except Exception:
                            continue
            except Exception as e:
                self.logger.error(f"Erro crítico no monitor de arquivos: {e}", exc_info=True)

            self.stop_event.wait(scan_interval_seconds)
        self.logger.info(f"Serviço de monitoramento parado.")

class FileProcessor(Thread):
    def __init__(self, profile_config, stop_event, logger):
        super().__init__()
        self.config = profile_config
        self.stop_event = stop_event
        self.logger = logger
        self.daemon = True

    def _calculate_hash(self, file_path):
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except FileNotFoundError:
            return None

    def _extract_unit_name(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    clean_line = line.strip()
                    if clean_line.startswith('EQD'):
                        parts = clean_line.split('+')
                        if len(parts) >= 3:
                            return parts[2]
            return 'NAO_ENCONTRADA'
        except Exception as e:
            self.logger.error(f"Erro ao extrair nome da unidade do ficheiro {os.path.basename(file_path)}: {e}")
            return 'ERRO_LEITURA'

    def run(self):
        db_path = self.config.get('db_path', '')
        self.logger.info("Processador de ficheiros iniciado.")
        while not self.stop_event.is_set():
            try:
                pending_files = data_manager.get_pending_files(db_path)
                if not pending_files:
                    self.stop_event.wait(5)
                    continue
                for record_id, file_path, retry_count in pending_files:
                    if self.stop_event.is_set():
                        break
                    self._process_file(record_id, file_path, retry_count)
            except Exception as e:
                self.logger.error(f"Erro no loop principal do processador: {e}", exc_info=True)
                self.stop_event.wait(10)
        self.logger.info("Processador de ficheiros parado.")

    @staticmethod
    def generate_preview(profile_config):
        """
        Simula a execução de um perfil e retorna uma lista de ficheiros que seriam processados.
        Não executa nenhuma ação real nem modifica o banco de dados.
        """
        try:
            source_dir = profile_config.get('source_path', '')
            patterns = [p.strip() for p in profile_config.get('file_format', '').split(',') if p.strip()]
            action = profile_config.get('action', 'copy')
            destination_path = profile_config.get('destination_path', '')

            age_map = { "Mesmo Dia": 0, "1 Mês": 30, "2 Meses": 60, "3 Meses": 90,
                        "6 Meses": 180, "Este Ano": 365, "Sem Limite": -1 }
            days_to_subtract = age_map.get(profile_config.get('file_age', 'Sem Limite'), -1)
            date_limit = None
            if days_to_subtract != -1:
                if profile_config.get('file_age') == "Este Ano":
                    date_limit = date(date.today().year, 1, 1)
                else:
                    date_limit = date.today() - timedelta(days=days_to_subtract)

            if not os.path.isdir(source_dir):
                raise FileNotFoundError(f"Pasta de origem não encontrada: {source_dir}")

            found_files = []
            with os.scandir(source_dir) as entries:
                for entry in entries:
                    if not entry.is_file():
                        continue

                    matched_pattern = next((p for p in patterns if fnmatch.fnmatch(entry.name, p)), None)
                    if not matched_pattern:
                        continue

                    mod_date = date.fromtimestamp(entry.stat().st_mtime)
                    if date_limit is not None and mod_date < date_limit:
                        continue

                    file_info = {
                        "arquivo": entry.path,
                        "regra": matched_pattern,
                        "acao": "move" if action == 'move' else "copy",
                        "destino": destination_path,
                        "novo_nome": entry.name,
                        "tamanho": f"{entry.stat().st_size / 1024:.2f} KB" if entry.stat().st_size > 1024 else f"{entry.stat().st_size} B"
                    }
                    found_files.append(file_info)

            return found_files, None

        except Exception as e:
            return [], str(e)

    def _process_file(self, record_id, file_path, retry_count):
        db_path = self.config.get('db_path', '')
        destination_dir = self.config.get('destination_path', '')
        action = self.config.get('action', 'copy')

        try:
            mod_time = os.path.getmtime(file_path)
            data_modificacao_str = datetime.fromtimestamp(mod_time).strftime('%d/%m/%Y %H:%M:%S')
            self.logger.info(f"Processando arquivo ID {record_id}: '{os.path.basename(file_path)}' (Modificado em: {data_modificacao_str})")
        except FileNotFoundError:
            self.logger.error(f"Arquivo não encontrado (ID: {record_id}): {file_path}. Marcando como falha.")
            data_manager.update_file_status(db_path, record_id, 'failed')
            return

        file_hash = self._calculate_hash(file_path)
        if file_hash is None:
            self.logger.error(f"Não foi possível calcular hash do arquivo ID {record_id}: {file_path}")
            return

        try:
            if data_manager.hash_exists(db_path, file_hash):
                self.logger.warning(f"Duplicado detectado pelo hash no processamento. ID: {record_id}.")
                data_manager.update_file_status(db_path, record_id, 'duplicate', file_hash=file_hash)
                return

            if not os.path.isdir(destination_dir):
                raise ValueError(f"A pasta de destino não é válida: {destination_dir}")

            unit_name = self._extract_unit_name(file_path)
            dest_path = os.path.join(destination_dir, os.path.basename(file_path))

            if action == 'move':
                shutil.move(file_path, dest_path)
            else:
                shutil.copy(file_path, dest_path)

            self.logger.info(f"Arquivo ID {record_id} processado com sucesso. Unidade: {unit_name}.")
            data_manager.update_file_status(db_path, record_id, 'sent', file_hash=file_hash)

        except Exception as e:
            self.logger.error(f"Falha ao processar arquivo ID {record_id}: {e}")
            if retry_count + 1 >= 5:
                data_manager.update_file_status(db_path, record_id, 'failed', increment_retry=True)
            else:
                data_manager.update_file_status(db_path, record_id, 'pending', increment_retry=True)