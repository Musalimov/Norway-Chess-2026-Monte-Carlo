#!/usr/bin/env python3
"""Out-of-sample evaluation: the deployed model vs baselines on NC 2026.

The model under test ("v4") is the *exact* deployed model: fitted parameters
are read from out/calibrated_params.json and structural parameters
(Armageddon strength, caps) from configs/model_v4.json via src/nc_common.py.
Players and the 30 actual results are read from the same
data/tournaments/norway2026.json that the C++ engine and the dashboard use, so
this script can no longer drift from what is actually simulated.

It is "out-of-sample" because the parameters were calibrated on 2022-2025 only
(see tools/calibrate.py, leave-one-tournament-out CV) and frozen before 2026.
v4 here is the frozen pre-tournament model (eff = eff0, no in-tournament form
updates); the prequential form-update variants live in src/eval_v4.py.

Baselines, computed on the same data:
  B0  uniform 0.25 over the 4 ordered outcomes
  v1  naive static Elo (classical ratings only, no styles, no trend),
      white_adv 35, draw_base 0.66, decay 0.0017, Armageddon on classical Elo

Per-game metrics over the 4 ordered outcomes (p1 points 3 / 1.5 / 1 / 0):
  log-loss (bits), Brier, RPS. Bootstrap (10k) CIs on pairwise differences.
Probabilities are analytic: at the game level Monte Carlo is unnecessary
(3 independent boards per round).
"""
import random

from nc_common import Model, metrics, mean

M = Model()
GAMES = M.games()


# ── naive static-Elo baseline (v1), on the canonical data ──────────────────────


def v1_white(white: str, black: str) -> list[float]:
    rw = M.players[white]["classical"]
    rb = M.players[black]["classical"]
    diff = rw - rb + 35.0
    pd = 0.66 * (2.718281828459045 ** (-abs(diff) * 0.0017))
    e = M.expect(diff)
    pw = max(e - pd / 2.0, 0.01)
    pb = max(1.0 - pw - pd, 0.01)
    pd = 1.0 - pw - pb
    parm = M.expect(rw - rb - 60.0)  # Armageddon on classical Elo, handicap -60
    return [pw, pd * parm, pd * (1.0 - parm), pb]


def v1_p1(g: dict) -> list[float]:
    a = v1_white(g["p1"], g["p2"])
    if g["color_known"]:
        f = a
    else:
        bb = v1_white(g["p2"], g["p1"])
        b = [bb[3], bb[2], bb[1], bb[0]]
        f = [(x + y) / 2.0 for x, y in zip(a, b)]
    s = sum(f)
    return [x / s for x in f]


def p1_dist(g: dict, model: str) -> list[float]:
    if model == "B0":
        return [0.25] * 4
    if model == "v1":
        return v1_p1(g)
    return M.p1_dist(g)  # v4 = deployed model, frozen at eff0


# ── per-game metrics ────────────────────────────────────────────────────────────

MODELS = ["B0", "v1", "v4"]
per_game = {m: [] for m in MODELS}
for g in GAMES:
    k = g["outcome"]
    for m in MODELS:
        per_game[m].append(metrics(p1_dist(g, m), k))

print(f"Model under test parameters (source: {M._fitted_source}):")
print(f"  WA={M.WA}  DBASE={M.DBASE}  DDEC={M.DDEC}  ARM_H={M.ARM_H}  "
      f"armageddon_strength={M.STRENGTH}")
print(f"Data: {M.name}, {len(GAMES)} games "
      f"({sum(1 for g in GAMES if g['how']=='classical')} decisive classical, "
      f"{sum(1 for g in GAMES if g['how']=='armageddon')} drawn->Armageddon)\n")

print(f"{'Model':<6}{'LogLoss(bits)':>14}{'Brier':>9}{'RPS':>9}")
for m in MODELS:
    cols = list(zip(*per_game[m]))
    print(f"{m:<6}{mean(cols[0]):>14.4f}{mean(cols[1]):>9.4f}{mean(cols[2]):>9.4f}")

# ── bootstrap CIs on pairwise differences ───────────────────────────────────────

random.seed(42)
n = len(GAMES)
print("\nBootstrap 95% CI on differences (negative = first model better), 10k resamples:")
for a, b in (("v4", "v1"), ("v4", "B0"), ("v1", "B0")):
    for mi, mname in ((0, "logloss"), (2, "rps")):
        diffs = []
        for _ in range(10000):
            idx = [random.randrange(n) for _ in range(n)]
            diffs.append(mean([per_game[a][i][mi] for i in idx])
                         - mean([per_game[b][i][mi] for i in idx]))
        diffs.sort()
        lo, hi = diffs[249], diffs[9749]
        pt = mean([x[mi] for x in per_game[a]]) - mean([x[mi] for x in per_game[b]])
        sig = "  *" if hi < 0 or lo > 0 else ""
        print(f"  {a} - {b} ({mname}): {pt:+.4f}  CI [{lo:+.4f}, {hi:+.4f}]{sig}")

# ── calibration check: predicted vs observed draw count ──────────────────────────

for m in ("v1", "v4"):
    pdraws = sum(p1_dist(g, m)[1] + p1_dist(g, m)[2] for g in GAMES)
    obs = sum(1 for g in GAMES if g["how"] == "armageddon")
    print(f"\n{m}: predicted draws {pdraws:.1f}/{n}, observed {obs}/{n}")
obs_arm = sum(1 for g in GAMES if g["how"] == "armageddon")
print(f"Observed classical draw share 2026: {obs_arm/n:.0%}")

# ── per-game detail: where the deployed model was most wrong ─────────────────────

detail = sorted(zip(GAMES, per_game["v4"], per_game["v1"]), key=lambda t: -t[1][0])
print("\nTop-5 surprises for v4 (bits, v1 in brackets):")
for g, m4, m1 in detail[:5]:
    nm1, nm2 = M.name_by_id[g["p1"]], M.name_by_id[g["p2"]]
    print(f"  R{g['round']:>2} {nm1}-{nm2} res {g['res']}: v4 {m4[0]:.2f} (v1 {m1[0]:.2f})")
