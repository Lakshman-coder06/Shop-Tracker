# Shop Work & Collection Tracker — Phase 3 (Privacy, Real Activity Detection, Management)

This is the biggest upgrade so far. Three things changed fundamentally:

1. **Worker data privacy is now enforced everywhere.** Every worker sees
   only their own jobs/expenses/pending records; Admin sees everything,
   plus a per-worker breakdown.
2. **Activity monitoring now watches the actual foreground window**
   instead of every running process - see below for why this matters.
3. **New management screens:** Change PIN, Manage Workers, Manage
   Services/Rates, Audit Log.

Login PINs are unchanged. Everything from earlier phases still works.

## 1. Worker privacy (and a bug I found and fixed)

Every worker-facing number and list is now scoped by `worker_id`:
Dashboard, Transactions, Expense's own-list, and Pending Records. Admin
and Supervisor see everyone's.

**I found and fixed two real privacy bugs while building this**, not
just designed around them:
- `get_pending_transactions()` had **no worker filter at all** - any
  worker who opened Pending Records could see every worker's pending
  jobs. Fixed.
- The Expense screen's "today's expenses" confirmation list called the
  database function *before* I'd wired the worker filter through it -
  caught this one via my own test script (it's in the test log below),
  not by inspection.

## 2. Why activity monitoring changed from "all processes" to "foreground window"

Phase 1.5 watched every running process and filtered out known Windows
system processes. The problem: **a program can sit open in the
background for hours without being touched**, and it would still show up
as "activity." It also couldn't distinguish "worker is using this" from
"this happens to be running."

Phase 3 instead asks Windows one question, repeatedly: *which window is
currently in front - the one being looked at and worked in?* That's a
much closer match to real usage, and it also fixes File Explorer
detection in a simpler way than Phase 1.5's separate window-counting
workaround: a File Explorer folder window genuinely *does* become the
foreground window when clicked into, so one mechanism now covers every
application instead of two.

Two things are deliberately excluded from tracking:
- **Shop Tracker's own windows** - otherwise clicking back to Shop
  Tracker to save a job would interrupt whatever you were tracking
  before it. Instead, Shop Tracker's own foreground time is invisible:
  the app you were using keeps "running" underneath it.
- **The Windows desktop/taskbar** (as opposed to an actual File Explorer
  folder window - told apart by window class name).

**What I could and couldn't test myself:** the real Windows API calls
(`GetForegroundWindow`, `GetWindowThreadProcessId`) only work on Windows -
I built and tested this sandboxed on Linux. To test the actual switching
*logic* rigorously anyway, the watcher takes its "what's in front right
now" data through a swappable function (`foreground_provider`) - in
production it calls the real Windows APIs; in my tests, I fed it a
scripted sequence of fake foreground-window snapshots and drove it
through your exact Photoshop → Chrome → File Explorer scenario, the
Shop-Tracker-self-exclusion case, and the desktop/taskbar exclusion case.
All passed - see the test log below. The real API calls themselves use
long-stable, standard Windows functions, but genuinely need your machine
to confirm.

## 3. New screens

| Screen | Who | What |
|---|---|---|
| **Change PIN** | Everyone | Change your own PIN (needs the current one). |
| **Manage Workers** | Admin only | Add workers, edit name/Employee ID, set Active/On Leave/Inactive, reset a PIN (with an optional "must change at next login" flag for temporary/shift-cover PINs). |
| **Manage Services** | Admin only | Add services, change rates, activate/deactivate. Rate changes never touch past transactions - each transaction stores the rate it was created with. |
| **Audit Log** | Admin only | Every PIN change/reset, worker status change, and service/rate change, with old and new values. View-only, even for Admin. |

Pending Records also gained: Customer/Reference, Advance, and Balance
columns, an "In Progress" status, and a "Cancel Job" action (soft-cancel
with a reason - nothing is ever deleted).

## 4. Dashboard: two different views now

**Worker dashboard:** My Jobs Today / My Sales / My Cash / My UPI / My
Expenses / My Expected Collection, My Current Activity, My Recent Jobs,
My Pending Jobs. No shop-wide numbers anywhere.

**Admin dashboard:** shop-wide totals, a Worker Performance table (one
row per worker, today's numbers), Daily Closing status with a mismatch
alert if today's saved closing doesn't balance, shop-wide pending job
count, and a shop-wide recent activity feed.

## 5. Visual redesign

A dark, professional theme is now applied app-wide (`theme.py`, loaded
once in `main.py`) - rounded buttons and cards, consistent colours
(green = good/active, orange = attention, red = mismatch/error, blue =
info), better spacing. The Activity Monitor screen got the most detailed
rework: a status card, a "Current Application" card with a live-ticking
duration, a ranked "Today's Application Usage" list with bar indicators,
and a colour-coded live event feed.

## How to run this on Windows

```
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```
No new dependencies this phase (pywin32 was already added in Phase 1.5,
for the same reason it's needed now).

## Tests performed

I ran your exact 25-step test script end-to-end against the actual
shipped files (not just read through the code) before sending this:

1-4. Worker 1 logs in, adds 3 jobs (Rs 50 Cash, Rs 20 Cash, Rs 30 UPI)
   and 1 expense (Rs 20 Cash), dashboard correctly shows Jobs=3,
   Sales=Rs 100, Expenses=Rs 20, logs out.
5-6. Worker 2 logs in - confirmed **zero** Worker 1 data visible across
   Dashboard, Transactions, Expense's list, and Pending Records. This is
   where I caught the Expense-list privacy bug described above.
7-8. Worker 2 adds their own job, confirmed they see only their own
   Rs 30 job (not Worker 1's Rs 100).
9-12. Admin logs in, sees all 4 transactions across both workers, shop
   total Rs 130, and a correct per-worker performance breakdown.
13-19. Simulated Photoshop → Chrome → File Explorer via the swappable
   foreground-window provider - confirmed correct start/stop pairing,
   File Explorer detected, and (by construction) no background/system
   process ever appears, since only the single foreground window is
   ever examined.
20. Change PIN - changed and verified working, changed back.
21. Worker Management - added a worker, set them On Leave, confirmed
   they're blocked from the login list.
22. Daily Closing - Rs 1000 opening + Rs 100 cash sales − Rs 20 cash
   expenses = Rs 1080 expected; entered Rs 1030 actual → Rs -50
   difference, correctly flagged, saved, and surfaced as a mismatch
   alert on the Admin dashboard.
23. Audit Log - confirmed worker-management and PIN-change entries
   recorded with old/new values.
24-25. Restarted the application as a brand-new process against the
   same database file - all workers, transactions, and statuses
   persisted correctly.

I also separately verified: a migration test against a simulated
pre-Phase-3 database (existing users/transactions preserved, active
flags correctly backfilled into the new status field); every call site
of the four privacy-sensitive query functions, to catch any other place
I might have forgotten to pass `worker_id` (found none beyond the one
above); and the full forced-PIN-change flow through `main.py` end to end
(reset with "require change" → login blocks the dashboard → change PIN →
dashboard unlocks).

## Remaining limitations

- Date-range filtering is still preset buttons (Today/Yesterday/Last 7
  days/All), not a free-form calendar range picker.
- The Expense screen's own-list is intentionally personal-only, even for
  Admin (a dedicated "all expenses" browsing screen doesn't exist yet -
  Admin can review expenses via the audit trail and Daily Closing's cash
  math, but not a full filterable expense table).
- Worker Management doesn't yet have a "Username" field distinct from
  Name/Employee ID (Name is used as the display identity, matching how
  login already worked).
- The temporary-PIN flow forces a change at next login, but doesn't
  auto-expire a temp PIN after a fixed time window.
- "Window title" is captured for each activity but only shown in
  Activity Details (not on the main Live Activity feed), since it can
  contain customer/document names.
