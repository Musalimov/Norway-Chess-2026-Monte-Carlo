#!/usr/bin/env python3
"""Multi-year leave-one-year-out (LOYO) backtest.

Each Norway Chess edition 2022-2026 is an independent event. For every year Y
the model is fitted on the OTHER four years (RPS + MAP, lambda=0.1, the
production setting) and scored out-of-sample on Y. This shows whether the
model's edge over uniform — and the benefit of strength sampling — generalises
across several independent tournaments rather than resting on 2026 alone.

Two levels are reported per year:
  * per-game (rating-only): RPS / Brier / log-loss on classical win/draw/loss,
    using src/nc_common.classical_wdl (the same core as the deployed model);
  * tournament: the probability the model assigned to the ACTUAL champion and
    the champion surprise in bits, from the C++ engine on the reconstructed
    schedule (ratings only, style 1, Armageddon on classical Elo).

For each, sigma=0 (point ratings) is compared with the CV-style fitted sigma to
show the strength-sampling effect year by year. Writes out/backtest.json.

Requires the compiled ./sim binary. Standard library only otherwise.
"""
import json
import math
import subprocess
import sys
from collections import defaultdict
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from nc_common import classical_wdl, mean  # noqa: E402

H = [g for g in json.loads((ROOT / "data/history.json").read_text()) if g["white_elo"] and g["black_elo"]]
YEARS = ["2022", "2023", "2024", "2025", "2026"]
K_OUT = {1.0: 0, 0.5: 1, 0.0: 2}
for g in H:
    g["_d"] = g["white_elo"] - g["black_elo"]
    g["_k"] = K_OUT[g["classical_result_white"]]
BYYEAR = {y: [g for g in H if g["year"] == y] for y in YEARS}

WA0, DD0, WSC, DSC, LAM = 35.0, 0.0017, 15.0, 0.0015, 0.1
GW = [25, 30, 35, 40, 45]
GB = [.60, .65, .70, .75]
GD = [.0006, .0012, .0018, .0024]
GS = [0, 40, 60, 80]


def rps(p3, k):
    cp = co = s = 0.0
    for i in range(2):
        cp += p3[i]; co += 1.0 if i == k else 0.0; s += (cp - co) ** 2
    return s / 2


def brier(p3, k):
    return sum((p3[i] - (1.0 if i == k else 0.0)) ** 2 for i in range(3))


def logloss(p3, k):
    return -math.log2(max(p3[k], 1e-12))


def avg_rps(games, wa, db, dd, sg):
    return mean([rps(classical_wdl(g["_d"] + wa, db, dd, sigma=sg), g["_k"]) for g in games])


def fit(games, force_sigma=None):
    grid_s = [0] if force_sigma == 0 else (GS if force_sigma is None else [force_sigma])
    best = None
    for wa, db, dd, sg in product(GW, GB, GD, grid_s):
        v = avg_rps(games, wa, db, dd, sg) + LAM * (((wa - WA0) / WSC) ** 2 + ((dd - DD0) / DSC) ** 2)
        if best is None or v < best[0]:
            best = (v, wa, db, dd, sg)
    return best[1:]


def standings(games):
    pts = defaultdict(float)
    for g in games:
        r = g["classical_result_white"]
        if r == 1.0:
            pts[g["white"]] += 3
        elif r == 0.0:
            pts[g["black"]] += 3
        else:
            a = g["armageddon"]
            if a:
                winner = a["white_player"] if a["white_won_minimatch"] else \
                    (g["white"] if a["white_player"] == g["black"] else g["black"])
                loser = g["white"] if winner == g["black"] else g["black"]
                pts[winner] += 1.5; pts[loser] += 1.0
            else:
                pts[g["white"]] += 1.25; pts[g["black"]] += 1.25
    return pts


def tok(name):
    return name.split(",")[0].replace(" ", "_").replace(".", "")


def champion_prob(year_games, wa, db, dd, armh, sg):
    """P(actual champion wins) from the C++ engine on the reconstructed schedule."""
    pts = standings(year_games)
    champ = max(pts, key=pts.get)
    elo = defaultdict(list)
    for g in year_games:
        elo[g["white"]].append(g["white_elo"]); elo[g["black"]].append(g["black_elo"])
    players = sorted(elo)
    idx = {p: i for i, p in enumerate(players)}
    eff = {p: mean(elo[p]) for p in players}
    lines = [f"PARAMS {wa} {db} {dd} {armh} 32.0 0.85 0.01 {sg}", f"PLAYERS {len(players)}"]
    for p in players:
        lines.append(f"{eff[p]} {eff[p]} 1.0 {tok(p)}")
    rounds = defaultdict(list)
    for g in year_games:
        rounds[g["round"]].append(g)
    rks = sorted(rounds)
    lines.append(f"ROUNDS {len(rks)}")
    for rk in rks:
        lines.append(f"GAMES {len(rounds[rk])}")
        for g in rounds[rk]:
            lines.append(f"{idx[g['white']]} {idx[g['black']]} 1 0")
    inp = "\n".join(lines) + "\n"
    out = json.loads(subprocess.run(["./sim", "full", "200000", "20260525", "0"],
                                    input=inp, capture_output=True, text=True, cwd=ROOT).stdout)
    pw = {p["name"]: p["p_win"] for p in out["players"]}
    return tok(champ), pw[tok(champ)], len(players)


