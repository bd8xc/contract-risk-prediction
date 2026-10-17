"""
Centralized logging configuration for the Legal Risk & Compliance AI System

Provides structured logging to both console and file with configurable levels.
All modules should use the logger from this file.
"""

import logging
import os
from .config import LOG_LEVEL, LOG_FILE_PATH

def setup_logging():
    """
    Initialize and configure the logging system.
    
    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, LOG_LEVEL))
    
    # Ensure logs directory exists
    log_dir = os.path.dirname(LOG_FILE_PATH)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # ========================================================================
    # File Handler - Detailed logging to file
    # ========================================================================
    file_handler = logging.FileHandler(LOG_FILE_PATH)
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    
    # ========================================================================
    # Console Handler - Summary logging to console
    # ========================================================================
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Initialize logger when module is imported
logger = setup_logging()

# Provide convenient access
__all__ = ['logger', 'setup_logging']
