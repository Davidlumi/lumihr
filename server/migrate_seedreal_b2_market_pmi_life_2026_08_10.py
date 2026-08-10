#!/usr/bin/env python3
"""Seed-realism B2 — market calibration: life assurance + PMI cluster (2026-08-10).

Tier-2 batch, part 1 (the two biggest, interlinked insured-benefit reshapes). Both
metrics are free (not frozen, not marginals). LUMI_DB-aware; DRY-RUN unless
--write --confirmed-by-david.

LIFE ASSURANCE (REW_BEN_045). Was under-seeded and — implausibly — rarer than PMI:
offered 60% overall, only 23%/31% at 50-249/250-999. Group life/death-in-service is
the cheapest, most prevalent UK insured benefit (near-universal at 1,000+). Raise to
a realistic rising gradient; when flipping 'Not offered' -> offered, do the
death-in-service sectors first (Construction/Logistics/Manufacturing — CIJC-style
norms), which also fixes the "Construction worst for death-in-service" finding.
Multiples assigned by band (2x mid, 4x+ at the top). Result: life > PMI globally.

PMI CLUSTER (REW_BEN_100 proportion-eligible, REW_BEN_044 eligibility rule,
REW_BEN_139 by-level matrix). The real PMI population = the 154 orgs with a 139
matrix, and that population already has a healthy 40%->94% size gradient. The defect
was that REW_BEN_100 (220 answers) and REW_BEN_044 were seeded INDEPENDENTLY of the
139 cluster — leaving ~50 orgs "offered" with no eligibility detail, 14 orgs
"Not offered" that contradict their own 139 Yes-rows, and 12 "All employees" orgs
with senior-only matrices. Fix by making 100 and 044 COHERE with 139 depth:
  - 0 Yes levels           -> 100 'Not offered'
  - senior levels only      -> 100 '10-24%',  044 'Grade/level restricted'
  - reaches manager         -> 100 '25-49%',  044 'Grade/level restricted'
  - reaches supervisor      -> 100 '50-74%',  044 'All employees'
  - reaches frontline       -> 100 '75%+',    044 'All employees'
Orgs with NO 139 matrix (66) -> 100 'Not offered' (they are not PMI-havers).
Then seed all-staff schemes: extend 139 (frontline+supervisor+manager = Yes) for a
deterministic subset of Tech/FS/Professional PMI-havers, since all-employee PMI is a
market norm there and the bank currently has zero frontline-eligible schemes.

REW_BEN_038 PMI/life checklist membership is realigned to these parents in the later
coherence-rederivation batch, not here.

    python3 server/migrate_seedreal_b2_market_pmi_life_2026_08_10.py                        # dry run
    python3 server/migrate_seedreal_b2_market_pmi_life_2026_08_10.py --write --confirmed-by-david
"""
import os, sys, sqlite3
from collections import defaultdict, Counter

DB = os.environ.get("LUMI_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi.db")
WRITE = "--write" in sys.argv and "--confirmed-by-david" in sys.argv
ORDER = ["50-249", "250-999", "1,000-4,999", "5,000-9,999", "10,000+"]
LEVELS = ["board_executive", "director", "head_of", "senior_manager", "manager",
          "supervisor_team_leader", "frontline_individual_contributor"]
LIFE_TARGET = {"50-249": .60, "250-999": .75, "1,000-4,999": .90, "5,000-9,999": .94, "10,000+": .97}
LIFE_MULT = {"50-249": "2×", "250-999": "2×", "1,000-4,999": "3×", "5,000-9,999": "3×", "10,000+": "4× or more"}
DIS_SECTORS = ("Construction", "Logistics", "Manufacturing")   # death-in-service-first flip priority
ALLSTAFF_SECTORS = {"Technology, Software & Digital", "Financial Services", "Professional Services"}
N_ALLSTAFF_SEED = 10


