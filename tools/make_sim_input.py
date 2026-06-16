#!/usr/bin/env python3
"""Convert tournament JSON + model config into the flat input format for C++.

This keeps the C++ engine dependency-free: data and parameters stay in JSON,
while the simulator reads a simple whitespace-separated stdin stream.

Usage:

  python3 tools/make_sim_input.py data/tournaments/norway2026.json \
      configs/model_v4.json | ./sim <mode> <iters> <seed> <after_round>
"""
import json
import sys

def main():
    tour = json.load(open(sys.argv[1]))
    cfg = json.load(open(sys.argv[2]))

    players = tour["players"]
    idx = {p["id"]: i for i, p in enumerate(players)}
    n = len(players)

    strength = cfg["armageddon_strength"]
    def arm(p):
        if strength == "blitz":     return p["blitz"]
        if strength == "rapid":     return p["rapid"]
        if strength == "classical": return p["classical"]
        return (p["rapid"] + p["blitz"]) / 2.0   # rapidblitz

    out = []
    # Header: model parameters.
    out.append(f"PARAMS {cfg['white_advantage']} {cfg['draw_base']} "
               f"{cfg['draw_decay']} {cfg['armageddon_handicap']} {cfg['form_k']} "
               f"{cfg['draw_probability_cap']} {cfg['min_outcome_probability']}")
    # Players: n, then one line per player: eff0 arm_strength style name.
    out.append(f"PLAYERS {n}")
    for p in players:
        eff0 = p["classical"] + p["live_adj"] + 2.0 * p["trend_mo"]
        out.append(f"{eff0} {arm(p)} {p['style']} {p['name']}")
    # Rounds: R, then per round: G games, each as p1 p2 color_known actual_outcome.
    rounds = tour["rounds"]
    out.append(f"ROUNDS {len(rounds)}")
    for rd in rounds:
        out.append(f"GAMES {len(rd['games'])}")
        for g in rd["games"]:
            color_known = 1 if g["color"] == "p1_white" else 0
            # Actual outcome index from p1 perspective:
            # 0 = p1 classical win, 1 = draw + p1 wins Armageddon,
            # 2 = draw + p2 wins Armageddon, 3 = p2 classical win.
            r = g["result"]; pts = r["p1_points"]
            if r["type"] == "classical":
                oc = 0 if pts == 3.0 else 3
            else:
                oc = 1 if pts == 1.5 else 2
            out.append(f"{idx[g['p1']]} {idx[g['p2']]} {color_known} {oc}")
    sys.stdout.write("\n".join(out) + "\n")

if __name__ == "__main__":
    main()
