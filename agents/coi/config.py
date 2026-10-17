"""
Configuration management for Legal Risk & Compliance AI System

Loads configuration from environment variables and .env file with sensible defaults.
All settings are centralized here for easy customization.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# ============================================================================
# LLM Configuration
# ============================================================================
LLM_BASE_URL = os.getenv("GROQ_API_BASE_URL", "https://api.groq.com/openai/v1")
LLM_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "120"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
MOCK_LLM_ENABLED = os.getenv("MOCK_LLM_ENABLED", "false").lower() == "true"

# ============================================================================
# API Configuration
# ============================================================================
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# ============================================================================
# Input Validation Configuration
# ============================================================================
MIN_QUESTION_LENGTH = int(os.getenv("MIN_QUESTION_LENGTH", "5"))
MAX_QUESTION_LENGTH = int(os.getenv("MAX_QUESTION_LENGTH", "5000"))

# ============================================================================
# Rate Limiting Configuration
# ============================================================================
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
RATE_LIMIT_COUNT = int(os.getenv("RATE_LIMIT_COUNT", "100"))
RATE_LIMIT_PERIOD = int(os.getenv("RATE_LIMIT_PERIOD", "3600"))  # 1 hour

# ============================================================================
# Logging Configuration
# ============================================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "logs/app.log")

# ============================================================================
# CORS Configuration
# ============================================================================
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:8000"
    ).split(",")
]

# ============================================================================
# Feature Flags
# ============================================================================
ENABLE_QUERY_LOGGING = os.getenv("ENABLE_QUERY_LOGGING", "true").lower() == "true"

# ============================================================================
# Model Verification Configuration
# ============================================================================
MIN_RESPONSE_LENGTH = int(os.getenv("MIN_RESPONSE_LENGTH", "10"))
MAX_RESPONSE_LENGTH = int(os.getenv("MAX_RESPONSE_LENGTH", "5000"))
MIN_RELEVANCE_OVERLAP = float(os.getenv("MIN_RELEVANCE_OVERLAP", "0.3"))

# ============================================================================
# Rewriting Configuration
# ============================================================================
ENABLE_AUTO_REWRITING = os.getenv("ENABLE_AUTO_REWRITING", "true").lower() == "true"
REWRITE_TIMEOUT = int(os.getenv("REWRITE_TIMEOUT", "30"))

# ============================================================================
# Configuration Summary (for debugging)
# ============================================================================
CONFIG_SUMMARY = {
    "LLM": {
        "base_url": LLM_BASE_URL,
        "model": LLM_MODEL,
        "timeout": LLM_TIMEOUT,
    },
    "API": {
        "host": API_HOST,
        "port": API_PORT,
        "environment": ENVIRONMENT,
        "debug": DEBUG_MODE,
    },
    "Validation": {
        "min_question_length": MIN_QUESTION_LENGTH,
        "max_question_length": MAX_QUESTION_LENGTH,
        "min_response_length": MIN_RESPONSE_LENGTH,
        "max_response_length": MAX_RESPONSE_LENGTH,
    },
    "RateLimit": {
        "enabled": RATE_LIMIT_ENABLED,
        "count": RATE_LIMIT_COUNT,
        "period_seconds": RATE_LIMIT_PERIOD,
    },
    "Logging": {
        "level": LOG_LEVEL,
        "file_path": LOG_FILE_PATH,
    },
    "CORS": {
        "allowed_origins": CORS_ALLOWED_ORIGINS,
    },
}
