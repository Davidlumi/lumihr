# -*- coding: utf-8 -*-
"""B1 data half (ship review 2026-07-09): REW_Q528801 + REW_Q534581 carried
sub_power_order=2 against Pay's 58 rows at 1, minting a duplicate 'Pay' section that
looped the guided questionnaire Pay<->Incentives. The CODE dedupe shipped in 0b7ca77;
this closes the DATA half (the rows themselves), shipped 2026-07-12 on David's
"ship all parked". The companion CSV fix (data/lumi_questions.csv) stops a --fresh
reseed reintroducing it.

Double-guarded per house rule: python3 migrate_b1_sub_power_order.py --write --confirmed-by-david
Reads LUMI_DB (defaults to ../lumi.db). Idempotent; prints before/after either way.
"""
import os
import sqlite3
import sys

IDS = ("REW_Q528801", "REW_Q534581")
DB = os.environ.get("LUMI_DB", os.path.join(os.path.dirname(__file__), "..", "lumi.db"))

conn = sqlite3.connect(DB)
rows = list(conn.execute(
    "SELECT id, sub_power, sub_power_order FROM questions WHERE id IN (?,?)", IDS))
print("before:", rows)
if "--write" in sys.argv and "--confirmed-by-david" in sys.argv:
    conn.execute("UPDATE questions SET sub_power_order=1 WHERE id IN (?,?)", IDS)
    conn.commit()
    print("after: ", list(conn.execute(
        "SELECT id, sub_power, sub_power_order FROM questions WHERE id IN (?,?)", IDS)))
    dist = list(conn.execute(
        "SELECT sub_power_order, COUNT(*) FROM questions WHERE sub_power='Pay' GROUP BY 1"))
    print("Pay sub_power_order distribution:", dist)
else:
    print("DRY RUN — pass --write --confirmed-by-david to apply.")
