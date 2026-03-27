from __future__ import annotations

from typing import Optional

from database import db_cursor


def authenticate_user(username: str, password: str) -> Optional[dict]:
    with db_cursor() as (conn, cur):
        cur.execute(
            '''SELECT id, username, full_name, is_admin, is_active
               FROM users
               WHERE username = ? AND password = ?''',
            (username.strip(), password.strip()),
        )
        row = cur.fetchone()
        if not row or row['is_active'] == 0:
            return None
        return dict(row)
