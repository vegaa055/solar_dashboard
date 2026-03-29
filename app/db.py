"""
app/db.py
Thin database connection layer using a connection pool.
"""
import os
import mysql.connector
from mysql.connector import pooling

_pool = None


def get_pool():
    """Initialize (once) and return the connection pool."""
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="solar_pool",
            pool_size=5,
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 3306)),
            database=os.getenv("DB_NAME", "solar_dashboard"),
            user=os.getenv("DB_USER", "solar_user"),
            password=os.getenv("DB_PASSWORD", ""),
        )
    return _pool


def get_conn():
    """Get a connection from the pool."""
    return get_pool().get_connection()