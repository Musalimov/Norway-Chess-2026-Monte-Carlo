#!/usr/bin/env python3
"""Round-by-round report (prequential v4 form updates).

For every round, predict the three games with the prequential state (effective
ratings updated only on previous rounds), compare the modal outcome with the
actual one, and record P(actual) plus surprise bits. Writes
out/rounds_report.json for the dashboard/archive.

Model + data come from src/nc_common.py (out/calibrated_params.json +
configs/model_v4.json + data/tournaments/norway2026.json), so this report is
consistent with eval_oos.py, eval_v4.py and the dashboard.
"""
import json
import math
from pathlib import Path

from nc_common import Model, expected_score, S_OF, ROOT

M = Model()
ROUNDS = M.rounds()
K = M.FORM_K
LBL = ["p1 classical win (3:0)", "draw, p1 wins Armageddon (1.5:1)",
       "draw, p2 wins Armageddon (1:1.5)", "p2 classical win (0:3)"]

eff = {pid: M.eff0(pid) for pid in M.order}
report = []
modal_hits = 0
side_calls = side_hits = 0

for ri, rnd in enumerate(ROUNDS, start=1):
    rgames = []
    for g in rnd:
        p = M.p1_dist(g, eff)
        k = g["outcome"]
        modal = max(range(4), key=lambda i: p[i])
        hit = (modal == k)
        modal_hits += hit
        ordering = None
        if k in (0, 3):
            side_calls += 1
            ordering = (p[0] > p[3]) if k == 0 else (p[3] > p[0])
            side_hits += ordering
        rgames.append({
            "p1": M.name_by_id[g["p1"]], "p2": M.name_by_id[g["p2"]],
            "col": "p1w" if g["color_known"] else "unk",
            "probs": [round(x, 4) for x in p],
            "modal": modal, "actual": k, "modal_hit": hit,
            "p_actual": round(p[k], 4), "bits": round(-math.log2(p[k]), 2),
            "win_side_correct": ordering,
        })
    report.append({"round": ri, "games": rgames,
                   "eff_before": {M.name_by_id[pid]: round(eff[pid], 1) for pid in M.order}})
    for g in rnd:
        s1 = S_OF[g["res"]]
        e1 = expected_score(M, g, eff)
        eff[g["p1"]] += K * (s1 - e1)
        eff[g["p2"]] -= K * (s1 - e1)

summary = {
    "modal_hits": modal_hits, "games": len(M.games()),
    "modal_hit_rate": modal_hits / len(M.games()),
    "decisive_games": side_calls, "win_side_correct": side_hits,
    "note": "modal = most probable of the 4 outcomes; win_side = among decisive "
            "classical games, whether the eventual winner had the higher predicted "
            "win probability",
}
(ROOT / "out" / "rounds_report.json").write_text(
    json.dumps({"summary": summary, "rounds": report}, indent=1, ensure_ascii=False))

for r in report:
    print(f"--- Round {r['round']} ---")
    for g in r["games"]:
        mark = "OK " if g["modal_hit"] else "  x"
        extra = ""
        if g["win_side_correct"] is not None and not g["modal_hit"]:
            extra = "  (winner side: " + ("correct" if g["win_side_correct"] else "wrong") + ")"
        print(f" {mark} {g['p1']:<9}-{g['p2']:<9} actual: {LBL[g['actual']]:<36} "
              f"modal: {LBL[g['modal']][:28]:<28} P(actual)={g['p_actual']*100:5.1f}%{extra}")
print(f"\nModal outcome hit rate: {modal_hits}/{len(M.games())} ({modal_hits/len(M.games()):.0%})")
print(f"Decisive games where the winner had the higher predicted win probability: "
      f"{side_hits}/{side_calls}")
