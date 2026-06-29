"""
TaxFlow CRM — Database layer
aiosqlite-based async SQLite with full CRUD operations.
"""
import aiosqlite
from datetime import datetime, date, timedelta
from typing import Optional, Any
from loguru import logger

from .config import get_settings


def _db_path() -> str:
    """Returns the current database path (reads from settings each call — cheap due to lru_cache)."""
    return get_settings().database_url


# Module-level alias updated by tests via: import backend.db as m; m.DB_PATH = "..."
# Runtime code uses _db_path() so patching DB_PATH also works.
DB_PATH: str = get_settings().database_url

# ─── Schema ───────────────────────────────────────────────────────────────────

CREATE_TABLES_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    email           TEXT    NOT NULL UNIQUE,
    full_name       TEXT    NOT NULL,
    role            TEXT    NOT NULL DEFAULT 'preparer',
    password_hash   TEXT    NOT NULL,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS clients (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name               TEXT    NOT NULL,
    email                   TEXT    NOT NULL UNIQUE,
    phone                   TEXT,
    address                 TEXT,
    tax_year                INTEGER NOT NULL DEFAULT 2024,
    filing_status           TEXT,
    entity_type             TEXT    NOT NULL DEFAULT 'individual',
    ssn_last4               TEXT,
    ein                     TEXT,
    state                   TEXT,
    assigned_preparer_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    notes                   TEXT,
    is_active               INTEGER NOT NULL DEFAULT 1,
    portal_password_hash    TEXT,
    created_at              TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS documents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id       INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    doc_type        TEXT    NOT NULL,
    tax_year        INTEGER NOT NULL DEFAULT 2024,
    status          TEXT    NOT NULL DEFAULT 'awaiting',
    notes           TEXT,
    received_at     TEXT,
    reviewed_at     TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(client_id, doc_type, tax_year)
);

