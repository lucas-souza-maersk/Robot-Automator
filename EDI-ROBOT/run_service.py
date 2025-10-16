import time
import logging
import logging.handlers
import os
import config_manager
from services import ServiceManager

def setup_service_logger():
    """Configura um logger autossuficiente para o serviço."""
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'service_engine.log')

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    handler = logging.handlers.TimedRotatingFileHandler(log_file, when='midnight', backupCount=7, encoding='utf-8')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def main():
    setup_service_logger()
    logging.info("Motor de Automação iniciado. A monitorizar perfis...")
    
    running_services = {}

    try:
        while True:
            profiles = config_manager.load_profiles()
            active_profiles = {name: config for name, config in profiles.items() if config.get('enabled', False)}

            if not active_profiles:
                logging.info("Nenhum perfil ativo encontrado. A verificar novamente em 60 segundos.")
            
            # Sincroniza os serviços em execução com os perfis ativos
            for name, config in active_profiles.items():
                if name not in running_services or not running_services[name].is_running():
                    logging.info(f"A tentar iniciar serviços para o perfil ativo '{name}'...")
                    
                    # --- BLOCO DE ROBUSTEZ: ISOLAMENTO DE FALHAS ---
                    try:
                        sm = ServiceManager(config, main_log_queue=None)
                        sm.start()
                        running_services[name] = sm
                    except Exception as e:
                        logging.error(f"FALHA CRÍTICA AO INICIAR O PERFIL '{name}': {e}", exc_info=True)
                        # O perfil falhou. O erro é registado, mas o serviço continua a rodar.
                    # --- FIM DO BLOCO DE ROBUSTEZ ---

            # Para serviços que estão a correr mas já não estão ativos no JSON
            for name, sm in list(running_services.items()):
                if name not in active_profiles:
                    logging.info(f"Perfil '{name}' desativado. Parando serviços...")
                    sm.stop()
                    del running_services[name]

            time.sleep(60)
            
    except KeyboardInterrupt:
        logging.info("Parando todos os serviços...")
        for service_manager in running_services.values():
            service_manager.stop()
        logging.info("Serviços parados. A sair.")

if __name__ == "__main__":
    main()