def main():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    fte = {r["org_id"]: r["fte_band"] for r in c.execute("SELECT org_id,fte_band FROM orgs WHERE classified=1")}
    ind = {r["org_id"]: r["industry"] for r in c.execute("SELECT org_id,industry FROM orgs WHERE classified=1")}
    changes = defaultdict(int)

    def g1(q):
        return {a["org_id"]: a["value"] for a in c.execute(
            "SELECT org_id,value FROM answers WHERE question_id=? AND matrix_row_id='' AND snapshot_id=1", (q,))}

    def setv(q, org, row, new):
        cur = c.execute("SELECT value FROM answers WHERE org_id=? AND question_id=? AND matrix_row_id=? AND snapshot_id=1",
                        (org, q, row)).fetchone()
        if cur is None or (cur["value"] or "") == new:
            return
        changes[q] += 1
        if WRITE:
            c.execute("UPDATE answers SET value=? WHERE org_id=? AND question_id=? AND matrix_row_id=? AND snapshot_id=1",
                      (new, org, q, row))

    # ================= LIFE ASSURANCE (REW_BEN_045) =================
    life = g1("REW_BEN_045")
    byband = defaultdict(list)
    for o in sorted(life):
        if o in fte:
            byband[fte[o]].append(o)
    for band, orgs in byband.items():
        tgt = round(LIFE_TARGET[band] * len(orgs))
        offered = [o for o in orgs if "Not offered" not in str(life[o])]
        notoff = [o for o in orgs if "Not offered" in str(life[o])]
        # flip death-in-service sectors first, then the rest (deterministic by org_id)
        notoff.sort(key=lambda o: (0 if any(s in str(ind.get(o, "")) for s in DIS_SECTORS) else 1, o))
        need = max(0, tgt - len(offered))
        for o in notoff[:need]:
            setv("REW_BEN_045", o, "", LIFE_MULT[band])
    # unclassified answering orgs: lift toward ~65% offered so life > PMI globally
    uncl = [o for o in sorted(life) if o not in fte]
    un_off = [o for o in uncl if "Not offered" not in str(life[o])]
    un_no = [o for o in uncl if "Not offered" in str(life[o])]
    for o in un_no[:max(0, round(.65 * len(uncl)) - len(un_off))]:
        setv("REW_BEN_045", o, "", "2×")

    # ================= PMI CLUSTER (REW_BEN_100 / 044 / 139) =================
    m139 = defaultdict(dict)
    for a in c.execute("SELECT org_id,matrix_row_id,value FROM answers WHERE question_id='REW_BEN_139' AND snapshot_id=1"):
        m139[a["org_id"]][a["matrix_row_id"]] = a["value"]
    pop = set(m139)

    # (a) seed all-staff schemes: extend 139 for a subset of Tech/FS/Prof PMI-havers
    cand = sorted(o for o in pop if ind.get(o) in ALLSTAFF_SECTORS
                  and m139[o].get("frontline_individual_contributor") != "Yes")
    for o in cand[:N_ALLSTAFF_SEED]:
        for lvl in ("manager", "supervisor_team_leader", "frontline_individual_contributor"):
            setv("REW_BEN_139", o, lvl, "Yes")
            m139[o][lvl] = "Yes"   # reflect for the state computation below

    # (b) realign REW_BEN_100 + REW_BEN_044 to each org's 139 depth
    def pmi_state(mm):
        yes = {l for l in LEVELS if mm.get(l) == "Yes"}
        if not yes:
            return ("Not offered", None)
        if "frontline_individual_contributor" in yes:
            return ("75%+", "All employees")
        if "supervisor_team_leader" in yes:
            return ("50–74%", "All employees")
        if "manager" in yes:
            return ("25–49%", "Grade/level restricted")
        return ("10–24%", "Grade/level restricted")

    b100 = g1("REW_BEN_100")
    for org in b100:
        if org in pop:
            band100, rule044 = pmi_state(m139[org])
            setv("REW_BEN_100", org, "", band100)
            if rule044 is not None:
                setv("REW_BEN_044", org, "", rule044)
        else:
            setv("REW_BEN_100", org, "", "Not offered")

    if WRITE:
        c.commit()

    # ---- report ----
    print(("APPLIED" if WRITE else "DRY RUN") + " — cell changes: " + str(dict(changes)))
    life2 = g1("REW_BEN_045")
    off = lambda d: {b: f"{sum(1 for o in byband[b] if 'Not offered' not in str(d[o]))}/{len(byband[b])}" for b in ORDER}
    print("  LIFE offered by band:", off(life2))
    life_g = sum(1 for v in life2.values() if "Not offered" not in str(v))
    b100b = g1("REW_BEN_100")
    pmi_g = sum(1 for v in b100b.values() if "Not offered" not in str(v))
    print("  LIFE offered global: %d/%d ; PMI offered global: %d/%d (life must exceed PMI)" %
          (life_g, len(life2), pmi_g, len(b100b)))
    print("  PMI by band:", {b: f"{sum(1 for o in byband[b] if 'Not offered' not in str(b100b.get(o,'')))}/{len(byband[b])}" for b in ORDER})
    # all-staff count
    allstaff = sum(1 for o in m139 if m139[o].get("frontline_individual_contributor") == "Yes"
                   or (WRITE and False))
    fr = sum(1 for o in m139 if c.execute("SELECT value FROM answers WHERE org_id=? AND question_id='REW_BEN_139' AND matrix_row_id='frontline_individual_contributor' AND snapshot_id=1", (o,)).fetchone()["value"] == "Yes")
    print("  PMI frontline-eligible (all-staff) orgs now: %d" % fr)
    c.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