CREATE TABLE IF NOT EXISTS deadlines (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id       INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    deadline_type   TEXT    NOT NULL,
    due_date        TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'upcoming',
    notes           TEXT,
    state_code      TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id       INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    sender_role     TEXT    NOT NULL,
    sender_name     TEXT,
    content         TEXT    NOT NULL,
    read            INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tasks (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id           INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    title               TEXT    NOT NULL,
    description         TEXT,
    due_date            TEXT,
    priority            TEXT    NOT NULL DEFAULT 'medium',
    completed           INTEGER NOT NULL DEFAULT 0,
    completed_at        TEXT,
    assigned_to_id      INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_documents_client ON documents(client_id);
CREATE INDEX IF NOT EXISTS idx_deadlines_client ON deadlines(client_id);
CREATE INDEX IF NOT EXISTS idx_deadlines_due ON deadlines(due_date);
CREATE INDEX IF NOT EXISTS idx_messages_client ON messages(client_id);
CREATE INDEX IF NOT EXISTS idx_tasks_client ON tasks(client_id);
"""


# ─── Connection Helper ────────────────────────────────────────────────────────

async def get_db() -> aiosqlite.Connection:
    """Get a database connection with row factory."""
    db = await aiosqlite.connect(_db_path())
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    await db.execute("PRAGMA journal_mode=WAL")
    return db


async def init_db():
    """Initialize database schema and default admin user."""
    logger.info(f"Initializing database at {_db_path()}")
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.executescript(CREATE_TABLES_SQL)
        await db.commit()

        # Create default admin if no users exist
        async with db.execute("SELECT COUNT(*) as cnt FROM users") as cursor:
            row = await cursor.fetchone()
            if row["cnt"] == 0:
                from .auth import hash_password
                _s = get_settings()
                admin_hash = hash_password(_s.admin_password)
                await db.execute(
                    "INSERT INTO users (email, full_name, role, password_hash) VALUES (?, ?, ?, ?)",
                    (_s.admin_email, "Admin User", "admin", admin_hash)
                )
                await db.commit()
                logger.info(f"Created default admin: {_s.admin_email}")


# ─── User CRUD ────────────────────────────────────────────────────────────────

async def get_user_by_email(email: str) -> Optional[dict]:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        async with db.execute(
            "SELECT * FROM users WHERE email = ? AND is_active = 1", (email,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_user_by_id(user_id: int) -> Optional[dict]:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        async with db.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def create_user(email: str, full_name: str, role: str, password_hash: str) -> dict:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        cur = await db.execute(
            "INSERT INTO users (email, full_name, role, password_hash) VALUES (?, ?, ?, ?)",
            (email, full_name, role, password_hash)
        )
        await db.commit()
        async with db.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)) as c:
            return dict(await c.fetchone())


async def list_users() -> list[dict]:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        async with db.execute(
            "SELECT id, email, full_name, role, is_active, created_at FROM users ORDER BY full_name"
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


# ─── Client CRUD ──────────────────────────────────────────────────────────────

async def create_client(data: dict) -> dict:
    fields = [
        "full_name", "email", "phone", "address", "tax_year", "filing_status",
        "entity_type", "ssn_last4", "ein", "state", "assigned_preparer_id",
        "notes", "is_active", "portal_password_hash"
    ]
    values = {f: data.get(f) for f in fields}
    cols = ", ".join(values.keys())
    placeholders = ", ".join("?" * len(values))
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        cur = await db.execute(
            f"INSERT INTO clients ({cols}) VALUES ({placeholders})",
            list(values.values())
        )
        await db.commit()
        async with db.execute("SELECT * FROM clients WHERE id = ?", (cur.lastrowid,)) as c:
            return dict(await c.fetchone())


async def get_client(client_id: int) -> Optional[dict]:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        async with db.execute(
            "SELECT * FROM clients WHERE id = ?", (client_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_client_by_email(email: str) -> Optional[dict]:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        async with db.execute(
            "SELECT * FROM clients WHERE email = ?", (email,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def list_clients(
    preparer_id: Optional[int] = None,
    entity_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    tax_year: Optional[int] = None,
) -> list[dict]:
    query = "SELECT * FROM clients WHERE 1=1"
    params: list[Any] = []

    if preparer_id is not None:
        query += " AND assigned_preparer_id = ?"
        params.append(preparer_id)
    if entity_type:
        query += " AND entity_type = ?"
        params.append(entity_type)
    if is_active is not None:
        query += " AND is_active = ?"
        params.append(1 if is_active else 0)
    if search:
        query += " AND (full_name LIKE ? OR email LIKE ? OR phone LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s])
    if tax_year:
        query += " AND tax_year = ?"
        params.append(tax_year)

    query += " ORDER BY full_name"

    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        async with db.execute(query, params) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def update_client(client_id: int, data: dict) -> Optional[dict]:
    if not data:
        return await get_client(client_id)

    set_clause = ", ".join(f"{k} = ?" for k in data.keys())
    params = list(data.values()) + [client_id]

    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        await db.execute(
            f"UPDATE clients SET {set_clause} WHERE id = ?", params
        )
        await db.commit()
        return await get_client(client_id)


async def delete_client(client_id: int) -> bool:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        cur = await db.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        await db.commit()
        return cur.rowcount > 0


# ─── Document CRUD ────────────────────────────────────────────────────────────

async def create_document(data: dict) -> dict:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        cur = await db.execute(
            """INSERT OR REPLACE INTO documents
               (client_id, doc_type, tax_year, status, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (data["client_id"], data["doc_type"], data["tax_year"],
             data.get("status", "awaiting"), data.get("notes"))
        )
        await db.commit()
        async with db.execute("SELECT * FROM documents WHERE id = ?", (cur.lastrowid,)) as c:
            return dict(await c.fetchone())


async def get_documents_for_client(client_id: int, tax_year: Optional[int] = None) -> list[dict]:
    query = "SELECT * FROM documents WHERE client_id = ?"
    params: list[Any] = [client_id]
    if tax_year:
        query += " AND tax_year = ?"
        params.append(tax_year)
    query += " ORDER BY doc_type"

    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        async with db.execute(query, params) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def update_document(doc_id: int, data: dict) -> Optional[dict]:
    if not data:
        return None

    # Auto-set timestamps
    if data.get("status") == "received" and "received_at" not in data:
        data["received_at"] = datetime.utcnow().isoformat()
    if data.get("status") == "reviewed" and "reviewed_at" not in data:
        data["reviewed_at"] = datetime.utcnow().isoformat()

    set_clause = ", ".join(f"{k} = ?" for k in data.keys())
    params = list(data.values()) + [doc_id]

    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        await db.execute(
            f"UPDATE documents SET {set_clause} WHERE id = ?", params
        )
        await db.commit()
        async with db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)) as c:
            row = await c.fetchone()
            return dict(row) if row else None


