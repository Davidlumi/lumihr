#!/usr/bin/env python3
"""Release 2026.5 WRITE — 54 REW265_* questions + the ratified seed (220 non-Tester).
Diff 6, approved 2026-07-14 with three riders. Copy-adapted from apply_2026_4.py;
all D-rulings inherit (D1 by-id recon in dryrun; D3 help mapping; D5 donor mirror).
Double-guarded: --write --confirmed-by-david. Append-only content-hash proof."""
import csv
import hashlib
import json
import re
import sqlite3
import sys

sys.path.insert(0, ".")
import reseed_engine as RE
import seed_release_2026_5 as K

WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
STAMP = "2026-07-14 18:40:00"
RELEASE = "2026.5"


def code_of(label):
    return re.sub(r"[^A-Z0-9]+", "_", label.upper()).strip("_")


def existing_hash(cur):
    h = hashlib.sha256()
    for t in ("answers", "answers_history"):
        for row in cur.execute("SELECT org_id, question_id, matrix_row_id, value FROM %s "
                               "WHERE question_id NOT LIKE 'REW265_%%' "
                               "ORDER BY org_id, question_id, matrix_row_id" % t):
            h.update(("|".join(str(x) for x in row) + "\n").encode())
    return h.hexdigest()


rel, hlp, anc, reg = K.load_rows()
c = sqlite3.connect("lumi.db")
c.row_factory = sqlite3.Row
cur = c.cursor()
cur.execute("PRAGMA wal_checkpoint(TRUNCATE)")
tester = cur.execute("SELECT org_id FROM orgs WHERE name='Tester'").fetchone()
tester = tester[0] if tester else None
orgs = [o for (o,) in cur.execute("SELECT DISTINCT org_id FROM answers WHERE snapshot_id=1").fetchall() if o != tester]
assert len(orgs) == 220
prof = {}
for p in ("org_profiles.json", "org_profiles_inferred.json"):
    prof.update(json.load(open(p)))
lat = {o: RE.latent(o, prof) for o in orgs}
sector_of = {o: (((prof.get(o) or {}).get("Industry") or "") + " " + ((prof.get(o) or {}).get("Subsector") or "")).lower() for o in orgs}
fte_db = {r["org_id"]: r["fte_band"] for r in cur.execute("SELECT org_id, fte_band FROM orgs")}


def fte_band(o):
    return fte_db.get(o) or (prof.get(o) or {}).get("FTE_Band")


parent_ans = {r["org_id"]: r["value"] for r in cur.execute(
    "SELECT org_id, value FROM answers WHERE question_id=? AND snapshot_id=1", (K.SHAREPLAN_PARENT,))}

if not WRITE:
    print("DRY: would insert 54 questions + cfg + seed %d orgs" % len(orgs))
    sys.exit(0)

h0 = existing_hash(cur)

# ===== 1. INSERT 54 (help_text <- MEMBER csv; help_why NOT member-visible — D3) =====
qo = cur.execute("SELECT MAX(question_order) FROM questions").fetchone()[0] or 950
for qid, r in rel.items():
    opts = K.split_options(r)
    oj = [{"code": code_of(l), "label": l, "order": i + 1, "is_na": K.is_na_label(l)}
          for i, l in enumerate(opts)]
    sm = "multi_select_count" if r["type"] == "multi_select" else "single_select"
    qo += 1
    cur.execute("""INSERT INTO questions
      (id,text,short_description,help_text,definition,superpower,sub_power,sub_power_order,type,category,
       options_json,default_chart_type,data_display_type,polarity,unit_type,lumi_tier,na_handling_json,
       benchmark_display,is_scored,scoring_config_json,is_required,question_order,question_version,
       historical_comparability,status,release_entered)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (qid, r["text"], r["text"][:120], hlp[qid], r["text"], "Reward", r["category"], K.SPO[r["category"]],
       r["type"], "practice", json.dumps(oj), "bar", "percentage_distribution", r["polarity"],
       "none", "Core", json.dumps({"exclude_from_scoring": True, "exclude_from_benchmarking": False, "na_codes": []}),
       r["text"], 0, json.dumps({"scoring_method": sm, "polarity": r["polarity"]}), 0, qo, "v1.0",
       "n/a", "active", RELEASE))
    cur.execute("""INSERT INTO core_changelog (release_id,lane,change_type,question_id,detail,signed_off_by,created_at)
      VALUES (?,?,?,?,?,?,?)""", (RELEASE, "release", "added", qid,
      "Added in 2026.5 (v1.0). help_why held in the release CSV per D3: %s" % (r.get("help_why", "")[:160]),
      "David Whitfield (Diff 6 approval + riders, 2026-07-14)", STAMP))

# ===== 2. CONFIG (register v8 by id; D5 donor mirror) =====
cfg = json.load(open("data/market_position_config.json"))
donor = cfg["metrics"]["REW26_WEL_MH_SUPPORT"]
for qid, r in rel.items():
    cls = reg[qid]["classification"]
    if cls == "practice":
        cfg["metrics"][qid] = {"class": "Practice", "type": "categorical", "direction": None,
                               "lens": "attract", "weight": 1}
    else:
        cfg["metrics"][qid] = dict(donor)
json.dump(cfg, open("data/market_position_config.json", "w"), indent=2, ensure_ascii=False)

# ===== 3. SEED =====
man = {r["id"]: r for r in csv.DictReader(open("diff6_seed_manifest.csv"))}
ans = []
seeded = {}
for qid, r in rel.items():
    dist = json.loads(man[qid]["target_dist"])
    na_opt = next((o for o in K.split_options(r) if K.is_na_label(o)), None)
    na, answ = [], []
    for o in orgs:
        rng = K.org_rng(qid, o)
        is_na = False
        if qid in K.WIRED:
            pv = (parent_ans.get(o) or "").strip()
            is_na = (not pv) or any(pv.startswith(v) for v in K.SHAREPLAN_NEGATIVE)
        elif qid == "REW265_GOV_GPGNAMING":
            is_na = fte_band(o) == "50-249"            # rider 1 — derived, no global rate
        elif qid == "REW265_INC_COMMCAP":
            is_na = not any(s in sector_of[o] for s in K.SALES_HEAVY)
        elif qid in K.SELF_NA_PRIOR and isinstance(K.SELF_NA_PRIOR[qid], float):
            is_na = rng.random() < K.SELF_NA_PRIOR[qid]
        (na if is_na and na_opt else answ).append(o)
    assign = {}
    if r["type"] == "multi_select":
        opts = [o for o in K.split_options(r) if not K.is_na_label(o) and o != "None"]
        if qid == "REW265_INC_SIPELEM":
            # rider 2: explicit No-SIP share among parent-positive orgs; the rest pick elements
            for o in answ:
                rng = K.org_rng(qid, o)
                if rng.random() < K.NO_SIP_SHARE:
                    assign[o] = "No SIP operated"
                else:
                    ch = [x for x in opts if K.org_rng(qid + x, o).random() <= max(0.10, dist.get(x, 0.3))]
                    assign[o] = ";".join(ch) if ch else "Free shares"
        else:
            per_opt = {x: max(0.06, dist.get(x, 0.15)) for x in opts}
            for o in answ:
                rng = K.org_rng(qid, o)
                ch = [x for x, p in per_opt.items() if rng.random() <= p]
                assign[o] = ";".join(ch) if ch else "None"
    else:
        groups = [(answ, dist)]
        if qid in K.TILTS:
            sects, delta = K.TILTS[qid]
            hit = [o for o in answ if any(s in sector_of[o] for s in sects)]
            plain = [o for o in answ if o not in set(hit)]
            groups = [(plain, dist), (hit, K.tilt(dist, delta))]
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
    seeded[qid] = assign
    for o in orgs:
        if o in assign and assign[o]:
            ans.append((o, 1, qid, "", assign[o], STAMP))

cur.executemany("INSERT INTO answers (org_id,snapshot_id,question_id,matrix_row_id,value,submitted_at) VALUES (?,?,?,?,?,?)", ans)
c.commit()
cur.execute("PRAGMA wal_checkpoint(TRUNCATE)")

assert existing_hash(cur) == h0, "PRE-EXISTING ANSWER ROWS MOVED — restore backup"
stray = cur.execute("SELECT COUNT(*) FROM answers WHERE submitted_at=? AND question_id NOT LIKE 'REW265_%'", (STAMP,)).fetchone()[0]
assert stray == 0

from collections import Counter
out = []
for row in csv.DictReader(open("diff6_seed_manifest.csv")):
    qid = row["id"]
    vals = seeded.get(qid, {})
    n = len(vals)
    na_n = sum(1 for v in vals.values() if v and K.is_na_label(v))
    top = Counter(v for v in vals.values() if v and not K.is_na_label(v)).most_common(3)
    row["seeded_n"] = n
    row["seeded_na"] = na_n
    if qid == "REW265_INC_SIPELEM":
        pos_n = sum(1 for o, v in vals.items() if v and v != "No SIP operated"
                    and not any((parent_ans.get(o) or "").startswith(x) for x in K.SHAREPLAN_NEGATIVE))
        nosip = sum(1 for v in vals.values() if v == "No SIP operated")
        row["seeded_top"] = "No SIP operated %d of %d parent-positive (rider 2); elements %d" % (nosip, nosip + pos_n, pos_n)
    else:
        row["seeded_top"] = "; ".join("%s %.0f%%" % (k[:26], 100 * v / max(1, n - na_n)) for k, v in top)
    out.append(row)
with open("diff6_seed_manifest.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader()
    w.writerows(out)
print("inserted 54 questions + cfg; %d answer rows across %d orgs; append-only hash IDENTICAL" % (len(ans), len(orgs)))
