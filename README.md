# Shop Work & Collection Tracker — Step 1 (Login + Dashboard)

This is the **first working version**. It only does two things so far:

1. **Login** — pick your name, enter your PIN.
2. **Dashboard** — shows today's numbers (all zero for now) and the main menu.

Every other button on the dashboard (New Job, Transactions, Expense, etc.)
just shows a "coming soon" message when clicked. That's expected — we'll
build those one at a time in the next steps, once this part is confirmed
working on your laptop.

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
   - You should land on the Dashboard, showing your name, today's date,
     zeroed-out numbers, and 6 menu buttons.
   - Click any menu button (e.g. "NEW JOB") — you should see a small popup
     saying it's coming in a future step.
   - Click "Log out" — you should return to the login screen.

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
├── database.py             <- Creates the database, tables, and handles login
├── requirements.txt        <- The one package this project needs (PySide6)
├── README.md                <- This file
├── shop_tracker.db          <- Created automatically the first time you run it
└── ui/
    ├── __init__.py
    ├── login_window.py     <- The login screen
    └── dashboard_window.py <- The dashboard screen
```

## What's next (once you confirm this step works)

Step 2 will be **Quick Job Entry** — the big service buttons (Xerox, Print,
Passport Photo, etc.) that let a worker record a completed job in a few
seconds, and the Dashboard numbers will start updating for real instead of
showing zero.
