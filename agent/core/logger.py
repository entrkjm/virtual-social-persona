import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime

# Logs directory
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Default Log File
LOG_FILE = os.path.join(LOG_DIR, f"agent_{datetime.now().strftime('%Y%m%d')}.log")

def setup_logger(name: str = "agent") -> logging.Logger:
    """
    Setup a centralized logger with console and file handlers.
    
    Format: [Timestamp] [Level] [Module] Message
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Prevent duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    # Formatter
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 1. File Handler (Rotating)
    # Max size 10MB, keep 5 backup files
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG) # File captures everything
    logger.addHandler(file_handler)

    # 2. Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO) # Console captures INFO+
    logger.addHandler(console_handler)

    return logger

# Global logger instance for easy import
logger = setup_logger()
