"""
activity_monitor.py
--------------------
Watches for a fixed list of applications being opened/closed while a
worker is logged in, and records the start/end times into the existing
'application_activity' table.

WHAT THIS IS: an activity audit. It only ever looks at two things -
(1) the list of currently running application process names, and
(2) the current time. That's it.

WHAT THIS IS NOT / NEVER DOES:
 - No keylogging
 - No password or clipboard capture
 - No screen recording, webcam, or microphone access
 - No reading of window titles, file contents, or browser history/URLs
 - It never runs unless a worker is actively logged into this app

HOW IT WORKS:
Every few seconds, it asks Windows "what processes are currently
running?" (this is the same kind of information Task Manager shows)
and checks the list against WATCHED_APPS below. If a watched app
wasn't running last check but is now, that's a "start" event. If it
was running last check but isn't anymore, that's a "stop" event.

EDITING THE WATCH LIST:
Add or remove entries in WATCHED_APPS. The key is the Windows process
name (visible in Task Manager's "Details" tab), the value is the
friendly name that gets stored/displayed.
"""

from PySide6.QtCore import QObject, QTimer, Signal
from datetime import datetime

import database

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


WATCHED_APPS = {
    "photoshop.exe": "Photoshop",
    "illustrator.exe": "Illustrator",
    "coreldrw.exe": "CorelDRAW",
    "winword.exe": "Microsoft Word",
    "excel.exe": "Microsoft Excel",
    "powerpnt.exe": "Microsoft PowerPoint",
    "acrord32.exe": "Adobe Reader",
    "acrobat.exe": "Adobe Acrobat",
    "mspaint.exe": "Paint",
    "notepad.exe": "Notepad",
    "chrome.exe": "Chrome",
    "msedge.exe": "Edge",
    "firefox.exe": "Firefox",
    "gimp-2.10.exe": "GIMP",
}

POLL_INTERVAL_MS = 3000  # check running applications every 3 seconds


class ActivityMonitor(QObject):
    """
    Runs on a QTimer on the main GUI thread (no background threads, so
    there's no risk of two things writing to the database at once).
    """

    activity_started = Signal(str)  # emits friendly app name when it starts
    activity_stopped = Signal(str, int)  # emits (friendly app name, duration_seconds) when it stops

    def __init__(self, worker_id):
        super().__init__()
        self.worker_id = worker_id
        self.running_apps = {}  # friendly_name -> {"start_time": datetime, "row_id": int}
        self.timer = QTimer()
        self.timer.timeout.connect(self.poll)

    def start(self):
        if not PSUTIL_AVAILABLE:
            return
        self.poll()
        self.timer.start(POLL_INTERVAL_MS)

    def stop(self):
        """Called on logout / app close - closes out any still-open activity rows."""
        self.timer.stop()
        now = datetime.now()
        for friendly_name in list(self.running_apps.keys()):
            self._end_activity(friendly_name, now)

    def poll(self):
        currently_running = set()
        try:
            for proc in psutil.process_iter(["name"]):
                pname = (proc.info.get("name") or "").lower()
                if pname in WATCHED_APPS:
                    currently_running.add(WATCHED_APPS[pname])
        except Exception:
            return  # if listing processes fails for any reason, just try again next cycle

        now = datetime.now()

        # Apps that weren't running last check but are now -> started
        for friendly_name in currently_running:
            if friendly_name not in self.running_apps:
                row_id = database.log_activity_start(self.worker_id, friendly_name, now)
                self.running_apps[friendly_name] = {"start_time": now, "row_id": row_id}
                self.activity_started.emit(friendly_name)

        # Apps that were running last check but aren't anymore -> stopped
        for friendly_name in list(self.running_apps.keys()):
            if friendly_name not in currently_running:
                self._end_activity(friendly_name, now)

    def _end_activity(self, friendly_name, end_time):
        info = self.running_apps.pop(friendly_name, None)
        if info is None:
            return
        database.log_activity_end(info["row_id"], info["start_time"], end_time)
        duration = int((end_time - info["start_time"]).total_seconds())
        self.activity_stopped.emit(friendly_name, duration)
