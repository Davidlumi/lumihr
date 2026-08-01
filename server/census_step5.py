#!/usr/bin/env python3
"""Census of step-5 column dependencies — SQL-named reads AND subscripted-row reads.

WHY THIS EXISTS. Four censuses of these dependencies were wrong (14 -> 17 -> 18 -> 19),
and each looked complete when written. The last two shapes were found only AFTER the
commit meant to close their class:

  14  literal-pattern grep    missed parameterised LIKE ?, exact `name =`, line-split literals
  17  tree-scoped AST         missed a repo-root file (capture_tiles.py)
  18  SQL-text AST            missed SELECT * -> dict -> Python-side comparison (verify_diff7:145)
  19  --                      missed orgs[o]["name"] consumed as EVIDENCE (verify_diff7:36)

Step 5's go/no-go rests on knowing every place a nulled column is read. This tool exists
so that claim can be defended instead of asserted.

TWO CLASSES.
  Class 1  the column is named in SQL text  -- SELECT name / WHERE normalized_name=? / ORDER BY o.name
  Class 2  the column is never named in SQL -- SELECT * bound to a name, later subscripted
           by an identity column. Sub-classified COMPARED (row["name"] == "...") or
           CONSUMED (nm = row["name"], then regex/format/return). CONSUMED is the more
           dangerous: it degrades silently instead of failing.

DELIBERATE LIMITS. This is a static instrument. It CANNOT see:
  - a column name held in a variable        col = "name";  row[col]
  - getattr / **kwargs / dict() round-trips
  - SQL assembled at runtime from non-literal fragments
  - anything crossing a serialisation boundary (JSON -> parse -> subscript)
  - a row passed into a helper and subscripted there (tracking is INTRA-SCOPE only)
These are printed with every run. A completeness claim this tool cannot support is worse
than no claim, so it makes none beyond what it actually covers.

Usage:
  python3 census_step5.py [--root DIR] [--columns orgs.name,users.email,...] [--all]
  --all  also print Class 1 hits that are writes (INSERT/CREATE/UPDATE), normally filtered
"""
import argparse, ast, os, re, sys

# The columns step 5 nulls. NOT baked in: the spec says "the moved columns" (S6 step 5) and
# the record says "the identity-bearing columns" (step-5 pre-flight), and NEITHER enumerates
# them. This default mirrors identity_recon.STEP5_REMOVED, which P2 established as the
# operative definition until step 5 pins its own list. Override with --columns.
DEFAULT_COLUMNS = ("orgs.name", "orgs.normalized_name",
                   "users.email", "users.pw_hash", "users.display_name",
                   "invites.email")

SKIP_DIRS = {".git", "node_modules", "__pycache__", "venv", ".venv", "build", "dist"}
WRITE_RE = re.compile(r"\b(INSERT|CREATE|UPDATE|DELETE|ON CONFLICT|ALTER)\b", re.I)


