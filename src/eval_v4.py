#!/usr/bin/env python3
"""Prequential evaluation with in-tournament form updates (K sensitivity).

Round r is predicted using ratings updated on the ACTUAL results of rounds
1..r-1 only (no leakage). Update rule (pre-registered, not tuned on 2026):
after each game  eff += K * (S - E),  S in {1, 0.5, 0}, E = colour-aware Elo
expectation, K = 32 primary; K = 16 / 64 reported as a priori sensitivity.

Everything else (parameters, ratings, data) comes from src/nc_common.py, i.e.
the deployed model in out/calibrated_params.json + configs/model_v4.json,
evaluated on data/tournaments/norway2026.json. v3 = K=0 (frozen, no updates).
"""
import random

from nc_common import Model, metrics, mean, expected_score, S_OF

M = Model()
ROUNDS = M.rounds()


def run(K: float):
    eff = {pid: M.eff0(pid) for pid in M.order}
    out = []
    for rnd in ROUNDS:
        # 1) predict the whole round with current eff (only past info used)
        for g in rnd:
            out.append(metrics(M.p1_dist(g, eff), g["outcome"]))
        # 2) then update on the round's actual results
        for g in rnd:
            s1 = S_OF[g["res"]]
            e1 = expected_score(M, g, eff)
            eff[g["p1"]] += K * (s1 - e1)
            eff[g["p2"]] -= K * (s1 - e1)
    return out, eff


print(f"Parameters (source: {M._fitted_source}): WA={M.WA} DBASE={M.DBASE} "
      f"DDEC={M.DDEC} ARM_H={M.ARM_H} strength={M.STRENGTH} (form K from config: {M.FORM_K})\n")

v3, _ = run(0)
results = {"v3 (K=0)": v3}
final_eff = None
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
            diffs.append(mean([results[name][i][mi] for i in idx])
                         - mean([v3[i][mi] for i in idx]))
        diffs.sort()
        pt = mean([r[mi] for r in results[name]]) - mean([r[mi] for r in v3])
        lo, hi = diffs[249], diffs[9749]
        sig = "  *" if hi < 0 or lo > 0 else ""
        print(f"  {name} - v3 ({mn}): {pt:+.4f}  CI [{lo:+.4f}, {hi:+.4f}]{sig}")
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

print("\nLogLoss by half (v3 -> v4 K=32):")
for tag, sl in (("rounds 1-5", slice(0, 15)), ("rounds 6-10", slice(15, 30))):
    print(f"  {tag}: {mean([r[0] for r in v3[sl]]):.4f} -> "
          f"{mean([r[0] for r in results['v4 K=32'][sl]]):.4f}")

print("\nFinal in-tournament eff ratings (K=32) vs start:")
for pid in M.order:
    print(f"  {M.name_by_id[pid]:<10} {M.eff0(pid):7.1f} -> {final_eff[pid]:7.1f}  "
          f"({final_eff[pid]-M.eff0(pid):+.1f})")
