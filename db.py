import os
import psycopg2
from psycopg2.extras import RealDictCursor

def _conn():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set")
    # sslmode ensure
    if "sslmode=" not in url:
        url = url + ("&" if "?" in url else "?") + "sslmode=require"
    return psycopg2.connect(url, cursor_factory=RealDictCursor)

def init_db():
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS locations (
            chat_id BIGINT NOT NULL,
            location TEXT NOT NULL,
            PRIMARY KEY (chat_id, location)
        )
        """)
        conn.commit()

# ---------- USERS ----------
def add_user(user_id: int):
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))
        conn.commit()

def get_all_users():
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT user_id FROM users")
        rows = cur.fetchall()
        return [r["user_id"] for r in rows]

# ---------- LOCATIONS (custom per chat) ----------
def get_custom_locations_db(chat_id: int):
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT location FROM locations WHERE chat_id = %s ORDER BY location ASC", (chat_id,))
        rows = cur.fetchall()
        return [r["location"] for r in rows]

def add_custom_location_db(chat_id: int, name: str):
    name = name.strip()
    if not name:
        return False, "Name cannot be empty."
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM locations WHERE chat_id=%s AND LOWER(location)=LOWER(%s)", (chat_id, name))
        if cur.fetchone():
            return False, "Already added."
        cur.execute("INSERT INTO locations (chat_id, location) VALUES (%s, %s)", (chat_id, name))
        conn.commit()
        return True, None

def remove_custom_location_db(chat_id: int, name: str):
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM locations WHERE chat_id=%s AND LOWER(location)=LOWER(%s)", (chat_id, name))
        ok = cur.rowcount > 0
        conn.commit()
        return (ok, None if ok else "Not found among custom locations.")

def reset_custom_locations_db(chat_id: int):
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM locations WHERE chat_id=%s", (chat_id,))
        conn.commit()