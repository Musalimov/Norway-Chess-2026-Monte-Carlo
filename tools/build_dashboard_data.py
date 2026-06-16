#!/usr/bin/env python3
"""Build dashboard_data.json from already generated simulation outputs.

The heavy 1,000,000-iteration simulation outputs are expected to already exist
in out/timeline_*.json and out/tournament_sim_v4.json. This script combines
those outputs with tournament metadata, analytic per-game probabilities, final
place distributions, reliability bins, and per-round Brier scores.
"""
import json, math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
tour = json.loads((ROOT / "data/tournaments/norway2026.json").read_text())
NAMES = [p["name"] for p in tour["players"]]
name_by_id = {p["id"]: p["name"] for p in tour["players"]}
pdict = {p["id"]: p for p in tour["players"]}
MODELS = ["rapidblitz", "blitz", "rapid", "classical"]

ITERS_MAIN = 1000000

# Load generated 1M timelines for each Armageddon-strength model.
tl_by_model = {m: json.loads((ROOT / f"out/timeline_{m}.json").read_text()) for m in MODELS}
main_tl = tl_by_model["rapidblitz"]

# Per-game 4-way probabilities, using the same formulas as the C++ model.
cfg = json.loads((ROOT / "configs/model_v4.json").read_text())
WA, DB, DD, ARMH = cfg["white_advantage"], cfg["draw_base"], cfg["draw_decay"], cfg["armageddon_handicap"]
DCAP, MINP = cfg["draw_probability_cap"], cfg["min_outcome_probability"]

def expect(d): return 1 / (1 + 10 ** (-d / 400))
def eff0(p): return p["classical"] + p["live_adj"] + 2 * p["trend_mo"]
def arm_r(p, s): return {"blitz": p["blitz"], "rapid": p["rapid"], "classical": p["classical"]}.get(s, (p["rapid"] + p["blitz"]) / 2)
def game4(wid, bid, s):
    w, b = pdict[wid], pdict[bid]
    diff = eff0(w) - eff0(b) + WA
    e = expect(diff)
    pd = min(DB * math.exp(-abs(diff) * DD) * w["style"] * b["style"], DCAP)
    pw = max(e - pd / 2, MINP)
    pb = max(1 - pw - pd, MINP)
    pd = 1 - pw - pb
    parm = expect(arm_r(w, s) - arm_r(b, s) - ARMH)
    return pw, pd * parm, pd * (1 - parm), pb

COLOR_KNOWN = {"p1_white": True, "unknown": False}
def actual4(g):
    r = g["result"]
    pts = r["p1_points"]
    if r["type"] == "classical":
        return 0 if pts == 3.0 else 3
    return 1 if pts == 1.5 else 2

rounds_pred = {}
for m in MODELS:
    rp = []
    for rd in tour["rounds"]:
        games = []
        for g in rd["games"]:
            p1, p2 = g["p1"], g["p2"]
            if COLOR_KNOWN[g["color"]]:
                f = game4(p1, p2, m)
            else:
                a = game4(p1, p2, m)
                bb = game4(p2, p1, m)
                f = [(a[0] + bb[3]) / 2, (a[1] + bb[2]) / 2, (a[2] + bb[1]) / 2, (a[3] + bb[0]) / 2]
            s = sum(f)
            f = [x / s for x in f]
            games.append({
                "p1": name_by_id[p1], "p2": name_by_id[p2], "color": g["color"],
                "probs": [round(x, 4) for x in f], "actual": actual4(g),
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
    },
}
(ROOT / "out/dashboard_data.json").write_text(json.dumps(out, ensure_ascii=False))
print(f"dashboard_data.json: built from {ITERS_MAIN:,}-iteration generated outputs")
