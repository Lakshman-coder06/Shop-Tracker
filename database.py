"""
database.py
------------
Handles all SQLite database setup and access for the
Shop Work & Collection Tracker.

For this first version we create the FULL database structure
(all 7 tables from the plan), but only 'users' and 'services'
are actively used by the app so far. The rest sit ready and
empty until we build Quick Job Entry, Expenses, etc. in later
steps. This avoids having to change the database shape later.
"""

import sqlite3
import hashlib
import os
from datetime import datetime

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shop_tracker.db")


def get_connection():
    """Create and return a connection to the SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # lets us read columns by name, e.g. row["name"]
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def hash_pin(pin: str) -> str:
    """Turn a PIN into a scrambled string so raw PINs are never stored in the database."""
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


def init_db():
    """Create all tables if they don't already exist, and seed starter data."""
    conn = get_connection()
    cur = conn.cursor()

    # ---------- USERS (workers / supervisor / admin) ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            pin_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('worker', 'supervisor', 'admin')),
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # ---------- SERVICES (Xerox, Printing, Passport Photo, ...) ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            rate REAL NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # ---------- TRANSACTIONS (built in a later step) ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_code TEXT NOT NULL UNIQUE,
            worker_id INTEGER NOT NULL,
            service_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            amount REAL NOT NULL,
            payment_method TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Completed',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (worker_id) REFERENCES users(id),
            FOREIGN KEY (service_id) REFERENCES services(id)
        )
    """)

    # ---------- EXPENSES (built in a later step) ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_code TEXT NOT NULL UNIQUE,
            worker_id INTEGER NOT NULL,
            purpose TEXT NOT NULL,
            amount REAL NOT NULL,
            payment_method TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (worker_id) REFERENCES users(id)
        )
    """)

    # ---------- APPLICATION ACTIVITY (built in a later step) ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS application_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL,
            app_name TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            duration_seconds INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (worker_id) REFERENCES users(id)
        )
    """)

    # ---------- DAILY CLOSING (built in a later step) ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_closing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            closing_date TEXT NOT NULL UNIQUE,
            expected_cash REAL NOT NULL,
            actual_cash REAL,
            difference REAL,
            closed_by INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (closed_by) REFERENCES users(id)
        )
    """)

    # ---------- AUDIT LOGS (built in a later step) ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            record_id INTEGER NOT NULL,
            field_changed TEXT,
            old_value TEXT,
            new_value TEXT,
            changed_by INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (changed_by) REFERENCES users(id)
        )
    """)

    conn.commit()
    _seed_starter_data(conn)
    conn.close()


def _seed_starter_data(conn):
    """Add default workers and default service rates, only if those tables are empty."""
    cur = conn.cursor()
    now = datetime.now().isoformat()

    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        default_users = [
            ("Worker 1", "1111", "worker"),
            ("Worker 2", "2222", "worker"),
            ("Worker 3", "3333", "worker"),
            ("Admin", "9999", "admin"),
        ]
        for name, pin, role in default_users:
            cur.execute(
                "INSERT INTO users (name, pin_hash, role, active, created_at, updated_at) "
                "VALUES (?, ?, ?, 1, ?, ?)",
                (name, hash_pin(pin), role, now, now),
            )

    cur.execute("SELECT COUNT(*) FROM services")
    if cur.fetchone()[0] == 0:
        default_services = [
            ("Xerox B&W", 2),
            ("Xerox Colour", 10),
            ("Printing", 5),
            ("Passport Photo", 80),
            ("Lamination", 20),
            ("Photoshop / Editing", 100),
            ("Invitation Design", 200),
            ("Album Design", 500),
            ("Other", 0),
        ]
        for name, rate in default_services:
            cur.execute(
                "INSERT INTO services (name, rate, active, created_at, updated_at) "
                "VALUES (?, ?, 1, ?, ?)",
                (name, rate, now, now),
            )

    conn.commit()


def get_active_workers():
    """Return all active users (workers, supervisor, admin) for the login screen."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, role FROM users WHERE active = 1 ORDER BY role, name")
    rows = cur.fetchall()
    conn.close()
    return rows


def verify_login(user_id: int, pin: str):
    """Check a PIN against one user's stored PIN hash. Returns the user row, or None if wrong."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ? AND active = 1", (user_id,))
    user = cur.fetchone()
    conn.close()
    if user and user["pin_hash"] == hash_pin(pin):
        return user
    return None


def get_today_summary():
    """
    Return today's dashboard numbers.
    For now this returns zeros, since Quick Job Entry (transactions)
    hasn't been built yet. This function will start returning real
    numbers once we add job entry in the next step.
    """
    return {
        "jobs": 0,
        "sales": 0.0,
        "cash": 0.0,
        "upi": 0.0,
        "expenses": 0.0,
        "expected_drawer": 0.0,
    }
