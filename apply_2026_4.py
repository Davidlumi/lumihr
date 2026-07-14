#!/usr/bin/env python3
"""Release 2026.4 WRITE — 45 REW264_* questions + the ratified seed (220 non-Tester).
Diff 5, ratified 2026-07-14. Double-guarded: --write --confirmed-by-david.

- questions insert: help_text <- MEMBER csv (D3); help_why goes to NO member-visible
  column (it lives in the committed authority CSV + the changelog detail).
- mp_config entries at import (the 2026_3 gap that left REW263 unclassified until
  Diff 2): 38 single ↑ + 4 multi ↑ -> the D5 donor shape (Level/ordinal/higher);
  3 neutral -> Practice. Fail-closed gauge stays closed to nothing.
- seed: manifest target distributions; SEVEN wired NA rows conditioned on the
  PARENT's actual per-org answer (REW264_WEL_EWA seeded FIRST for its two children);
  six self-declared NA priors; MEALS sector tilt; largest-remainder + latent-spine
  ordering for ladder questions (reseed_engine, the 2026_3 machinery).
- APPEND-ONLY assert: content hash over answers/answers_history EXCLUDING REW264_*
  ids is byte-identical before/after; new rows exist ONLY under REW264_* ids.
"""
import csv
import hashlib
import json
import re
import sqlite3
import sys

sys.path.insert(0, ".")
import reseed_engine as RE
import seed_release_2026_4 as K

WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
STAMP = "2026-07-14 17:30:00"
RELEASE = "2026.4"


def code_of(label):
    return re.sub(r"[^A-Z0-9]+", "_", label.upper()).strip("_")


def existing_hash(cur):
    h = hashlib.sha256()
    for t in ("answers", "answers_history"):
        for row in cur.execute("SELECT org_id, question_id, matrix_row_id, value FROM %s "
                               "WHERE question_id NOT LIKE 'REW264_%%' "
                               "ORDER BY org_id, question_id, matrix_row_id" % t):
            h.update(("|".join(str(x) for x in row) + "\n").encode())
    return h.hexdigest()


rel, hlp, anc = K.load_rows()
c = sqlite3.connect("lumi.db")
c.row_factory = sqlite3.Row
cur = c.cursor()
cur.execute("PRAGMA wal_checkpoint(TRUNCATE)")

tester = cur.execute("SELECT org_id FROM orgs WHERE name='Tester'").fetchone()
tester = tester[0] if tester else None
orgs = [o for (o,) in cur.execute("SELECT DISTINCT org_id FROM answers WHERE snapshot_id=1").fetchall() if o != tester]
assert len(orgs) == 220, "cohort must be the 220 convention (D4): %d" % len(orgs)
prof = {}
for p in ("org_profiles.json", "org_profiles_inferred.json"):
    prof.update(json.load(open(p)))
lat = {o: RE.latent(o, prof) for o in orgs}
sector_of = {o: (prof.get(o) or {}).get("Sector") or (prof.get(o) or {}).get("sector") or "" for o in orgs}

if not WRITE:
    print("DRY: would insert 45 questions + cfg entries + seed %d orgs; run dryrun_2026_4.py for gates" % len(orgs))
    sys.exit(0)

h0 = existing_hash(cur)

