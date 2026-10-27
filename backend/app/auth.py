import hashlib
import secrets

from .db import connect

ACCOUNTS = (
    ("admin", "系统管理员", "系统管理员", "Admin#2026"),
    ("lead", "投标负责人", "投标负责人", "Lead#2026"),
    ("business", "商务编制", "商务", "Biz#2026"),
    ("finance", "财务审核", "财务", "Fin#2026"),
)


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000).hex()


def seed_users() -> None:
    with connect() as conn:
        for username, display_name, role, password in ACCOUNTS:
            existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if existing:
                continue
            salt = secrets.token_hex(8)
            conn.execute(
                """
                INSERT INTO users (username, display_name, role, password_salt, password_hash)
                VALUES (?, ?, ?, ?, ?)
                """,
                (username, display_name, role, salt, hash_password(password, salt)),
            )


def login(username: str, password: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username.strip(),)).fetchone()
        if row is None or hash_password(password, row["password_salt"]) != row["password_hash"]:
            return None
        token = secrets.token_urlsafe(24)
        conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, row["id"]))
        return {
            "access_token": token,
            "user": {"username": row["username"], "display_name": row["display_name"], "role": row["role"]},
        }


def current_user(token: str) -> dict | None:
    if not token:
        return None
    with connect() as conn:
        row = conn.execute(
            """
            SELECT u.username, u.display_name, u.role
            FROM sessions s JOIN users u ON u.id = s.user_id
            WHERE s.token = ?
            """,
            (token,),
        ).fetchone()
    return dict(row) if row else None


def logout(token: str) -> None:
    if not token:
        return
    with connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