async def get_document_completion(client_id: int, tax_year: Optional[int] = None) -> dict:
    docs = await get_documents_for_client(client_id, tax_year)
    applicable = [d for d in docs if d["status"] != "not_applicable"]
    received = [d for d in docs if d["status"] == "received"]
    reviewed = [d for d in docs if d["status"] == "reviewed"]
    awaiting = [d for d in docs if d["status"] == "awaiting"]
    na = [d for d in docs if d["status"] == "not_applicable"]

    total = len(applicable)
    completed = len(received) + len(reviewed)
    pct = (completed / total * 100) if total > 0 else 0.0

    return {
        "client_id": client_id,
        "total": len(docs),
        "awaiting": len(awaiting),
        "received": len(received),
        "reviewed": len(reviewed),
        "not_applicable": len(na),
        "completion_pct": round(pct, 1),
    }


# ─── Deadline CRUD ────────────────────────────────────────────────────────────

async def create_deadline(data: dict) -> dict:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        cur = await db.execute(
            """INSERT INTO deadlines (client_id, deadline_type, due_date, status, notes, state_code)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["client_id"], data["deadline_type"], str(data["due_date"]),
             data.get("status", "upcoming"), data.get("notes"), data.get("state_code"))
        )
        await db.commit()
        async with db.execute("SELECT * FROM deadlines WHERE id = ?", (cur.lastrowid,)) as c:
            return dict(await c.fetchone())


async def get_deadlines_for_client(client_id: int) -> list[dict]:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        async with db.execute(
            "SELECT * FROM deadlines WHERE client_id = ? ORDER BY due_date",
            (client_id,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_upcoming_deadlines(days: int = 30, preparer_id: Optional[int] = None) -> list[dict]:
    today = date.today().isoformat()
    future = (date.today() + timedelta(days=days)).isoformat()

    query = """
        SELECT d.*, c.full_name as client_name
        FROM deadlines d
        JOIN clients c ON c.id = d.client_id
        WHERE d.due_date BETWEEN ? AND ?
          AND d.status IN ('upcoming', 'in_progress')
    """
    params: list[Any] = [today, future]

    if preparer_id:
        query += " AND c.assigned_preparer_id = ?"
        params.append(preparer_id)

    query += " ORDER BY d.due_date"

    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        async with db.execute(query, params) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def update_deadline(deadline_id: int, data: dict) -> Optional[dict]:
    if not data:
        return None
    if "due_date" in data and data["due_date"]:
        data["due_date"] = str(data["due_date"])

    set_clause = ", ".join(f"{k} = ?" for k in data.keys())
    params = list(data.values()) + [deadline_id]

    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        await db.execute(
            f"UPDATE deadlines SET {set_clause} WHERE id = ?", params
        )
        await db.commit()
        async with db.execute("SELECT * FROM deadlines WHERE id = ?", (deadline_id,)) as c:
            row = await c.fetchone()
            return dict(row) if row else None


async def delete_deadline(deadline_id: int) -> bool:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        cur = await db.execute("DELETE FROM deadlines WHERE id = ?", (deadline_id,))
        await db.commit()
        return cur.rowcount > 0


def auto_generate_deadlines(client_id: int, entity_type: str, tax_year: int) -> list[dict]:
    """Generate standard deadlines based on entity type and tax year."""
    y = tax_year
    ny = tax_year + 1  # next year (when return is due)
    deadlines = []

    if entity_type == "individual":
        deadlines = [
            {"deadline_type": "Federal Return (1040/1120/1065)", "due_date": date(ny, 4, 15)},
            {"deadline_type": "Federal Extension", "due_date": date(ny, 10, 15)},
            {"deadline_type": "Q1 Estimated Tax (Apr 15)", "due_date": date(ny, 4, 15)},
            {"deadline_type": "Q2 Estimated Tax (Jun 15)", "due_date": date(ny, 6, 15)},
            {"deadline_type": "Q3 Estimated Tax (Sep 15)", "due_date": date(ny, 9, 15)},
            {"deadline_type": "Q4 Estimated Tax (Jan 15)", "due_date": date(ny + 1, 1, 15)},
        ]
    elif entity_type in ("s_corp", "c_corp"):
        deadlines = [
            {"deadline_type": "Federal Return (1040/1120/1065)", "due_date": date(ny, 3, 15)},
            {"deadline_type": "Federal Extension", "due_date": date(ny, 9, 15)},
            {"deadline_type": "Corporate Estimated Tax", "due_date": date(ny, 4, 15)},
            {"deadline_type": "Corporate Estimated Tax", "due_date": date(ny, 6, 15)},
            {"deadline_type": "Corporate Estimated Tax", "due_date": date(ny, 9, 15)},
            {"deadline_type": "Corporate Estimated Tax", "due_date": date(ny, 12, 15)},
            {"deadline_type": "W-2/1099 Filing (Jan 31)", "due_date": date(ny, 1, 31)},
        ]
    elif entity_type == "partnership":
        deadlines = [
            {"deadline_type": "Federal Return (1040/1120/1065)", "due_date": date(ny, 3, 15)},
            {"deadline_type": "Federal Extension", "due_date": date(ny, 9, 15)},
            {"deadline_type": "W-2/1099 Filing (Jan 31)", "due_date": date(ny, 1, 31)},
        ]
    elif entity_type == "llc":
        deadlines = [
            {"deadline_type": "Federal Return (1040/1120/1065)", "due_date": date(ny, 4, 15)},
            {"deadline_type": "Federal Extension", "due_date": date(ny, 10, 15)},
            {"deadline_type": "Q1 Estimated Tax (Apr 15)", "due_date": date(ny, 4, 15)},
            {"deadline_type": "Q2 Estimated Tax (Jun 15)", "due_date": date(ny, 6, 15)},
            {"deadline_type": "Q3 Estimated Tax (Sep 15)", "due_date": date(ny, 9, 15)},
            {"deadline_type": "Q4 Estimated Tax (Jan 15)", "due_date": date(ny + 1, 1, 15)},
        ]
    else:  # sole_proprietor, nonprofit, other
        deadlines = [
            {"deadline_type": "Federal Return (1040/1120/1065)", "due_date": date(ny, 4, 15)},
            {"deadline_type": "Federal Extension", "due_date": date(ny, 10, 15)},
        ]

    for d in deadlines:
        d["client_id"] = client_id
        d["status"] = "upcoming"

    return deadlines


# ─── Message CRUD ─────────────────────────────────────────────────────────────

async def create_message(client_id: int, sender_role: str, content: str, sender_name: Optional[str] = None) -> dict:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        cur = await db.execute(
            "INSERT INTO messages (client_id, sender_role, sender_name, content) VALUES (?, ?, ?, ?)",
            (client_id, sender_role, sender_name, content)
        )
        await db.commit()
        async with db.execute("SELECT * FROM messages WHERE id = ?", (cur.lastrowid,)) as c:
            return dict(await c.fetchone())


async def get_messages_for_client(client_id: int, limit: int = 100) -> list[dict]:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        async with db.execute(
            "SELECT * FROM messages WHERE client_id = ? ORDER BY created_at DESC LIMIT ?",
            (client_id, limit)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in reversed(rows)]


async def mark_messages_read(client_id: int, sender_role: str) -> int:
    """Mark all messages from a specific role as read."""
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        cur = await db.execute(
            "UPDATE messages SET read = 1 WHERE client_id = ? AND sender_role = ? AND read = 0",
            (client_id, sender_role)
        )
        await db.commit()
        return cur.rowcount


async def get_unread_message_counts() -> dict[int, int]:
    """Returns {client_id: unread_count} for all clients with unread messages."""
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        async with db.execute(
            """SELECT client_id, COUNT(*) as cnt FROM messages
               WHERE sender_role = 'client' AND read = 0
               GROUP BY client_id"""
        ) as cur:
            rows = await cur.fetchall()
            return {r["client_id"]: r["cnt"] for r in rows}


async def get_all_message_threads() -> list[dict]:
    """Get latest message per client for inbox view."""
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        async with db.execute(
            """SELECT m.client_id, c.full_name as client_name,
                      m.content as last_message, m.created_at as last_at,
                      m.sender_role as last_sender,
                      SUM(CASE WHEN m2.sender_role = 'client' AND m2.read = 0 THEN 1 ELSE 0 END) as unread_count
               FROM messages m
               JOIN clients c ON c.id = m.client_id
               LEFT JOIN messages m2 ON m2.client_id = m.client_id
               WHERE m.id = (
                   SELECT id FROM messages WHERE client_id = m.client_id ORDER BY created_at DESC LIMIT 1
               )
               GROUP BY m.client_id
               ORDER BY m.created_at DESC"""
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


# ─── Task CRUD ────────────────────────────────────────────────────────────────

async def create_task(data: dict) -> dict:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        cur = await db.execute(
            """INSERT INTO tasks (client_id, title, description, due_date, priority, assigned_to_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["client_id"], data["title"], data.get("description"),
             str(data["due_date"]) if data.get("due_date") else None,
             data.get("priority", "medium"), data.get("assigned_to_id"))
        )
        await db.commit()
        async with db.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)) as c:
            return dict(await c.fetchone())


