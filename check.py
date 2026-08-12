#!/usr/bin/env python3
"""
SpaceX SEC Filing Monitor

Fetches SpaceX's SEC submissions feed, detects filings that are new
since the last run, and POSTs each one to a Google Apps Script Web
App, which sends the team email (reusing your existing MailApp
logic). State (last-seen accession number) lives in state.json,
which the GitHub Actions workflow commits back to the repo after
every run.

Usage:
    python check.py              # normal check
    python check.py --test-email # send the most recent filing as a
                                  # test, without touching state.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

# ---------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------

SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK0001181412.json"

# SEC requires a real, declared User-Agent identifying the requester.
# Python's requests library actually sends this (unlike Apps Script's
# UrlFetchApp, which silently overrides any custom User-Agent).
USER_AGENT = "Lemoko Investments drew@lemokomanagement.com"

# Skip Forms 3/4/5 (and amendments), mirroring owner=exclude on EDGAR.
EXCLUDED_FORMS = {"3", "3/A", "4", "4/A", "5", "5/A"}

STATE_PATH = Path(__file__).parent / "state.json"

WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")


# ---------------------------------------------------------------
# STATE
# ---------------------------------------------------------------

def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"last_accession": None}


def save_state(state: dict) -> None:
    state["last_checked_utc"] = datetime.now(timezone.utc).isoformat()
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")


# ---------------------------------------------------------------
# SEC
# ---------------------------------------------------------------

def get_recent_filings() -> list:
    response = requests.get(
        SEC_SUBMISSIONS_URL,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=30,
    )
    response.raise_for_status()

    recent = response.json()["filings"]["recent"]

    filings = []
    for i, form in enumerate(recent["form"]):
        if form.upper().strip() in EXCLUDED_FORMS:
            continue
        filings.append(
            {
                "accessionNumber": recent["accessionNumber"][i],
                "filingDate": recent["filingDate"][i],
                "reportDate": recent["reportDate"][i],
                "form": form,
                "primaryDocument": recent["primaryDocument"][i],
                "primaryDocDescription": recent["primaryDocDescription"][i] or "",
            }
        )
    return filings


# ---------------------------------------------------------------
# WEBHOOK (Apps Script)
# ---------------------------------------------------------------

def send_filing_alert(filing: dict) -> None:
    if not WEBHOOK_URL or not WEBHOOK_SECRET:
        raise RuntimeError(
            "WEBHOOK_URL / WEBHOOK_SECRET are not set (expected as env vars / "
            "GitHub Actions secrets)."
        )

    payload = {**filing, "secret": WEBHOOK_SECRET}
    response = requests.post(WEBHOOK_URL, json=payload, timeout=30)
    response.raise_for_status()

    result = response.json()
    if result.get("error"):
        raise RuntimeError(f"Webhook rejected the request: {result['error']}")

    print(f"Alert sent for {filing['form']} / {filing['accessionNumber']}")


# ---------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------

def run_test_email() -> None:
    filings = get_recent_filings()
    if not filings:
        print("No filings available.")
        sys.exit(1)
    send_filing_alert(filings[0])


def run_check() -> None:
    filings = get_recent_filings()
    if not filings:
        print("No filings found.")
        return

    state = load_state()
    last_accession = state.get("last_accession")

    if not last_accession:
        # First run: establish baseline, no email for existing filings.
        state["last_accession"] = filings[0]["accessionNumber"]
        save_state(state)
        print(f"Initialized baseline: {filings[0]['accessionNumber']}")
        return

    previous_index = next(
        (i for i, f in enumerate(filings) if f["accessionNumber"] == last_accession),
        None,
    )

    if previous_index == 0:
        print("No new SpaceX SEC filings.")
        save_state(state)
        return

    if previous_index is None:
        # Old accession fell out of the recent-filings window.
        print("Previous accession not found in feed; resetting baseline.")
        state["last_accession"] = filings[0]["accessionNumber"]
        save_state(state)
        return

    new_filings = list(reversed(filings[:previous_index]))
    print(f"Found {len(new_filings)} new filing(s).")

    for filing in new_filings:
        send_filing_alert(filing)
        state["last_accession"] = filing["accessionNumber"]
        save_state(state)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-email", action="store_true")
    args = parser.parse_args()

    if args.test_email:
        run_test_email()
    else:
        run_check()
