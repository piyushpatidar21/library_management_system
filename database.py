from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / 'library.db'


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON;')
    return conn


@contextmanager
def db_cursor():
    conn = get_connection()
    cur = conn.cursor()
    try:
        yield conn, cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def init_db() -> None:
    with db_cursor() as (conn, cur):
        cur.executescript(
            '''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                full_name TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS memberships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                membership_code TEXT UNIQUE NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                contact_number TEXT NOT NULL,
                contact_address TEXT NOT NULL,
                aadhaar_no TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                membership_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Active',
                fine_pending REAL NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS catalog_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serial_no TEXT UNIQUE NOT NULL,
                item_type TEXT NOT NULL CHECK(item_type IN ('Book','Movie')),
                title TEXT NOT NULL,
                author_name TEXT NOT NULL,
                category TEXT NOT NULL,
                cost REAL NOT NULL,
                procurement_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Available',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                issue_code TEXT UNIQUE NOT NULL,
                membership_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                issue_date TEXT NOT NULL,
                due_date TEXT NOT NULL,
                return_date TEXT,
                remarks TEXT,
                fine_amount REAL NOT NULL DEFAULT 0,
                fine_paid INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Issued',
                FOREIGN KEY(membership_id) REFERENCES memberships(id),
                FOREIGN KEY(item_id) REFERENCES catalog_items(id)
            );

            CREATE TABLE IF NOT EXISTS issue_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                membership_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                requested_date TEXT NOT NULL,
                request_fulfilled_date TEXT,
                status TEXT NOT NULL DEFAULT 'Pending',
                FOREIGN KEY(membership_id) REFERENCES memberships(id)
            );

            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                issue_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                paid_on TEXT NOT NULL,
                remarks TEXT,
                FOREIGN KEY(issue_id) REFERENCES issues(id)
            );
            '''
        )


def table_has_rows(table_name: str) -> bool:
    with db_cursor() as (conn, cur):
        cur.execute(f'SELECT EXISTS(SELECT 1 FROM {table_name} LIMIT 1)')
        return bool(cur.fetchone()[0])
