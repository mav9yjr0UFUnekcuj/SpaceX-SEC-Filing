# SpaceX SEC Filing Monitor (Python + GitHub Actions + Apps Script)

Why this exists: Google Apps Script's `UrlFetchApp` silently overrides any
custom `User-Agent` header you set, so it can never satisfy the SEC's
fair-access policy (which requires a real declared User-Agent) — that's
what was causing the `403` from `data.sec.gov`. Python's `requests`
library sends the header exactly as specified, so the fetch step moves
to Python. Everything else — the email itself — stays in your existing
Apps Script, unchanged.

```
GitHub Actions (every 10 min)
   -> check.py fetches data.sec.gov/submissions/CIK0001181412.json
   -> diffs against state.json (last accession number seen)
   -> on a new filing, POSTs it to your Apps Script Web App
        -> Apps Script's sendFilingAlert_() sends the email, same as before
```

## 1. Add the webhook endpoint to your existing Apps Script project

Open your current "SpaceX SEC Filing Monitor" Apps Script project and
paste the contents of `apps_script_webhook_addition.gs` into `Code.gs`,
below your existing code. It calls your existing `sendFilingAlert_()` —
nothing else in that file needs to change.

In the Apps Script editor: **Project Settings (gear icon) → Script
Properties → Add script property**:

- Property: `WEBHOOK_SECRET`
- Value: any long random string (e.g. generate one with
  `openssl rand -hex 24` in a terminal, or any password generator)

Keep this value handy — you'll paste the same string into GitHub in step 3.

## 2. Deploy the Apps Script as a Web App

**Deploy → New deployment**:

- Type: **Web app**
- Execute as: **Me**
- Who has access: **Anyone** (this is fine — the shared-secret check in
  `doPost` is what actually protects it; nobody without the secret can
  trigger an email)

Click **Deploy**, then copy the Web app URL it gives you
(`https://script.google.com/macros/s/.../exec`).

## 3. Create the GitHub repo

Create a new repo (private is fine) and add all the files in this
folder, preserving the `.github/workflows/` path.

Then **Settings → Secrets and variables → Actions → New repository
secret**, and add two secrets:

- `WEBHOOK_URL` — the Web app URL from step 2
- `WEBHOOK_SECRET` — the same string you put in Script Properties in step 1

## 4. Test it

From the **Actions** tab, open "SpaceX SEC Filing Monitor" and click
**Run workflow** to trigger it manually (don't wait for the schedule).
The first run just establishes a baseline silently — no email.

To force an actual test email without waiting for a real filing, run
locally or via a manual Actions step:

```
python check.py --test-email
```

This sends the most recent filing as a real email and does not touch
`state.json`.

## 5. Let it run

Once pushed, the schedule in `spacex_sec_monitor.yml` checks every 10
minutes and commits the updated `state.json` back to the repo after
every run (this also keeps the repo "active," which matters — GitHub
auto-disables scheduled workflows in repos with no commits for 60 days).

**One thing worth knowing:** GitHub Actions gives free accounts 2,000
minutes/month for private repos. A run every 10 minutes is ~4,300
minutes/month at GitHub's per-minute billing, which is over that free
allowance. Two easy fixes if that matters to you:

- Make the repo **public** instead (nothing in it is sensitive — the
  webhook URL and secret live only in GitHub Secrets, never in the
  code) — public repos get unlimited Actions minutes, or
- Loosen the cron to every 20–30 minutes
  (`*/30 * * * *` in the workflow file comfortably fits the free tier).

Either is a one-line change whenever you want to make it.
