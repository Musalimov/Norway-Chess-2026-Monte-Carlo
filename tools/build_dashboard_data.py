#!/usr/bin/env python3
"""Build dashboard_data.json from already generated simulation outputs.

The heavy 1,000,000-iteration simulation outputs are expected to already exist
in out/timeline_*.json and out/tournament_sim_v4.json. This script combines
those outputs with tournament metadata, analytic per-game probabilities, final
place distributions, reliability bins, and per-round Brier scores.

All per-game probabilities come from src/nc_common.py (one Model per Armageddon
strength). There is no second copy of the probability formula here, so the
dashboard cannot disagree with src/eval_*.py or with what the C++ engine
simulated.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from nc_common import Model  # noqa: E402

MODELS = ["rapidblitz", "blitz", "rapid", "classical"]
ITERS_MAIN = 1000000

# One Model per Armageddon strength; they share fitted params + ratings and
# differ only in the strength used for the Armageddon tiebreak.
M = {m: Model(config=ROOT / f"configs/model_v4_{m}.json") for m in MODELS}
base = M["rapidblitz"]
tour = base.tournament
NAMES = [p["name"] for p in tour["players"]]
name_by_id = base.name_by_id

tl_by_model = {m: json.loads((ROOT / f"out/timeline_{m}.json").read_text()) for m in MODELS}
main_tl = tl_by_model["rapidblitz"]

# Per-game 4-way probabilities, straight from the shared model.
rounds_pred = {}
for m in MODELS:
    rp = []
    for rd in tour["rounds"]:
        games = []
        for g in rd["games"]:
            ng = {"p1": g["p1"], "p2": g["p2"], "color_known": g["color"] == "p1_white"}
            f = M[m].p1_dist(ng)
            games.append({
                "p1": name_by_id[g["p1"]], "p2": name_by_id[g["p2"]], "color": g["color"],
                "probs": [round(x, 4) for x in f], "actual": base.outcome_index(g["result"]),
                "result_type": g["result"]["type"], "p1_points": g["result"]["p1_points"],
            })
        rp.append({"round": rd["round"], "games": games})
    rounds_pred[m] = rp

# Timelines from generated 1M outputs.
timelines = {}
for m in MODELS:
    cps = tl_by_model[m]["checkpoints"]
    timelines[m] = {
        "p_win": [{n: c["p_win"][n] for n in NAMES} for c in cps],
        "e_pts": [{n: c["e_pts"][n] for n in NAMES} for c in cps],
    }

# Contention status by checkpoint.
def games_left(name, after):
    return sum(1 for rd in tour["rounds"] if rd["round"] > after
               for g in rd["games"] if name in (name_by_id[g["p1"]], name_by_id[g["p2"]]))

checkpoints = []
for cp in main_tl["checkpoints"]:
    after = cp["after_round"]
    ap = cp["actual_pts"]
    mx = {n: ap[n] + 3.0 * games_left(n, after) for n in NAMES}
    lead = max(ap.values())
    checkpoints.append({
        "after_round": after,
        "max_reachable": {n: round(mx[n], 1) for n in NAMES},
        "eliminated": {n: (mx[n] < lead) for n in NAMES},
        "p_win": cp["p_win"], "e_pts": cp["e_pts"], "actual_pts": ap,
    })

# Final-place distribution from the generated full simulation.
rankdist = {}
fs = json.loads((ROOT / "out/tournament_sim_v4.json").read_text())
for p in fs["players"]:
    rankdist[p["name"]] = p["rank_dist"]

# Reliability bins and per-round Brier score.
pairs = []
for rd in rounds_pred["rapidblitz"]:
    for g in rd["games"]:
        for i, p in enumerate(g["probs"]):
            pairs.append((p, 1 if g["actual"] == i else 0))
rel = []
nb = 5
for b in range(nb):
    lo, hi = b / nb, (b + 1) / nb
    sel = [(p, y) for p, y in pairs if (lo <= p < hi or (b == nb - 1 and p == 1.0))]
    if sel:
        rel.append({
            "pred": round(sum(p for p, _ in sel) / len(sel), 3),
            "obs": round(sum(y for _, y in sel) / len(sel), 3),
            "n": len(sel),
        })
per_round = []
for rd in rounds_pred["rapidblitz"]:
    br = sum(sum((g["probs"][i] - (1 if i == g["actual"] else 0)) ** 2 for i in range(4)) for g in rd["games"])
    per_round.append(round(br / len(rd["games"]), 4))

# Outcome-call metrics on the displayed (static, rapidblitz) probabilities, so the
# numbers quoted in the README are reproducible from this file and match the cards.
g3_hits = draw_modal = dir_hits = dir_calls = 0
total_games = 0
for rd in rounds_pred["rapidblitz"]:
    for g in rd["games"]:
        total_games += 1
        p = g["probs"]
        three = [p[0], p[1] + p[2], p[3]]            # win / draw / loss
        modal = max(range(3), key=lambda i: three[i])
        actual_cls = 0 if g["actual"] == 0 else (2 if g["actual"] == 3 else 1)
        g3_hits += (modal == actual_cls)
        draw_modal += (modal == 1)
        if actual_cls in (0, 2):                       # decisive game
            dir_calls += 1
            dir_hits += (p[0] > p[3]) if actual_cls == 0 else (p[3] > p[0])

out = {
    "tournament": tour["name"], "models": MODELS,
    "iters_main": ITERS_MAIN,
    "players": [{
        "name": p["name"], "classical": p["classical"], "rapid": p["rapid"],
        "blitz": p["blitz"], "style": p["style"], "rank_dist": rankdist.get(p["name"]),
    } for p in tour["players"]],
    "timelines": timelines,
    "checkpoints": checkpoints, "rounds_pred": rounds_pred,
    "final_standings": {n: main_tl["checkpoints"][-1]["actual_pts"][n] for n in NAMES},
    "metrics": {
        "reliability": rel, "per_round_brier": per_round,
        "mean_brier": round(sum(per_round) / len(per_round), 4), "uniform_brier": 0.75,
        "outcome_call_hits": g3_hits, "outcome_call_games": total_games,
        "draw_was_modal": draw_modal,
        "directional_hits": dir_hits, "directional_games": dir_calls,
    },
}
(ROOT / "out/dashboard_data.json").write_text(json.dumps(out, ensure_ascii=False))
print(f"dashboard_data.json: built from {ITERS_MAIN:,}-iteration generated outputs")
