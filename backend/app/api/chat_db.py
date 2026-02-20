import os
import json
from typing import Any, Dict, List

import pymysql

from .chat_env import env_bool


def _mysql_conn():
    host = os.getenv("MYSQL_HOST")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER")
    password = os.getenv("MYSQL_PASSWORD", "")
    db = os.getenv("MYSQL_DB")
    if not host or not user or not db:
        raise RuntimeError("MySQL env not configured: MYSQL_HOST/MYSQL_USER/MYSQL_DB required")

    use_ssl = env_bool(os.getenv("MYSQL_SSL"), default=False)

    kwargs = dict(
        host=host,
        port=port,
        user=user,
        password=password,
        database=db,
        charset="utf8mb4",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )
    if use_ssl:
        kwargs["ssl"] = {"ssl": {}}
    return pymysql.connect(**kwargs)


def _ensure_saved_table():
    sql = """
    CREATE TABLE IF NOT EXISTS saved_recos (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        client_key VARCHAR(128) NOT NULL,
        image_path TEXT,
        result_json JSON,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    conn = _mysql_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
    finally:
        conn.close()


def db_save_reco(client_key: str, image_path: str, result: Dict[str, Any]) -> int:
    _ensure_saved_table()
    conn = _mysql_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO saved_recos (client_key, image_path, result_json) VALUES (%s, %s, %s)",
                (client_key, image_path, json.dumps(result, ensure_ascii=False)),
            )
            return int(cur.lastrowid)
    finally:
        conn.close()


def db_list_recos(client_key: str, limit: int = 20) -> List[Dict[str, Any]]:
    _ensure_saved_table()
    conn = _mysql_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, image_path, created_at, result_json FROM saved_recos "
                "WHERE client_key=%s ORDER BY id DESC LIMIT %s",
                (client_key, int(limit)),
            )
            rows = cur.fetchall() or []
            out: List[Dict[str, Any]] = []
            for r in rows:
                rj = r.get("result_json")
                if isinstance(rj, str):
                    try:
                        rj = json.loads(rj)
                    except Exception:
                        rj = {}
                r["result_json"] = rj if isinstance(rj, dict) else {}
                out.append(r)
            return out
    finally:
        conn.close()