"""
arena/db/database.py
--------------------
PostgreSQL connection pool and query helpers for The Arena.
Uses psycopg2 with a simple connection pool.
"""

import logging
import os
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

_pool = None


def init_pool(min_conn=1, max_conn=5):
    """Initialize the connection pool from DATABASE_URL."""
    global _pool
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set")
    _pool = pool.SimpleConnectionPool(min_conn, max_conn, url)
    logger.info("DB pool initialized.")


@contextmanager
def get_conn():
    """Get a connection from the pool, auto-return on exit."""
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


# ── Fund queries ──────────────────────────────────────────────

def get_all_funds():
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM funds WHERE is_active = TRUE ORDER BY id")
            return cur.fetchall()


def get_fund(slug: str):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM funds WHERE slug = %s", (slug,))
            return cur.fetchone()


def update_balance(fund_id: int, new_balance: float):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE funds SET current_balance = %s WHERE id = %s",
                (new_balance, fund_id),
            )


# ── Trade queries ─────────────────────────────────────────────

def insert_trade(fund_id: int, cycle_id: str, symbol: str, action: str,
                 shares: float, price: float, reasoning: str, paper: bool = True):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO trades (fund_id, cycle_id, symbol, action, shares, price, reasoning, paper)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                (fund_id, cycle_id, symbol, action, shares, price, reasoning, paper),
            )
            return cur.fetchone()[0]


def get_trades(fund_id: int, limit: int = 50):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM trades WHERE fund_id = %s ORDER BY created_at DESC LIMIT %s",
                (fund_id, limit),
            )
            return cur.fetchall()


# ── Position queries ──────────────────────────────────────────

def upsert_position(fund_id: int, symbol: str, shares: float,
                    avg_price: float, current_price: float = None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO positions (fund_id, symbol, shares, avg_price, current_price)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (fund_id, symbol) DO UPDATE
                   SET shares = EXCLUDED.shares,
                       avg_price = EXCLUDED.avg_price,
                       current_price = COALESCE(EXCLUDED.current_price, positions.current_price),
                       updated_at = NOW()""",
                (fund_id, symbol, shares, avg_price, current_price),
            )


def get_positions(fund_id: int):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM positions WHERE fund_id = %s AND shares > 0",
                (fund_id,),
            )
            return cur.fetchall()


# ── Roast queries ─────────────────────────────────────────────

def insert_roast(fund_id: int, roast_date, content: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO roasts (fund_id, roast_date, content)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (fund_id, roast_date) DO UPDATE SET content = EXCLUDED.content""",
                (fund_id, roast_date, content),
            )


def get_roasts(roast_date):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT r.*, f.name, f.slug FROM roasts r
                   JOIN funds f ON r.fund_id = f.id
                   WHERE r.roast_date = %s ORDER BY f.id""",
                (roast_date,),
            )
            return cur.fetchall()


# ── Leaderboard ───────────────────────────────────────────────

def get_leaderboard():
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT slug, name, model, current_balance, starting_balance,
                          ROUND(((current_balance - starting_balance) / starting_balance) * 100, 2) AS pnl_pct
                   FROM funds WHERE is_active = TRUE
                   ORDER BY current_balance DESC"""
            )
            return cur.fetchall()