async def get_tasks_for_client(client_id: int) -> list[dict]:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        async with db.execute(
            "SELECT * FROM tasks WHERE client_id = ? ORDER BY completed, due_date NULLS LAST, priority",
            (client_id,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def update_task(task_id: int, data: dict) -> Optional[dict]:
    if not data:
        return None
    if data.get("completed") is True and "completed_at" not in data:
        data["completed_at"] = datetime.utcnow().isoformat()
        data["completed"] = 1
    if data.get("completed") is False:
        data["completed"] = 0
        data["completed_at"] = None
    if "due_date" in data and data["due_date"]:
        data["due_date"] = str(data["due_date"])

    set_clause = ", ".join(f"{k} = ?" for k in data.keys())
    params = list(data.values()) + [task_id]

    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        await db.execute(
            f"UPDATE tasks SET {set_clause} WHERE id = ?", params
        )
        await db.commit()
        async with db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)) as c:
            row = await c.fetchone()
            return dict(row) if row else None


# ─── Dashboard Queries ────────────────────────────────────────────────────────

async def get_dashboard_stats() -> dict:
    today = date.today().isoformat()
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    in_7 = (date.today() + timedelta(days=7)).isoformat()
    in_30 = (date.today() + timedelta(days=30)).isoformat()

    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        async def scalar(sql, params=()):
            async with db.execute(sql, params) as c:
                row = await c.fetchone()
                return row[0] if row else 0

        total_clients = await scalar("SELECT COUNT(*) FROM clients")
        active_clients = await scalar("SELECT COUNT(*) FROM clients WHERE is_active = 1")
        docs_this_week = await scalar(
            "SELECT COUNT(*) FROM documents WHERE status IN ('received', 'reviewed') AND received_at >= ?",
            (week_ago,)
        )
        deadlines_7 = await scalar(
            "SELECT COUNT(*) FROM deadlines WHERE due_date BETWEEN ? AND ? AND status IN ('upcoming', 'in_progress')",
            (today, in_7)
        )
        deadlines_30 = await scalar(
            "SELECT COUNT(*) FROM deadlines WHERE due_date BETWEEN ? AND ? AND status IN ('upcoming', 'in_progress')",
            (today, in_30)
        )
        unread_msgs = await scalar(
            "SELECT COUNT(*) FROM messages WHERE sender_role = 'client' AND read = 0"
        )
        completed_returns = await scalar(
            "SELECT COUNT(*) FROM deadlines WHERE deadline_type LIKE '%Return%' AND status = 'completed'"
        )

        # At-risk: clients with any missed deadline
        missed_clients = await scalar(
            """SELECT COUNT(DISTINCT client_id) FROM deadlines
               WHERE status = 'missed' OR (due_date < ? AND status = 'upcoming')""",
            (today,)
        )

        return {
            "total_clients": total_clients,
            "active_clients": active_clients,
            "docs_received_this_week": docs_this_week,
            "deadlines_in_7_days": deadlines_7,
            "deadlines_in_30_days": deadlines_30,
            "at_risk_clients": missed_clients,
            "unread_messages": unread_msgs,
            "completed_returns_ytd": completed_returns,
        }


