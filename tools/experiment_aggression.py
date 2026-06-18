#!/usr/bin/env python3
"""Prototype + LOYO backtest of standings-aware draw dynamics (improvement #2).

Diagnosed weakness: the static draw band makes a draw the modal call in ~29/30
games and gives weak directional accuracy on decisive games. Norway Chess
already rewards decisive play, and players push harder late and when chasing the
lead. We add a single parameter AGG that shrinks the draw probability by

    draw_mult = exp(-AGG * lateness * pressure)
    lateness  = (round-1)/(R-1)                      in [0,1]
    pressure  = max over the two players of
                clamp(1 - deficit_to_leader / (3*(rounds_left+1)), 0, 1)

so late-round games involving someone still in reach of the lead become more
decisive. The reduced draw mass is returned to win/loss around the Elo
expectation. `pressure` is computable from the standings BEFORE the game, so the
model is analytic and can be honestly backtested on historical editions (prior
standings come from the actual earlier rounds of that edition).

For each year: fit (WA,DBASE,DDEC,AGG) on the other four editions at the
deployed sigma=60, evaluate out-of-sample. AGG=0 (current model) is compared
with the fitted AGG on the metrics the diagnosis flagged: directional accuracy
on decisive games and how often a draw is the modal call, plus RPS/Brier.
"""
import json, math
from collections import defaultdict
from itertools import product
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from nc_common import mean  # noqa: E402

H = [g for g in json.loads((ROOT / "data/history.json").read_text()) if g["white_elo"] and g["black_elo"]]
YEARS = ["2022", "2023", "2024", "2025", "2026"]
K_OUT = {1.0: 0, 0.5: 1, 0.0: 2}
SIGMA = 60.0
WA0, DD0, WSC, DSC, LAM = 35.0, 0.0017, 15.0, 0.0015, 0.1
GW = [30, 35, 40]; GB = [.65, .70, .75]; GD = [.0012, .0018, .0024]; GA = [0, .3, .6, 1.0, 1.5, 2.0]
_GHX = (0.0, .8162878828589647, -.8162878828589647, 1.6735516287674714, -1.6735516287674714, 2.651961356835233, -2.651961356835233)
_GHW = (.8102646175568073, .4256072526101278, .4256072526101278, .05451558281912703, .05451558281912703, .0009717812450995192, .0009717812450995192)
SP = math.sqrt(math.pi)

# Reconstruct prior-round standings context for every game (NC scoring).
def nc_points(g, pts):
    r = g["classical_result_white"]
    if r == 1.0: pts[g["white"]] += 3
    elif r == 0.0: pts[g["black"]] += 3
    else:
        a = g["armageddon"]
        if a:
            win = a["white_player"] if a["white_won_minimatch"] else (g["white"] if a["white_player"] == g["black"] else g["black"])
            los = g["white"] if win == g["black"] else g["black"]
            pts[win] += 1.5; pts[los] += 1.0
        else: pts[g["white"]] += 1.25; pts[g["black"]] += 1.25

for y in YEARS:
    gy = sorted([g for g in H if g["year"] == y], key=lambda g: g["round"])
    R = max(g["round"] for g in gy)
    Rcount = len(set(g["round"] for g in gy))
    pts = defaultdict(float)
    by_round = defaultdict(list)
    for g in gy: by_round[g["round"]].append(g)
    seen = 0
    rounds_sorted = sorted(by_round)
    for ri, rnum in enumerate(rounds_sorted):
        lead = max(pts.values()) if pts else 0.0
        rounds_left = (Rcount - 1) - ri
        late = ri / max(Rcount - 1, 1)
        for g in by_round[rnum]:
            def press(p):
                d = lead - pts[p]
                return max(0.0, min(1.0, 1 - d / (3 * (rounds_left + 1))))
            g["_late"] = late
            g["_press"] = max(press(g["white"]), press(g["black"]))
            g["_d"] = g["white_elo"] - g["black_elo"]
            g["_k"] = K_OUT[g["classical_result_white"]]
        for g in by_round[rnum]: nc_points(g, pts)

BYYEAR = {y: [g for g in H if g["year"] == y] for y in YEARS}

