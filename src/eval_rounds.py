#!/usr/bin/env python3
"""Round-by-round report.

For every round, predict the three games with the prequential v4 state
(effective ratings are updated only on previous rounds), then compare the
modal outcome with the actual one and compute P(actual) plus surprise bits.
Writes out/rounds_report.json for the dashboard/archive.
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = json.loads((ROOT / "data" / "dataset_full.json").read_text())
PL = D["players_pretournament"]

WA, DBASE, DDEC, ARM_H, K = 35.0, 0.70, 0.0018, -30.0, 32.0
LBL = ["p1 classical win (3:0)", "draw, p1 wins Armageddon (1.5:1)",
       "draw, p2 wins Armageddon (1:1.5)", "p2 classical win (0:3)"]
RES_IDX = {3.0: 0, 1.5: 1, 1.0: 2, 0.0: 3}
S_OF = {3.0: 1.0, 1.5: 0.5, 1.0: 0.5, 0.0: 0.0}

def expect(d): return 1.0 / (1.0 + 10 ** (-d / 400.0))
def eff0(p): return PL[p]["classical"] + PL[p]["live_adj"] + 2.0 * PL[p]["trend_mo"]

def dist_white(eff, w, b):
    diff = eff[w] - eff[b] + WA
    pd = min(DBASE * math.exp(-abs(diff) * DDEC) * PL[w]["style"] * PL[b]["style"], 0.85)
    e = expect(diff)
    pw = max(e - pd / 2.0, 0.01)
    pb = max(1.0 - pw - pd, 0.01)
    pd = 1.0 - pw - pb
    parm = expect(PL[w]["blitz"] - PL[b]["blitz"] - ARM_H)
    return [pw, pd * parm, pd * (1 - parm), pb]

def p1_dist(eff, g):
    a = dist_white(eff, g["p1"], g["p2"])
    bb = dist_white(eff, g["p2"], g["p1"])
    b = [bb[3], bb[2], bb[1], bb[0]]
    return a if g["col"] == "p1w" else [(x + y) / 2 for x, y in zip(a, b)]

eff = {p: eff0(p) for p in PL}
report = []
modal_hits = 0
side_calls = side_hits = 0  # when decisive: did the higher-win-prob side win?

for rnd in D["rounds"]:
    rgames = []
    for g in rnd["games"]:
        p = p1_dist(eff, g)
        k = RES_IDX[g["res"]]
        modal = max(range(4), key=lambda i: p[i])
        hit = (modal == k)
        modal_hits += hit
        # Decisive classical games: did the eventual winner have the higher win probability?
        ordering = None
        if k in (0, 3):
            side_calls += 1
            ordering = (p[0] > p[3]) if k == 0 else (p[3] > p[0])
            side_hits += ordering
        rgames.append({
            "p1": g["p1"], "p2": g["p2"], "col": g["col"], "probs": [round(x, 4) for x in p],
            "modal": modal, "actual": k, "modal_hit": hit,
            "p_actual": round(p[k], 4), "bits": round(-math.log2(p[k]), 2),
            "win_side_correct": ordering,
        })
    report.append({"round": rnd["r"], "games": rgames,
                   "eff_before": {p: round(eff[p], 1) for p in PL}})
    for g in rnd["games"]:
        s1 = S_OF[g["res"]]
        if g["col"] == "p1w":
            e1 = expect(eff[g["p1"]] - eff[g["p2"]] + WA)
        else:
            e1 = 0.5 * (expect(eff[g["p1"]] - eff[g["p2"]] + WA)
                        + expect(eff[g["p1"]] - eff[g["p2"]] - WA))
        eff[g["p1"]] += K * (s1 - e1)
        eff[g["p2"]] -= K * (s1 - e1)

summary = {
    "modal_hits": modal_hits, "games": 30, "modal_hit_rate": modal_hits / 30,
    "decisive_games": side_calls, "win_side_correct": side_hits,
    "note": "modal = most probable of the 4 outcomes; win_side = among decisive classical games, whether the eventual winner had the higher predicted win probability",
}
(ROOT / "out" / "rounds_report.json").write_text(
    json.dumps({"summary": summary, "rounds": report}, indent=1, ensure_ascii=False))

for r in report:
    print(f"--- Round {r['round']} ---")
    for g in r["games"]:
        mark = "✓" if g["modal_hit"] else "✗"
        extra = ""
        if g["win_side_correct"] is not None and not g["modal_hit"]:
            extra = "  (winner side: " + ("correct" if g["win_side_correct"] else "wrong") + ")"
        print(f" {mark} {g['p1']:<9}-{g['p2']:<9} actual: {LBL[g['actual']]:<36} "
              f"modal: {LBL[g['modal']][:28]:<28} P(actual)={g['p_actual']*100:5.1f}%{extra}")
print(f"\nModal outcome hit rate: {modal_hits}/30 ({modal_hits/30:.0%})")
print(f"Decisive games where the winner had the higher predicted win probability: {side_hits}/{side_calls}")
