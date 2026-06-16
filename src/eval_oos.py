#!/usr/bin/env python3
"""Out-of-sample evaluation: frozen pre-tournament models vs all 30 games of NC 2026.

Models (all parameters frozen on pre-May-25 information only):
  B0  uniform 0.25 over the 4 outcomes
  v1  static Elo: white_adv 35, draw_base 0.66, armageddon on classical Elo, handicap -60
  v3  calibrated: white_adv 19.5, draw_base 0.60 (NC 2022-25 draw share),
      armageddon on blitz Elo with handicap -14.3 (194 historical NC armageddons: 101 W / 93 B),
      velocity (live adj + 2mo trend), style multipliers (pre-2026 reputations, subjective prior)

Unknown colors -> 50/50 mixture over both color assignments.
Metrics per game over 4 ordered outcomes (p1 points 3 / 1.5 / 1 / 0):
  log-loss (bits), Brier, RPS. Bootstrap (10k) CIs on pairwise differences.
Probabilities are analytic: Monte Carlo is unnecessary at game level (3 independent boards).
"""
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = json.loads((ROOT / "data" / "dataset_full.json").read_text())
PL = D["players_pretournament"]

def expect(diff):
    return 1.0 / (1.0 + 10 ** (-diff / 400.0))

def game_dist(white, black, m):
    """Return P over p_white outcomes [3, 1.5, 1, 0]."""
    if m == "v1":
        rw, rb = PL[white]["classical"], PL[black]["classical"]
        diff = rw - rb + 35.0
        pd = 0.66 * math.exp(-abs(diff) * 0.0017)
        parm = expect(rw - rb - 60.0)
    else:  # v3
        def eff(p): return PL[p]["classical"] + PL[p]["live_adj"] + 2.0 * PL[p]["trend_mo"]
        diff = eff(white) - eff(black) + 19.5
        pd = 0.60 * math.exp(-abs(diff) * 0.0017) * PL[white]["style"] * PL[black]["style"]
        pd = min(pd, 0.85)
        parm = expect(PL[white]["blitz"] - PL[black]["blitz"] - (-14.3))
    e = expect(diff)
    pw = max(e - pd / 2.0, 0.01)
    pb = max(1.0 - pw - pd, 0.01)
    pd = 1.0 - pw - pb
    return [pw, pd * parm, pd * (1 - parm), pb]

def p1_dist(g, m):
    if m == "B0":
        return [0.25] * 4
    a = game_dist(g["p1"], g["p2"], m)                      # p1 has White
    bb = game_dist(g["p2"], g["p1"], m)                     # p2 has White
    b = [bb[3], bb[2], bb[1], bb[0]]                        # reorder to p1 perspective
    if g["col"] == "p1w":
        return a
    return [(x + y) / 2 for x, y in zip(a, b)]

RES_IDX = {3.0: 0, 1.5: 1, 1.0: 2, 0.0: 3}

games = [g for r in D["rounds"] for g in r["games"]]
MODELS = ["B0", "v1", "v3"]
per_game = {m: [] for m in MODELS}   # (logloss, brier, rps)

for g in games:
    k = RES_IDX[g["res"]]
    for m in MODELS:
        p = p1_dist(g, m)
        ll = -math.log2(max(p[k], 1e-12))
        br = sum((p[i] - (1.0 if i == k else 0.0)) ** 2 for i in range(4))
        cp, co, rps = 0.0, 0.0, 0.0
        for i in range(3):  # RPS over ordered outcomes
            cp += p[i]; co += 1.0 if i == k else 0.0
            rps += (cp - co) ** 2
        per_game[m].append((ll, br, rps / 3))

def mean(xs): return sum(xs) / len(xs)

print(f"{'Model':<6}{'LogLoss(bits)':>14}{'Brier':>9}{'RPS':>9}")
for m in MODELS:
    cols = list(zip(*per_game[m]))
    print(f"{m:<6}{mean(cols[0]):>14.4f}{mean(cols[1]):>9.4f}{mean(cols[2]):>9.4f}")

random.seed(42)
n = len(games)
print("\nBootstrap 95% CI on differences (negative = first model better), 10k resamples:")
for a, b in (("v3", "v1"), ("v3", "B0"), ("v1", "B0")):
    for mi, mname in ((0, "logloss"), (2, "rps")):
        diffs = []
        for _ in range(10000):
            idx = [random.randrange(n) for _ in range(n)]
            diffs.append(mean([per_game[a][i][mi] for i in idx]) -
                         mean([per_game[b][i][mi] for i in idx]))
        diffs.sort()
        lo, hi = diffs[249], diffs[9749]
        pt = mean([per_game[a][i][mi] for i in range(n)]) - mean([per_game[b][i][mi] for i in range(n)])
        sig = "  *" if hi < 0 or lo > 0 else ""
        print(f"  {a} - {b} ({mname}): {pt:+.4f}  CI [{lo:+.4f}, {hi:+.4f}]{sig}")

# calibration check: predicted vs observed aggregates
for m in ("v1", "v3"):
    pdraws = sum(p1_dist(g, m)[1] + p1_dist(g, m)[2] for g in games)
    print(f"\n{m}: predicted draws {pdraws:.1f}/30, observed {sum(1 for g in games if g['how']=='arm')}/30")
obs_arm = sum(1 for g in games if g["how"] == "arm")
print(f"Observed classical draw share 2026: {obs_arm/30:.0%} (training estimate was 60%)")

# per-game detail: where each model was most wrong (top 5 by v3 logloss)
detail = sorted(zip(games, per_game["v3"], per_game["v1"]), key=lambda t: -t[1][0])
print("\nTop-5 surprises for v3 (bits, v1 in brackets):")
for g, m3, m1 in detail[:5]:
    print(f"  R? {g['p1']}-{g['p2']} res {g['res']}: v3 {m3[0]:.2f} (v1 {m1[0]:.2f})")
