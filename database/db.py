import os
import sqlite3
import pymysql
import pymysql.cursors
from flask import g, current_app
from config import Config

_db_mode = None  # 'mysql' or 'sqlite'

def test_mysql_connection():
    """Test if MySQL server is reachable."""
    try:
        conn = pymysql.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            port=Config.MYSQL_PORT,
            connect_timeout=2
        )
        # Create database if doesn't exist
        with conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{Config.MYSQL_DB}` DEFAULT CHARACTER SET utf8mb4;")
        conn.select_db(Config.MYSQL_DB)
        conn.close()
        return True
    except Exception as e:
        return False

def get_db_mode():
    """Determine whether to use MySQL or SQLite."""
    global _db_mode
    if _db_mode is not None:
        return _db_mode
    
    if Config.DB_TYPE == 'sqlite':
        _db_mode = 'sqlite'
    elif Config.DB_TYPE == 'mysql':
        if test_mysql_connection():
            _db_mode = 'mysql'
        else:
            raise ConnectionError(f"Cannot connect to MySQL at {Config.MYSQL_HOST}:{Config.MYSQL_PORT}")
    else:  # 'auto'
        if test_mysql_connection():
            _db_mode = 'mysql'
        else:
            _db_mode = 'sqlite'
    return _db_mode

def get_db():
    """Get request-scoped database connection."""
    mode = get_db_mode()
    
    if 'db' not in g:
        if mode == 'mysql':
            g.db = pymysql.connect(
                host=Config.MYSQL_HOST,
                user=Config.MYSQL_USER,
                password=Config.MYSQL_PASSWORD,
                database=Config.MYSQL_DB,
                port=Config.MYSQL_PORT,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True
            )
        else:
            os.makedirs(os.path.dirname(Config.SQLITE_PATH), exist_ok=True)
            conn = sqlite3.connect(Config.SQLITE_PATH)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            g.db = conn
    return g.db

def close_db(e=None):
    """Close the database connection at the end of the request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    """Execute a query and fetch all or one result as dictionary."""
    conn = get_db()
    mode = get_db_mode()
    
    if mode == 'sqlite':
        sqlite_query = query.replace('%s', '?').replace('NOW()', "DATETIME('now', 'localtime')")
        cur = conn.cursor()
        cur.execute(sqlite_query, args)
        rows = cur.fetchall()
        cur.close()
        results = [dict(row) for row in rows]
        return (results[0] if results else None) if one else results
    else:
        with conn.cursor() as cur:
            cur.execute(query, args)
            results = cur.fetchall()
            return (results[0] if results else None) if one else results

def execute_db(query, args=()):
    """Execute an INSERT, UPDATE, or DELETE query and return lastrowid."""
    conn = get_db()
    mode = get_db_mode()
    
    if mode == 'sqlite':
        sqlite_query = query.replace('%s', '?').replace('NOW()', "DATETIME('now', 'localtime')")
        cur = conn.cursor()
        cur.execute(sqlite_query, args)
        conn.commit()
        last_id = cur.lastrowid
        cur.close()
        return last_id
    else:
        with conn.cursor() as cur:
            cur.execute(query, args)
            conn.commit()
            return cur.lastrowid