def fold(node):
    """Reconstruct a string expression as far as statically possible."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) and isinstance(v.value, str) else "?"
                       for v in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        l, r = fold(node.left), fold(node.right)
        if l is None and r is None:
            return None
        return (l or "") + (" " if isinstance(node.op, ast.Mod) else "") + (r or "")
    return None


def base_name(node):
    """Walk a subscript/call chain down to its root Name, or None.
    orgs[o]["name"] -> orgs ;  dict(row)["name"] -> row ;  r["name"] -> r"""
    while True:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Subscript):
            node = node.value; continue
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id in ("dict", "list", "tuple") and node.args:
                node = node.args[0]; continue
            if isinstance(f, ast.Attribute) and f.attr in ("fetchone", "fetchall", "copy"):
                node = f.value; continue
            return None
        if isinstance(node, ast.Attribute):
            node = node.value; continue
        return None


def sql_strings(node):
    """Every folded string inside an expression."""
    out = []
    for n in ast.walk(node):
        if isinstance(n, (ast.Constant, ast.JoinedStr, ast.BinOp)):
            s = fold(n)
            if s:
                out.append(s)
    return out


NESTED = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


def walk_scope(node):
    """ast.walk, but STOPPING at nested function/class boundaries.

    The precision fix. The first version used ast.walk, which descends into every nested
    def — so in a 6,000-line module every `row = <execute>` anywhere became a module-level
    binding and every `row["name"]` anywhere matched it. Eight app.py hits traced back to
    peer_groups and dashboards rows that way."""
    stack = list(ast.iter_child_nodes(node))
    while stack:
        n = stack.pop()
        yield n
        if not isinstance(n, NESTED):
            stack.extend(ast.iter_child_nodes(n))


def bound_names(node):
    """EVERY name this scope binds, by any means, whatever the source. A name bound here
    from a non-target source SHADOWS an enclosing target binding — which is what makes
    `def _dash_meta(row, vis): ... row["name"]` a non-hit."""
    out = set()
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        a = node.args
        for grp in (a.posonlyargs, a.args, a.kwonlyargs):
            out.update(x.arg for x in grp)
        for x in (a.vararg, a.kwarg):
            if x: out.add(x.arg)
    for n in walk_scope(node):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            out.add(n.id)
        elif isinstance(n, (ast.withitem,)) and n.optional_vars is not None:
            for m in ast.walk(n.optional_vars):
                if isinstance(m, ast.Name): out.add(m.id)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
    return out


class Scope:
    """One module body or one function body. Bindings come from this scope's OWN body;
    reads resolve innermost-outward through enclosing scopes (so a module-level row read
    inside a function — verify_diff7:36 — is still found), stopping at the first scope
    that binds the name at all (so a shadowing rebind is not followed outward)."""
    def __init__(self, node, tables):
        self.node, self.tables = node, tables
        self.rows = {}        # name -> the SQL that produced it
        self.containers = {}  # name -> the SQL that produced it
        self.shadows = bound_names(node)

    def _touches_target(self, expr):
        for s in sql_strings(expr):
            up = s.upper()
            if "SELECT" not in up and "FROM" not in up:
                continue
            for t in self.tables:
                if re.search(r"\b%s\b" % t, s, re.I):
                    return " ".join(s.split())[:120]
        return None

    def _rowsrc(self, expr):
        """Does this expression contain a .execute(<sql over a target table>)?"""
        for n in ast.walk(expr):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
               and n.func.attr == "execute" and n.args:
                sql = self._touches_target(n.args[0])
                if sql:
                    return sql
        return None

    def collect(self):
        for n in walk_scope(self.node):
            # X = <rowsrc>  /  X = {..for r in <rowsrc>}  /  X = [..]
            if isinstance(n, ast.Assign):
                sql = self._rowsrc(n.value)
                if sql:
                    kind = "containers" if isinstance(
                        n.value, (ast.DictComp, ast.ListComp, ast.SetComp, ast.GeneratorExp)) else "rows"
                    for t in n.targets:
                        for nm in ast.walk(t):
                            if isinstance(nm, ast.Name):
                                getattr(self, kind)[nm.id] = sql
            # for X in <rowsrc>:
            if isinstance(n, ast.For):
                sql = self._rowsrc(n.iter)
                if sql:
                    for nm in ast.walk(n.target):
                        if isinstance(nm, ast.Name):
                            self.rows[nm.id] = sql
                # for k, v in <container>.items():
                if isinstance(n.iter, ast.Call) and isinstance(n.iter.func, ast.Attribute) \
                   and n.iter.func.attr in ("items", "values"):
                    b = base_name(n.iter.func.value)
                    if b in self.containers and isinstance(n.target, ast.Tuple):
                        for nm in n.target.elts[-1:]:
                            if isinstance(nm, ast.Name):
                                self.rows[nm.id] = self.containers[b]
            # comprehension generators: {k: f(r) for r in <rowsrc>} and .items() variants
            if isinstance(n, (ast.DictComp, ast.ListComp, ast.SetComp, ast.GeneratorExp)):
                for g in n.generators:
                    sql = self._rowsrc(g.iter)
                    if sql:
                        for nm in ast.walk(g.target):
                            if isinstance(nm, ast.Name):
                                self.rows[nm.id] = sql
                    if isinstance(g.iter, ast.Call) and isinstance(g.iter.func, ast.Attribute) \
                       and g.iter.func.attr in ("items", "values"):
                        b = base_name(g.iter.func.value)
                        if b in self.containers and isinstance(g.target, ast.Tuple):
                            for nm in g.target.elts[-1:]:
                                if isinstance(nm, ast.Name):
                                    self.rows[nm.id] = self.containers[b]
        return self


def in_compare(node, parents):
    """Is this read inside a Compare? -> COMPARED, else CONSUMED."""
    p = parents.get(id(node))
    depth = 0
    while p is not None and depth < 6:
        if isinstance(p, ast.Compare):
            return True
        p = parents.get(id(p)); depth += 1
    return False


def scan_file(path, cols):
    """Return (class1_hits, class2_hits, parse_error)."""
    tables = sorted({c.split(".")[0] for c in cols})
    bycol = {}
    for c in cols:
        t, col = c.split(".")
        bycol.setdefault(col, set()).add(t)
    try:
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src)
    except Exception as e:
        return [], [], str(e)

    parents = {}
    for n in ast.walk(tree):
        for ch in ast.iter_child_nodes(n):
            parents[id(ch)] = n

    # ---- Class 1: the column is named in SQL text
    c1 = {}
    for n in ast.walk(tree):
        if not isinstance(n, (ast.Constant, ast.JoinedStr, ast.BinOp)):
            continue
        s = fold(n)
        if not s or len(s) > 6000:
            continue
        up = s.upper()
        if "SELECT" not in up and "FROM" not in up and "ORDER BY" not in up:
            continue
        for col, tabs in bycol.items():
            if not re.search(r"(?<![_.\w])(?:[A-Za-z_]\w*\.)?%s\b" % col, s):
                continue
            if not any(re.search(r"\b%s\b" % t, s, re.I) for t in tabs):
                continue
            prev = c1.get(n.lineno)
            txt = " ".join(s.split())[:130]
            if prev is None or len(txt) > len(prev[1]):
                c1[n.lineno] = (col, txt, bool(WRITE_RE.search(s)))
            break

    # ---- Class 2: SELECT * (or any row) bound, then subscripted by an identity column
    # scope tree: each node mapped to its chain of enclosing scopes, outermost last
    scopes, chain = [tree], {id(tree): []}
    stack = [(tree, [])]
    while stack:
        node, anc = stack.pop()
        for ch in ast.walk(node) if node is tree else [node]:
            pass
        for n in walk_scope(node):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scopes.append(n); chain[id(n)] = [node] + anc
                stack.append((n, [node] + anc))
    built = {}
    for sc in scopes:
        built[id(sc)] = Scope(sc, tables).collect()
    c2 = {}
    for sc in scopes:
        S = built[id(sc)]
        lex = [S] + [built[id(a)] for a in chain.get(id(sc), []) if id(a) in built]
        for n in walk_scope(sc):
            key = col = None
            if isinstance(n, ast.Subscript):
                k = n.slice
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    col = k.value; key = n.value
            elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                 and n.func.attr == "get" and n.args and isinstance(n.args[0], ast.Constant) \
                 and isinstance(n.args[0].value, str):
                col = n.args[0].value; key = n.func.value
            if col is None or col not in bycol:
                continue
            b = base_name(key)
            if b is None:
                continue
            sql = None
            for sc_i, s_i in enumerate(lex):
                if b in s_i.rows:      sql = s_i.rows[b]; break
                if b in s_i.containers: sql = s_i.containers[b]; break
                if b in s_i.shadows:   break        # shadowed here — do not look outward
            if sql is None:
                continue
            c2[n.lineno] = (col, b, sql, "COMPARED" if in_compare(n, parents) else "CONSUMED")
    return c1, c2, None



# --------------------------------------------------------------- self-test --
# BOTH DIRECTIONS. The first version tested recall only — it checked that known sites
# were found and never that non-sites were excluded, and passed 21/21 while over-reporting
# Class 2 by roughly 2.5x. A test that cannot fail in one direction is not testing it.
POSITIVE = [
  ("module binding read inside a function (the verify_diff7:36 closure shape)", """
