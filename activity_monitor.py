"""
activity_monitor.py
--------------------
Detects application activity for the currently logged-in worker, using
TWO separate mechanisms, because Windows applications work two different
ways:

1. ProcessActivityWatcher - for normal programs (Chrome, Word, Photoshop,
   Notepad, VLC, and anything else). These each run as their own process,
   so we can watch the list of running processes and notice when a new
   one appears/disappears. This is DYNAMIC: it classifies every process
   it sees via process_classifier.py rather than checking a fixed list,
   so it detects programs that didn't exist when this file was written.

2. FileExplorerWindowWatcher - for File Explorer specifically. explorer.exe
   is the Windows shell - it draws the taskbar and desktop and is already
   running before Shop Tracker starts, for as long as you're logged into
   Windows. Opening a folder doesn't start a new process, so watcher #1
   can never see File Explorer "start" or "stop". The only way to detect
   an actual File Explorer window opening/closing is to watch WINDOWS
   directly: every normal File Explorer folder window has had the window
   class name "CabinetWClass" since Windows 7. This watcher counts how
   many windows with that class exist, the same way watcher #1 counts
   processes - grouped, not per-window, to avoid a flood of entries when
   several folder windows are open at once.

Both watchers write into the same 'application_activity' table via
database.log_activity_start / log_activity_end - no separate table.

WHAT THIS DOES: reads (a) the list of running process names/paths, and
(b) the list of visible top-level window handles + their class names.
That's it.

WHAT THIS NEVER DOES:
 - No keylogging, no password/clipboard capture
 - No screen recording, no webcam/microphone access
 - No reading of window TITLES, file contents, or browser history/URLs
 - Only runs while a worker is logged into Shop Tracker

ActivityMonitor (at the bottom) is the single object the rest of the app
talks to - it owns exactly one of each watcher and combines their
results, so there is never more than one poller running per login and
never a risk of duplicate records.
"""

from PySide6.QtCore import QObject, QTimer, Signal
from datetime import datetime
import os
import platform
import getpass

import database
import process_classifier

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import win32gui  # part of pywin32 - Windows only
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

POLL_INTERVAL_MS = 2000  # check every 2 seconds
FILE_EXPLORER_WINDOW_CLASS = "CabinetWClass"  # File Explorer folder window class since Windows 7


def _safe_computer_name():
    try:
        return platform.node() or None
    except Exception:
        return None


def _safe_username():
    try:
        return getpass.getuser() or None
    except Exception:
        return None


# =====================================================================
# Watcher 1: normal processes (dynamic, no hardcoded app list)
# =====================================================================

class ProcessActivityWatcher(QObject):
    """
    Every poll: lists all running processes, classifies each one, and
    treats "at least one process with this executable name is running"
    as one activity - regardless of how many individual processes that
    program actually uses. This is what makes multi-process programs
    like Chrome show up as ONE entry instead of dozens.
    """

    activity_started = Signal(str)
    activity_stopped = Signal(str, int)

    def __init__(self, worker_id, computer_name, windows_username):
        super().__init__()
        self.worker_id = worker_id
        self.computer_name = computer_name
        self.windows_username = windows_username
        self.running = {}  # exe_name_lower -> {"friendly": str, "start_time": datetime, "row_id": int}
        self.timer = QTimer()
        self.timer.timeout.connect(self.poll)
        self.self_pid = os.getpid()

        self.last_scan_time = None
        self.last_process_count = 0
        self.last_user_app_count = 0
        self.last_error = None

    def start(self):
        if not PSUTIL_AVAILABLE:
            return
        self.poll()
        self.timer.start(POLL_INTERVAL_MS)

    def stop(self):
        self.timer.stop()
        now = datetime.now()
        for exe_key in list(self.running.keys()):
            self._end(exe_key, now)

    def poll(self):
        if not PSUTIL_AVAILABLE:
            return
        try:
            procs = list(psutil.process_iter(["pid", "name", "exe"]))
        except Exception as e:
            self.last_error = str(e)
            return  # try again next cycle rather than crashing

        self.last_scan_time = datetime.now()
        self.last_process_count = len(procs)

        current_user_apps = {}  # exe_name_lower -> friendly name
        for proc in procs:
            try:
                name = proc.info.get("name") or ""
                if not name:
                    continue
                exe_path = proc.info.get("exe")
                is_self = proc.info.get("pid") == self.self_pid
                category = process_classifier.classify_process(name, exe_path, is_self)
                if category == "user":
                    current_user_apps[name.lower()] = process_classifier.friendly_name(name)
            except Exception:
                continue  # a single odd process should never break the whole scan

        self.last_user_app_count = len(current_user_apps)
        now = datetime.now()

        for exe_key, friendly in current_user_apps.items():
            if exe_key not in self.running:
                row_id = database.log_activity_start(
                    self.worker_id, friendly, exe_key, now,
                    self.computer_name, self.windows_username,
                )
                self.running[exe_key] = {"friendly": friendly, "start_time": now, "row_id": row_id}
                self.activity_started.emit(friendly)

        for exe_key in list(self.running.keys()):
            if exe_key not in current_user_apps:
                self._end(exe_key, now)

    def _end(self, exe_key, end_time):
        info = self.running.pop(exe_key, None)
        if info is None:
            return
        database.log_activity_end(info["row_id"], info["start_time"], end_time)
        duration = int((end_time - info["start_time"]).total_seconds())
        self.activity_stopped.emit(info["friendly"], duration)

    def currently_open(self):
        return [(v["friendly"], v["start_time"]) for v in self.running.values()]


