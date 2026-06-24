#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nightly notification sweep.

Run after aggregate.py recomputes the benchmark: recompute each unlocked org's
signal set, diff against signal_state, record appeared/cleared/moved change
events and fan them out per-user. Optionally roll opted-in users' events into
an email digest.

    python3 notification_sweep.py             # sweep only
    python3 notification_sweep.py --snapshot  # run_snapshot first, then sweep
    python3 notification_sweep.py --digest     # also send email digests

A typical nightly cron is two steps:  python3 aggregate.py  &&  python3 notification_sweep.py --digest
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn, init_schema
import app
import notifications


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", action="store_true", help="run_snapshot before sweeping")
    ap.add_argument("--snapshot-id", type=int, default=1)
    ap.add_argument("--digest", action="store_true", help="send email digests after sweeping")
    ap.add_argument("--base-url", default=os.environ.get("LUMI_BASE_URL", ""))
    args = ap.parse_args()

    conn = get_conn()
    init_schema(conn)
    if args.snapshot:
        from aggregate import run_snapshot
        run_snapshot(args.snapshot_id)
    app.run_signal_sweep(conn)
    if args.digest:
        sent = notifications.run_email_digest(conn, base_url=args.base_url)
        print("Email digests sent: %d" % sent)


if __name__ == "__main__":
    main()
