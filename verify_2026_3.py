#!/usr/bin/env python3
"""Verify Release 2026.3 post-aggregation: served applicable-based marginals vs signed targets,
N/A rates (incl. corrected priors + ruling #2), spine correlations, multi-select contradictions."""
import json, sqlite3, sys
from collections import Counter
import numpy as np
sys.path.insert(0, '.')
import reseed_engine as RE, seed_release_2026_3 as K

NOMINAL = {'REW263_GOV_SIGNOFF','REW263_BEN_PENBASIS','REW263_INC_POOLFUND','REW263_REC_CURRENCY'}
TOL = 0.03
c = sqlite3.connect('lumi.db'); c.row_factory = sqlite3.Row
orgs = [o for (o,) in c.execute('SELECT DISTINCT org_id FROM answers WHERE snapshot_id=1').fetchall()]
prof = {}
for p in ('org_profiles.json','org_profiles_inferred.json'): prof.update(json.load(open(p)))
lat = {o: RE.latent(o, prof) for o in orgs}

def ordering(qid, spec):
    if spec['type'] == 'multi_select': return None
    if 'order' in spec: return spec['order']
    oo = RE.option_order(list(spec['dist']), qid)
    if oo is not None: return oo
    if qid in NOMINAL: return None
    return list(spec['dist'].keys())

worst_dev = 0; worst_q = None; fails = 0; anchored_corrs = []
print('%-26s %4s %5s %7s %6s' % ('qid','nApp','NA%','maxdev','corr'))
for qid, spec in K.BASELINES.items():
    p = json.loads(c.execute("SELECT payload_json FROM benchmark_snapshots WHERE snapshot_id=1 AND question_id=?", (qid,)).fetchone()[0])
    allb = p['all']; opts = allb['options']; n = allb['n']
    na_ct = sum(o['count'] for o in opts if o.get('is_na'))
    app = n - na_ct or 1
    # raw answers for corr + contradiction
    raw = [(o, v) for o, v in c.execute("SELECT org_id,value FROM answers WHERE question_id=? AND snapshot_id=1", (qid,)).fetchall() if v]
    if spec['type'] == 'multi_select':
        contra = sum(1 for _, v in raw if 'None' in [x.strip() for x in v.split(';')] and len([x for x in v.split(';') if x.strip()]) > 1)
        print('%-26s %4d %5.1f   multi: None+positive contradictions=%d' % (qid, app, 100*na_ct/n, contra))
        continue
    realised = {o['label']: o['count']/app for o in opts if not o.get('is_na')}
    tgt = K.SIGNED_TARGETS.get(qid, spec['dist'])
    dev = max(abs(realised.get(op, 0)-tgt.get(op, 0)) for op in tgt)
    if dev > worst_dev: worst_dev, worst_q = dev, qid
    if dev > TOL: fails += 1
    order = ordering(qid, spec); corr = float('nan')
    if order is not None:
        rk = {op: i for i, op in enumerate(order)}
        xy = [(lat[o], rk[v]) for o, v in raw if v in rk and o in lat]
        ys = [y for _, y in xy]
        if len(set(ys)) > 1: corr = float(np.corrcoef([x for x, _ in xy], ys)[0, 1]); anchored_corrs.append(corr)
    cs = '%.3f' % corr if corr == corr else '  -'
    print('%-26s %4d %5.1f %7.4f %6s' % (qid, app, 100*na_ct/n, dev, cs))

print('\n--- KEY N/A CHECKS (rulings) ---')
for qid, want in [('REW263_INC_DEFERRAL','~72 (no_deferral 0.72)'),('REW263_PAY_COMPARATIO','~42 (no_ranges 0.42)'),
                  ('REW263_BEN_CICOVER','~62 (no_ci 0.62)'),('REW263_PAY_SHIFTRIGHTS','~17 (ruling#2)'),
                  ('REW263_PAY_GUARHRSAVG','~14 (ruling#2)')]:
    p = json.loads(c.execute("SELECT payload_json FROM benchmark_snapshots WHERE snapshot_id=1 AND question_id=?", (qid,)).fetchone()[0])
    allb = p['all']; na_ct = sum(o['count'] for o in allb['options'] if o.get('is_na'))
    print('  %-26s N/A=%4.1f%%   target %s' % (qid, 100*na_ct/allb['n'], want))

ac = np.array(anchored_corrs)
print('\nSUMMARY: marginals worst_dev=%.4f on %s (tol=%.2f) -> %s | fails=%d' % (worst_dev, worst_q, TOL, 'PASS' if fails == 0 else 'FAIL', fails))
print('  anchored corr: min=%.3f median=%.3f max=%.3f (%d anchored, all>0: %s)' % (ac.min(), np.median(ac), ac.max(), len(ac), bool((ac > 0).all())))
print('  total live questions now:', c.execute("SELECT COUNT(*) FROM questions WHERE status='active'").fetchone()[0])
