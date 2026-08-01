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


class Scope:
    """One module body or one function body. Bindings are collected per scope; reads are
    matched within the same scope. INTRA-SCOPE ONLY — see the limits in the docstring."""
    def __init__(self, node, tables):
        self.node, self.tables = node, tables
        self.rows = {}        # name -> the SQL that produced it
        self.containers = {}  # name -> the SQL that produced it

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
        body = self.node.body if hasattr(self.node, "body") else []
        for n in ast.walk(self.node):
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
    scopes = [tree] + [n for n in ast.walk(tree)
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    c2 = {}
    for sc in scopes:
        S = Scope(sc, tables).collect()
        known = dict(S.rows)
        for n in ast.walk(sc):
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
            sql = known.get(b) or S.containers.get(b)
            if sql is None:
                continue
            c2[n.lineno] = (col, b, sql, "COMPARED" if in_compare(n, parents) else "CONSUMED")
    return c1, c2, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    ap.add_argument("--columns", default=",".join(DEFAULT_COLUMNS))
    ap.add_argument("--all", action="store_true", help="also show Class 1 writes (normally filtered)")
    a = ap.parse_args()
    cols = tuple(c.strip() for c in a.columns.split(",") if c.strip())
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
    print("  * a row passed into a helper and subscripted there — Class 2 tracking is")
    print("    INTRA-SCOPE ONLY (module body, or one function body); no cross-call,")
    print("    no cross-module, no cross-file")
    print("  * .js entirely — web/js reads RENDERED names off API payloads, never a column")
    print("This tool claims completeness for NOTHING beyond the two classes above, at that depth.")
    print("-" * 100)
    print("TOTAL: %d Class 1 read(s) + %d Class 2 = %d site(s)" % (len(reads), len(C2), len(reads) + len(C2)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
