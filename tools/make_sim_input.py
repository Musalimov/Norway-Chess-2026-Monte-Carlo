#!/usr/bin/env python3
"""Convert tournament JSON + model config into the flat input format for C++.

Thin wrapper around src/nc_common.py: the parameters, effective ratings,
Armageddon strengths and the exact stdin format all come from the single
shared model, so the simulated model can never drift from the evaluated one.

Usage:

  python3 tools/make_sim_input.py data/tournaments/norway2026.json \
      configs/model_v4.json | ./sim <mode> <iters> <seed> <after_round>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from nc_common import Model  # noqa: E402


def main():
    M = Model(tournament=Path(sys.argv[1]), config=Path(sys.argv[2]))
    sys.stdout.write(M.sim_input())


if __name__ == "__main__":
    main()