pg_rows, t_rows = [], []
agg = {"fit": defaultdict(float), "sig0": defaultdict(float), "uni": defaultdict(float), "n": 0}
for y in YEARS:
    train = [g for g in H if g["year"] != y]
    test = BYYEAR[y]
    wa, db, dd, sg = fit(train)                 # sigma in the grid
    wa0, db0, dd0, _ = fit(train, force_sigma=0)  # sigma forced to 0
    # per-game OOS
    r_fit = avg_rps(test, wa, db, dd, sg)
    b_fit = mean([brier(classical_wdl(g["_d"] + wa, db, dd, sigma=sg), g["_k"]) for g in test])
    l_fit = mean([logloss(classical_wdl(g["_d"] + wa, db, dd, sigma=sg), g["_k"]) for g in test])
    r_0 = avg_rps(test, wa0, db0, dd0, 0)
    r_uni = mean([rps([1/3, 1/3, 1/3], g["_k"]) for g in test])
    b_uni = mean([brier([1/3, 1/3, 1/3], g["_k"]) for g in test])
    pg_rows.append((y, len(test), sg, r_0, r_fit, r_uni, b_fit, b_uni, l_fit))
    for key, r, b in (("fit", r_fit, b_fit), ("sig0", r_0, None), ("uni", r_uni, b_uni)):
        agg[key]["rps"] += r * len(test)
        if b is not None:
            agg[key]["brier"] += b * len(test)
    agg["n"] += len(test)
    # tournament OOS (champion surprise): need ARM_H — fit it cheaply on train armageddons
    arms = [g for g in train if g["armageddon"]]
    def ad(g):
        a = g["armageddon"]; return g["_d"] if a["white_player"] == g["white"] else -g["_d"]
    armh = min((sum((1/(1+10**(-(ad(g)-h)/400)) - (1.0 if g["armageddon"]["white_won_minimatch"] else 0.0))**2
                    for g in arms)/len(arms) + 0.1*((h+30)/40)**2, h) for h in range(-150, 151, 5))[1]
    champ, p_fit, npl = champion_prob(test, wa, db, dd, armh, sg)
    _, p_0, _ = champion_prob(test, wa0, db0, dd0, armh, 0)
    t_rows.append((y, champ, npl, p_0, p_fit))

print("=== Per-game leave-one-year-out (rating-only, RPS / Brier / log-loss) ===")
print(f"{'year':>5} {'n':>3} {'sigma':>5} | {'RPS sigma0':>10} {'RPS fit':>8} {'RPS unif':>8} | "
      f"{'Brier fit':>9} {'Brier unif':>10} {'LL fit':>7}")
for y, n, sg, r0, rf, ru, bf, bu, lf in pg_rows:
    star = " *" if rf < ru else "  "
    print(f"{y:>5} {n:>3} {sg:>5} | {r0:>10.4f} {rf:>8.4f}{star} {ru:>8.4f} | {bf:>9.4f} {bu:>10.4f} {lf:>7.4f}")
n = agg["n"]
print(f"{'ALL':>5} {n:>3} {'—':>5} | {agg['sig0']['rps']/n:>10.4f} {agg['fit']['rps']/n:>8.4f}   "
      f"{agg['uni']['rps']/n:>8.4f} | {agg['fit']['brier']/n:>9.4f} {agg['uni']['brier']/n:>10.4f}")

print("\n=== Tournament leave-one-year-out (probability assigned to the actual champion) ===")
print(f"{'year':>5} {'champion':>12} {'players':>7} | {'P sigma0':>9} {'P fit':>7} | "
      f"{'bits sigma0':>11} {'bits fit':>9} {'bits unif':>9}")
for y, champ, npl, p0, pf in t_rows:
    print(f"{y:>5} {champ:>12} {npl:>7} | {p0*100:>8.1f}% {pf*100:>6.1f}% | "
          f"{-math.log2(max(p0,1e-9)):>11.2f} {-math.log2(max(pf,1e-9)):>9.2f} {math.log2(npl):>9.2f}")

out = {
    "method": "leave-one-year-out; fit on the other 4 editions (RPS+MAP, lambda=0.1)",
    "per_game": [dict(year=y, n=n, sigma=sg, rps_sigma0=round(r0, 4), rps_fit=round(rf, 4),
                      rps_uniform=round(ru, 4), brier_fit=round(bf, 4), brier_uniform=round(bu, 4),
                      logloss_fit=round(lf, 4)) for y, n, sg, r0, rf, ru, bf, bu, lf in pg_rows],
    "per_game_all": dict(n=n, rps_sigma0=round(agg["sig0"]["rps"]/n, 4),
                         rps_fit=round(agg["fit"]["rps"]/n, 4), rps_uniform=round(agg["uni"]["rps"]/n, 4),
                         brier_fit=round(agg["fit"]["brier"]/n, 4), brier_uniform=round(agg["uni"]["brier"]/n, 4)),
    "tournament": [dict(year=y, champion=champ, players=npl, p_champion_sigma0=round(p0, 4),
                        p_champion_fit=round(pf, 4), bits_sigma0=round(-math.log2(max(p0, 1e-9)), 2),
                        bits_fit=round(-math.log2(max(pf, 1e-9)), 2),
                        bits_uniform=round(math.log2(npl), 2)) for y, champ, npl, p0, pf in t_rows],
}
(ROOT / "out/backtest.json").write_text(json.dumps(out, indent=1))
print("\nsaved: out/backtest.json")
