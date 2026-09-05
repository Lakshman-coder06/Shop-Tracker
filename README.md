# Shop Work & Collection Tracker — Phase 2 (All Menu Screens Working)

Every button on the Dashboard menu now opens a real, working screen backed
by the SQLite database. No more "coming soon" popups anywhere.

| Button | What it does |
|---|---|
| **NEW JOB** | Fast job entry. Pick a service (rate auto-fills, but you can type over it - e.g. for a discount), quantity, payment method, status. Saves instantly, clears itself for the next job. |
| **TRANSACTIONS** | Today's totals + a full table of every job, newest first. Date filter (Today/Yesterday/Last 7 days/All). |
| **EXPENSE** | Fast expense entry (category, amount, reason, payment source) with a running list of today's expenses right below the form. |
| **PENDING RECORDS** | Any job not yet both Completed and Paid. Select a row, mark it Completed and/or Paid - each change is written to the database and logged to the audit trail. |
| **ACTIVITY** | Reuses the Activity History screen from Phase 1.5 (unchanged - filters, search, sorting, refresh button). |
| **DAILY CLOSING** | Opening Cash + Cash Sales − Cash Expenses = Expected Cash. Enter Actual Cash to see the Difference, with a plain-language status message. Admin/Supervisor only can edit and save; workers see it read-only. |

Login and the Dashboard's overall layout are unchanged. The Dashboard's six
summary numbers (Jobs Today, Total Sales, Cash, UPI, Expenses, Expected
Drawer) are now **real** - they update the moment you save a job or expense
anywhere in the app, not just on next login.

## How money flows through the app (so the numbers make sense)

- A job's **Status** (Completed/Pending) and **Payment Status** (Paid/
  Unpaid) are separate. Saving a job as *Completed* assumes it was paid on
  the spot (the normal walk-in case) - status and payment both flip
  automatically. Saving as *Pending* leaves it unpaid until someone marks
  it Paid from Pending Records (e.g. custom design work picked up later).
- **Total Sales / Cash / UPI** on the Dashboard only count money actually
  *Paid* - a Pending+Unpaid job doesn't inflate "money in hand."
  **Jobs Today** counts all non-cancelled jobs regardless of payment.
- **Expected Drawer / Expected Cash** only subtracts **Cash** expenses (a
  UPI expense doesn't remove physical cash from the drawer).

## New/changed files this phase

```
ShopTracker/
├── database.py                    <- +migration (new columns), +12 new functions
├── requirements.txt                <- unchanged
├── ui/
│   ├── dashboard_window.py        <- all 6 menu buttons wired to real screens; live-refreshing numbers
│   ├── job_entry_window.py        <- NEW
│   ├── transactions_window.py     <- NEW
│   ├── expense_entry_window.py    <- NEW
│   ├── pending_records_window.py  <- NEW
│   └── daily_closing_window.py    <- NEW
```
`main.py`, `login_window.py`, and everything from Phase 1.5 (activity
monitoring) are **unchanged**.

## Database changes (safe, additive migration - your data is untouched)

- `transactions` gained: `customer_reference`, `rate`, `notes`, `payment_status`
- `expenses` gained: `category`, `notes`
- `services` gained 5 new entries (Print B&W, Print Colour, Photo Print,
  Scanning, Invitation Printing) - the old ones are kept as-is, including
  any rate you'd already customized
- `audit_logs` is now actually used - every "Mark as Completed" / "Mark as
  Paid" leaves a permanent, timestamped record of who changed what

## How to run this on Windows

Same as before - nothing new to install this phase:
```
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Tests I performed (all passing, run against the actual shipped files)

I ran your exact 18-step test script end-to-end in an automated harness
before sending this to you:

1. Login as Worker 1 → Dashboard loads
2-4. NEW JOB: Passport Photo, qty 2, **rate manually overridden to Rs 50**
   (its configured default is Rs 80 - I caught and fixed a bug here, see
   "What I fixed" below), Cash, Save → "Job saved successfully"
5-6. TRANSACTIONS: Rs 100 total confirmed, row shows the overridden Rs 50
   rate correctly
7-9. EXPENSE: Bus Fare Rs 40 Cash → appears immediately in the list
10-11. PENDING RECORDS: empty (job was Completed+Paid) → created a second,
   Pending job to specifically exercise Mark Completed / Mark Paid, both
   worked and it correctly disappeared from the list once both were done
12-13. ACTIVITY: opens correctly
14-15. DAILY CLOSING: Opening 1000 + Cash Sales 120 − Cash Expenses 40 =
   Expected 1080, confirmed against real transaction/expense data; entered
   Actual 1050 → Difference −30, "Cash difference detected" message shown
   correctly; Save persisted correctly
16. Logout → back to login screen, session closed
17-18. Login as Admin → sees both jobs (2) and correct total sales (Rs 120)

I also separately verified: workers cannot edit Daily Closing (view-only,
as Admin/Supervisor-only editing wasn't explicitly restated in this request
but matches the role pattern already used elsewhere in the app); a
migration test against a simulated pre-Phase-2 database confirmed existing
data and custom rates survive untouched; and all 7 screens can be open
simultaneously with Activity Monitoring still running, including a forced-
quit safety check.

## What I fixed during testing

Your own test script set `Rate = ₹50` for Passport Photo, but I'd
initially built Rate as a read-only field auto-filled from the service's
configured price (₹80) - it would have silently ignored your override.
Running your test script caught this immediately, so I made Rate an
editable field (still auto-filled as a starting point) before finishing.

## Remaining limitations (things intentionally NOT done this phase)

- No screen yet to edit service rates or add/deactivate services (must be
  done by hand in the database for now)
- No expense approval workflow (expenses save immediately - the original
  spec's Admin-approval step isn't built)
- "Possible Missed Entries" on the Dashboard is still a placeholder (0) -
  connecting activity data to missing transactions is a later phase
- Daily Closing's Opening Cash isn't remembered day-to-day automatically
  (you re-enter it each time, though Actual Cash pre-fills if you already
  saved a closing for today)
- No printable/exportable reports yet
