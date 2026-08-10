#!/usr/bin/env python3
"""Seed-realism B8 — Tier-3: dental prevalence (2026-08-10).

REW263_BEN_DENTAL had only 11 rows (siblings have 220) — a 5% dental-offer rate vs a
~20-35% UK norm, making the cut unusable. The design pass showed a naive 209-row
insert FAILS the coherence gate (REW263_BEN_DENTAL is a conditioned child of the
REW_BEN_038 'Dental cover' tick: child_any_answer must be a subset of the parent tick
set). So grow the PARENT and CHILD together for the SAME orgs, size-tilted to ~30%
offer; non-offerers are left absent (= not offered). Coherence holds by construction
(child set == parent set). Deterministic (sha256; no RNG). LUMI_DB-aware; DRY-RUN
unless --write --confirmed-by-david.

    python3 server/migrate_seedreal_b8_dental_2026_08_10.py                        # dry run
    python3 server/migrate_seedreal_b8_dental_2026_08_10.py --write --confirmed-by-david
"""
import os, sys, sqlite3, hashlib
from collections import Counter

DB = os.environ.get("LUMI_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
STAMP = "2026-07-21 09:00:00"   # matches the existing 11-row dental tranche (canonical)
OFFER_RATE = {"50-249": 0.18, "250-999": 0.22, "1,000-4,999": 0.32,
              "5,000-9,999": 0.38, "10,000+": 0.44, None: 0.22}
BIG = ("1,000-4,999", "5,000-9,999", "10,000+")


def u(tag, org):
    return int(hashlib.sha256(("%s|%s" % (tag, org)).encode()).hexdigest()[:8], 16) / 0x100000000


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    fte = {r["org_id"]: r["fte_band"] for r in c.execute("SELECT org_id,fte_band FROM orgs WHERE classified=1")}
    answering = [r["org_id"] for r in c.execute("SELECT DISTINCT org_id FROM answers WHERE snapshot_id=1")]
    b038 = {a["org_id"]: a["value"] for a in c.execute(
        "SELECT org_id,value FROM answers WHERE question_id='REW_BEN_038' AND matrix_row_id='' AND snapshot_id=1")}
    existing = {a["org_id"] for a in c.execute(
        "SELECT org_id FROM answers WHERE question_id='REW263_BEN_DENTAL' AND snapshot_id=1")}

    # offerer set: existing 11 + deterministic size-tilted draw
    offerers = set(existing)
    for org in answering:
        if u("DENTAL_OFFER", org) < OFFER_RATE.get(fte.get(org)):
            offerers.add(org)

    added_038 = inserted = 0
    for org in sorted(offerers):
        # parent tick
        val = str(b038.get(org, ""))
        if "Dental cover" not in val:
            parts = [p.strip() for p in val.split(";") if p.strip() and p.strip() != "None"]
            parts.append("Dental cover")
            added_038 += 1
            if WRITE:
                c.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id='REW_BEN_038' AND matrix_row_id='' AND snapshot_id=1",
                          ("; ".join(parts), org))
        # child row
        if org not in existing:
            band = fte.get(org)
            fund = "Employer-paid" if (band in BIG and u("DENTAL_FUND", org) < 0.45) else "Voluntary (employee-funded)"
            inserted += 1
            if WRITE:
                c.execute("INSERT INTO answers (org_id,snapshot_id,question_id,matrix_row_id,value,submitted_at) "
                          "VALUES (?,1,'REW263_BEN_DENTAL','',?,?)", (org, fund, STAMP))
    if WRITE:
        c.commit()

    # report
    child = {a["org_id"]: a["value"] for a in c.execute(
        "SELECT org_id,value FROM answers WHERE question_id='REW263_BEN_DENTAL' AND snapshot_id=1")}
    parent = {o for o, v in ({a["org_id"]: a["value"] for a in c.execute(
        "SELECT org_id,value FROM answers WHERE question_id='REW_BEN_038' AND matrix_row_id='' AND snapshot_id=1")}).items()
        if "Dental cover" in str(v)}
    print(("APPLIED" if WRITE else "DRY RUN") + " — 038 dental ticks added: %d | DENTAL rows inserted: %d" % (added_038, inserted))
    print("  dental offerers: %d/%d (%.0f%%) | funding split: %s"
          % (len(child), len(answering), 100 * len(child) / len(answering), dict(Counter(child.values()))))
    print("  coherence child⊆parent: %s (child=%d parent=%d)" % (set(child) <= parent, len(child), len(parent)))
    # by-band offer rate
    bb = Counter(fte.get(o) for o in child if o in fte)
    tot = Counter(fte.values())
    print("  offer by band:", {b: "%d/%d" % (bb.get(b, 0), tot[b]) for b in ["50-249", "250-999", "1,000-4,999", "5,000-9,999", "10,000+"]})
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
