import logging
import queue
from logging.handlers import QueueHandler, TimedRotatingFileHandler

def create_profile_logger(log_path, log_queue):
    logger_name = log_path
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

    logger.propagate = False

    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    file_handler = TimedRotatingFileHandler(
        log_path, 
        when='midnight', 
        interval=1, 
        backupCount=30,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if log_queue:
        queue_handler = QueueHandler(log_queue)
        logger.addHandler(queue_handler)

    return logger

def setup_main_logger(log_queue):
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    file_handler = TimedRotatingFileHandler('app_main.log', when='midnight', backupCount=7, encoding='utf-8')
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    if log_queue:
        queue_handler = QueueHandler(log_queue)
        root_logger.addHandler(queue_handler)