orgs = {r["org_id"]: dict(r) for r in c.execute("SELECT * FROM orgs")}
def form(o):
    return orgs[o]["name"] or ""
"""),
  ("direct row, compared", """
row = c.execute("SELECT * FROM orgs WHERE org_id=?", (x,)).fetchone()
if row["name"] == "Acme": pass
"""),
  ("loop variable over users", """
for r in c.execute("SELECT * FROM users WHERE org_id=?", (o,)):
    print(r["email"])
"""),
]
NEGATIVE = [
  ("row from peer_groups, not a target table", """
row = c.execute("SELECT * FROM peer_groups WHERE group_id=?", (g,)).fetchone()
label = row["name"]
"""),
  ("row from dashboards, not a target table", """
row = c.execute("SELECT * FROM dashboards WHERE dashboard_id=?", (d,)).fetchone()
label = row["name"]
"""),
  ("function parameter shadows an outer binding (_dash_meta)", """
row = c.execute("SELECT * FROM orgs WHERE org_id=?", (x,)).fetchone()
def _dash_meta(row, vis):
    return {"name": row["name"]}
"""),
  ("nested rebind from a non-target source shadows the outer orgs row", """
row = c.execute("SELECT * FROM orgs WHERE org_id=?", (x,)).fetchone()
def inner():
    row = c.execute("SELECT * FROM peer_groups WHERE group_id=?", (g,)).fetchone()
    return row["name"]
