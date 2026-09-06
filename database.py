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

    # ---------- WORKER SESSIONS (NEW in Phase 1) ----------
    # One row per login. logout_time/duration_seconds stay NULL until the
    # worker logs out (or closes the app, which we also catch).
    cur.execute("""
        CREATE TABLE IF NOT EXISTS worker_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL,
            login_time TEXT NOT NULL,
            logout_time TEXT,
            duration_seconds INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (worker_id) REFERENCES users(id)
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
    _migrate_schema(conn)
    _seed_starter_data(conn)
    conn.close()


def _migrate_schema(conn):
    """
    Safe, additive-only migration. Never drops or renames anything and
    never touches existing rows - only adds new columns if they don't
    already exist, and adds new default services if missing by name.
    Existing data (activity history, sessions, etc.) is preserved untouched.
    """
    cur = conn.cursor()

    # --- application_activity (Phase 1.5) ---
    cur.execute("PRAGMA table_info(application_activity)")
    existing_cols = {row[1] for row in cur.fetchall()}
    if "process_name" not in existing_cols:
        cur.execute("ALTER TABLE application_activity ADD COLUMN process_name TEXT")
    if "computer_name" not in existing_cols:
        cur.execute("ALTER TABLE application_activity ADD COLUMN computer_name TEXT")
    if "windows_username" not in existing_cols:
        cur.execute("ALTER TABLE application_activity ADD COLUMN windows_username TEXT")

    # --- transactions (Phase 2: Quick Job Entry) ---
    cur.execute("PRAGMA table_info(transactions)")
    existing_cols = {row[1] for row in cur.fetchall()}
    if "customer_reference" not in existing_cols:
        cur.execute("ALTER TABLE transactions ADD COLUMN customer_reference TEXT")
    if "rate" not in existing_cols:
        cur.execute("ALTER TABLE transactions ADD COLUMN rate REAL")
    if "notes" not in existing_cols:
        cur.execute("ALTER TABLE transactions ADD COLUMN notes TEXT")
    if "payment_status" not in existing_cols:
        cur.execute("ALTER TABLE transactions ADD COLUMN payment_status TEXT DEFAULT 'Paid'")

    # --- expenses (Phase 2: Expense Entry) ---
    cur.execute("PRAGMA table_info(expenses)")
    existing_cols = {row[1] for row in cur.fetchall()}
    if "category" not in existing_cols:
        cur.execute("ALTER TABLE expenses ADD COLUMN category TEXT")
    if "notes" not in existing_cols:
        cur.execute("ALTER TABLE expenses ADD COLUMN notes TEXT")

    # --- users (Phase 3: worker management, PIN reset, temp-PIN flow) ---
    cur.execute("PRAGMA table_info(users)")
    existing_cols = {row[1] for row in cur.fetchall()}
    if "status" not in existing_cols:
        # Backfill from the existing active flag so nobody's login state changes
        cur.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'Active'")
        cur.execute("UPDATE users SET status = CASE WHEN active = 1 THEN 'Active' ELSE 'Inactive' END")
    if "employee_id" not in existing_cols:
        cur.execute("ALTER TABLE users ADD COLUMN employee_id TEXT")
    if "must_change_pin" not in existing_cols:
        cur.execute("ALTER TABLE users ADD COLUMN must_change_pin INTEGER DEFAULT 0")

    # --- transactions (Phase 3: advance/balance for Pending jobs) ---
    cur.execute("PRAGMA table_info(transactions)")
    existing_cols = {row[1] for row in cur.fetchall()}
    if "advance_amount" not in existing_cols:
        cur.execute("ALTER TABLE transactions ADD COLUMN advance_amount REAL DEFAULT 0")

    # --- application_activity (Phase 3: foreground-window title, when useful) ---
    cur.execute("PRAGMA table_info(application_activity)")
    existing_cols = {row[1] for row in cur.fetchall()}
    if "window_title" not in existing_cols:
        cur.execute("ALTER TABLE application_activity ADD COLUMN window_title TEXT")

    conn.commit()

    # --- services: add any new ones that don't already exist by name ---
    # (Phase 1 seeded a shorter list; Phase 2 needs a fuller one. We only
    # ADD missing names here - nothing is renamed or removed, so any rates
    # you've already customized are untouched.)
    now = datetime.now().isoformat()
    fuller_service_list = [
        ("Xerox B&W", 2), ("Xerox Colour", 10), ("Print B&W", 5), ("Print Colour", 10),
        ("Passport Photo", 80), ("Photo Print", 15), ("Lamination", 20), ("Scanning", 10),
        ("Invitation Design", 200), ("Invitation Printing", 15), ("Album Design", 500), ("Other", 0),
    ]
    cur.execute("SELECT name FROM services")
    existing_names = {row[0] for row in cur.fetchall()}
    for name, rate in fuller_service_list:
        if name not in existing_names:
            cur.execute(
                "INSERT INTO services (name, rate, active, created_at, updated_at) VALUES (?, ?, 1, ?, ?)",
                (name, rate, now, now),
            )
    conn.commit()


def _seed_starter_data(conn):
    """Add default workers, only if the users table is empty. (Services are
    seeded additively inside _migrate_schema, which always runs first.)"""
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


def get_today_summary(worker_id: int = None):
    """
    Today's numbers, computed from actual transactions and expenses.
    Pass worker_id to scope everything to just that worker ("My Sales" on
    the Worker dashboard) - leave it None for shop-wide totals (Admin
    dashboard only).
      - jobs: count of all non-cancelled transactions today
      - sales/cash/upi: only transactions that are actually PAID (a Pending
        job that hasn't been paid yet doesn't count as money in hand)
      - expenses: all expenses recorded today, any payment source
      - expected_drawer: cash actually collected minus CASH expenses only
        (a UPI expense doesn't remove physical cash from the drawer)
    """
    conn = get_connection()
    cur = conn.cursor()
    w = " AND worker_id = ?" if worker_id is not None else ""
    p = (worker_id,) if worker_id is not None else ()

    cur.execute(f"""
        SELECT COUNT(*) FROM transactions
        WHERE date(created_at) = date('now', 'localtime') AND status != 'Cancelled' {w}
    """, p)
    jobs = cur.fetchone()[0]

    cur.execute(f"""
        SELECT COALESCE(SUM(amount), 0) FROM transactions
        WHERE date(created_at) = date('now', 'localtime')
          AND status != 'Cancelled' AND payment_status = 'Paid' {w}
    """, p)
    sales = cur.fetchone()[0]

    cur.execute(f"""
        SELECT COALESCE(SUM(amount), 0) FROM transactions
        WHERE date(created_at) = date('now', 'localtime')
          AND status != 'Cancelled' AND payment_status = 'Paid' AND payment_method = 'Cash' {w}
    """, p)
    cash = cur.fetchone()[0]

    cur.execute(f"""
        SELECT COALESCE(SUM(amount), 0) FROM transactions
        WHERE date(created_at) = date('now', 'localtime')
          AND status != 'Cancelled' AND payment_status = 'Paid' AND payment_method = 'UPI' {w}
    """, p)
    upi = cur.fetchone()[0]

    cur.execute(f"""
        SELECT COALESCE(SUM(amount), 0) FROM expenses
        WHERE date(created_at) = date('now', 'localtime') {w}
    """, p)
    expenses_all = cur.fetchone()[0]

    cur.execute(f"""
        SELECT COALESCE(SUM(amount), 0) FROM expenses
        WHERE date(created_at) = date('now', 'localtime') AND payment_method = 'Cash' {w}
    """, p)
    cash_expenses = cur.fetchone()[0]

    conn.close()
    return {
        "jobs": jobs,
        "sales": sales,
        "cash": cash,
        "upi": upi,
        "expenses": expenses_all,
        "expected_drawer": cash - cash_expenses,
    }


def get_worker_performance_today():
    """One row per active worker with today's numbers - powers the Admin
    dashboard's 'Worker Performance' section. Uses get_today_summary()
    under the hood so the math is identical to what each worker sees on
    their own dashboard."""
    workers = get_active_workers()
    result = []
    for w in workers:
        if w["role"] == "admin":
            continue  # Admin doesn't do jobs - no point showing a zeroed row
        summary = get_today_summary(worker_id=w["id"])
        result.append({"worker_id": w["id"], "worker_name": w["name"], **summary})
    return result


def get_active_services():
    """All active services, for the Service dropdown in New Job. Ordered by
    id so they appear in the same sensible grouping they were seeded in."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, rate FROM services WHERE active = 1 ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return rows


# =====================================================================
# PHASE 1 — Worker session tracking
# =====================================================================

def start_worker_session(worker_id: int) -> int:
    """Record a new login session for a worker. Returns the new session's id."""
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().isoformat(timespec="seconds")
    cur.execute(
        "INSERT INTO worker_sessions (worker_id, login_time, created_at) VALUES (?, ?, ?)",
        (worker_id, now, now),
    )
    conn.commit()
    session_id = cur.lastrowid
    conn.close()
    return session_id


def end_worker_session(session_id: int):
    """Fill in the logout time and duration for a session that just ended."""
    if session_id is None:
        return
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT login_time, logout_time FROM worker_sessions WHERE id = ?", (session_id,))
    row = cur.fetchone()
    if row is None or row["logout_time"] is not None:
        # Either the session doesn't exist, or it was already closed once
        # (this can happen if logout AND window-close both fire - harmless).
        conn.close()
        return
    login_time = datetime.fromisoformat(row["login_time"])
    now = datetime.now()
    duration = int((now - login_time).total_seconds())
    cur.execute(
        "UPDATE worker_sessions SET logout_time = ?, duration_seconds = ? WHERE id = ?",
        (now.isoformat(timespec="seconds"), duration, session_id),
    )
    conn.commit()
    conn.close()


# =====================================================================
# PHASE 1.5 — Application activity tracking (dynamic, general-purpose)
# (still writes into the same application_activity table - no new table)
# =====================================================================

def log_activity_start(worker_id: int, app_name: str, process_name: str,
                        start_time: datetime, computer_name: str = None,
                        windows_username: str = None, window_title: str = None) -> int:
    """Record that an application/window just started. Returns the new row's id."""
    conn = get_connection()
    cur = conn.cursor()
    ts = start_time.isoformat(timespec="seconds")
    cur.execute(
        "INSERT INTO application_activity "
        "(worker_id, app_name, process_name, start_time, computer_name, windows_username, window_title, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (worker_id, app_name, process_name, ts, computer_name, windows_username, window_title, ts),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def log_activity_end(row_id: int, start_time: datetime, end_time: datetime):
    """Fill in the end time and duration once an application/window closes."""
    conn = get_connection()
    cur = conn.cursor()
    duration = int((end_time - start_time).total_seconds())
    cur.execute(
        "UPDATE application_activity SET end_time = ?, duration_seconds = ? WHERE id = ?",
        (end_time.isoformat(timespec="seconds"), duration, row_id),
    )
    conn.commit()
    conn.close()


def get_recent_activity(limit: int = 25, worker_id: int = None):
    """Most recent activity rows (newest first), optionally for one worker. Used by the Live Activity screen."""
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT aa.*, u.name AS worker_name
        FROM application_activity aa
        JOIN users u ON u.id = aa.worker_id
    """
    params = []
    if worker_id is not None:
        query += " WHERE aa.worker_id = ?"
        params.append(worker_id)
    query += " ORDER BY aa.start_time DESC LIMIT ?"
    params.append(limit)
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_activity_history(date_filter: str = None, worker_id: int = None,
                          app_name: str = None, status_filter: str = None):
    """
    Filtered activity rows for the History screen.
    date_filter: None | 'today' | 'yesterday' | 'week'
    status_filter: None | 'open' (no end_time yet) | 'closed'
    """
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT aa.*, u.name AS worker_name
        FROM application_activity aa
        JOIN users u ON u.id = aa.worker_id
        WHERE 1=1
    """
    params = []

    if date_filter == "today":
        query += " AND date(aa.start_time) = date('now', 'localtime')"
    elif date_filter == "yesterday":
        query += " AND date(aa.start_time) = date('now', '-1 day', 'localtime')"
    elif date_filter == "week":
        query += " AND date(aa.start_time) >= date('now', '-7 day', 'localtime')"

    if worker_id is not None:
        query += " AND aa.worker_id = ?"
        params.append(worker_id)

    if app_name:
        query += " AND aa.app_name = ?"
        params.append(app_name)

    if status_filter == "open":
        query += " AND aa.end_time IS NULL"
    elif status_filter == "closed":
        query += " AND aa.end_time IS NOT NULL"

    query += " ORDER BY aa.start_time DESC"
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_activity_by_id(activity_id: int):
    """Full detail for one activity row (for the Activity Details dialog)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT aa.*, u.name AS worker_name
        FROM application_activity aa
        JOIN users u ON u.id = aa.worker_id
        WHERE aa.id = ?
    """, (activity_id,))
    row = cur.fetchone()
    conn.close()
    return row


def get_distinct_activity_apps():
    """Every distinct application name ever recorded - for the History screen's Application filter."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT app_name FROM application_activity ORDER BY app_name")
    rows = [r[0] for r in cur.fetchall()]
    conn.close()
    return rows


def get_last_activity_saved():
    """Timestamp of the most recently saved activity row, for the Diagnostics screen."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT created_at FROM application_activity ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    return row["created_at"] if row else None


def check_db_connection() -> bool:
    """Simple health check for the Diagnostics screen."""
    try:
        conn = get_connection()
        conn.execute("SELECT 1")
        conn.close()
        return True
    except Exception:
        return False

# =====================================================================
# PHASE 2 — Quick Job Entry, Transactions, Expenses, Pending Records,
# Daily Closing. All of this reuses the tables already created above.
# =====================================================================

def log_audit(table_name: str, record_id: int, field_changed: str,
              old_value, new_value, changed_by: int):
    """Every correction (e.g. marking a job Completed or Paid) leaves a
    permanent trace here - nothing is ever silently overwritten."""
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().isoformat(timespec="seconds")
    cur.execute(
        "INSERT INTO audit_logs (table_name, record_id, field_changed, old_value, new_value, changed_by, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (table_name, record_id, field_changed, str(old_value), str(new_value), changed_by, now),
    )
    conn.commit()
    conn.close()


def _next_daily_code(cur, table: str, code_column: str, prefix: str) -> str:
    """JOB-20260902-0001 style code: prefix + today's date + a daily sequence."""
    today_str = datetime.now().strftime("%Y%m%d")
    cur.execute(f"SELECT COUNT(*) FROM {table} WHERE date(created_at) = date('now', 'localtime')")
    seq = cur.fetchone()[0] + 1
    return f"{prefix}-{today_str}-{seq:04d}"


# ---- Transactions (New Job / Transactions / Pending Records) ----

def create_transaction(worker_id: int, service_id: int, quantity: int, rate: float,
                        payment_method: str, status: str,
                        customer_reference: str = None, notes: str = None,
                        advance_amount: float = 0):
    """Saves one job. payment_status is derived from status: a job marked
    Completed at entry time is assumed paid on the spot (matches how a
    walk-in shop works); Pending/In Progress jobs are assumed unpaid until
    someone marks them paid later from Pending Records - unless an advance
    was taken, which is tracked separately (advance_amount) and doesn't by
    itself flip payment_status to Paid, since a balance may still be owed.
    Returns (id, transaction_code)."""
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().isoformat(timespec="seconds")
    amount = round(quantity * rate, 2)
    payment_status = "Paid" if status == "Completed" else "Unpaid"
    code = _next_daily_code(cur, "transactions", "transaction_code", "JOB")

    cur.execute(
        "INSERT INTO transactions "
        "(transaction_code, worker_id, service_id, quantity, amount, rate, payment_method, "
        " status, payment_status, customer_reference, notes, advance_amount, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (code, worker_id, service_id, quantity, amount, rate, payment_method,
         status, payment_status, customer_reference, notes, advance_amount, now, now),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id, code


def get_transactions(date_filter: str = "today", worker_id: int = None):
    """date_filter: 'today' | 'yesterday' | 'week' | None (all)"""
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT t.*, u.name AS worker_name, s.name AS service_name
        FROM transactions t
        JOIN users u ON u.id = t.worker_id
        JOIN services s ON s.id = t.service_id
        WHERE 1=1
    """
    params = []
    if date_filter == "today":
        query += " AND date(t.created_at) = date('now', 'localtime')"
    elif date_filter == "yesterday":
        query += " AND date(t.created_at) = date('now', '-1 day', 'localtime')"
    elif date_filter == "week":
        query += " AND date(t.created_at) >= date('now', '-7 day', 'localtime')"
    if worker_id is not None:
        query += " AND t.worker_id = ?"
        params.append(worker_id)
    query += " ORDER BY t.created_at DESC"
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_today_transaction_totals():
    """Totals block shown at the top of the Transactions screen."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(CASE WHEN payment_status='Paid' THEN amount ELSE 0 END), 0),
               COALESCE(SUM(CASE WHEN payment_status='Paid' AND payment_method='Cash' THEN amount ELSE 0 END), 0),
               COALESCE(SUM(CASE WHEN payment_status='Paid' AND payment_method='UPI' THEN amount ELSE 0 END), 0)
        FROM transactions
        WHERE date(created_at) = date('now', 'localtime') AND status != 'Cancelled'
    """)
    jobs, sales, cash, upi = cur.fetchone()
    conn.close()
    return {"jobs": jobs, "sales": sales, "cash": cash, "upi": upi}


def get_pending_transactions(worker_id: int = None):
    """Anything not yet both Completed and Paid (and not Cancelled) - what
    the Pending Records screen shows. Pass worker_id to scope to one
    worker's own pending jobs only (this is the fix for the privacy gap
    where any worker could previously see every worker's pending jobs)."""
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT t.*, u.name AS worker_name, s.name AS service_name
        FROM transactions t
        JOIN users u ON u.id = t.worker_id
        JOIN services s ON s.id = t.service_id
        WHERE t.status != 'Cancelled' AND NOT (t.status = 'Completed' AND t.payment_status = 'Paid')
    """
    params = []
    if worker_id is not None:
        query += " AND t.worker_id = ?"
        params.append(worker_id)
    query += " ORDER BY t.created_at DESC"
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def mark_transaction_completed(transaction_id: int, changed_by: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT status FROM transactions WHERE id = ?", (transaction_id,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        return
    old_status = row["status"]
    now = datetime.now().isoformat(timespec="seconds")
    cur.execute("UPDATE transactions SET status = 'Completed', updated_at = ? WHERE id = ?", (now, transaction_id))
    conn.commit()
    conn.close()
    if old_status != "Completed":
        log_audit("transactions", transaction_id, "status", old_status, "Completed", changed_by)


def mark_transaction_in_progress(transaction_id: int, changed_by: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT status FROM transactions WHERE id = ?", (transaction_id,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        return
    old_status = row["status"]
    now = datetime.now().isoformat(timespec="seconds")
    cur.execute("UPDATE transactions SET status = 'In Progress', updated_at = ? WHERE id = ?", (now, transaction_id))
    conn.commit()
    conn.close()
    if old_status != "In Progress":
        log_audit("transactions", transaction_id, "status", old_status, "In Progress", changed_by)


def cancel_transaction(transaction_id: int, reason: str, changed_by: int):
    """Soft-cancel only - the row is never deleted, just marked Cancelled
    and excluded from financial totals and Pending Records. Matches the
    'prefer soft-delete for financial records' rule."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT status FROM transactions WHERE id = ?", (transaction_id,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        return
    old_status = row["status"]
    now = datetime.now().isoformat(timespec="seconds")
    cur.execute(
        "UPDATE transactions SET status = 'Cancelled', notes = COALESCE(notes || ' | ', '') || ?, updated_at = ? WHERE id = ?",
        (f"Cancelled: {reason}", now, transaction_id),
    )
    conn.commit()
    conn.close()
    log_audit("transactions", transaction_id, "status", old_status, f"Cancelled ({reason})", changed_by)


def mark_transaction_paid(transaction_id: int, changed_by: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT payment_status FROM transactions WHERE id = ?", (transaction_id,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        return
    old_status = row["payment_status"]
    now = datetime.now().isoformat(timespec="seconds")
    cur.execute("UPDATE transactions SET payment_status = 'Paid', updated_at = ? WHERE id = ?", (now, transaction_id))
    conn.commit()
    conn.close()
    if old_status != "Paid":
        log_audit("transactions", transaction_id, "payment_status", old_status, "Paid", changed_by)


# ---- Expenses ----

def create_expense(worker_id: int, category: str, reason: str, amount: float,
                    payment_method: str, notes: str = None):
    """Returns (id, expense_code)."""
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().isoformat(timespec="seconds")
    code = _next_daily_code(cur, "expenses", "expense_code", "EXP")
    cur.execute(
        "INSERT INTO expenses "
        "(expense_code, worker_id, category, purpose, amount, payment_method, status, notes, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 'Recorded', ?, ?, ?)",
        (code, worker_id, category, reason, amount, payment_method, notes, now, now),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id, code


def get_expenses_today(worker_id: int = None):
    """Pass worker_id to scope to one worker's own expenses only (fixes a
    privacy gap where the Expense screen's running list showed everyone's
    expenses, not just the logged-in worker's)."""
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT e.*, u.name AS worker_name
        FROM expenses e
        JOIN users u ON u.id = e.worker_id
        WHERE date(e.created_at) = date('now', 'localtime')
    """
    params = []
    if worker_id is not None:
        query += " AND e.worker_id = ?"
        params.append(worker_id)
    query += " ORDER BY e.created_at DESC"
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return rows


# ---- Daily Closing ----

def get_daily_totals_for_closing():
    """Cash sales (paid), UPI sales (paid), and CASH-ONLY expenses for today -
    exactly the inputs the Daily Closing formula needs."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(SUM(CASE WHEN payment_method='Cash' AND payment_status='Paid' THEN amount ELSE 0 END), 0),
               COALESCE(SUM(CASE WHEN payment_method='UPI' AND payment_status='Paid' THEN amount ELSE 0 END), 0)
        FROM transactions
        WHERE date(created_at) = date('now', 'localtime') AND status != 'Cancelled'
    """)
    cash_sales, upi_sales = cur.fetchone()

    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM expenses
        WHERE date(created_at) = date('now', 'localtime') AND payment_method = 'Cash'
    """)
    cash_expenses = cur.fetchone()[0]
    conn.close()
    return {"cash_sales": cash_sales, "upi_sales": upi_sales, "cash_expenses": cash_expenses}


def get_daily_closing(closing_date: str = None):
    """Fetch a previously saved closing record for a date (defaults to today), if any."""
    conn = get_connection()
    cur = conn.cursor()
    if closing_date:
        cur.execute("SELECT * FROM daily_closing WHERE closing_date = ?", (closing_date,))
    else:
        cur.execute("SELECT * FROM daily_closing WHERE closing_date = date('now', 'localtime')")
    row = cur.fetchone()
    conn.close()
    return row


def save_daily_closing(opening_cash: float, expected_cash: float, actual_cash: float,
                        difference: float, closed_by: int):
    """One row per date - saving the same day again updates that row rather
    than creating a duplicate (closing_date is UNIQUE)."""
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().isoformat(timespec="seconds")
    cur.execute("""
        INSERT INTO daily_closing (closing_date, expected_cash, actual_cash, difference, closed_by, created_at)
        VALUES (date('now', 'localtime'), ?, ?, ?, ?, ?)
        ON CONFLICT(closing_date) DO UPDATE SET
            expected_cash = excluded.expected_cash,
            actual_cash = excluded.actual_cash,
            difference = excluded.difference,
            closed_by = excluded.closed_by
    """, (expected_cash, actual_cash, difference, closed_by, now))
    conn.commit()
    conn.close()


# =====================================================================
# PHASE 3 — Worker management, service/rate management, PIN security,
# audit log viewing, and per-app usage totals (for the redesigned
# foreground-window Activity screen).
# =====================================================================

# ---- Worker management (Admin only) ----

def get_all_workers_admin():
    """Every worker/admin account regardless of active status - Worker
    Management needs to show Inactive/On Leave people too, not just who
    can currently log in."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users ORDER BY role, name")
    rows = cur.fetchall()
    conn.close()
    return rows


def create_worker(name: str, pin: str, role: str, employee_id: str = None):
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().isoformat(timespec="seconds")
    cur.execute(
        "INSERT INTO users (name, pin_hash, role, active, status, employee_id, must_change_pin, created_at, updated_at) "
        "VALUES (?, ?, ?, 1, 'Active', ?, 0, ?, ?)",
        (name, hash_pin(pin), role, employee_id, now, now),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def update_worker(user_id: int, name: str, employee_id: str, changed_by: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, employee_id FROM users WHERE id = ?", (user_id,))
    old = cur.fetchone()
    now = datetime.now().isoformat(timespec="seconds")
    cur.execute(
        "UPDATE users SET name = ?, employee_id = ?, updated_at = ? WHERE id = ?",
        (name, employee_id, now, user_id),
    )
    conn.commit()
    conn.close()
    if old and old["name"] != name:
        log_audit("users", user_id, "name", old["name"], name, changed_by)


def set_worker_status(user_id: int, status: str, changed_by: int):
    """status: 'Active' | 'On Leave' | 'Inactive'. Active is the only
    status that can log in - On Leave and Inactive both block login
    (active=0), but stay visually distinct in Worker Management."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT status FROM users WHERE id = ?", (user_id,))
    old = cur.fetchone()
    now = datetime.now().isoformat(timespec="seconds")
    active = 1 if status == "Active" else 0
    cur.execute(
        "UPDATE users SET status = ?, active = ?, updated_at = ? WHERE id = ?",
        (status, active, now, user_id),
    )
    conn.commit()
    conn.close()
    if old and old["status"] != status:
        log_audit("users", user_id, "status", old["status"], status, changed_by)


def admin_reset_pin(user_id: int, new_pin: str, changed_by: int, require_change: bool = True):
    """Admin resets someone's PIN (e.g. for a shift-cover worker or a
    forgotten PIN). require_change=True forces a change prompt at next
    login, so a temporary PIN can't stay in permanent use unnoticed."""
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().isoformat(timespec="seconds")
    cur.execute(
        "UPDATE users SET pin_hash = ?, must_change_pin = ?, updated_at = ? WHERE id = ?",
        (hash_pin(new_pin), 1 if require_change else 0, now, user_id),
    )
    conn.commit()
    conn.close()
    log_audit("users", user_id, "pin_hash", "(hidden)", "(reset by admin)", changed_by)


def change_own_pin(user_id: int, current_pin: str, new_pin: str) -> bool:
    """Worker/Admin changes their own PIN. Returns False if current_pin is
    wrong (and nothing is changed); True on success."""
    user = verify_login(user_id, current_pin)
    if user is None:
        return False
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().isoformat(timespec="seconds")
    cur.execute(
        "UPDATE users SET pin_hash = ?, must_change_pin = 0, updated_at = ? WHERE id = ?",
        (hash_pin(new_pin), now, user_id),
    )
    conn.commit()
    conn.close()
    log_audit("users", user_id, "pin_hash", "(hidden)", "(changed by self)", user_id)
    return True


# ---- Service / rate management (Admin only) ----

def get_all_services_admin():
    """Every service regardless of active status, for the management screen."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM services ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return rows


def create_service(name: str, rate: float, changed_by: int):
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().isoformat()
    cur.execute(
        "INSERT INTO services (name, rate, active, created_at, updated_at) VALUES (?, ?, 1, ?, ?)",
        (name, rate, now, now),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    log_audit("services", row_id, "created", None, f"{name} @ Rs{rate}", changed_by)
    return row_id


def update_service_rate(service_id: int, new_rate: float, changed_by: int):
    """Existing transactions already stored their own rate at the time they
    were created, so changing a service's rate here never alters past
    records - only future New Job entries will see the new price."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, rate FROM services WHERE id = ?", (service_id,))
    old = cur.fetchone()
    now = datetime.now().isoformat()
    cur.execute("UPDATE services SET rate = ?, updated_at = ? WHERE id = ?", (new_rate, now, service_id))
    conn.commit()
    conn.close()
    if old and old["rate"] != new_rate:
        log_audit("services", service_id, "rate", old["rate"], new_rate, changed_by)


def set_service_active(service_id: int, active: bool, changed_by: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, active FROM services WHERE id = ?", (service_id,))
    old = cur.fetchone()
    now = datetime.now().isoformat()
    cur.execute("UPDATE services SET active = ?, updated_at = ? WHERE id = ?", (1 if active else 0, now, service_id))
    conn.commit()
    conn.close()
    if old and bool(old["active"]) != active:
        log_audit("services", service_id, "active", bool(old["active"]), active, changed_by)


# ---- Audit log viewer (Admin only) ----

def get_audit_logs(table_name: str = None, limit: int = 200):
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT al.*, u.name AS changed_by_name
        FROM audit_logs al
        LEFT JOIN users u ON u.id = al.changed_by
        WHERE 1=1
    """
    params = []
    if table_name:
        query += " AND al.table_name = ?"
        params.append(table_name)
    query += " ORDER BY al.id DESC LIMIT ?"
    params.append(limit)
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return rows


# ---- Activity usage totals (for the redesigned Activity screen) ----

def get_today_app_usage_totals(worker_id: int = None):
    """Total time spent per application today, longest first - powers
    'TODAY'S APPLICATION USAGE'. Only counts activity that has actually
    ended (has a duration); the one currently open app is tracked live in
    memory by the monitor itself, not from this historical query."""
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT app_name, SUM(duration_seconds) AS total_seconds
        FROM application_activity
        WHERE date(start_time) = date('now', 'localtime') AND duration_seconds IS NOT NULL
    """
    params = []
    if worker_id is not None:
        query += " AND worker_id = ?"
        params.append(worker_id)
    query += " GROUP BY app_name ORDER BY total_seconds DESC"
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return rows
