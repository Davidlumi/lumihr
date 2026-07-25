"""register_resolve.py — the C9 canonical-register rule expressed in code (register follow-up 1,
2026-07-25): THE CANONICAL REGISTER IS THE HIGHEST-DATED lumi_anchor_register_vYYYY-MM-DD.csv IN THE
REPO ROOT. Every consumer resolves through here; the literal pattern lives in exactly this one place.

HARD ERROR if no versioned register exists — never a silent fallback to the prior
lumi_anchor_register_CLAUDECODE.csv (Jul-19, superseded) or the stale Jun-21 JSON.
"""
import glob
import os
import re

_ROOT = os.path.dirname(os.path.abspath(__file__))
_PATTERN = "lumi_anchor_register_v*.csv"
_DATED = re.compile(r"lumi_anchor_register_v(\d{4}-\d{2}-\d{2})\.csv$")


def resolve_canonical_register(root=_ROOT):
    """Absolute path of the canonical (highest-dated) versioned register CSV.

    Raises RuntimeError when none exists — the caller must never fall back to a
    prior-generation file silently (the C9 rule, ruled 2026-07-24)."""
    candidates = []
    for p in glob.glob(os.path.join(root, _PATTERN)):
        m = _DATED.search(os.path.basename(p))
        if m:
            candidates.append((m.group(1), p))
    if not candidates:
        raise RuntimeError(
            "No versioned register (lumi_anchor_register_vYYYY-MM-DD.csv) found in %r — refusing to "
            "fall back to a prior-generation file. The canonical register is the highest-dated "
            "versioned CSV (C9 rule, DECISIONS 2026-07-24)." % root)
    candidates.sort()
    return candidates[-1][1]


if __name__ == "__main__":
    p = resolve_canonical_register()
    print(p)