"""),
]


def _self_test(cols):
    import tempfile
    ok = True
    print("SELF-TEST — both directions\n")
    for label, src, want in ([(l, s, True) for l, s in POSITIVE] +
                             [(l, s, False) for l, s in NEGATIVE]):
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(src); p = f.name
        _, c2, err = scan_file(p, cols)
        os.unlink(p)
        got = bool(c2)
        good = (got == want)
        ok &= good
        print("  %-4s %-8s %s" % ("PASS" if good else "FAIL",
                                  "expect+" if want else "expect-", label))
        if not good:
            print("       got %d Class 2 hit(s): %s" % (len(c2), list(c2.values())[:2]))
    print("\n  SELF-TEST: %s" % ("all cases pass" if ok else "*** FAILURES ***"))
    return 0 if ok else 1

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    ap.add_argument("--columns", default=",".join(DEFAULT_COLUMNS))
    ap.add_argument("--all", action="store_true", help="also show Class 1 writes (normally filtered)")
    ap.add_argument("--self-test", action="store_true", help="run positive AND negative controls")
    a = ap.parse_args()
    cols = tuple(c.strip() for c in a.columns.split(",") if c.strip())
    if a.self_test:
        return _self_test(cols)
    root = os.path.abspath(a.root)

    files, errs = [], []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP_DIRS and not d.startswith(".")]
        for f in sorted(fn):
            if f.endswith(".py"):
                files.append(os.path.join(dp, f))

    print("CENSUS — step-5 column dependencies")
    print("root    : %s" % root)
    print("columns : %s" % ", ".join(cols))
    print("          (default mirrors identity_recon.STEP5_REMOVED — the operative definition")
    print("           until step 5 pins its own list; the spec never enumerates it)")
    print("files   : %d .py scanned   |   .js NOT scanned (rendered names are a different class)" % len(files))
    print()

    C1, C2 = [], []
    for p in sorted(files):
        c1, c2, err = scan_file(p, cols)
        rel = os.path.relpath(p, root)
        if err:
            errs.append((rel, err)); continue
        for ln, (col, txt, isw) in sorted(c1.items()):
            C1.append((rel, ln, col, txt, isw))
        for ln, (col, b, sql, mode) in sorted(c2.items()):
            C2.append((rel, ln, col, b, sql, mode))

    reads = [h for h in C1 if not h[4]]
    writes = [h for h in C1 if h[4]]
    print("=" * 100)
    print("CLASS 1 — column named in SQL text: %d read(s)   (+%d write/DDL, %s)"
          % (len(reads), len(writes), "shown below" if a.all else "filtered; --all to show"))
    print("=" * 100)
    for rel, ln, col, txt, _ in reads:
        print("  %-44s %-22s %s" % ("%s:%d" % (rel, ln), col, txt))
    if a.all and writes:
        print("\n  -- writes/DDL (not reads) --")
        for rel, ln, col, txt, _ in writes:
            print("  %-44s %-22s %s" % ("%s:%d" % (rel, ln), col, txt))

    print()
    print("=" * 100)
    print("CLASS 2 — column NOT named in SQL; row bound then subscripted: %d" % len(C2))
    print("=" * 100)
    for rel, ln, col, b, sql, mode in C2:
        print("  %-44s %-10s %-9s via %-8s  %s" % ("%s:%d" % (rel, ln), col, mode, b, sql[:52]))

    if errs:
        print("\n  UNPARSED (%d) — these were NOT scanned:" % len(errs))
        for rel, e in errs:
            print("    %-44s %s" % (rel, e[:70]))

    print()
    print("-" * 100)
    print("WHAT THIS RUN DOES NOT COVER — a static instrument cannot see:")
    print("  * a column name held in a variable        col = \"name\";  row[col]")
    print("  * getattr / **kwargs / dict() round-trips")
    print("  * SQL assembled at runtime from non-literal fragments")
    print("  * values crossing a serialisation boundary (JSON -> parse -> subscript)")
    print("  * a row RETURNED BY ANOTHER FUNCTION and subscripted at the call site.")
    print("    Class 2 tracking is INTRA-SCOPE ONLY: no cross-call, no cross-module.")
    print("    THIS IS NOT HYPOTHETICAL. Live example: auth.get_valid_invite() returns")
    print("      conn.execute(\"SELECT * FROM invites WHERE token=? ...\").fetchone()")
    print("    and app.py:1590/:1605 subscript that row for invites.email. Both are real")
    print("    step-5 defects — :1605 breaks invite acceptance outright — and NEITHER")
    print("    appears below. An earlier, buggier version of this tool surfaced them only")
    print("    by accident, through the scope leak this fix removed. Recovering them needs")
    print("    one-level return analysis, which this tool does not yet do.")
    print("  * .js entirely — web/js reads RENDERED names off API payloads, never a column")
    print("PRECISION: Class 2 resolves names lexically (own scope, then enclosing scopes,")
    print("  stopping at the first scope that rebinds the name). Validated against negative")
    print("  controls — peer_groups/dashboards rows, and function parameters that shadow an")
    print("  outer binding, are NOT reported. Where a rebind is conditional or a chain crosses")
    print("  two scopes it still errs toward reporting: a noisy hit beats a missed one.")
    print("This tool claims completeness for NOTHING beyond the two classes above, at that depth.")
    print("-" * 100)
    print("TOTAL: %d Class 1 read(s) + %d Class 2 = %d site(s)" % (len(reads), len(C2), len(reads) + len(C2)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
