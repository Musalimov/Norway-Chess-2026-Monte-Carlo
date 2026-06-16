#!/usr/bin/env python3
"""Regularized calibration for the Norway Chess probability model.

The script avoids a raw maximum-likelihood fit because the small historical
sample can overfit. Instead it uses:

1. Ranked Probability Score (RPS) on ordered outcomes
   [White win > draw > Black win].
2. MAP regularization toward physically plausible priors.
3. Leave-one-tournament-out cross-validation to choose lambda.
4. Bootstrap resampling to estimate parameter stability.

Only the Python standard library is required.

Run from the project root:

    python3 tools/calibrate.py
"""
import json, math, random, os
from itertools import product
from collections import defaultdict

H = [g for g in json.loads(open('data/history.json').read()) if g['white_elo'] and g['black_elo']]
TY = ('2022', '2023', '2024', '2025')
TRAIN = [g for g in H if g['year'] in TY]
TEST  = [g for g in H if g['year'] == '2026']
K_OUT = {1.0: 0, 0.5: 1, 0.0: 2}
for g in H:
    g['_d'] = g['white_elo'] - g['black_elo']
    g['_k'] = K_OUT[g['classical_result_white']]

def E(d): return 1 / (1 + 10 ** (-d / 400))

def rps(p3, k):
    cp = co = s = 0.0
    for i in range(2):
        cp += p3[i]
        co += 1.0 if i == k else 0.0
        s += (cp - co) ** 2
    return s / 2

def probs_d(d, wa, db, dd):
    diff = d + wa
    pd = min(db * math.exp(-abs(diff) * dd), 0.85)
    e = E(diff)
    pw = max(e - pd / 2, .01)
    pb = max(1 - pw - pd, .01)
    return pw, 1 - pw - pb, pb

def avg_rps(games, wa, db, dd):
    return sum(rps(probs_d(g['_d'], wa, db, dd), g['_k']) for g in games) / len(games)

WA0, DD0, WSC, DSC = 35.0, 0.0017, 15.0, 0.0015

def obj(games, wa, db, dd, lam):
    return avg_rps(games, wa, db, dd) + lam * (((wa - WA0) / WSC) ** 2 + ((dd - DD0) / DSC) ** 2)

GW = [20, 25, 30, 35, 40, 45, 50, 55, 60]
GB = [.50, .55, .60, .65, .70, .75]
GD = [0, .0006, .0012, .0018, .0024, .003]

def fit(games, lam):
    best = None
    for wa, db, dd in product(GW, GB, GD):
        v = obj(games, wa, db, dd, lam)
        if best is None or v < best[0]:
            best = (v, wa, db, dd)
    return best[1:]

def cv(lam):
    t = n = 0
    for h in TY:
        tr = [g for g in TRAIN if g['year'] != h]
        te = [g for g in TRAIN if g['year'] == h]
        wa, db, dd = fit(tr, lam)
        t += sum(rps(probs_d(g['_d'], wa, db, dd), g['_k']) for g in te)
        n += len(te)
    return t / n

print("Choosing lambda by leave-one-tournament-out CV (RPS, lower is better):")
lams = [0.0, 0.1, 0.25, 0.5, 1.0]
cvs = {l: cv(l) for l in lams}
for l in lams:
    print(f"  lambda={l:<5} CV-RPS={cvs[l]:.5f}{'  <- best' if l == min(cvs, key=cvs.get) else ''}")
bl = min(cvs, key=cvs.get)

WA, DB, DD = fit(TRAIN, bl)
print(f"\n=== Parameters (lambda={bl}, RPS+MAP, trained on 2022-2025) ===")
print(f"  WA    = {WA}    (prior {WA0}; naive MLE pushed this much higher)")
print(f"  DBASE = {DB}   (Norway Chess is draw-heavy relative to many elite events)")
print(f"  DDEC  = {DD}")

arms = [g for g in TRAIN if g['armageddon']]
def ad(g):
    a = g['armageddon']
    return g['_d'] if a['white_player'] == g['white'] else -g['_d']
def ah(h):
    b = sum((E(ad(g) - h) - (1.0 if g['armageddon']['white_won_minimatch'] else 0.0)) ** 2
            for g in arms) / len(arms)
    return b + 0.1 * ((h + 30) / 40) ** 2
ARM = min((ah(h), h) for h in range(-150, 151, 5))[1]
ww = sum(g['armageddon']['white_won_minimatch'] for g in arms)
print(f"  ARM_H = {ARM}    (White won {ww}/{len(arms)} = {ww/len(arms):.0%})")

uni = sum(rps([1/3, 1/3, 1/3], g['_k']) for g in TEST) / len(TEST)
print("\n=== Out-of-sample on 2026 (RPS, lower is better) ===")
print(f"  regularized (lambda={bl}): {avg_rps(TEST, WA, DB, DD):.4f}")
print(f"  previous priors:           {avg_rps(TEST, 19.5, 0.60, 0.0017):.4f}")
print(f"  naive MLE (57.5/.62/0):   {avg_rps(TEST, 57.5, 0.62, 0.0):.4f}")
print(f"  uniform (1/3):            {uni:.4f}")

random.seed(1)
boots = sorted(fit([random.choice(TRAIN) for _ in TRAIN], bl)[0] for _ in range(120))
print(f"\nBootstrap WA: median {boots[60]}, 90% CI [{boots[6]}, {boots[113]}]")
print("A narrow interval means the regularization is suppressing sample noise.")

draws = defaultdict(int)
tot = defaultdict(int)
for g in TRAIN:
    for p in (g['white'], g['black']):
        tot[p] += 1
        draws[p] += g['classical_result_white'] == 0.5
avg = sum(draws.values()) / sum(tot.values())
print(f"\nStyles (draw share / field average {avg:.2f}, minimum 10 games):")
for p in sorted(tot, key=lambda x: -tot[x]):
    if tot[p] >= 10:
        print(f"  {p:<26}{draws[p]/tot[p]/avg:5.2f}")

os.makedirs('out', exist_ok=True)
json.dump({'WA': WA, 'DBASE': DB, 'DDEC': DD, 'ARM_H': ARM, 'lambda': bl,
           'method': 'RPS + MAP regularization + leave-one-tournament-out CV',
           'oos_2026_rps': round(avg_rps(TEST, WA, DB, DD), 4)},
          open('out/calibrated_params.json', 'w'), indent=1)
print("\nsaved: out/calibrated_params.json")
