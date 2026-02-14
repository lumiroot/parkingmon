import sqlite3
from datetime import datetime, timedelta

import config


def get_connection():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS parking_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collected_at TEXT NOT NULL,
            parking_name TEXT NOT NULL,
            total_spaces INTEGER NOT NULL,
            occupied_spaces INTEGER NOT NULL,
            available_spaces INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_collected_at
        ON parking_records (collected_at)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_parking_name
        ON parking_records (parking_name)
    """)
    conn.commit()
    conn.close()


def insert_record(collected_at, parking_name, total, occupied, available):
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO parking_records
            (collected_at, parking_name, total_spaces, occupied_spaces, available_spaces)
        VALUES (?, ?, ?, ?, ?)
        """,
        (collected_at, parking_name, total, occupied, available),
    )
    conn.commit()
    conn.close()


def get_records(hours=24, parking_name=None):
    conn = get_connection()
    since = (datetime.now() - timedelta(hours=hours)).isoformat()

    if parking_name:
        rows = conn.execute(
            """
            SELECT collected_at, parking_name, total_spaces,
                   occupied_spaces, available_spaces
            FROM parking_records
            WHERE collected_at >= ? AND parking_name = ?
            ORDER BY collected_at ASC
            """,
            (since, parking_name),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT collected_at, parking_name, total_spaces,
                   occupied_spaces, available_spaces
            FROM parking_records
            WHERE collected_at >= ?
            ORDER BY collected_at ASC
            """,
            (since,),
        ).fetchall()

    conn.close()
    return [dict(row) for row in rows]


def get_parking_names():
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT parking_name FROM parking_records ORDER BY parking_name"
    ).fetchall()
    conn.close()
    return [row["parking_name"] for row in rows]


def get_latest_records():
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT pr.collected_at, pr.parking_name, pr.total_spaces,
               pr.occupied_spaces, pr.available_spaces
        FROM parking_records pr
        INNER JOIN (
            SELECT MAX(collected_at) as max_at FROM parking_records
        ) latest ON pr.collected_at = latest.max_at
        ORDER BY pr.parking_name
        """
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]
