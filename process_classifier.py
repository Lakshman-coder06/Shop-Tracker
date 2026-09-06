"""
process_classifier.py
----------------------
Decides how a running process should be treated:

  "system" -> Windows background/service process. Never shown to the worker.
  "self"   -> Shop Tracker's own process. Excluded so it can't show up in
              its own activity feed.
  "user"   -> Everything else. This is what gets shown as activity.

IMPORTANT: this is NOT a whitelist of allowed apps. Anything that isn't
recognized as system/self falls through to "user" and IS monitored. This
is what lets the monitor detect apps that didn't exist when this file was
written, without changing any code - Admin only ever needs to touch
SYSTEM_PROCESS_NAMES below if a specific background process turns out to
be noisy on your shop PC.

FRIENDLY_NAMES is separate and purely cosmetic - a nicer display name for
common programs. Anything not listed still gets shown, just using a
cleaned-up version of its file name (e.g. "SomeNewApp.exe" -> "SomeNewApp").

NOTE (Phase 3): activity_monitor.py switched from process-enumeration to
foreground-window detection, which makes classify_process() below no
longer the active filtering mechanism - a background process can no
longer become "the foreground window" in the first place, so the
system/user distinction it draws isn't needed for filtering anymore.
It's left in place (harmless, still correct) in case a future feature
wants it. friendly_name() is still actively used for display names.
"""

from __future__ import annotations  # lets us use modern type hints on older Python too

import os

# Windows background/service processes that should never appear as
# "activity" - they run constantly regardless of what the worker is doing.
# If a specific background process ever floods the activity feed on your
# real shop PC, add its process name here (lowercase, from Task Manager's
# "Details" tab) - nothing else needs to change.
SYSTEM_PROCESS_NAMES = {
    "svchost.exe", "services.exe", "lsass.exe", "csrss.exe", "wininit.exe",
    "winlogon.exe", "smss.exe", "dwm.exe", "taskhostw.exe", "runtimebroker.exe",
    "dllhost.exe", "conhost.exe", "fontdrvhost.exe", "sihost.exe", "ctfmon.exe",
    "searchindexer.exe", "searchapp.exe", "searchui.exe", "shellexperiencehost.exe",
    "startmenuexperiencehost.exe", "applicationframehost.exe", "spoolsv.exe",
    "wmiprvse.exe", "msmpeng.exe", "securityhealthservice.exe",
    "securityhealthsystray.exe", "audiodg.exe", "registry", "system",
    "system idle process", "memcompression", "textinputhost.exe", "lockapp.exe",
    "logonui.exe", "backgroundtaskhost.exe", "systemsettings.exe", "wudfhost.exe",
    "widgets.exe", "widgetservice.exe", "crashpad_handler.exe", "consent.exe",
    "usernotificationservice.exe", "uhssvc.exe", "explorer.exe",
    # explorer.exe is deliberately listed here: it's the Windows shell and
    # runs continuously, so it's excluded from the generic process feed.
    # It's tracked separately, at the window level, in activity_monitor.py -
    # that's the only way to catch individual File Explorer windows opening
    # and closing (see the module docstring there for why).
}

# Cosmetic only - not a filter. Extend freely; anything missing still works.
FRIENDLY_NAMES = {
    "chrome.exe": "Google Chrome",
    "msedge.exe": "Microsoft Edge",
    "firefox.exe": "Mozilla Firefox",
    "winword.exe": "Microsoft Word",
    "excel.exe": "Microsoft Excel",
    "powerpnt.exe": "Microsoft PowerPoint",
    "acrord32.exe": "Adobe Reader",
    "acrobat.exe": "Adobe Acrobat",
    "photoshop.exe": "Adobe Photoshop",
    "illustrator.exe": "Adobe Illustrator",
    "coreldrw.exe": "CorelDRAW",
    "notepad.exe": "Notepad",
    "mspaint.exe": "Paint",
    "calculator.exe": "Calculator",
    "calc.exe": "Calculator",
    "vlc.exe": "VLC Media Player",
    "gimp-2.10.exe": "GIMP",
    "explorer.exe": "File Explorer",
}


def friendly_name(exe_name: str) -> str:
    """Turn 'chrome.exe' into 'Google Chrome', or 'SomeNewApp.exe' into
    'SomeNewApp' if we've never heard of it."""
    key = exe_name.lower()
    if key in FRIENDLY_NAMES:
        return FRIENDLY_NAMES[key]
    base = exe_name[:-4] if key.endswith(".exe") else exe_name
    return base.replace("_", " ").replace("-", " ").strip().title() or exe_name


def classify_process(exe_name: str, exe_path: str | None, is_self: bool = False) -> str:
    """
    Returns "system", "self", or "user". No hardcoded whitelist of allowed
    apps - only a blocklist of known background processes. Everything else
    defaults to "user", which is what makes new/unknown apps get detected
    automatically.
    """
    if is_self:
        return "self"

    key = (exe_name or "").lower()
    if key in SYSTEM_PROCESS_NAMES:
        return "system"

    if exe_path:
        p = exe_path.lower().replace("/", "\\")
        # Programs living directly inside the Windows system folders are
        # almost always background components, not something a worker
        # deliberately opened. Programs the worker opens normally live
        # under Program Files, AppData, etc.
        if p.startswith("c:\\windows\\") or "\\windows\\system32\\" in p or "\\windows\\syswow64\\" in p:
            return "system"

    return "user"
