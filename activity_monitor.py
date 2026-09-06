"""
activity_monitor.py
--------------------
PHASE 3 REWRITE: foreground-window detection, replacing Phase 1.5's
process-enumeration approach.

WHY THE CHANGE: Phase 1.5 watched every running process and classified
each as system/user - but "is this process running" isn't the same as
"is the worker actually using this." A program can sit open in the
background for hours without being touched. This version instead asks
Windows one simple question, repeatedly: "which window is currently in
the foreground - the one the worker is actually looking at and typing
into?" That is a much more accurate proxy for real usage, and as a bonus
it completely solves the File Explorer problem from Phase 1.5 in a
simpler way: a File Explorer folder window genuinely DOES become the
foreground window when you click into it, so no separate window-counting
watcher is needed anymore - one mechanism now covers every application.

HOW IT WORKS: every 2 seconds, ask Windows for the foreground window's
owning process (via win32gui.GetForegroundWindow +
win32process.GetWindowThreadProcessId + psutil). If it's a different
program than the one currently being tracked, close out the old entry and
open a new one - this naturally produces exactly the "Photoshop opened ->
Photoshop closed, Chrome opened -> ..." timeline from the spec, driven by
real window switches instead of process start/stop.

TWO DELIBERATE EXCLUSIONS (not tracked as "activity"):
 - Shop Tracker's own windows. Otherwise every click back into Shop
   Tracker to save a job would interrupt whatever was being tracked
   before it. Instead, Shop Tracker's own foreground time is transparent:
   the previously-tracked app just keeps running underneath it, and gets
   properly closed out next time a DIFFERENT real app comes forward.
 - The Windows desktop/taskbar/Start menu (explorer.exe's shell chrome,
   as opposed to an actual File Explorer folder window - the two are
   told apart by window class name, see FILE_EXPLORER_WINDOW_CLASS).

WHAT THIS NEVER DOES: no keylogging, no clipboard/password capture, no
screen recording, no reading of typed text or web page contents. It only
ever reads (a) which window is in front, (b) that window's process name
and title, and (c) the clock. Window TITLE is captured (per the request)
since it can help tell activities apart, but is not shown prominently in
the main views because it can contain customer/document names - it's only
surfaced in Activity Details, and never sent anywhere.

TESTABILITy NOTE: the actual Windows API calls (_default_foreground_info)
can only be exercised on a real Windows machine. Everything else here -
the switching logic, the Shop-Tracker/desktop exclusions, multi-step
sequences - is decoupled from that one function via the `foreground_provider`
constructor argument, so it's fully testable by substituting a fake
sequence of foreground windows. See the test suite for exactly that.
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
    import win32gui
    import win32process
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

POLL_INTERVAL_MS = 2000
FILE_EXPLORER_WINDOW_CLASS = "CabinetWClass"  # a real File Explorer folder window
SELF_WINDOW_TITLE_HINT = "Shop Work & Collection Tracker"  # matches every window title this app sets


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


def _default_foreground_info():
    """The real Windows implementation. Returns a dict with exe_name,
    window_title, class_name, pid - or None if nothing meaningful can be
    determined right now (nothing is foreground, access denied, etc).
    This is the ONLY function in this file that talks to actual Windows
    APIs - everything else takes its output as plain data."""
    if not (WIN32_AVAILABLE and PSUTIL_AVAILABLE):
        return None
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        class_name = win32gui.GetClassName(hwnd)
        window_title = win32gui.GetWindowText(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if not pid:
            return None
        proc = psutil.Process(pid)
        exe_name = proc.name()
        return {"exe_name": exe_name, "window_title": window_title, "class_name": class_name, "pid": pid}
    except Exception:
        return None


class ForegroundWindowWatcher(QObject):
    """Tracks the single application currently in the foreground for one
    worker's session. See the module docstring for the full explanation."""

    activity_started = Signal(str)
    activity_stopped = Signal(str, int)

    def __init__(self, worker_id, computer_name, windows_username, foreground_provider=None):
        super().__init__()
        self.worker_id = worker_id
        self.computer_name = computer_name
        self.windows_username = windows_username
        # Dependency injection point: production uses the real Windows call;
        # tests substitute a fake sequence of foreground-window snapshots.
        self.foreground_provider = foreground_provider or _default_foreground_info
        self.self_pid = os.getpid()

        self.current_key = None        # lowercase exe name of the app currently tracked, or None
        self.current_friendly = None
        self.current_row_id = None
        self.current_start = None
        self.current_title = None

        self.timer = QTimer()
        self.timer.timeout.connect(self.poll)

        self.last_scan_time = None
        self.last_info = None
        # A custom provider (tests) doesn't need the real Windows libraries at
        # all - only the default, real-Windows path depends on them.
        self.available = (foreground_provider is not None) or (WIN32_AVAILABLE and PSUTIL_AVAILABLE)

    def start(self):
        if not self.available:
            return
        self.poll()
        self.timer.start(POLL_INTERVAL_MS)

    def stop(self):
        self.timer.stop()
        if self.current_key is not None:
            self._end_current(datetime.now())

    def poll(self):
        if not self.available:
            return
        try:
            info = self.foreground_provider()
        except Exception:
            return  # try again next cycle rather than crashing
        self.last_scan_time = datetime.now()
        self.last_info = info
        now = self.last_scan_time

        if info is None:
            return  # couldn't determine foreground window this cycle - leave state as-is

        if info.get("pid") == self.self_pid:
            return  # Shop Tracker itself is in front - transparent, don't touch tracked state

        exe_name = info.get("exe_name") or ""
        class_name = info.get("class_name") or ""
        key = exe_name.lower()

        if key == "explorer.exe" and class_name != FILE_EXPLORER_WINDOW_CLASS:
            # This is the desktop, taskbar, or Start menu - not a real app
            # the worker opened. Treat it like nothing meaningful is in front.
            self._end_current(now)
            return

        friendly = "File Explorer" if key == "explorer.exe" else process_classifier.friendly_name(exe_name)

        if self.current_key == key:
            return  # same app still in front - nothing changed

        self._end_current(now)
        self._start_new(key, friendly, info.get("window_title"), now)

    def _end_current(self, end_time):
        if self.current_key is None:
            return
        database.log_activity_end(self.current_row_id, self.current_start, end_time)
        duration = int((end_time - self.current_start).total_seconds())
        self.activity_stopped.emit(self.current_friendly, duration)
        self.current_key = None
        self.current_friendly = None
        self.current_row_id = None
        self.current_start = None
        self.current_title = None

    def _start_new(self, key, friendly, window_title, start_time):
        row_id = database.log_activity_start(
            self.worker_id, friendly, key, start_time,
            self.computer_name, self.windows_username, window_title,
        )
        self.current_key = key
        self.current_friendly = friendly
        self.current_row_id = row_id
        self.current_start = start_time
        self.current_title = window_title
        self.activity_started.emit(friendly)

    def current_app(self):
        """Returns (friendly_name, start_time, window_title) for the Live
        Activity screen's 'Current Application' card, or None if nothing
        is currently being tracked."""
        if self.current_key is None:
            return None
        return (self.current_friendly, self.current_start, self.current_title)

    def diagnostic_status(self):
        if not self.available:
            missing = []
            if not WIN32_AVAILABLE:
                missing.append("pywin32")
            if not PSUTIL_AVAILABLE:
                missing.append("psutil")
            return f"UNAVAILABLE (missing: {', '.join(missing)} — run: pip install " + " ".join(missing) + ")"
        return "ACTIVE (foreground-window detection)"


