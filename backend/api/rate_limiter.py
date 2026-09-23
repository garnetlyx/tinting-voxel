"""
Rate limiting configuration using slowapi.

Separated from main.py to avoid circular imports.
"""
from slowapi import Limiter

from api.client_ip import client_ip
from config.settings import settings

limiter = Limiter(key_func=client_ip, enabled=settings.rate_limit_enabled)
