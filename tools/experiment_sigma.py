#!/usr/bin/env python3
"""Before/after experiment: does per-iteration strength sampling (sigma) help?

For a sweep of sigma it reports, on the actual 2026 edition:
  * per-game OOS scores (log-loss, Brier, RPS) + 4-way calibration error (ECE)
    and how often a draw is the modal call — computed analytically from the
    marginalised model in src/nc_common.py;
  * tournament-level honesty — the probability the model assigned to the actual
    champion (Praggnanandhaa), the favourite's (Carlsen) probability, the
    champion surprise in bits, and a rank RPS of the actual finishing order —
    computed from the C++ engine (1 offset per player per simulated tournament).

sigma = 0 is the current point-rating model (the "before").
"""
import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from nc_common import Model, metrics, mean  # noqa: E402

SIGMAS = [0, 20, 40, 60, 80, 100, 120]
ITERS, SEED = "400000", "20260525"
ACTUAL_RANK = {"Pragg": 0, "So": 1, "Firouzja": 2, "Carlsen": 3, "Keymer": 4, "Gukesh": 5}
CHAMPION = "Pragg"


def per_game(sigma):
    M = Model()
    M.STRENGTH_SIGMA = float(sigma)
    games = M.games()
    rows = [metrics(M.p1_dist(g), g["outcome"]) for g in games]
    ll, br, rps = (mean(c) for c in zip(*rows))
    draw_modal = sum(1 for g in games if (lambda p: p[1] + p[2] > max(p[0], p[3]))(M.p1_dist(g)))
    # 4-way calibration error (ECE) over pooled predicted probabilities
    pairs = [(p, 1 if g["outcome"] == i else 0)
             for g in games for i, p in enumerate(M.p1_dist(g))]
    ece = 0.0
    nb = 5
    for b in range(nb):
        lo, hi = b / nb, (b + 1) / nb
        sel = [(p, y) for p, y in pairs if (lo <= p < hi or (b == nb - 1 and p == 1.0))]
        if sel:
            conf = mean([p for p, _ in sel]); acc = mean([y for _, y in sel])
            ece += len(sel) / len(pairs) * abs(acc - conf)
    return ll, br, rps, draw_modal, ece


def tournament(sigma):
    M = Model(config=ROOT / "configs/model_v4_rapidblitz.json")
    M.STRENGTH_SIGMA = float(sigma)
    out = json.loads(subprocess.run(["./sim", "full", ITERS, SEED, "0"],
                                    input=M.sim_input(), capture_output=True, text=True).stdout)
    pw = {p["name"]: p["p_win"] for p in out["players"]}
    rd = {p["name"]: p["rank_dist"] for p in out["players"]}
    p_champ = pw[CHAMPION]
    # rank RPS of the actual finishing order, averaged across players
    n = 6
    rps_terms = []
    for name, actual in ACTUAL_RANK.items():
        cdf_p = cdf_a = 0.0; s = 0.0
        for k in range(n - 1):
            cdf_p += rd[name][k]; cdf_a += 1.0 if actual == k else 0.0
            s += (cdf_p - cdf_a) ** 2
        rps_terms.append(s / (n - 1))
    return pw["Carlsen"], p_champ, -math.log2(max(p_champ, 1e-9)), mean(rps_terms)


print(f"{'sigma':>5} | {'logloss':>7} {'Brier':>6} {'RPS':>6} {'drawMod':>7} {'ECE':>6} | "
      f"{'Carlsen':>7} {'P(champ)':>8} {'champ bits':>10} {'rankRPS':>7}")
print("-" * 92)
base = None
for sg in SIGMAS:
    ll, br, rps, dm, ece = per_game(sg)
    carl, pchamp, bits, rankrps = tournament(sg)
    row = (f"{sg:>5} | {ll:>7.4f} {br:>6.4f} {rps:>6.4f} {dm:>5}/30 {ece:>6.3f} | "
           f"{carl*100:>6.1f}% {pchamp*100:>7.1f}% {bits:>10.2f} {rankrps:>7.4f}")
    print(row)
    if sg == 0:
        base = (ll, br, rps, ece, pchamp, bits, rankrps)

print("\nUniform baseline: per-game Brier 0.750, RPS 0.2083.  P(champ) under uniform = 1/6 = 16.7%.")
if base:
    print(f"\nbefore (sigma=0):  Brier {base[1]:.4f}  RPS {base[2]:.4f}  ECE {base[3]:.3f}  "
          f"P(champ) {base[4]*100:.1f}%  champ bits {base[5]:.2f}  rankRPS {base[6]:.4f}")