async def get_recent_activity(limit: int = 20) -> list[dict]:
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        activity = []

        # Recent documents
        async with db.execute(
            """SELECT d.id, d.doc_type, d.status, d.received_at as ts,
                      c.full_name, c.id as client_id
               FROM documents d JOIN clients c ON c.id = d.client_id
               WHERE d.status IN ('received', 'reviewed') AND d.received_at IS NOT NULL
               ORDER BY d.received_at DESC LIMIT 10"""
        ) as cur:
            for row in await cur.fetchall():
                r = dict(row)
                activity.append({
                    "type": "document",
                    "description": f"{r['full_name']} submitted {r['doc_type']}",
                    "client_id": r["client_id"],
                    "client_name": r["full_name"],
                    "timestamp": r["ts"],
                    "icon": "📄",
                })

        # Recent messages
        async with db.execute(
            """SELECT m.id, m.content, m.created_at as ts, m.sender_role,
                      c.full_name, c.id as client_id
               FROM messages m JOIN clients c ON c.id = m.client_id
               ORDER BY m.created_at DESC LIMIT 10"""
        ) as cur:
            for row in await cur.fetchall():
                r = dict(row)
                who = "Client" if r["sender_role"] == "client" else "Staff"
                activity.append({
                    "type": "message",
                    "description": f"{r['full_name']}: {r['content'][:60]}...",
                    "client_id": r["client_id"],
                    "client_name": r["full_name"],
                    "timestamp": r["ts"],
                    "icon": "💬",
                })

        # Sort by timestamp descending
        activity.sort(key=lambda x: x["timestamp"] or "", reverse=True)
        return activity[:limit]


async def get_at_risk_clients() -> list[dict]:
    today = date.today().isoformat()
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        async with db.execute(
            """SELECT DISTINCT c.*
               FROM clients c
               LEFT JOIN deadlines d ON d.client_id = c.id
               WHERE c.is_active = 1
                 AND (
                   (d.status = 'missed') OR
                   (d.due_date < ? AND d.status = 'upcoming')
                 )
               ORDER BY c.full_name
               LIMIT 10""",
            (today,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