class ActivityMonitor(QObject):
    """Thin facade so the rest of the app (Dashboard, Live Activity,
    Diagnostics) has one simple object to talk to, regardless of what's
    happening underneath."""

    activity_started = Signal(str)
    activity_stopped = Signal(str, int)

    def __init__(self, worker_id, foreground_provider=None):
        super().__init__()
        self.worker_id = worker_id
        self.computer_name = _safe_computer_name()
        self.windows_username = _safe_username()

        self.watcher = ForegroundWindowWatcher(
            worker_id, self.computer_name, self.windows_username, foreground_provider,
        )
        self.watcher.activity_started.connect(self.activity_started.emit)
        self.watcher.activity_stopped.connect(self.activity_stopped.emit)

    def start(self):
        self.watcher.start()

    def stop(self):
        self.watcher.stop()

    def current_app(self):
        return self.watcher.current_app()

    def insert_test_event(self):
        """Inserts a fake 'Test Event' that auto-closes after 5 seconds -
        NOT real detection, only proves the recording+display pipeline
        works. Clearly labeled wherever it's shown."""
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
        current = self.current_app()
        return {
            "monitoring_active": self.watcher.timer.isActive(),
            "available": self.watcher.available,
            "status_text": self.watcher.diagnostic_status(),
            "last_scan": self.watcher.last_scan_time,
            "current_app": current[0] if current else None,
            "computer_name": self.computer_name,
            "windows_username": self.windows_username,
            "worker_id": self.worker_id,
            "db_connected": database.check_db_connection(),
            "last_activity_saved": database.get_last_activity_saved(),
            "poll_interval_seconds": POLL_INTERVAL_MS / 1000,
        }
