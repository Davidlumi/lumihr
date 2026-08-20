# -*- coding: utf-8 -*-
"""Long AI generations run in the background, with progress a member can believe.

WHY. The board pack and the reward document are several model calls deep. A typical one
lands in 15-25 seconds, but the API retries transient failures twice behind a 120-second
ceiling, so a loaded afternoon can stretch one generation past five minutes. A spinner for
five minutes is indistinguishable from a hang, and a member who navigates away loses the
work. So the work outlives the request: the member gets a preparing screen they may leave,
and an email when the document is ready.

THE PROGRESS RULE. A percentage that is invented is worse than no percentage, because the
member calibrates on it and then it lies. So:

  * Step boundaries are REAL. A step advances only when that work has actually finished.
  * Inside a step, the bar eases forward on elapsed time against how long that step has
    ACTUALLY taken for this kind of job before (the mean over this deployment's completed
    jobs, not a guess), and is capped short of the next boundary. It can never overtake
    the truth.
  * 100% means the artefact exists. Nothing else reports 100%.

A step that over-runs therefore PARKS near the top of its own share of the bar rather than
sailing on to 99%. That is the honest picture, and `slow` reports it so the screen can say
so in words too.

CRASH SAFETY. The runner is an in-process daemon thread (single-instance deployment, the
same assumption the signal sweep makes). A process that dies mid-generation leaves a row
reading `running` forever, so `reap_stale` fails those on boot.

What `slow` is NOT: liveness. A step is one blocking model call, so nothing can beat a
heart while it runs — `slow` only means "this step has taken far longer than this
deployment's own jobs usually take". Process death is caught by `reap_stale`, not here.
"""
import json
import os
import threading
import traceback
import uuid

# How long each step usually takes, in seconds, before this kind of job has any history.
# Deliberately generous: a bar that under-promises and arrives early reads as fast, while
# one that over-promises and stalls at 90% reads as broken.
KINDS = {
    # Three steps, not four: the number-grounding check runs INSIDE the narrative call
    # (validate_pack_narrative, with a retry), so reporting it separately would be a
    # boundary that does not exist. The step is named for both halves instead.
    "boardpack": {
        "label": "board pack",
        "steps": [
            ("Gathering your figures", 5),
            ("Writing and checking the narrative", 45),
            ("Saving your pack", 2),
        ],
    },
    # Four steps because the document really is four independent generations — the page
    # used to fire them in parallel from the browser and lose all four if the member
    # navigated away. Each boundary here is one of those calls returning.
    # Rebuild plan is one call, but one call is 21s on a quiet API and 97s on a loaded one
    # — the same spinner problem at a smaller scale, so it gets the same treatment.
    "reward_plan": {
        "label": "reward plan",
        "steps": [("Sequencing your gaps into a plan", 30)],
    },
    "reward_document": {
        "label": "reward document",
        "steps": [
            ("Reading your strategy against the market", 30),
            ("Writing your strategy narrative", 40),
            ("Diagnosing where you stand", 35),
            ("Drafting your plan", 30),
        ],
    },
}

# a step running this much longer than expected is worth saying out loud
SLOW_SECONDS = int(os.environ.get("LUMI_JOB_SLOW_SECONDS", "120"))

_RUNNERS = {}           # kind -> callable(job_id, params, progress) -> result_id
_lock = threading.Lock()


def register(kind, fn):
    """Wire a kind to the function that does its work. app.py registers on import, which
    keeps the actual generation beside the route that shares its code."""
    _RUNNERS[kind] = fn


# --------------------------------------------------------------------------- store --

def _now(conn):
    return conn.execute("SELECT datetime('now')").fetchone()[0]


def create(conn, kind, org_id, user_id, params=None, notify_email=None):
    if kind not in KINDS:
        raise ValueError("unknown job kind: %s" % kind)
    job_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO generation_jobs(job_id, org_id, user_id, kind, status, step_index, "
        "step_started_at, params_json, notify_email) "
        "VALUES (?,?,?,?,'running',0,datetime('now'),?,?)",
        (job_id, org_id, user_id, kind, json.dumps(params or {}), notify_email or None))
    conn.commit()
    return job_id


def get(conn, job_id, org_id=None):
    """Fetch a job. org_id scopes it — a job id must never read across organisations."""
    if org_id:
        return conn.execute("SELECT * FROM generation_jobs WHERE job_id=? AND org_id=?",
                            (job_id, org_id)).fetchone()
    return conn.execute("SELECT * FROM generation_jobs WHERE job_id=?", (job_id,)).fetchone()


def advance(conn, job_id, step_index):
    """Move to a step. Called only when the previous step's work is genuinely done."""
    conn.execute("UPDATE generation_jobs SET step_index=?, step_started_at=datetime('now'), "
                 "updated_at=datetime('now') WHERE job_id=?", (step_index, job_id))
    conn.commit()


def finish(conn, job_id, result_id):
    conn.execute("UPDATE generation_jobs SET status='done', result_id=?, "
                 "finished_at=datetime('now'), updated_at=datetime('now') WHERE job_id=?",
                 (result_id, job_id))
    conn.commit()


def fail(conn, job_id, error):
    conn.execute("UPDATE generation_jobs SET status='failed', error=?, "
                 "finished_at=datetime('now'), updated_at=datetime('now') WHERE job_id=?",
                 (str(error)[:400], job_id))
    conn.commit()


