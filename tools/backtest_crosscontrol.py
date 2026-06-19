#!/usr/bin/env python3
"""LOYO backtest of speed cross-control (#3) using historical rapid/blitz.

Now that data/fide/speed_ratings.json carries each player's rapid+blitz as of
each edition, cross-control can finally be validated the same way as strength
sampling: for each year, fit (WA,DBASE,DDEC,CC) on the other four editions
(sigma=60 fixed) and score out-of-sample. CC scales a field-centred speed gap
  gap_p = 0.5*((rapid_p - std_p) + (blitz_p - std_p))   (FIDE May snapshot)
added to the player's classical rating. CC=0 (current model) is compared with
the fitted CC on RPS / Brier / directional accuracy on decisive games.
"""
import json, math
from collections import defaultdict
from itertools import product
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from nc_common import classical_wdl, mean  # noqa: E402

H = [g for g in json.loads((ROOT / "data/history.json").read_text()) if g["white_elo"] and g["black_elo"]]
SR = json.loads((ROOT / "data/fide/speed_ratings.json").read_text())["monthly"]
YEARS = ["2022", "2023", "2024", "2025", "2026"]
K_OUT = {1.0: 0, 0.5: 1, 0.0: 2}
SIGMA = 60.0
WA0, DD0, WSC, DSC, LAM = 35.0, 0.0017, 15.0, 0.0015, 0.1
GW, GB, GD = [30, 35, 40], [.65, .70, .75], [.0012, .0018, .0024]
GC = [0, 0.1, 0.25, 0.5, 0.75, 1.0]

# field-centred speed gap (dev) per (year, player), from the edition roster
roster = defaultdict(set)
for g in H:
    roster[g["year"]].add(g["white"]); roster[g["year"]].add(g["black"])
DEV = {}
for y in YEARS:
    gaps = {}
    for n in roster[y]:
        r = SR.get(n, {}).get(f"{y}-05")
        if r and r["std"] and r["rapid"] and r["blitz"]:
            gaps[n] = 0.5 * ((r["rapid"] - r["std"]) + (r["blitz"] - r["std"]))
    fm = mean(list(gaps.values()))
    DEV[y] = {n: gaps.get(n, fm) - fm for n in roster[y]}

for g in H:
    g["_k"] = K_OUT[g["classical_result_white"]]
    g["_dw"] = DEV[g["year"]].get(g["white"], 0.0)
    g["_db"] = DEV[g["year"]].get(g["black"], 0.0)
BY = {y: [g for g in H if g["year"] == y] for y in YEARS}


def probs(g, wa, db, dd, cc):
    diff = (g["white_elo"] + cc * g["_dw"]) - (g["black_elo"] + cc * g["_db"]) + wa
    return classical_wdl(diff, db, dd, sigma=SIGMA)

def rps(p, k):
    cp = co = s = 0.0
    for i in range(2):
        cp += p[i]; co += 1.0 if i == k else 0.0; s += (cp - co) ** 2
    return s / 2
def brier(p, k): return sum((p[i] - (1.0 if i == k else 0.0)) ** 2 for i in range(3))

def fit(games, force0):
    gc = [0] if force0 else GC
    best = None
    for wa, db, dd, cc in product(GW, GB, GD, gc):
        v = mean([rps(probs(g, wa, db, dd, cc), g["_k"]) for g in games]) \
            + LAM * (((wa - WA0) / WSC) ** 2 + ((dd - DD0) / DSC) ** 2)
        if best is None or v < best[0]: best = (v, wa, db, dd, cc)
    return best[1:]

def ev(games, wa, db, dd, cc):
    rl = bl = 0.0; dm = dirh = dirn = 0
    for g in games:
        p = probs(g, wa, db, dd, cc); k = g["_k"]
        rl += rps(p, k); bl += brier(p, k)
        if max(range(3), key=lambda i: p[i]) == 1: dm += 1
        if k in (0, 2):
            dirn += 1; dirh += (p[0] > p[2]) if k == 0 else (p[2] > p[0])
    n = len(games)
    return rl / n, bl / n, dm, n, dirh, dirn

print("=== Speed cross-control: LOYO (sigma=60 fixed) ===")
print(f"{'year':>5} {'CC':>4} | {'RPS base':>8} {'RPS cc':>8} | {'Brier base':>10} {'Brier cc':>8} | "
      f"{'directional b->cc':>17}")
tb = defaultdict(float); n_all = 0; dh_b = dn_b = dh_c = dn_c = 0
for y in YEARS:
    tr = [g for g in H if g["year"] != y]; te = BY[y]
    wb, bb, db0, _ = fit(tr, True)
    wc, bc, dc, cc = fit(tr, False)
    rb, brb, _, n, hb, nb = ev(te, wb, bb, db0, 0)
    rc, brc, _, _, hc, nc = ev(te, wc, bc, dc, cc)
    print(f"{y:>5} {cc:>4} | {rb:>8.4f} {rc:>8.4f} | {brb:>10.4f} {brc:>8.4f} | {hb}/{nb} -> {hc}/{nc}")
    tb['rb'] += rb*n; tb['rc'] += rc*n; tb['bb'] += brb*n; tb['bc'] += brc*n; n_all += n
    dh_b += hb; dn_b += nb; dh_c += hc; dn_c += nc
print(f"{'ALL':>5} {'-':>4} | {tb['rb']/n_all:>8.4f} {tb['rc']/n_all:>8.4f} | "
      f"{tb['bb']/n_all:>10.4f} {tb['bc']/n_all:>8.4f} | {dh_b}/{dn_b} -> {dh_c}/{dn_c}")
print("\nbase = CC=0 (current). cc = fitted cross-control. directional = winner had higher win prob.")
