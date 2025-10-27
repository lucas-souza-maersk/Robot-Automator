import time
import logging
import logging.handlers
import os
import config_manager
from services import ServiceManager


def setup_service_logger():
    """Configure an independent logger for the automation engine service."""
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "service_engine.log")

    logger = logging.getLogger("service_engine")
    logger.setLevel(logging.DEBUG)

    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file, when="midnight", backupCount=7, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    console_handler.setLevel(logging.DEBUG)
    logger.addHandler(console_handler)

    return logger


def start_profile(name, config, running_services, logger):
    """Start a profile and register it in the running_services dictionary."""
    try:
        sm = ServiceManager(config, main_log_queue=None)
        sm.start()
        running_services[name] = {"manager": sm, "config": config}
        logger.info(f"Profile '{name}' started successfully.")
    except KeyError as e:
        logger.error(f"Failed to start profile '{name}' due to a missing configuration key: {e}. Please check profiles.json.", exc_info=True)
    except Exception as e:
        logger.error(f"An unexpected error occurred while starting profile '{name}': {e}", exc_info=True)


def stop_profile(name, running_services, logger):
    """Stop a running profile and remove it from the dictionary."""
    if name in running_services:
        try:
            running_services[name]["manager"].stop()
            del running_services[name]
            logger.info(f"Profile '{name}' stopped successfully.")
        except Exception as e:
            logger.warning(f"Error stopping profile '{name}': {e}")
    else:
        logger.warning(f"Attempted to stop profile '{name}', which was not running.")


def main():
    logger = setup_service_logger()
    logger.info("Automation Engine started. Monitoring for active profiles...")

    running_services = {}
    check_interval_seconds = 20

    try:
        while True:
            logger.debug("Loading profiles from config...")
            try:
                profiles = config_manager.load_profiles()
            except Exception as e:
                logger.error(f"Fatal error while loading profiles.json: {e}", exc_info=True)
                time.sleep(check_interval_seconds)
                continue
            active_profile_names = {
                name for name, cfg in profiles.items() if cfg.get("enabled", False)
            }
            
            logger.debug(f"Found active profiles: {list(active_profile_names) or 'None'}")
            
            for name in active_profile_names:
                config = profiles[name]
                if name not in running_services:
                    logger.info(f"New active profile detected: '{name}'. Starting...")
                    start_profile(name, config, running_services, logger)
                else:
                    old_config = running_services[name]["config"]
                    if config != old_config:
                        logger.info(f"Configuration change detected for '{name}'. Restarting service...")
                        stop_profile(name, running_services, logger)
                        start_profile(name, config, running_services, logger)
                    elif not running_services[name]["manager"].is_running():
                        logger.warning(f"Service for '{name}' was not running. Attempting restart...")
                        
                        try:
                            alert_mgr = running_services[name]["manager"].alert_manager
                            alert_mgr.send(
                                "CRITICAL",
                                f"Crash de Perfil - {name}",
                                f"O serviço principal detectou que o perfil '{name}' não estava rodando (crash). Uma reinicialização está sendo tentada agora."
                            )
                        except Exception as alert_e:
                            logger.error(f"Failed to send crash alert for profile '{name}': {alert_e}")

                        start_profile(name, config, running_services, logger)

            running_profile_names = set(running_services.keys())
            profiles_to_stop = running_profile_names - active_profile_names
            
            for name in profiles_to_stop:
                logger.info(f"Profile '{name}' is no longer active or was removed. Stopping...")
                stop_profile(name, running_services, logger)

            logger.debug(f"Cycle complete. Waiting {check_interval_seconds} seconds...")
            time.sleep(check_interval_seconds)

    except KeyboardInterrupt:
        logger.info("Shutdown signal received. Stopping all services...")
        for name in list(running_services.keys()):
            stop_profile(name, running_services, logger)
        logger.info("All services stopped. Automation Engine is exiting.")


if __name__ == "__main__":
    main()