# lumi — People Analytics Benchmarking Platform

A multi-tenant benchmarking platform for the lumi HR co-operative: 220 seeded UK member
organisations, 778 benchmark questions across 10 superpowers, with server-side aggregation,
n≥5 suppression, AI board packs, gap-to-£ modelling, a conversational analyst, Peer Twin
bespoke peer groups, a metadata-driven questionnaire, and tokenised sharing.

## Run it

```bash
# 1. install dependencies (Python 3.9+)
python3 -m pip install --user fastapi "uvicorn[standard]" bcrypt httpx

# 2. import the seed data and build the benchmark (one-off, ~30s)
cd server
python3 seed_import.py --fresh        # loads library + registry + 220 response files
python3 aggregate.py                  # computes benchmark_snapshots (~2s, re-runnable)

# 3. start the platform
python3 -m uvicorn app:app --port 8060
# open http://localhost:8060
```

**Demo accounts** (attached to seed org *Thornbridge Retail Group plc*, full tier):

| Role   | Email                          | Password         |
|--------|--------------------------------|------------------|
| Admin       | `director@thornbridge.example` | `lumi-demo-2026` |
| Contributor | `analyst@thornbridge.example`  | `lumi-data-2026` |
| Viewer      | `ceo@thornbridge.example`      | `lumi-view-2026` |

New organisations can self-register from the sign-in screen (they join at Core tier and must
complete ≥90% of Core questions before peer comparison unlocks — the co-op rule).

**Optional AI narrative**: set `ANTHROPIC_API_KEY` (and optionally `ANTHROPIC_MODEL`,
default `claude-sonnet-4-20250514`) before starting the server to enable Claude-written
board-pack narrative and the conversational analyst. Without a key both features fall back
to clearly-labelled deterministic output — no fabricated numbers either way.

## Verify

```bash
cd server && python3 verify.py     # 37 checks: aggregation, tenancy, suppression,
                                   # submission validation, shares, twin, £ model, board pack
```

The suite creates throwaway probe orgs and removes them (and re-aggregates) on completion.

`./run_gates.sh` is the canonical full-suite entry point: throwaway DB copy → fresh gate servers → all ten qa_* gates → restores the dev server (see the script header for the doctrine).

## Layout

```
data/                  inputs (question library, registry, 220 response CSVs)
server/
  db.py                SQLite schema (ANSI types — Postgres is a driver swap)
  seed_import.py       Phase 1a: import + registry join + reconciliation report
  aggregate.py         Phase 1b: the aggregation engine (single suppression code path)
  positions.py         percentile ranks, gaps/strengths, readouts, gap-to-£, gap register
  peer_twin.py         cosine-similarity bespoke peer groups
  retrieval.py         keyword retrieval for the analyst
  claude_api.py        server-side Claude calls + deterministic fallbacks
  auth.py              bcrypt, sessions, rate limiting, invites, resets
  app.py               FastAPI app: tenancy middleware + all routes
  verify.py            quality-bar verification suite
web/                   React 18 (vendored UMD + htm, no build step), custom SVG charts
DECISIONS.md           decision log, data quality findings, hardening list
```

Key invariants:
- **Raw answers never leave the server** except to the owning org's authenticated users;
  internal `_values`/`_scores` arrays are stripped by the API layer (verified in the suite).
- **Every aggregate with n<5 is suppressed**, in one code path (`aggregate.py`), for every
  cut including Peer Twin and share links.
- **Tenancy is middleware**: `org_id` always comes from the session (or a share token's
  stored org), never from the client.
