# Gitignored live-DB-writing scripts — census

Recorded 2026-08-03 (PH-PROV-1 ruling addendum §6.1: the "nine gitignored scripts"
figure was folklore; this file replaces it and is regenerated, not hand-edited).

Command:

```bash
git check-ignore *.py server/*.py | while read f; do
  wr=$(grep -cE "INSERT INTO|UPDATE \w+ SET|DELETE FROM" "$f")
  oi=$(grep -cE "(INSERT INTO|DELETE FROM) (orgs|invites)\b|UPDATE (orgs|invites) SET" "$f")
  [ "$wr" -gt 0 ] && echo "$f sql-writes:$wr orgs/invites:$oi"
done
```

Result (2026-08-03): **10 gitignored .py files on disk; 6 contain SQL writes; 0 touch
`orgs` or `invites`.**

| script | SQL writes | orgs/invites writes |
|---|---|---|
| apply_2026_3.py | 3 | 0 |
| apply_incprot.py | 1 | 0 |
| apply_matrixfix.py | 1 | 0 |
| apply_msfix.py | 3 | 0 |
| apply_recheck6.py | 2 | 0 |
| apply_seedfix_p2.py | 2 | 0 |

Non-writing gitignored scripts: audit_drift.py, audit_eligible.py, capture_tiles.py,
dryrun_2026_3.py.
