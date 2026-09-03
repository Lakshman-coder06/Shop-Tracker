# Shop Work & Collection Tracker — Phase 1 (Sessions + Activity Monitoring)

Building on the working Login + Dashboard, this phase adds:

1. **Worker session tracking** — every login/logout is recorded with exact
   timestamps and duration, in a new `worker_sessions` table.
2. **Application activity monitoring** — while a worker is logged in, the app
   watches for a fixed list of Windows programs (Photoshop, Word, Chrome,
   etc.) opening and closing, and records each start/end time into the
   existing `application_activity` table. This is shown live on the
   dashboard, and the dashboard clearly states that monitoring is on.

Login and the Dashboard's core layout are unchanged from Step 1 — same
buttons, same flow. The other menu buttons (New Job, Transactions, Expense,
etc.) still just show a "coming soon" message — those come in later phases.

**What is *not* recorded, ever:** keystrokes, passwords, clipboard contents,
screen recordings, webcam/mic, or website addresses/window titles. Only the
*name* of a watched application and *when* it started/stopped.

## Default logins (change these later in Settings, once we build that)

| Name     | PIN  | Role  |
|----------|------|-------|
| Worker 1 | 1111 | worker |
| Worker 2 | 2222 | worker |
| Worker 3 | 3333 | worker |
| Admin    | 9999 | admin  |

## How to run this on Windows

1. **Install Python** (if you don't have it): go to https://python.org/downloads,
   download the latest Python 3, and run the installer.
   ⚠️ On the first install screen, tick **"Add python.exe to PATH"** before clicking Install.

2. **Open Command Prompt** in the project folder:
   - Extract/unzip the `ShopTracker` folder somewhere, e.g. `C:\ShopTracker`
   - Open the folder in File Explorer, click the address bar, type `cmd`, press Enter.

3. **Create a virtual environment** (keeps this project's packages separate from everything else on your PC):
   ```
   python -m venv venv
   venv\Scripts\activate
   ```
   You should see `(venv)` appear at the start of the command line.

4. **Install the required package:**
   ```
   pip install -r requirements.txt
   ```
   This downloads PySide6 (the toolkit that draws the windows/buttons). It's
   a few hundred MB, so it may take a few minutes depending on your internet.

5. **Run the app:**
   ```
   python main.py
   ```
   A window titled "Shop Work & Collection Tracker - Login" should appear.

6. **Test it:**
   - Click "Worker 1", enter PIN `1111`, click LOGIN.
   - You should land on the Dashboard, showing your name, today's date, a
     "Session started: <time>" label, zeroed-out numbers, and 6 menu buttons.
   - Just below the numbers you should see a green line: "● Activity
     monitoring is ON", followed by the list of watched apps.
   - Open one of the watched apps (Notepad is the easiest to test with —
     it's built into Windows). Within a few seconds, a line should appear
     under "LIVE ACTIVITY" saying `<time> — Notepad started`.
   - Close Notepad. Within a few seconds another line should appear:
     `<time> — Notepad closed (Xs)`.
   - Click any menu button (e.g. "NEW JOB") — you should still see the
     "coming in a future step" popup.
   - Click "Log out" — you return to the login screen, and your session's
     logout time + duration get saved automatically.

A file called `shop_tracker.db` will appear in the folder the first time you
run it — that's your local database. It's created automatically; you don't
need to do anything with it.

## If something goes wrong

- **`'python' is not recognized...`** → Python isn't on PATH. Reinstall Python
  and make sure to tick "Add python.exe to PATH".
- **Install of PySide6 fails / times out** → check your internet connection
  and try `pip install -r requirements.txt` again.
- **Anything else** → take a screenshot of the exact error text in Command
  Prompt and send it over — that's all we need to fix it.

## Folder structure (what each file does)

```
ShopTracker/
├── main.py                 <- Run this file to start the app
├── database.py             <- Database, tables, login, sessions, activity logging
├── activity_monitor.py     <- Watches Windows processes for the watch list (NEW)
├── requirements.txt        <- PySide6 + psutil (NEW dependency)
├── README.md                <- This file
├── shop_tracker.db          <- Created automatically the first time you run it
└── ui/
    ├── __init__.py
    ├── login_window.py     <- The login screen (unchanged)
    └── dashboard_window.py <- Dashboard: now shows session info + live activity feed
```

## Editing the watched-application list

Open `activity_monitor.py` and edit the `WATCHED_APPS` dictionary near the
top. Each line maps a Windows process name (visible in Task Manager's
"Details" tab) to a friendly display name, e.g.:

```python
"photoshop.exe": "Photoshop",
```

Add or remove lines as needed — no other file needs to change.

## What's next (once you confirm this phase works)

Phase 2 will be **Quick Job Entry** — the big service buttons (Xerox, Print,
Passport Photo, etc.) that let a worker record a completed job in a few
seconds. Once that's in, the Dashboard's zeroed-out numbers will start
reflecting real sales.