def wdl(diff, db, dd, agg, late, press):
    def core(d):
        pd = db * math.exp(-abs(d) * dd) * math.exp(-agg * late * press)
        pd = min(pd, 0.85)
        e = 1 / (1 + 10 ** (-d / 400))
        pw = max(e - pd / 2, .01); pb = max(1 - pw - pd, .01)
        return pw, 1 - pw - pb, pb
    tau = SIGMA * math.sqrt(2.0); acc = [0, 0, 0]
    for x, w in zip(_GHX, _GHW):
        v = core(diff + math.sqrt(2) * tau * x)
        for i in range(3): acc[i] += w * v[i]
    return [a / SP for a in acc]

def rps(p, k):
    cp = co = s = 0.0
    for i in range(2):
        cp += p[i]; co += 1.0 if i == k else 0.0; s += (cp - co) ** 2
    return s / 2
def brier(p, k): return sum((p[i] - (1.0 if i == k else 0.0)) ** 2 for i in range(3))

def avg_obj(games, wa, db, dd, agg):
    return mean([rps(wdl(g["_d"] + wa, db, dd, agg, g["_late"], g["_press"]), g["_k"]) for g in games]) \
        + LAM * (((wa - WA0) / WSC) ** 2 + ((dd - DD0) / DSC) ** 2)

def fit(games, force_agg=None):
    ga = [0] if force_agg == 0 else GA
    best = None
    for wa, db, dd, agg in product(GW, GB, GD, ga):
        v = avg_obj(games, wa, db, dd, agg)
        if best is None or v < best[0]: best = (v, wa, db, dd, agg)
    return best[1:]

def evalyear(games, wa, db, dd, agg):
    rp = dm = 0.0; dirh = dirn = 0
    rl, bl = [], []
    for g in games:
        p = wdl(g["_d"] + wa, db, dd, agg, g["_late"], g["_press"]); k = g["_k"]
        rl.append(rps(p, k)); bl.append(brier(p, k))
        if max(range(3), key=lambda i: p[i]) == 1: dm += 1
        if k in (0, 2):
            dirn += 1
            dirh += (p[0] > p[2]) if k == 0 else (p[2] > p[0])
    return mean(rl), mean(bl), dm, len(games), dirh, dirn

print("=== Standings-aware draw dynamics: LOYO (sigma=60 fixed) ===")
print(f"{'year':>5} {'AGG':>4} | {'RPS base':>8} {'RPS agg':>8} | {'Brier base':>10} {'Brier agg':>9} | "
      f"{'drawModal b->a':>14} | {'directional b->a':>16}")
agg_tot = defaultdict(float); n_tot = 0; dirh_b = dirn_b = dirh_a = dirn_a = dm_b = dm_a = 0
for y in YEARS:
    tr = [g for g in H if g["year"] != y]; te = BYYEAR[y]
    wb, bb, db_, _ = fit(tr, force_agg=0)
    wa, ba, da, ag = fit(tr)
    rb, brb, dmb, n, hb, nb = evalyear(te, wb, bb, db_, 0)
    ra, bra, dma, _, ha, na = evalyear(te, wa, ba, da, ag)
    print(f"{y:>5} {ag:>4} | {rb:>8.4f} {ra:>8.4f} | {brb:>10.4f} {bra:>9.4f} | "
          f"{int(dmb):>5}/{n} -> {int(dma):>2}/{n}   | {hb}/{nb} -> {ha}/{na}")
    agg_tot['rb'] += rb * n; agg_tot['ra'] += ra * n; agg_tot['brb'] += brb * n; agg_tot['bra'] += bra * n
    n_tot += n; dm_b += dmb; dm_a += dma; dirh_b += hb; dirn_b += nb; dirh_a += ha; dirn_a += na
print(f"{'ALL':>5} {'—':>4} | {agg_tot['rb']/n_tot:>8.4f} {agg_tot['ra']/n_tot:>8.4f} | "
      f"{agg_tot['brb']/n_tot:>10.4f} {agg_tot['bra']/n_tot:>9.4f} | {int(dm_b):>5}/{n_tot} -> {int(dm_a):>2}/{n_tot} | "
      f"{dirh_b}/{dirn_b} -> {dirh_a}/{dirn_a}")
print("\nbase = current model (AGG=0); agg = with fitted standings-aware draw dynamics.")
print("directional = on decisive games, model gave the winning side the higher prob.")
