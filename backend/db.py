"""Database connection utilities."""

import mysql.connector
from mysql.connector import MySQLConnection


def get_connection() -> MySQLConnection:
    """Return a new connection to the sct_2024 database."""
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="sct_2024",
    )