def mark_notified(conn, job_id):
    """Stamped BEFORE the send, so a crash mid-send loses the email rather than sending it
    twice — a member would rather miss a notification than get four of them."""
    cur = conn.execute("UPDATE generation_jobs SET notified_at=datetime('now') "
                       "WHERE job_id=? AND notified_at IS NULL", (job_id,))
    conn.commit()
    return cur.rowcount > 0


def reap_stale(conn):
    """Boot-time: a row still reading 'running' cannot be, because the only thing that runs
    jobs is this process and it has just started. Fail them so nobody watches a bar that
    stopped moving before the restart."""
    cur = conn.execute(
        "UPDATE generation_jobs SET status='failed', "
        "error='interrupted by a server restart — please try again', "
        "finished_at=datetime('now'), updated_at=datetime('now') WHERE status='running'")
    conn.commit()
    return cur.rowcount


# ------------------------------------------------------------------------ progress --

def _expected_step_seconds(conn, kind, step_index):
    """How long this step should take, calibrated on completed jobs of this kind. Returns
    None until there is history, so the first few members get the configured estimate
    rather than a number derived from nothing."""
    row = conn.execute(
        "SELECT COUNT(*) c FROM generation_jobs WHERE kind=? AND status='done'",
        (kind,)).fetchone()
    if not row or row["c"] < 3:          # too few to be a mean worth trusting
        return None
    # Per-step timings are not stored individually; total duration over the sum of the
    # configured weights gives a calibration factor that scales every step together. That
    # is honest about what is known: the shape comes from the config, the SCALE from
    # this deployment's own measured jobs.
    tot = conn.execute(
        "SELECT AVG(strftime('%s', finished_at) - strftime('%s', created_at)) a "
        "FROM generation_jobs WHERE kind=? AND status='done' AND finished_at IS NOT NULL "
        "AND created_at >= datetime('now', '-30 day')", (kind,)).fetchone()
    if not tot or not tot["a"]:
        return None
    configured_total = sum(w for _, w in KINDS[kind]["steps"]) or 1
    factor = float(tot["a"]) / configured_total
    # ignore an implausible factor (a clock change, a job that sat queued behind a restart)
    if not (0.2 <= factor <= 5.0):
        return None
    return KINDS[kind]["steps"][step_index][1] * factor


def state(conn, row):
    """The member-facing view of a job: percent, what it is doing, and whether it has
    stopped moving. Percent is composed so it can never claim more than is true."""
    kind = row["kind"]
    spec = KINDS.get(kind) or {"label": kind, "steps": [("Working", 30)]}
    steps = spec["steps"]
    total_w = sum(w for _, w in steps) or 1
    idx = max(0, min(int(row["step_index"] or 0), len(steps) - 1))

    if row["status"] == "done":
        return {"status": "done", "percent": 100, "step": "Ready", "step_index": len(steps),
                "steps_total": len(steps), "result_id": row["result_id"],
                "kind": kind, "label": spec["label"], "slow": False}
    if row["status"] == "failed":
        return {"status": "failed", "percent": 0, "step": "Stopped", "step_index": idx,
                "steps_total": len(steps), "error": row["error"],
                "kind": kind, "label": spec["label"], "slow": False}

    done_w = sum(w for _, w in steps[:idx])
    elapsed = conn.execute(
        "SELECT strftime('%s','now') - strftime('%s', COALESCE(?, created_at)) e "
        "FROM generation_jobs WHERE job_id=?",
        (row["step_started_at"], row["job_id"])).fetchone()["e"] or 0
    expect = _expected_step_seconds(conn, kind, idx) or steps[idx][1]
    # ease to at most 90% of the CURRENT step: the last tenth belongs to the step actually
    # finishing, so the bar never sits at a boundary it has not reached
    frac = min(0.9, float(elapsed) / max(1.0, float(expect)))
    percent = int(round(100.0 * (done_w + steps[idx][1] * frac) / total_w))

    return {"status": "running", "percent": max(1, min(99, percent)), "step": steps[idx][0],
            "step_index": idx, "steps_total": len(steps), "kind": kind,
            "label": spec["label"], "slow": elapsed > max(SLOW_SECONDS, expect * 3),
            "elapsed_seconds": int(elapsed)}


# -------------------------------------------------------------------------- runner --

def start(kind, job_id, params, on_done=None):
    """Run the job on a daemon thread. Never raises into the caller: the request that
    started the job has already returned the job id, and every outcome is a row."""
    def _work():
        from db import get_conn                 # thread-local connection, per db.get_conn
        conn = get_conn()

        def progress(step_index):
            advance(conn, job_id, step_index)

        try:
            result_id = _RUNNERS[kind](job_id, params, progress)
            finish(conn, job_id, result_id)
        except Exception as e:                  # noqa: BLE001 — a job must never take the app down
            traceback.print_exc()
            fail(conn, job_id, e)
        if on_done:
            try:
                on_done(job_id)
            except Exception:                   # noqa: BLE001 — a failed email is not a failed job
                traceback.print_exc()

    threading.Thread(target=_work, name="lumi-gen-%s" % kind[:12], daemon=True).start()
