#!/usr/bin/env python3
"""v4: prequential evaluation with in-tournament form updates.

Round r is predicted using ratings updated on ACTUAL results of rounds 1..r-1
(no leakage: at prediction time only past information is used).
Update rule (pre-registered, not tuned on 2026): after each classical game
  eff += K * (S - E),  S in {1, 0.5, 0}, E = Elo expectation incl. color,
  K = 32 primary; K = 16 / 64 reported as sensitivity, chosen a priori.
Everything else identical to v3 (frozen). Bootstrap CIs vs v3.
"""
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = json.loads((ROOT / "data" / "dataset_full.json").read_text())
PL = D["players_pretournament"]

WA, DBASE, DDEC, ARM_H = 35.0, 0.70, 0.0018, -30.0

def expect(diff):
    return 1.0 / (1.0 + 10 ** (-diff / 400.0))

def eff0(p):
    return PL[p]["classical"] + PL[p]["live_adj"] + 2.0 * PL[p]["trend_mo"]

def dist_white(eff, white, black):
    diff = eff[white] - eff[black] + WA
    pd = min(DBASE * math.exp(-abs(diff) * DDEC) * PL[white]["style"] * PL[black]["style"], 0.85)
    e = expect(diff)
    pw = max(e - pd / 2.0, 0.01)
    pb = max(1.0 - pw - pd, 0.01)
    pd = 1.0 - pw - pb
    parm = expect(PL[white]["blitz"] - PL[black]["blitz"] - ARM_H)
    return [pw, pd * parm, pd * (1 - parm), pb]   # p_white pts 3/1.5/1/0

def p1_dist(eff, g):
    a = dist_white(eff, g["p1"], g["p2"])
    bb = dist_white(eff, g["p2"], g["p1"])
    b = [bb[3], bb[2], bb[1], bb[0]]
    return a if g["col"] == "p1w" else [(x + y) / 2 for x, y in zip(a, b)]

RES_IDX = {3.0: 0, 1.5: 1, 1.0: 2, 0.0: 3}
S_OF = {3.0: 1.0, 1.5: 0.5, 1.0: 0.5, 0.0: 0.0}

def metrics(p, k):
    ll = -math.log2(max(p[k], 1e-12))
    br = sum((p[i] - (1.0 if i == k else 0.0)) ** 2 for i in range(4))
    cp = co = rps = 0.0
    for i in range(3):
        cp += p[i]; co += 1.0 if i == k else 0.0
        rps += (cp - co) ** 2
    return ll, br, rps / 3

def run(K):
    eff = {p: eff0(p) for p in PL}
    out = []
    for rnd in D["rounds"]:
        # 1) predict the whole round with current eff
        for g in rnd["games"]:
            out.append(metrics(p1_dist(eff, g), RES_IDX[g["res"]]))
        # 2) then update on the round's actual classical results
        for g in rnd["games"]:
            s1 = S_OF[g["res"]]
            if g["col"] == "p1w":
                e1 = expect(eff[g["p1"]] - eff[g["p2"]] + WA)
            else:
                e1 = 0.5 * (expect(eff[g["p1"]] - eff[g["p2"]] + WA)
                            + expect(eff[g["p1"]] - eff[g["p2"]] - WA))
            eff[g["p1"]] += K * (s1 - e1)
            eff[g["p2"]] += K * ((1 - s1) - (1 - e1))
    return out, eff

def mean(xs): return sum(xs) / len(xs)

# v3 = K=0 (no updates)
v3, _ = run(0)
results = {"v3 (K=0)": v3}
for K in (16, 32, 64):
    results[f"v4 K={K}"], eff_final = run(K)
    if K == 32:
        final_eff = eff_final

print(f"{'Model':<12}{'LogLoss':>9}{'Brier':>9}{'RPS':>9}")
for name, r in results.items():
    c = list(zip(*r))
    print(f"{name:<12}{mean(c[0]):>9.4f}{mean(c[1]):>9.4f}{mean(c[2]):>9.4f}")
print(f"{'B0':<12}{2.0:>9.4f}{0.75:>9.4f}{0.2083:>9.4f}")

random.seed(42)
n = len(v3)
print("\nBootstrap 95% CI (negative = first better), 10k resamples:")
for name in ("v4 K=32", "v4 K=16", "v4 K=64"):
    for mi, mn in ((0, "logloss"), (2, "rps")):
        diffs = []
        for _ in range(10000):
            idx = [random.randrange(n) for _ in range(n)]
            diffs.append(mean([results[name][i][mi] for i in idx]) -
                         mean([v3[i][mi] for i in idx]))
        diffs.sort()
        pt = mean([r[mi] for r in results[name]]) - mean([r[mi] for r in v3])
        lo, hi = diffs[249], diffs[9749]
        sig = "  *" if hi < 0 or lo > 0 else ""
        print(f"  {name} - v3 ({mn}): {pt:+.4f}  CI [{lo:+.4f}, {hi:+.4f}]{sig}")
    # uniform comparison for K=32
b032 = [(2.0, 0.75, 0.2083)] * 0
for mi, mn in ((0, "logloss"), (2, "rps")):
    base = 2.0 if mi == 0 else 0.2083
    diffs = []
    for _ in range(10000):
        idx = [random.randrange(n) for _ in range(n)]
        diffs.append(mean([results["v4 K=32"][i][mi] for i in idx]) - base)
    diffs.sort()
    pt = mean([r[mi] for r in results["v4 K=32"]]) - base
    lo, hi = diffs[249], diffs[9749]
    sig = "  *" if hi < 0 or lo > 0 else ""
    print(f"  v4 K=32 - B0 ({mn}): {pt:+.4f}  CI [{lo:+.4f}, {hi:+.4f}]{sig}")

# first half vs second half (form updates should help later rounds)
print("\nLogLoss by half (v3 -> v4 K=32):")
for tag, sl in (("rounds 1-5", slice(0, 15)), ("rounds 6-10", slice(15, 30))):
    print(f"  {tag}: {mean([r[0] for r in v3[sl]]):.4f} -> "
          f"{mean([r[0] for r in results['v4 K=32'][sl]]):.4f}")

print("\nFinal in-tournament eff ratings (K=32) vs start:")
for p in PL:
    print(f"  {p:<10} {eff0(p):7.1f} -> {final_eff[p]:7.1f}  ({final_eff[p]-eff0(p):+.1f})")