# =====================================================================
# Watcher 2: File Explorer, at the window level (Windows only)
# =====================================================================

class FileExplorerWindowWatcher(QObject):
    """See the module docstring above for why this exists as a separate,
    window-level watcher instead of being handled by watcher #1."""

    activity_started = Signal(str)
    activity_stopped = Signal(str, int)

    def __init__(self, worker_id, computer_name, windows_username):
        super().__init__()
        self.worker_id = worker_id
        self.computer_name = computer_name
        self.windows_username = windows_username
        self.open_hwnds = set()
        self.first_open_time = None
        self.row_id = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.poll)
        self.available = WIN32_AVAILABLE

    def start(self):
        if not self.available:
            return
        self.poll()
        self.timer.start(POLL_INTERVAL_MS)

    def stop(self):
        if not self.available:
            return
        self.timer.stop()
        if self.open_hwnds:
            self._close(datetime.now())

    def poll(self):
        if not self.available:
            return
        hwnds = set()
        try:
            def _enum(hwnd, _):
                if not win32gui.IsWindowVisible(hwnd):
                    return
                try:
                    cls = win32gui.GetClassName(hwnd)
                except Exception:
                    return
                if cls == FILE_EXPLORER_WINDOW_CLASS:
                    hwnds.add(hwnd)
            win32gui.EnumWindows(_enum, None)
        except Exception:
            return  # try again next cycle

        now = datetime.now()
        was_open = len(self.open_hwnds) > 0
        self.open_hwnds = hwnds
        is_open = len(self.open_hwnds) > 0

        if is_open and not was_open:
            self.first_open_time = now
            self.row_id = database.log_activity_start(
                self.worker_id, "File Explorer", "explorer.exe (window)", now,
                self.computer_name, self.windows_username,
            )
            self.activity_started.emit("File Explorer")
        elif not is_open and was_open:
            self._close(now)

    def _close(self, end_time):
        if self.row_id is not None and self.first_open_time is not None:
            database.log_activity_end(self.row_id, self.first_open_time, end_time)
            duration = int((end_time - self.first_open_time).total_seconds())
            self.activity_stopped.emit("File Explorer", duration)
        self.open_hwnds = set()
        self.row_id = None
        self.first_open_time = None

    def currently_open(self):
        if not self.open_hwnds or self.first_open_time is None:
            return []
        return [("File Explorer", self.first_open_time)]

    def diagnostic_status(self):
        if not self.available:
            return "UNAVAILABLE (pywin32 not installed — run: pip install pywin32)"
        return f"ACTIVE (window-class monitoring: {FILE_EXPLORER_WINDOW_CLASS})"


# =====================================================================
# Combined facade - this is the one object the rest of the app uses
# =====================================================================

class ActivityMonitor(QObject):
    """Owns exactly one ProcessActivityWatcher and one FileExplorerWindowWatcher,
    and presents them to the rest of the app as a single monitor with one
    start(), one stop(), and combined signals/queries."""

    activity_started = Signal(str)
    activity_stopped = Signal(str, int)

    def __init__(self, worker_id):
        super().__init__()
        self.worker_id = worker_id
        self.computer_name = _safe_computer_name()
        self.windows_username = _safe_username()

        self.process_watcher = ProcessActivityWatcher(worker_id, self.computer_name, self.windows_username)
        self.explorer_watcher = FileExplorerWindowWatcher(worker_id, self.computer_name, self.windows_username)

        self.process_watcher.activity_started.connect(self.activity_started.emit)
        self.process_watcher.activity_stopped.connect(self.activity_stopped.emit)
        self.explorer_watcher.activity_started.connect(self.activity_started.emit)
        self.explorer_watcher.activity_stopped.connect(self.activity_stopped.emit)

    def start(self):
        self.process_watcher.start()
        self.explorer_watcher.start()

    def stop(self):
        self.process_watcher.stop()
        self.explorer_watcher.stop()

    def currently_open(self):
        return self.process_watcher.currently_open() + self.explorer_watcher.currently_open()

    def insert_test_event(self):
        """Inserts a fake 'Test Application' activity that auto-closes after
        5 seconds. This is NOT real detection - it only proves the
        recording + display pipeline itself works, so you can tell a
        recording problem apart from a detection problem. Clearly labeled
        wherever it's shown."""
        now = datetime.now()
        row_id = database.log_activity_start(
            self.worker_id, "Test Event (synthetic)", "test.synthetic", now,
            self.computer_name, self.windows_username,
        )
        self.activity_started.emit("Test Event (synthetic)")

        def _end():
            end_time = datetime.now()
            database.log_activity_end(row_id, now, end_time)
            duration = int((end_time - now).total_seconds())
            self.activity_stopped.emit("Test Event (synthetic)", duration)

        QTimer.singleShot(5000, _end)

    def diagnostics(self):
        return {
            "monitoring_active": self.process_watcher.timer.isActive(),
            "psutil_available": PSUTIL_AVAILABLE,
            "last_scan": self.process_watcher.last_scan_time,
            "processes_detected": self.process_watcher.last_process_count,
            "user_apps_detected": self.process_watcher.last_user_app_count,
            "currently_open_count": len(self.currently_open()),
            "explorer_status": self.explorer_watcher.diagnostic_status(),
            "computer_name": self.computer_name,
            "windows_username": self.windows_username,
            "worker_id": self.worker_id,
            "db_connected": database.check_db_connection(),
            "last_activity_saved": database.get_last_activity_saved(),
            "poll_interval_seconds": POLL_INTERVAL_MS / 1000,
        }
