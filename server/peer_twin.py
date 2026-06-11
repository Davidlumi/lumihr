"""Peer Twin — 'Organisations like you'.

Cosine similarity over the Phase 1 similarity vectors (one-hot categoricals +
min-max numerics). Top-K most similar registry-matched orgs form a bespoke
peer group (K=12, never below 8). Aggregates for the twin cut run through the
SAME engine code path as every other cut, so n>=5 suppression is enforced
identically. Peer names are never exposed — only the attribute rationale.
"""
import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_conn, uj, j, get_meta
from aggregate import aggregate_question_for_orgs, load_answers
from library import load_questions

TWIN_K = 12
TWIN_MIN_K = 8

# Attributes shown in the "Why these peers?" panel (categoricals only —
# numeric closeness is described, not listed).
RATIONALE_ATTRS = [
    ("Industry", "Industry"), ("FTE_Band", "Size (FTE band)"),
    ("Ownership_Type", "Ownership"), ("Archetype", "Organisation archetype"),
    ("Turnover_Band", "Turnover band"), ("Avg_Tenure_Band", "Average tenure"),
    ("HR_Maturity", "HR maturity"), ("Operating_Model", "Operating model"),
    ("Business_Maturity", "Business maturity"),
]


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def compute_twin(conn, org_id, force=False):
    """Returns {peer_org_ids, rationale} or None if the org has no vector."""
    if not force:
        row = conn.execute("SELECT * FROM peer_twin_cache WHERE org_id=?", (org_id,)).fetchone()
        if row:
            return {"peer_org_ids": uj(row["peer_org_ids_json"]),
                    "rationale": uj(row["rationale_json"])}
    me = conn.execute("SELECT * FROM orgs WHERE org_id=?", (org_id,)).fetchone()
    if me is None or not me["similarity_vector_json"]:
        return None
    my_vec = uj(me["similarity_vector_json"])
    my_reg = uj(me["registry_json"], {})

    sims = []
    candidates = conn.execute(
        "SELECT org_id, similarity_vector_json, registry_json FROM orgs "
        "WHERE similarity_vector_json IS NOT NULL AND org_id != ? AND submission_complete=1",
        (org_id,)).fetchall()
    for c in candidates:
        sims.append((cosine(my_vec, uj(c["similarity_vector_json"])), c["org_id"],
                     uj(c["registry_json"], {})))
    sims.sort(key=lambda t: -t[0])
    k = max(TWIN_MIN_K, min(TWIN_K, len(sims)))
    chosen = sims[:k]
    if len(chosen) < TWIN_MIN_K:
        return None

    # rationale: which attributes the twin group shares with the org
    shared = []
    for attr, label in RATIONALE_ATTRS:
        mine = my_reg.get(attr)
        if mine is None:
            continue
        same = sum(1 for _s, _o, reg in chosen if reg.get(attr) == mine)
        shared.append({"attribute": label, "your_value": mine,
                       "matching_peers": same, "of": len(chosen)})
    shared.sort(key=lambda s: -s["matching_peers"])
    rationale = {
        "k": len(chosen),
        "similarity_range": [round(chosen[-1][0], 3), round(chosen[0][0], 3)],
        "attributes": shared,
        "note": ("Your twin group is the %d organisations most similar to you across "
                 "industry, size, ownership, workforce shape and HR context. "
                 "Peer organisations are never named.") % len(chosen),
    }
    peer_ids = [oid for _s, oid, _r in chosen]
    conn.execute(
        "INSERT OR REPLACE INTO peer_twin_cache(org_id, peer_org_ids_json, rationale_json) VALUES (?,?,?)",
        (org_id, j(peer_ids), j(rationale)))
    conn.commit()
    return {"peer_org_ids": peer_ids, "rationale": rationale}


_twin_payload_cache = {}


def twin_blocks(conn, org_id, snapshot_id=1):
    """{question_id: {main, rows: {row_id: block}, score}} computed through the
    standard engine path (same suppression). Cached in-process per org."""
    key = (org_id, snapshot_id)
    if key in _twin_payload_cache:
        return _twin_payload_cache[key]
    twin = compute_twin(conn, org_id)
    if twin is None:
        return None
    org_ids = set(twin["peer_org_ids"])
    questions = load_questions()
    answers = load_answers(conn, snapshot_id)
    out = {}
    for qid, q in questions.items():
        blk, mr, sc, pres = aggregate_question_for_orgs(q, org_ids, answers.get(qid, {}))
        entry = {"main": blk, "score": sc, "presence": pres}
        if mr is not None:
            entry["rows"] = {m["row_id"]: m["block"] for m in mr}
        out[qid] = entry
    _twin_payload_cache[key] = out
    return out


def invalidate_twin_caches():
    _twin_payload_cache.clear()
