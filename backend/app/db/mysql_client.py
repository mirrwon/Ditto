import os
from typing import Optional

import pymysql
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

_conn: Optional[pymysql.connections.Connection] = None
_last_error: Optional[str] = None


def _build_conn() -> pymysql.connections.Connection:
    host = os.getenv("MYSQL_HOST", "localhost")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD") or None
    db = os.getenv("MYSQL_DB") or None
    use_ssl = os.getenv("MYSQL_SSL", "").strip().lower() in ("1", "true", "yes", "on")

    ssl_config = {"ssl": {}} if use_ssl else None

    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=db,
        ssl=ssl_config,
        autocommit=True,
    )


def get_mysql() -> Optional[pymysql.connections.Connection]:
    global _conn
    global _last_error
    try:
        if _conn is None or not getattr(_conn, "open", False):
            _conn = _build_conn()
        _conn.ping(reconnect=True)
        _last_error = None
        return _conn
    except Exception as exc:
        _conn = None
        _last_error = repr(exc)
        return None


def get_mysql_error() -> Optional[str]:
    return _last_error