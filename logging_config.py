import logging
import logging.handlers
from pathlib import Path
import os

def setup_logging(app_name="ekranchik"):
    """Настройка логирования для приложений (Flask и Bot)"""
    
    # Используем переменную окружения, по умолчанию - папка 'logs'
    logs_dir = Path(os.getenv('LOGS_DIR', 'logs'))
    logs_dir.mkdir(exist_ok=True, parents=True)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    logger = logging.getLogger(app_name)
    logger.setLevel(logging.DEBUG)
    
    # Очищаем существующие обработчики
    logger.handlers = []
    
    # Файловый обработчик с ротацией
    log_file = logs_dir / f"{app_name}.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger
