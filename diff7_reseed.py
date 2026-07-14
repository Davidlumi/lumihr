#!/usr/bin/env python3
"""DIFF 7 — seed realism reseed (surgical). Corrects seeded answers on the 99 wave
metrics (REW264_*/REW265_*) per David's rulings R1-R4 + (1)(2)(3). Old book is ground
truth and is NEVER written — hash-asserted byte-identical. Append-only: snapshot the
prior value into answers_history, DELETE the answers row, INSERT the corrected value.
Deterministic per-org RNG sha256(qid|SEED_DATE|org_id). Double-guarded --write
--confirmed-by-david. Authority: lumi_seed_realism_fix_targets.csv (12 rows).

Five fix classes: F1 legal-form flips; F2 cross-book conditioning (EVSALSAC/COMMCAP/
SALSAC); F3 anchor shapes + F4 pole corrections (12 target rows, EOT KEEP); F5 shape
jitter on 63 conservative-tier single-selects.
Run: python3 diff7_reseed.py            (DRYRUN: manifest + ledger, no writes)
     python3 diff7_reseed.py --write --confirmed-by-david
"""
import csv
import hashlib
import json
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict

sys.path.insert(0, ".")
sys.path.insert(0, "server")
import reseed_engine as RE  # latent()

SEED_DATE = "2026-07-14"
STAMP = "2026-07-14 22:30:00"
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
DB = os.environ.get("LUMI_DB", "lumi.db")
WAVE_LIKE = ("REW264_", "REW265_")
EOT = "REW265_INC_EOT"                      # R2 KEEP — never touched, asserted identical

# ---- deterministic helpers -------------------------------------------------
def org_rng(salt, org_id):
    import random
    return random.Random(hashlib.sha256(f"{salt}|{SEED_DATE}|{org_id}".encode()).hexdigest())


def metric_jit(qid):
    """Deterministic per-metric signed jitter magnitude in [0.05, 0.08] (F5)."""
    h = int(hashlib.sha256(f"{qid}|{SEED_DATE}|jit".encode()).hexdigest()[:8], 16)
    mag = 0.05 + (h % 31) / 1000.0            # 0.050 .. 0.080
    sign = 1 if (h >> 8) & 1 else -1
    return sign * mag


def largest_remainder(dist, m):
    raw = {o: dist[o] * m for o in dist}
    base = {o: int(raw[o]) for o in dist}
    short = m - sum(base.values())
    for o in sorted(dist, key=lambda o: -(raw[o] - base[o]))[:short]:
        base[o] += 1
    return base


def assign_by_latent(orgs, counts, lean_to_gen, lat, salt):
    """orgs get options so leanest option -> lowest latent. Returns {org: value}."""
    rank = {o: i for i, o in enumerate(lean_to_gen)}
    seq = []
    for op in sorted(counts, key=lambda o: rank.get(o, 999)):
        seq += [op] * counts[op]
    ordered = sorted(orgs, key=lambda o: (lat.get(o, 0.5), org_rng(salt, o).random()))
    return dict(zip(ordered, seq))


# ---- load -------------------------------------------------------------------
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row
cur = c.cursor()
cur.execute("PRAGMA wal_checkpoint(TRUNCATE)")
orgs = {r["org_id"]: dict(r) for r in cur.execute("SELECT * FROM orgs")}
tester = next((o for o, r in orgs.items() if r["name"] == "Tester"), None)
resp = [o for (o,) in cur.execute("SELECT DISTINCT org_id FROM answers WHERE snapshot_id=1") if o != tester]
assert len(resp) == 220, len(resp)
A = {}
for r in cur.execute("SELECT question_id, org_id, value FROM answers WHERE snapshot_id=1 AND (matrix_row_id IS NULL OR matrix_row_id='')"):
    A[(r["question_id"], r["org_id"])] = r["value"]
prof = {}
for p in ("org_profiles.json", "org_profiles_inferred.json"):
    prof.update(json.load(open(p)))
lat = {o: RE.latent(o, prof) for o in resp}
cfg = json.load(open("data/market_position_config.json"))
def klass(qid):
    return (cfg["metrics"].get(qid) or {}).get("class")
TGT = {r["metric_id"]: r for r in csv.DictReader(open("lumi_seed_realism_fix_targets.csv"))}
a4 = {r["id_hint"]: r for r in csv.DictReader(open("lumi_2026_4_anchor_register.csv"))}
a5 = {r["id_hint"]: r for r in csv.DictReader(open("lumi_2026_5_anchor_register.csv"))}
def opts_of(qid):
    return [o["label"] for o in json.loads(cur.execute("SELECT options_json FROM questions WHERE id=?", (qid,)).fetchone()["options_json"])]
def qtype(qid):
    return cur.execute("SELECT type FROM questions WHERE id=?", (qid,)).fetchone()["type"]

changes = {}          # (qid, org) -> new_value   (only where it differs from current)
ledger = defaultdict(lambda: {"writes": 0})


def set_change(qid, org, val):
    if val is None:
        return
    if A.get((qid, org)) != val:
        changes[(qid, org)] = val


def parse_tgt(row):
    d = {}
    for part in row["target_distribution"].split(";"):
        if "=" not in part:
            return None
        k, v = part.rsplit("=", 1)
        d[k.strip()] = float(v)
    s = sum(d.values())
    return {k: v / s for k, v in d.items()}


# ===================== F1 — legal-form flips =====================
SHARE_OWN = {"Public Listed (PLC)", "Private (UK-owned)", "Private (Founder/Family)",
             "Founder-led (Private)", "VC-backed (Private)", "PE-backed", "Subsidiary of Global Group"}
NONSHARE_OWN = {"Public Sector Body", "Charity / Non-profit", "Mutual / Co-operative", "Partnership / LLP"}
def form(o):
    ot = (orgs[o].get("ownership_type") or "").strip()
    if ot in SHARE_OWN:
        return "share"
    if ot in NONSHARE_OWN:
        return "nonshare"
    nm = orgs[o]["name"] or ""
    if re.search(r"(plc|ltd|limited)\.?$", nm, re.I):
        return "share"
    if re.search(r"(LLP|council|nhs|trust|authority|commission|foundation|university|housing association|society|partnership)\b", nm, re.I):
        return "nonshare"
    return "unknown"

F1 = {"REW264_INC_EMICSOP": "Not applicable (no share capital)",
      "REW264_INC_SHAREPLAN": "Not applicable (no shares)"}
f1_led = {}
for qid, na in F1.items():
    flip = keep = unk = 0
    for o in resp:
        if A.get((qid, o)) != na:
            continue
        f = form(o)
        if f == "share":
            set_change(qid, o, "Neither"); flip += 1
        elif f == "nonshare":
            keep += 1
        else:
            unk += 1
    f1_led[qid] = {"na_total": flip + keep + unk, "flip": flip, "keep": keep, "unknown": unk}
    ledger[qid]["writes"] = flip

# ===================== F2 — cross-book conditioning =====================
# (1) EVSALSAC: positive with no CAR_COST_02 'Yes' -> negative-substantive family
EV = "REW264_BEN_EVSALSAC"
EV_POS = {"EV-only", "EV-led (EV prioritised)"}
ev_neg_family = Counter(A.get((EV, o)) for o in resp
                        if (A.get((EV, o)) or "") not in EV_POS and (A.get((EV, o)) or "") != "Not applicable" and A.get((EV, o)))
ev_neg_dist = {k: v / sum(ev_neg_family.values()) for k, v in ev_neg_family.items()}  # {'Fuel-neutral':1.0}
ev_flippers = [o for o in resp if (A.get((EV, o)) in EV_POS) and not (A.get(("CAR_COST_02", o)) or "").startswith("Yes")]
ev_counts = largest_remainder(ev_neg_dist, len(ev_flippers))
for o, v in assign_by_latent(ev_flippers, ev_counts, list(ev_neg_dist), lat, EV).items():
    set_change(EV, o, v)
ledger[EV]["writes"] = len(ev_flippers)

# (2) COMMCAP: 27 (135=No & substantive) -> NA ; 97 (135=Yes & NA) -> substantive mirror 50/35/15
CC = "REW265_INC_COMMCAP"; CC_NA = "Not applicable (no commission plans)"
cc_sub = {"Hard cap", "Soft cap or decelerator", "Uncapped"}
yes135 = [o for o in resp if (A.get(("REW_INC_135", o)) or "").startswith("Yes")]
cc_to_na = [o for o in resp if not (A.get(("REW_INC_135", o)) or "").startswith("Yes") and A.get((CC, o)) in cc_sub]
for o in cc_to_na:
    set_change(CC, o, CC_NA)
cc_kept = [o for o in yes135 if A.get((CC, o)) in cc_sub]                 # the 26, untouched
cc_fill = [o for o in yes135 if A.get((CC, o)) == CC_NA]                  # the 97
cc_target_prop = {"Hard cap": 0.50, "Soft cap or decelerator": 0.35, "Uncapped": 0.15}
cc_target_ct = largest_remainder(cc_target_prop, len(yes135))            # over full 123
kept_ct = Counter(A.get((CC, o)) for o in cc_kept)
cc_gap = {k: max(0, cc_target_ct.get(k, 0) - kept_ct.get(k, 0)) for k in cc_target_prop}
# reconcile gap to exactly len(cc_fill)
diff = len(cc_fill) - sum(cc_gap.values())
for k in sorted(cc_gap, key=lambda k: -cc_target_prop[k]):
    if diff == 0:
        break
    step = 1 if diff > 0 else -1
    if cc_gap[k] + step >= 0:
        cc_gap[k] += step; diff -= step
cc_order = ["Uncapped", "Soft cap or decelerator", "Hard cap"]           # lean->generous (capped=stricter=lean? treat Hard cap as generous-to-employer control); latent pairing only
for o, v in assign_by_latent(cc_fill, cc_gap, cc_order, lat, CC).items():
    set_change(CC, o, v)
ledger[CC]["writes"] = len(cc_to_na) + len(cc_fill)

# (3) SALSAC: 66 NA-with-evidence -> substantive, mirror each metric's substantive marginal
def salsac_evidence(o):
    if (A.get(("REW26_BEN_SALSAC", o)) or "").startswith("Yes"):
        return True
    v = A.get(("WEL_BMAP_FIN_SALARY_SACRIFICE_001", o)) or ""
    return any(x.strip() and x.strip() not in ("None of the above", "Don't know", "Other (not listed)") for x in v.split(";"))
for qid in ("REW264_PEN_SALSACIMPACT", "REW264_PEN_SALSACRESPONSE"):
    na_lab = next(l for l in opts_of(qid) if l.startswith("Not applicable"))
    subs = [l for l in opts_of(qid) if not l.startswith("Not applicable")]
    marg = Counter(A.get((qid, o)) for o in resp if A.get((qid, o)) in subs)
    dist = {k: marg[k] / sum(marg.values()) for k in subs}
    flippers = [o for o in resp if A.get((qid, o)) == na_lab and salsac_evidence(o)]
    counts = largest_remainder(dist, len(flippers))
    lean_gen = sorted(subs, key=lambda k: dist[k])          # least-common -> most-common as pseudo-order
    for o, v in assign_by_latent(flippers, counts, lean_gen, lat, qid).items():
        set_change(qid, o, v)
    ledger[qid]["writes"] = len(flippers)

# ===================== F3/F4 — 12 target rows =====================
LEAN_ORDER = {
    "REW265_INC_SAYEDISC": ["No discount", "Under 10%", "10–19%", "20% (maximum)"],
    "REW265_INC_SHAREPART": ["Under 10%", "10–25%", "26–50%", "Over 50%"],
    "REW265_INC_BONUSTIME": ["Over 4 months", "3–4 months", "Within 3 months of year end"],
    "REW265_TIME_WORKATION": ["Prohibited", "Formal cap (days per year)", "Case-by-case", "Uncapped"],
    "REW265_INC_BONUSDISC": ["No discretion — formula applies", "Discretion applied, undocumented", "Manager discretion", "Committee discretion, documented"],
    "REW264_PEN_GREENDEFAULT": ["Standard default", "Unsure", "ESG-tilted", "Yes net-zero aligned"],
    "REW265_GOV_BROKER": ["None", "Project-based adviser", "Full-service broker"],
    "REW265_GOV_REBROKE": ["Never", "Less often than every 3 years", "Every 2–3 years", "Annually"],
}
APPLICABLE_NA = {"REW265_INC_SAYEDISC": "Not applicable", "REW265_INC_SHAREPART": "Not applicable",
                 "REW264_PEN_GREENDEFAULT": "Not applicable (no DC default fund)"}

def reshape_single(qid, extra_sortkey=None):
    dist = parse_tgt(TGT[qid])
    na = APPLICABLE_NA.get(qid)
    base = [o for o in resp if not (na and A.get((qid, o)) == na)]
    counts = largest_remainder(dist, len(base))
    order = LEAN_ORDER[qid]
    rank = {o: i for i, o in enumerate(order)}
    seq = [op for op in sorted(counts, key=lambda o: rank.get(o, 999)) for _ in range(counts[op])]
    key = extra_sortkey or (lambda o: (lat.get(o, 0.5), org_rng(qid, o).random()))
    for o, v in zip(sorted(base, key=key), seq):
        set_change(qid, o, v)
    ledger[qid]["writes"] = sum(1 for o in base if (qid, o) in changes)

# straightforward reshapes
for qid in ("REW265_INC_SAYEDISC", "REW265_INC_SHAREPART", "REW265_INC_BONUSTIME",
            "REW265_TIME_WORKATION", "REW265_INC_BONUSDISC", "REW264_PEN_GREENDEFAULT"):
    reshape_single(qid)
# BROKER first, then REBROKE with coherence: no-broker orgs cluster at the lean (Never) end
reshape_single("REW265_GOV_BROKER")
brk_none = {o for o in resp if (changes.get(("REW265_GOV_BROKER", o), A.get(("REW265_GOV_BROKER", o))) or "").startswith("None")}
reshape_single("REW265_GOV_REBROKE", extra_sortkey=lambda o: (0 if o in brk_none else 1, lat.get(o, 0.5), org_rng("REW265_GOV_REBROKE", o).random()))

# HOLPAYMETHOD: rolled-up mass concentrated in hosp/retail/leisure sector
HP = "REW264_PAY_HOLPAYMETHOD"
def sector(o):
    return ((orgs[o].get("industry") or "") + " " + (orgs[o].get("subsector") or "")).lower()
hp_sec = [o for o in resp if any(s in sector(o) for s in ("hospitalit", "retail", "leisure", "food", "grocery", "travel"))]
hp_non = [o for o in resp if o not in set(hp_sec)]
hp_dist = parse_tgt(TGT[HP])
hp_ct = largest_remainder(hp_dist, 220)                          # rolled-up target count
roll_n = hp_ct["Rolled-up 12.07%"]
# all rolled-up -> lowest-latent sector orgs; remainder distributed 52-wk/accrual/unsure
hp_sec_sorted = sorted(hp_sec, key=lambda o: (lat.get(o, 0.5), org_rng(HP, o).random()))
roll_orgs = hp_sec_sorted[:roll_n]
rest_orgs = [o for o in resp if o not in set(roll_orgs)]
rest_dist = {k: hp_dist[k] for k in ("52-week average", "Accrual per GB regs", "Unsure")}
rest_dist = {k: v / sum(rest_dist.values()) for k, v in rest_dist.items()}
rest_ct = largest_remainder(rest_dist, len(rest_orgs))
for o in roll_orgs:
    set_change(HP, o, "Rolled-up 12.07%")
for o, v in assign_by_latent(rest_orgs, rest_ct, ["Unsure", "Accrual per GB regs", "52-week average"], lat, HP).items():
    set_change(HP, o, v)
ledger[HP]["writes"] = sum(1 for o in resp if (HP, o) in changes)

# SIPELEM (multi): per-option incidence among current SIP operators
SIP = "REW265_INC_SIPELEM"
sip_ops = [o for o in resp if (A.get((SIP, o)) or "") not in ("No SIP operated", "", None)]
sip_inc = {k: v / 100.0 for k, v in ((p.rsplit("=", 1)[0].strip(), float(p.rsplit("=", 1)[1]))
                                     for p in TGT[SIP]["target_distribution"].split(";"))}
SIP_ORD = ["Partnership shares", "Matching shares", "Free shares", "Dividend shares"]
# exact per-option incidence (small base n=27 -> Bernoulli variance blows TOL; assign
# each option to exactly round(incidence*n) operators, chosen by per-(option,org) RNG)
sip_pick = {o: [] for o in sip_ops}
for opt in SIP_ORD:
    k = round(sip_inc.get(opt, 0) * len(sip_ops))
    for o in sorted(sip_ops, key=lambda o: org_rng(SIP + "|" + opt, o).random())[:k]:
        sip_pick[o].append(opt)
for o in sip_ops:
    picks = sip_pick[o] or ["Partnership shares"]
    set_change(SIP, o, ";".join(x for x in SIP_ORD if x in picks))
ledger[SIP]["writes"] = sum(1 for o in sip_ops if (SIP, o) in changes)

# CHILDCARE (multi): preserve 20 old-book nursery holders; reshape rest to incidence
CH = "REW264_TIME_CHILDCARE"
ch_inc = {k: v / 100.0 for k, v in ((p.rsplit("=", 1)[0].strip(), float(p.rsplit("=", 1)[1]))
                                    for p in TGT[CH]["target_distribution"].split(";"))}
nursery_evidence = [o for o in resp if (A.get(("WEL_SUP_FAC_002", o)) or "").lower().startswith("yes")
                    and "Workplace nursery" in (A.get((CH, o)) or "")]
preserve = set(nursery_evidence)
# exact per-option incidence (over the full 220) for the three non-nursery options;
# nursery = the preserved floor only (binding override of the 4% target on that cell).
CH_ORD = ["Nursery partnership/subsidy", "Backup/emergency care", "Childcare concierge"]
free = [o for o in resp if o not in preserve]
ch_pick = {o: [] for o in free}
for opt in CH_ORD:
    k = round(ch_inc.get(opt, 0) * len(resp))
    for o in sorted(free, key=lambda o: org_rng(CH + "|" + opt, o).random())[:k]:
        ch_pick[o].append(opt)
for o in free:
    picks = ch_pick[o]
    set_change(CH, o, ";".join(picks) if picks else "None")
ledger[CH]["writes"] = sum(1 for o in resp if (CH, o) in changes)

# EOT — KEEP (assert no change touches it)
assert not any(k[0] == EOT for k in changes), "EOT must be byte-identical (R2)"

# ===================== F5 — shape jitter =====================
NEAR_FLOOR = {"REW265_TIME_GRANDPARENT", "REW265_TIME_UNLIMITEDAL", "REW265_TIME_LEAVEDONATE", EOT}
F1F2 = {"REW264_INC_EMICSOP", "REW264_INC_SHAREPLAN", EV, CC, "REW264_PEN_SALSACIMPACT", "REW264_PEN_SALSACRESPONSE"}
def tier(qid):
    r = a4.get(qid) or a5.get(qid)
    return r["status"] if r else "?"
def is_na_lab(l):
    ll = (l or "").lower()
    return ll.startswith("not applicable") or ll.startswith("not in scope")
def na_labels(qid):
    """Scope-out/NA option labels for a metric — the options_json is_na flag PLUS the
    label pattern. NICSHARING's 'No sal-sac scheme' is is_na but not label-matched; a
    label-only base would reshuffle those scope-out orgs into substantive answers and
    manufacture comparable readings (caught by the Thornbridge 279->281 ledger)."""
    return {o["label"] for o in json.loads(cur.execute("SELECT options_json FROM questions WHERE id=?", (qid,)).fetchone()["options_json"])
            if o.get("is_na") or is_na_lab(o["label"])}
def anchor_ceiling(qid):
    r = a4.get(qid) or a5.get(qid)
    t = (r or {}).get("real_anchor") or ""
    if re.search(r"\d+\s*[–-]\s*\d+\s*%", t) or re.search(r"\bband\b|\bmedian\b|\bregion\b", t, re.I):
        return None
    m = re.search(r"(\d{1,2}(?:\.\d)?)\s*%", t)
    return float(m.group(1)) / 100.0 if m else None

jit_rows = []
for qid in sorted({q for q in (set(a4) | set(a5))
                   if q.startswith(WAVE_LIKE) and qtype(q) == "single_select"
                   and q not in TGT and q not in NEAR_FLOOR and q not in F1F2 and tier(q) != "anchored"}):
    nal = na_labels(qid)
    subs = [l for l in opts_of(qid) if l not in nal]
    base = [o for o in resp if (A.get((qid, o)) or "") not in nal and A.get((qid, o))]
    if len(subs) < 2 or not base:
        continue
    cur_ct = Counter(A.get((qid, o)) for o in base)
    lean = max(subs, key=lambda s: cur_ct.get(s, 0))          # modal = conservative lean pole
    p_lean = cur_ct.get(lean, 0) / len(base)
    rest = [s for s in subs if s != lean]
    # High-entropy deterministic reshape: a per-metric lean level with fine resolution
    # + a per-(metric,option) descending tail, so no two jittered rows share a rounded
    # shape (the house-shape pathology). Each derived purely from qid -> deterministic.
    ha = int(hashlib.sha256((qid + "|" + SEED_DATE + "|lean").encode()).hexdigest()[:8], 16)
    new_lean = 0.60 + (ha % 200) / 1000.0                     # [0.600, 0.799], 200 buckets
    ceil = anchor_ceiling(qid)
    if ceil is not None and (1 - new_lean) > ceil + 0.02:     # respect verify-queued ceiling
        new_lean = max(0.55, 1 - ceil)
    rest_sorted = sorted(rest, key=lambda s: -cur_ct.get(s, 0))   # keep current descending order
    raw = [50 + int(hashlib.sha256((qid + "|" + s).encode()).hexdigest()[:8], 16) % 100 for s in rest_sorted]
    raw = sorted(raw, reverse=True)                           # descending tail weights
    tw = sum(raw) or 1
    dist = {lean: new_lean}
    for s, wgt in zip(rest_sorted, raw):
        dist[s] = (1 - new_lean) * wgt / tw
    counts = largest_remainder(dist, len(base))
    order = [lean] + rest_sorted
    for o, v in assign_by_latent(base, counts, order, lat, qid).items():
        set_change(qid, o, v)
    w = sum(1 for o in base if (qid, o) in changes)
    ledger[qid]["writes"] = w
    jit_rows.append((qid, tier(qid), round(p_lean, 3), round(new_lean, 3), ceil, w))

# ===================== manifest + ledger =====================
total_writes = len(changes)
print("DIFF 7 %s — %d cell changes across %d metrics" % ("WRITE" if WRITE else "DRYRUN", total_writes, len({k[0] for k in changes})))
print("F1:", f1_led)
print("F2 EVSALSAC flips:", len(ev_flippers), "-> neg family", dict(ev_neg_family), "(single-option -> flat 'Fuel-neutral')")
print("F2 COMMCAP: to_na", len(cc_to_na), "| fill_97 gap", cc_gap, "| kept_26", dict(kept_ct), "| target_123", cc_target_ct)
print("F2 SALSAC writes:", {q: ledger[q]["writes"] for q in ("REW264_PEN_SALSACIMPACT", "REW264_PEN_SALSACRESPONSE")})
print("CHILDCARE preserved nursery holders:", len(preserve))
print("F5 jitter rows:", len(jit_rows))

man_rows = []
for qid in sorted({k[0] for k in changes} | set(TGT)):
    q_changes = {o: v for (qq, o), v in changes.items() if qq == qid}
    new_marg = Counter(changes.get((qid, o), A.get((qid, o))) for o in resp)
    n = sum(new_marg.values())
    top = "; ".join("%s %.0f%%" % (k[:24], 100 * new_marg[k] / max(1, n)) for k in sorted(new_marg, key=lambda k: -new_marg[k])[:5] if k)
    fclass = ("F1" if qid in F1 else "F2" if qid in {EV, CC, "REW264_PEN_SALSACIMPACT", "REW264_PEN_SALSACRESPONSE"}
              else "F3/F4-target" if qid in TGT else "F5-jitter")
    tgt = TGT[qid]["target_distribution"] if qid in TGT else ""
    man_rows.append({"metric_id": qid, "fix_class": fclass, "class": klass(qid) or "",
                     "writes": len(q_changes), "target": tgt[:80], "achieved_top": top})
with open("diff7_seed_manifest.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["metric_id", "fix_class", "class", "writes", "target", "achieved_top"])
    w.writeheader(); w.writerows(man_rows)
print("manifest: diff7_seed_manifest.csv (%d rows)" % len(man_rows))

if not WRITE:
    print("\nDRY — no DB writes. Inspect diff7_seed_manifest.csv, then --write --confirmed-by-david.")
    sys.exit(0)

# ===================== APPLY (append-only) =====================
def oldbook_hash(cur):
    h = hashlib.sha256()
    for r in cur.execute("SELECT org_id, question_id, matrix_row_id, value FROM answers "
                         "WHERE question_id NOT LIKE 'REW264_%' AND question_id NOT LIKE 'REW265_%' "
                         "ORDER BY org_id, question_id, matrix_row_id"):
        h.update(("|".join(str(x) for x in r) + "\n").encode())
    return h.hexdigest()

h0 = oldbook_hash(cur)
eot_before = cur.execute("SELECT org_id, value FROM answers WHERE question_id=? AND snapshot_id=1 ORDER BY org_id", (EOT,)).fetchall()
eot_before = [tuple(r) for r in eot_before]

n = 0
for (qid, org), newv in changes.items():
    old = cur.execute("SELECT value, submitted_at FROM answers WHERE org_id=? AND snapshot_id=1 AND question_id=? AND (matrix_row_id IS NULL OR matrix_row_id='')", (org, qid)).fetchone()
    if old is not None:
        cur.execute("INSERT INTO answers_history (org_id, snapshot_id, question_id, matrix_row_id, value, recorded_at) VALUES (?,1,?,'',?,?)",
                    (org, qid, old["value"], old["submitted_at"] or STAMP))
    cur.execute("DELETE FROM answers WHERE org_id=? AND snapshot_id=1 AND question_id=? AND (matrix_row_id IS NULL OR matrix_row_id='')", (org, qid))
    cur.execute("INSERT INTO answers (org_id, snapshot_id, question_id, matrix_row_id, value, submitted_at) VALUES (?,1,?,'',?,?)", (org, qid, newv, STAMP))
    cur.execute("INSERT INTO answers_history (org_id, snapshot_id, question_id, matrix_row_id, value, recorded_at) VALUES (?,1,?,'',?,?)", (org, qid, newv, STAMP))
    n += 1
c.commit()
cur.execute("PRAGMA wal_checkpoint(TRUNCATE)")

assert oldbook_hash(cur) == h0, "OLD BOOK MOVED — restore lumi.db.bak_pre_diff7_20260714"
eot_after = [tuple(r) for r in cur.execute("SELECT org_id, value FROM answers WHERE question_id=? AND snapshot_id=1 ORDER BY org_id", (EOT,)).fetchall()]
assert eot_after == eot_before, "EOT changed — R2 violated"
print("APPLIED %d cell changes. old book hash IDENTICAL. EOT byte-identical." % n)
