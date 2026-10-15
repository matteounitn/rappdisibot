"""Persistenza su SQLite.

Invariante: ogni funzione di questo modulo è **sincrona** e non contiene ``await``.
Una singola chiamata è quindi indivisibile rispetto all'event loop di asyncio.
Le sequenze "leggi poi scrivi" che attraversano un await (creazione topic,
chiusura ticket) vanno protette da ``core.lock_for``.
"""

from __future__ import annotations

import sqlite3

DEFAULT_DB_PATH = "rappdisibot.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
    banned INTEGER NOT NULL DEFAULT 0,
    username TEXT
);

CREATE TABLE IF NOT EXISTS tickets(
    user_id INTEGER PRIMARY KEY,
    topic_id INTEGER NOT NULL,
    open INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS admins(
    user_id INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS settings(
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS operators(
    user_id INTEGER PRIMARY KEY
);
"""

_conn: sqlite3.Connection | None = None


def init(path: str = DEFAULT_DB_PATH) -> None:
    """Apre (o riapre) la connessione e crea lo schema."""
    global _conn
    if _conn is not None:
        _conn.close()
    _conn = sqlite3.connect(path)
    _conn.executescript(_SCHEMA)
    cols = [row[1] for row in _conn.execute("PRAGMA table_info(users)").fetchall()]
    if "banned" not in cols:
        _conn.execute("ALTER TABLE users ADD COLUMN banned INTEGER NOT NULL DEFAULT 0")
    if "username" not in cols:
        _conn.execute("ALTER TABLE users ADD COLUMN username TEXT")
    _conn.commit()


def _db() -> sqlite3.Connection:
    if _conn is None:
        raise RuntimeError("db.init() deve essere chiamato prima di usare il database")
    return _conn


# --- utenti ---------------------------------------------------------------


def upsert_user(uid: int, username: str | None = None) -> None:
    clean = username.lstrip("@").lower().strip() if username else None
    if clean == "":
        clean = None
    _db().execute(
        """
        INSERT INTO users(user_id, username) VALUES(?, ?)
        ON CONFLICT(user_id) DO UPDATE SET username = excluded.username
        """,
        (uid, clean),
    )
    _db().commit()


def get_username(uid: int) -> str | None:
    row = _db().execute("SELECT username FROM users WHERE user_id = ?", (uid,)).fetchone()
    return row[0] if row and row[0] is not None else None


def find_user_by_username(username: str) -> int | None:
    clean = username.lstrip("@").lower().strip() if username else ""
    if not clean:
        return None
    row = _db().execute(
        "SELECT user_id FROM users WHERE LOWER(username) = ?", (clean,)
    ).fetchone()
    return row[0] if row else None


def count_users() -> int:
    return _db().execute("SELECT COUNT(*) FROM users").fetchone()[0]


def set_banned(uid: int, banned: bool) -> None:
    _db().execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (uid,))
    _db().execute(
        "UPDATE users SET banned = ? WHERE user_id = ?", (1 if banned else 0, uid)
    )
    _db().commit()


def is_banned(uid: int) -> bool:
    row = _db().execute("SELECT banned FROM users WHERE user_id = ?", (uid,)).fetchone()
    return bool(row[0]) if row else False


def count_banned() -> int:
    return _db().execute("SELECT COUNT(*) FROM users WHERE banned = 1").fetchone()[0]


def broadcast_user_ids() -> list[int]:
    rows = _db().execute(
        "SELECT user_id FROM users WHERE banned = 0 ORDER BY user_id"
    ).fetchall()
    return [row[0] for row in rows]

# --- ticket ---------------------------------------------------------------


def create_ticket(uid: int, topic_id: int) -> None:
    """Apre un ticket per l'utente (sostituisce l'eventuale ticket precedente)."""
    _db().execute(
        "INSERT OR REPLACE INTO tickets(user_id, topic_id, open, created_at)"
        " VALUES(?, ?, 1, CURRENT_TIMESTAMP)",
        (uid, topic_id),
    )
    _db().commit()


def get_open_topic(uid: int) -> int | None:
    row = _db().execute(
        "SELECT topic_id FROM tickets WHERE user_id = ? AND open = 1", (uid,)
    ).fetchone()
    return row[0] if row else None


def get_user_by_topic(topic_id: int) -> int | None:
    row = _db().execute(
        "SELECT user_id FROM tickets WHERE topic_id = ? AND open = 1", (topic_id,)
    ).fetchone()
    return row[0] if row else None


def get_user_by_topic_any(topic_id: int) -> int | None:
    row = _db().execute(
        "SELECT user_id FROM tickets WHERE topic_id = ?", (topic_id,)
    ).fetchone()
    return row[0] if row else None

def close_ticket(uid: int) -> None:
    _db().execute("UPDATE tickets SET open = 0 WHERE user_id = ?", (uid,))
    _db().commit()


def list_open_tickets() -> list[tuple[int, int, str]]:
    return _db().execute(
        "SELECT user_id, topic_id, created_at FROM tickets"
        " WHERE open = 1 ORDER BY created_at, user_id"
    ).fetchall()


def count_open_tickets() -> int:
    return _db().execute("SELECT COUNT(*) FROM tickets WHERE open = 1").fetchone()[0]


def count_tickets() -> int:
    return _db().execute("SELECT COUNT(*) FROM tickets").fetchone()[0]


# --- admin ----------------------------------------------------------------


def seed_admins(ids: tuple[int, ...]) -> None:
    """Reinserisce gli admin da config.ini a ogni avvio (idempotente)."""
    _db().executemany("INSERT OR IGNORE INTO admins(user_id) VALUES(?)", [(i,) for i in ids])
    _db().commit()


def add_admin(uid: int) -> None:
    _db().execute("INSERT OR IGNORE INTO admins(user_id) VALUES(?)", (uid,))
    _db().commit()


def remove_admin(uid: int) -> None:
    _db().execute("DELETE FROM admins WHERE user_id = ?", (uid,))
    _db().commit()


def is_admin(uid: int) -> bool:
    row = _db().execute("SELECT 1 FROM admins WHERE user_id = ?", (uid,)).fetchone()
    return row is not None


def list_admins() -> list[int]:
    rows = _db().execute("SELECT user_id FROM admins ORDER BY user_id").fetchall()
    return [row[0] for row in rows]


# --- impostazioni ---------------------------------------------------------


def get_setting(key: str) -> str | None:
    """Restituisce il valore di una chiave di configurazione o None."""
    row = _db().execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def set_setting(key: str, value: str) -> None:
    """Imposta o sovrascrive una chiave di configurazione."""
    _db().execute(
        "INSERT OR REPLACE INTO settings(key, value) VALUES(?, ?)", (key, value)
    )
    _db().commit()


def delete_setting(key: str) -> None:
    """Elimina una chiave di configurazione."""
    _db().execute("DELETE FROM settings WHERE key = ?", (key,))
    _db().commit()


# --- operatori ------------------------------------------------------------


def add_operator(uid: int) -> None:
    """Aggiunge un utente alla lista degli operatori."""
    _db().execute("INSERT OR IGNORE INTO operators(user_id) VALUES(?)", (uid,))
    _db().commit()


def remove_operator(uid: int) -> None:
    """Rimuove un utente dalla lista degli operatori."""
    _db().execute("DELETE FROM operators WHERE user_id = ?", (uid,))
    _db().commit()


def is_operator(uid: int) -> bool:
    """Verifica se un utente è registrato come operatore."""
    row = _db().execute("SELECT 1 FROM operators WHERE user_id = ?", (uid,)).fetchone()
    return row is not None


def list_operators() -> list[int]:
    """Restituisce gli ID di tutti gli operatori ordinati per ID."""
    rows = _db().execute("SELECT user_id FROM operators ORDER BY user_id").fetchall()
    return [row[0] for row in rows]


def count_operators() -> int:
    """Restituisce il numero totale di operatori registrati."""
    return _db().execute("SELECT COUNT(*) FROM operators").fetchone()[0]