# ===== 1. INSERT 45 CATALOGUE ROWS (help_text <- member file; help_why NOT imported) =====
qo = cur.execute("SELECT MAX(question_order) FROM questions").fetchone()[0] or 900
ins = 0
for qid, r in rel.items():
    sub = r["category"]
    opts = K.split_options(r)
    oj = [{"code": code_of(l), "label": l, "order": i + 1,
           "is_na": K.is_na_label(l)} for i, l in enumerate(opts)]
    sm = "multi_select_count" if r["type"] == "multi_select" else "single_select"
    qo += 1
    cur.execute("""INSERT INTO questions
      (id,text,short_description,help_text,definition,superpower,sub_power,sub_power_order,type,category,
       options_json,default_chart_type,data_display_type,polarity,unit_type,lumi_tier,na_handling_json,
       benchmark_display,is_scored,scoring_config_json,is_required,question_order,question_version,
       historical_comparability,status,release_entered)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (qid, r["text"], r["text"][:120], hlp[qid], r["text"], "Reward", sub, K.SPO[sub],
       r["type"], "practice", json.dumps(oj), "bar", "percentage_distribution", r["polarity"],
       "none", "Core", json.dumps({"exclude_from_scoring": True, "exclude_from_benchmarking": False, "na_codes": []}),
       r["text"], 0, json.dumps({"scoring_method": sm, "polarity": r["polarity"]}), 0, qo, "v1.0",
       "n/a", "active", RELEASE))
    cur.execute("""INSERT INTO core_changelog (release_id,lane,change_type,question_id,detail,signed_off_by,created_at)
      VALUES (?,?,?,?,?,?,?)""", (RELEASE, "release", "added", qid,
      "Added in 2026.4 (v1.0). Internal rationale (help_why) held in the release CSV per D3: %s" % (r.get("help_why", "")[:180]),
      "David Whitfield (Diff 5 rulings, 2026-07-14)", STAMP))
    ins += 1

# ===== 2. CONFIG ENTRIES (the 2026_3 gap, closed) =====
cfg = json.load(open("data/market_position_config.json"))
donor = cfg["metrics"]["REW26_WEL_MH_SUPPORT"]           # D5 mirror
n_cfg = 0
for qid, r in rel.items():
    if r["polarity"] == "neutral":
        ent = {"class": "Practice", "type": "categorical", "direction": None, "lens": "attract", "weight": 1}
    else:
        ent = dict(donor)                                # Level/ordinal/higher_is_better
    cfg["metrics"][qid] = ent
    n_cfg += 1
json.dump(cfg, open("data/market_position_config.json", "w"), indent=2, ensure_ascii=False)

# ===== 3. SEED (EWA first for its intra-wave children) =====
order_ids = ["REW264_WEL_EWA"] + [q for q in rel if q != "REW264_WEL_EWA"]
seeded_values = {}      # qid -> {org: value}
manifest_rows = {r["id"]: r for r in csv.DictReader(open("diff5_seed_manifest.csv"))}
ans = []
for qid in order_ids:
    r = rel[qid]
    dist = json.loads(manifest_rows[qid]["target_dist"])
    na_opt = next((o for o in K.split_options(r) if K.is_na_label(o)), None)
    na, answ = [], []
    for o in orgs:
        rng = K.org_rng(qid, o)
        is_na = False
        if qid in K.WIRED:
            parent, na_vals = K.WIRED[qid]
            pv = seeded_values.get(parent, {}).get(o)
            if pv is None:
                row = cur.execute("SELECT value FROM answers WHERE question_id=? AND org_id=? AND snapshot_id=1",
                                  (parent, o)).fetchone()
                pv = row["value"] if row else None
            is_na = (pv is None) or any(pv.strip().startswith(v) for v in na_vals)
        elif qid in K.SELF_NA_PRIOR:
            is_na = rng.random() < K.SELF_NA_PRIOR[qid]
        (na if is_na and na_opt else answ).append(o)
    m = len(answ) or 1
    assign = {}
    if r["type"] == "multi_select":
        opts = [o for o in K.split_options(r) if not K.is_na_label(o) and o != "None"]
        per_opt = {o: max(0.06, dist.get(o, 0.15)) for o in opts}
        for o in answ:
            rng = K.org_rng(qid, o)
            ch = [x for x, p in per_opt.items() if rng.random() <= p]
            assign[o] = ";".join(ch) if ch else "None"
    else:
        d = dist
        if qid == "REW264_WEL_MEALS":
            for o in answ:
                pass  # per-org tilt handled below via grouped assignment
        # sector-tilt MEALS: split orgs into tilted / untilted groups, each largest-remainder'd
        groups = [(answ, d)]
        if qid == "REW264_WEL_MEALS":
            tilted = [o for o in answ if any(s in (sector_of[o] or "").lower() for s in K.MEALS_TILT_SECTORS)]
            plain = [o for o in answ if o not in set(tilted)]
            groups = [(plain, d), (tilted, K.meals_tilt(d, "hospitality"))]
        for grp, gd in groups:
            if not grp:
                continue
            counts = K.largest_remainder(gd, len(grp))
            order = RE.option_order(list(gd), qid) or list(gd.keys())
            rank = {op: i for i, op in enumerate(order)}
            seq = [op for op in sorted(counts, key=lambda x: rank.get(x, 999)) for _ in range(counts[op])]
            for o, v in zip(sorted(grp, key=lambda o: lat[o]), seq):
                assign[o] = v
    for o in na:
        assign[o] = na_opt
    seeded_values[qid] = assign
    for o in orgs:
        if o in assign and assign[o] is not None:
            ans.append((o, 1, qid, "", assign[o], STAMP))

cur.executemany("INSERT INTO answers (org_id,snapshot_id,question_id,matrix_row_id,value,submitted_at) VALUES (?,?,?,?,?,?)", ans)
c.commit()
cur.execute("PRAGMA wal_checkpoint(TRUNCATE)")

# ===== 4. ASSERTIONS + manifest seeded column =====
h1 = existing_hash(cur)
assert h0 == h1, "PRE-EXISTING ANSWER ROWS MOVED — restore backup NOW"
stray = cur.execute("SELECT COUNT(*) FROM answers WHERE submitted_at=? AND question_id NOT LIKE 'REW264_%'", (STAMP,)).fetchone()[0]
assert stray == 0, "seed wrote outside REW264_*: %d rows" % stray
out = []
for row in csv.DictReader(open("diff5_seed_manifest.csv")):
    qid = row["id"]
    vals = seeded_values.get(qid, {})
    n = len(vals)
    na_n = sum(1 for v in vals.values() if v and K.is_na_label(v))
    from collections import Counter
    top = Counter(v for v in vals.values() if v and not K.is_na_label(v)).most_common(3)
    row["seeded_n"] = n
    row["seeded_na"] = na_n
    row["seeded_top"] = "; ".join("%s %.0f%%" % (k[:28], 100 * v / max(1, n - na_n)) for k, v in top)
    out.append(row)
with open("diff5_seed_manifest.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader()
    w.writerows(out)
print("inserted %d questions, %d cfg entries, %d answer rows across %d orgs" % (ins, n_cfg, len(ans), len(orgs)))
print("append-only hash IDENTICAL over pre-existing rows; manifest seeded columns written")
