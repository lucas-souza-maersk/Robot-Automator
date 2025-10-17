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
    except Exception as e:
        logger.error(f"Failed to start profile '{name}': {e}", exc_info=True)


def stop_profile(name, running_services, logger):
    """Stop a running profile and remove it from the dictionary."""
    try:
        running_services[name]["manager"].stop()
        del running_services[name]
        logger.info(f"Profile '{name}' stopped successfully.")
    except Exception as e:
        logger.warning(f"Error stopping profile '{name}': {e}")


def main():
    logger = setup_service_logger()
    logger.info("Automation Engine started. Monitoring profiles...")

    running_services = {}

    try:
        while True:
            logger.debug("Loading profiles from config_manager...")
            try:
                profiles = config_manager.load_profiles()
            except Exception as e:
                logger.error(f"Error while loading profiles: {e}", exc_info=True)
                time.sleep(30)
                continue

            active_profiles = {
                name: cfg for name, cfg in profiles.items() if cfg.get("enabled", False)
            }

            logger.debug(f"Active profiles: {list(active_profiles.keys()) or 'none'}")

            for name, config in active_profiles.items():
                if name not in running_services:
                    logger.info(f"Starting new profile '{name}'...")
                    start_profile(name, config, running_services, logger)
                else:
                    old_config = running_services[name]["config"]
                    if config != old_config:
                        logger.info(f"Configuration changed for '{name}'. Restarting service...")
                        stop_profile(name, running_services, logger)
                        start_profile(name, config, running_services, logger)
                    elif not running_services[name]["manager"].is_running():
                        logger.warning(f"Service '{name}' not running. Attempting restart...")
                        start_profile(name, config, running_services, logger)

            for name in list(running_services.keys()):
                if name not in active_profiles:
                    logger.info(f"Profile '{name}' was disabled. Stopping...")
                    stop_profile(name, running_services, logger)

            logger.debug("Cycle complete. Waiting 60 seconds before next check.")
            time.sleep(60)

    except KeyboardInterrupt:
        logger.info("Stopping all services...")
        for name in list(running_services.keys()):
            stop_profile(name, running_services, logger)
        logger.info("All services stopped. Exiting Automation Engine.")


if __name__ == "__main__":
    main()
