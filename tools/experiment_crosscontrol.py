#!/usr/bin/env python3
"""Speed cross-control (improvement #3): mechanism check on 2026 only.

Cross-control blends each player's field-relative rapid/blitz strength into
their effective classical rating (folded into Model.eff0 via the CC parameter),
on the hypothesis that relative speed strength signals sharper current form —
the lever the multi-year backtest identified for decisive-game accuracy.

IMPORTANT: this is an IN-SAMPLE check on the 30 games of 2026 only. It cannot be
validated out-of-sample, because history.json (2022-2025) stores no historical
rapid/blitz ratings — they exist only for the six 2026 players. So this script
shows the direction and size of the effect (a mechanism check), NOT evidence
that cross-control helps. CC therefore stays 0 in the deployed model until
per-edition speed ratings are added to the dataset (see README).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from nc_common import Model, metrics, mean  # noqa: E402

print("Per-player field-centred speed gap (rapid/blitz vs classical):")
M0 = Model()
fm = M0._field_mean_speed_gap()
for pid in M0.order:
    p = M0.players[pid]
    gap = 0.5 * ((p["rapid"] - p["classical"]) + (p["blitz"] - p["classical"])) - fm
    print(f"  {M0.name_by_id[pid]:<10} classical {p['classical']}  speed-gap(centred) {gap:+.1f}")

print("\nIN-SAMPLE 2026 sensitivity (NOT out-of-sample):")
print(f"{'CC':>5} | {'RPS':>7} {'Brier':>7} {'drawModal':>9} {'directional':>12} | {'Carlsen eff':>11}")
for cc in [0.0, 0.25, 0.5, 0.75, 1.0]:
    M = Model(); M.CC = cc
    games = M.games()
    rl, bl = [], []
    dm = dirh = dirn = 0
    for g in games:
        p = M.p1_dist(g); k = g["outcome"]
        rl.append(metrics(p, k)[2]); bl.append(metrics(p, k)[1])
        if p[1] + p[2] > max(p[0], p[3]):
            dm += 1
        if k in (0, 3):
            dirn += 1
            dirh += (p[0] > p[3]) if k == 0 else (p[3] > p[0])
    print(f"{cc:>5} | {mean(rl):>7.4f} {mean(bl):>7.4f} {dm:>6}/{len(games)} {dirh:>6}/{dirn:>3}     | "
          f"{M.eff0('carlsen'):>11.1f}")
print("\ndirectional = on decisive games, model gave the winning side the higher prob.")
