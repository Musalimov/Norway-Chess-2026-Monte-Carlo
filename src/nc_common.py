#!/usr/bin/env python3
"""Single source of truth for the Norway Chess probability model in Python.

Every evaluation script (eval_oos / eval_v4 / eval_rounds) and the dashboard
builder must describe *exactly the same model the C++ engine simulates*.
Historically each script hard-coded its own parameters and read a separate,
drifted copy of the data (data/dataset_full.json), so the out-of-sample
numbers no longer matched the deployed configs/model_v4.json. This module
removes that drift:

  * fitted parameters (WA, DBASE, DDEC, ARM_H)  -> out/calibrated_params.json
  * structural parameters (armageddon strength, caps, form_k) -> configs/model_v4.json
  * players + actual results                    -> data/tournaments/norway2026.json

The analytic game distribution here is byte-for-byte the same formula as
src/model.hpp / tools/build_dashboard_data.py, so a game-level evaluation and
the dashboard can never disagree about what "the model" is again.

Standard library only.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_jsonc(path: Path) -> dict:
    """Load JSON or JSONC (strip // line comments)."""
    return json.loads(re.sub(r"//[^\n]*", "", path.read_text(encoding="utf-8")))


# ── Model parameters ──────────────────────────────────────────────────────────


class Model:
    """The deployed model: fitted params + structural params + per-player ratings."""

    def __init__(
        self,
        tournament: Path = ROOT / "data/tournaments/norway2026.json",
        calib: Path = ROOT / "out/calibrated_params.json",
        config: Path = ROOT / "configs/model_v4.json",
    ):
        cfg = _load_jsonc(config)

        # Fitted parameters come from the calibration output when present;
        # otherwise fall back to the config. The config is allowed to carry the
        # same fitted values for the C++ side, but calibrated_params.json wins.
        if calib.exists():
            c = _load_jsonc(calib)
            self.WA = float(c["WA"])
            self.DBASE = float(c["DBASE"])
            self.DDEC = float(c["DDEC"])
            self.ARM_H = float(c["ARM_H"])
            self.STRENGTH_SIGMA = float(c.get("SIGMA", 0.0))
            self.CC = float(c.get("CC", 0.0))
            self._fitted_source = str(calib.relative_to(ROOT))
            self._warn_if_config_drift(cfg)
        elif all(k in cfg for k in ("white_advantage", "draw_base", "draw_decay", "armageddon_handicap")):
            # Legacy fallback only: a config that still embeds the fitted values.
            self.WA = float(cfg["white_advantage"])
            self.DBASE = float(cfg["draw_base"])
            self.DDEC = float(cfg["draw_decay"])
            self.ARM_H = float(cfg["armageddon_handicap"])
            self.STRENGTH_SIGMA = float(cfg.get("strength_sigma", 0.0))
            self.CC = 0.0
            self._fitted_source = str(config.relative_to(ROOT)) + " (legacy: no calibration file)"
        else:
            raise FileNotFoundError(
                f"Fitted parameters not found. Expected {calib} (run tools/calibrate.py "
                "to produce it). Configs no longer carry the fitted values by design."
            )

        # Structural parameters always come from the config.
        self.DCAP = float(cfg["draw_probability_cap"])
        self.MINP = float(cfg["min_outcome_probability"])
        self.FORM_K = float(cfg["form_k"])
        self.STRENGTH = cfg["armageddon_strength"]
        # STRENGTH_SIGMA (whole-event form variance, Elo) is a fitted parameter,
        # set above from the calibration file. 0 reproduces point-rating behaviour.

        self.tournament = _load_jsonc(tournament)
        self.name = self.tournament.get("name", "Tournament")
        self.players = {p["id"]: p for p in self.tournament["players"]}
        self.name_by_id = {p["id"]: p["name"] for p in self.tournament["players"]}
        self.order = [p["id"] for p in self.tournament["players"]]

    def _warn_if_config_drift(self, cfg: dict) -> None:
        pairs = [
            ("white_advantage", self.WA),
            ("draw_base", self.DBASE),
            ("draw_decay", self.DDEC),
            ("armageddon_handicap", self.ARM_H),
        ]
        drift = [
            (k, cfg.get(k), v)
            for k, v in pairs
            if cfg.get(k) is not None and abs(float(cfg[k]) - v) > 1e-9
        ]
        if drift:
            msg = ", ".join(f"{k}: config={c} vs calibrated={v}" for k, c, v in drift)
            print(
                f"[nc_common] WARNING: configs/model_v4.json disagrees with "
                f"out/calibrated_params.json ({msg}). Using the calibrated values; "
                f"re-run tools/calibrate.py and sync the config to silence this.",
                file=sys.stderr,
            )

    # ── per-player derived quantities ──────────────────────────────────────────

    def _field_mean_speed_gap(self) -> float:
        gaps = [0.5 * ((p["rapid"] - p["classical"]) + (p["blitz"] - p["classical"]))
                for p in self.players.values()]
        return sum(gaps) / len(gaps)

    def eff0(self, pid: str) -> float:
        """Pre-tournament effective Elo: classical + live adjustment + 2-month trend,
        plus an optional speed cross-control term.

        Cross-control (experimental, CC=0 by default): a player whose rapid/blitz
        strength is high *relative to the field* may be in sharper current form,
        so a fraction CC of their field-centred speed-minus-classical gap is added.
        Folded into eff0 so the engine and dashboard pick it up with no further
        change. CC lives in out/calibrated_params.json and defaults to 0 because
        it cannot yet be validated out-of-sample (see README: history.json has no
        historical rapid/blitz ratings)."""
        p = self.players[pid]
        base = p["classical"] + p["live_adj"] + 2.0 * p["trend_mo"]
        if self.CC != 0.0:
            gap = 0.5 * ((p["rapid"] - p["classical"]) + (p["blitz"] - p["classical"]))
            base += self.CC * (gap - self._field_mean_speed_gap())
        return base

    def arm_strength(self, pid: str) -> float:
        p = self.players[pid]
        s = self.STRENGTH
        if s == "blitz":
            return p["blitz"]
        if s == "rapid":
            return p["rapid"]
        if s == "classical":
            return p["classical"]
        return (p["rapid"] + p["blitz"]) / 2.0  # rapidblitz

    # ── feed for the C++ engine ─────────────────────────────────────────────────

    def params_line(self) -> str:
        """The PARAMS header the C++ simulator reads from stdin.

        Same single source as the Python model, so make_sim_input.py can never
        feed the engine different numbers than src/eval_*.py evaluate.
        """
        return (
            f"PARAMS {self.WA} {self.DBASE} {self.DDEC} {self.ARM_H} "
            f"{self.FORM_K} {self.DCAP} {self.MINP} {self.STRENGTH_SIGMA}"
        )

    @staticmethod
    def outcome_index(result: dict) -> int:
        """4-way outcome index from p1's perspective for an actual result.

        0 = p1 classical win, 1 = draw + p1 wins Armageddon,
        2 = draw + p2 wins Armageddon, 3 = p2 classical win.
        """
        pts = result["p1_points"]
        if result["type"] == "classical":
            return 0 if pts == 3.0 else 3
        return 1 if pts == 1.5 else 2

    # ── analytic outcome distribution (mirrors src/model.hpp) ───────────────────

    @staticmethod
    def expect(diff: float) -> float:
        return 1.0 / (1.0 + 10.0 ** (-diff / 400.0))

    # 7-point Gauss-Hermite nodes/weights for marginalising over strength noise.
    _GH_X = (0.0, 0.8162878828589647, -0.8162878828589647,
             1.6735516287674714, -1.6735516287674714,
             2.651961356835233, -2.651961356835233)
    _GH_W = (0.8102646175568073, 0.4256072526101278, 0.4256072526101278,
             0.05451558281912703, 0.05451558281912703,
             0.0009717812450995192, 0.0009717812450995192)
    _SQRT_PI = math.sqrt(math.pi)

    def _core(self, diff: float, sw: float, sb: float, parm: float) -> list[float]:
        e = self.expect(diff)
        pd = min(self.DBASE * math.exp(-abs(diff) * self.DDEC) * sw * sb, self.DCAP)
        pw = max(e - pd / 2.0, self.MINP)
        pb = max(1.0 - pw - pd, self.MINP)
        pd = 1.0 - pw - pb
        return [pw, pd * parm, pd * (1.0 - parm), pb]

    def game4(self, white: str, black: str, eff: dict | None = None) -> list[float]:
        """4-way distribution from White's perspective: [3, 1.5, 1, 0] points.

        1.5 = classical draw, White wins the Armageddon; 1 = draw, Black wins it.
        If `eff` is given it overrides the pre-tournament ratings (used for the
        prequential form-update evaluations). When STRENGTH_SIGMA > 0 the
        per-game distribution is marginalised over independent N(0, sigma)
        strength draws for each player (difference noise N(0, sigma*sqrt2)),
        matching what the C++ engine samples per simulated tournament.
        """
        ew = eff[white] if eff else self.eff0(white)
        eb = eff[black] if eff else self.eff0(black)
        sw, sb = self.players[white]["style"], self.players[black]["style"]
        diff0 = ew - eb + self.WA
        parm = self.expect(self.arm_strength(white) - self.arm_strength(black) - self.ARM_H)
        if self.STRENGTH_SIGMA <= 0.0:
            return self._core(diff0, sw, sb, parm)
        tau = self.STRENGTH_SIGMA * math.sqrt(2.0)        # std of the difference noise
        acc = [0.0, 0.0, 0.0, 0.0]
        for x, w in zip(self._GH_X, self._GH_W):
            v = self._core(diff0 + math.sqrt(2.0) * tau * x, sw, sb, parm)
            for i in range(4):
                acc[i] += w * v[i]
        return [a / self._SQRT_PI for a in acc]

    # ── feed for the C++ engine (single source for make_sim_input) ──────────────

    def sim_input(self) -> str:
        """The full whitespace stream the C++ simulator reads from stdin."""
        players = self.tournament["players"]
        idx = {p["id"]: i for i, p in enumerate(players)}
        out = [self.params_line(), f"PLAYERS {len(players)}"]
        for p in players:
            out.append(f"{self.eff0(p['id'])} {self.arm_strength(p['id'])} {p['style']} {p['name']}")
        rounds = self.tournament["rounds"]
        out.append(f"ROUNDS {len(rounds)}")
        for rd in rounds:
            out.append(f"GAMES {len(rd['games'])}")
            for g in rd["games"]:
                color_known = 1 if g["color"] == "p1_white" else 0
                out.append(f"{idx[g['p1']]} {idx[g['p2']]} {color_known} {self.outcome_index(g['result'])}")
        return "\n".join(out) + "\n"

    def p1_dist(self, g: dict, eff: dict | None = None) -> list[float]:
        """4-way distribution from p1's perspective, normalised to sum 1.

        Unknown colour -> equal mixture over both colour assignments.
        """
        a = self.game4(g["p1"], g["p2"], eff)
        if g["color_known"]:
            f = a
        else:
            bb = self.game4(g["p2"], g["p1"], eff)
            b = [bb[3], bb[2], bb[1], bb[0]]  # reorder to p1 perspective
            f = [(x + y) / 2.0 for x, y in zip(a, b)]
        s = sum(f)
        return [x / s for x in f]

    # ── actual results, normalised ─────────────────────────────────────────────

    def games(self) -> list[dict]:
        """Flatten the schedule into normalised game dicts.

        Each dict: p1, p2 (ids), color_known (bool), res (p1 points 3/1.5/1/0),
        outcome (index 0..3), how ("classical"/"armageddon"), round (int).
        """
        out = []
        for rd in self.tournament["rounds"]:
            for g in rd["games"]:
                pts = g["result"]["p1_points"]
                out.append(
                    {
                        "p1": g["p1"],
                        "p2": g["p2"],
                        "color_known": g["color"] == "p1_white",
                        "res": pts,
                        "outcome": self.outcome_index(g["result"]),
                        "how": g["result"]["type"],
                        "round": rd["round"],
                    }
                )
        return out

    def rounds(self) -> list[list[dict]]:
        """Same games, grouped per round, in schedule order."""
        all_games = self.games()
        by_round: dict[int, list[dict]] = {}
        for g in all_games:
            by_round.setdefault(g["round"], []).append(g)
        return [by_round[r] for r in sorted(by_round)]


# ── shared scoring helpers ──────────────────────────────────────────────────────

# Sw used for the Elo form update: classical win 1, any draw 0.5, loss 0.
S_OF = {3.0: 1.0, 1.5: 0.5, 1.0: 0.5, 0.0: 0.0}


def metrics(p: list[float], k: int) -> tuple[float, float, float]:
    """(log-loss in bits, Brier over 4 outcomes, RPS over 3 ordered thresholds)."""
    ll = -math.log2(max(p[k], 1e-12))
    br = sum((p[i] - (1.0 if i == k else 0.0)) ** 2 for i in range(4))
    cp = co = rps = 0.0
    for i in range(3):
        cp += p[i]
        co += 1.0 if i == k else 0.0
        rps += (cp - co) ** 2
    return ll, br, rps / 3.0


def expected_score(m: Model, g: dict, eff: dict) -> float:
    """Colour-aware Elo expectation for p1 (used by the form update)."""
    a, b = g["p1"], g["p2"]
    if g["color_known"]:
        return m.expect(eff[a] - eff[b] + m.WA)
    return 0.5 * (
        m.expect(eff[a] - eff[b] + m.WA) + m.expect(eff[a] - eff[b] - m.WA)
    )


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


# ── shared classical win/draw/loss core (used by the multi-year backtest) ───────

_GH_X = (0.0, 0.8162878828589647, -0.8162878828589647,
         1.6735516287674714, -1.6735516287674714,
         2.651961356835233, -2.651961356835233)
_GH_W = (0.8102646175568073, 0.4256072526101278, 0.4256072526101278,
         0.05451558281912703, 0.05451558281912703,
         0.0009717812450995192, 0.0009717812450995192)
_SQRT_PI = math.sqrt(math.pi)


def classical_wdl(diff: float, db: float, dd: float,
                  dcap: float = 0.85, minp: float = 0.01,
                  sigma: float = 0.0) -> tuple[float, float, float]:
    """Classical (win, draw, loss) for an Elo gap `diff` already including White's
    edge, style folded into 1. Same formula as Model._core (minus the Armageddon
    split), marginalised over N(0, sigma*sqrt2) difference noise when sigma > 0.
    Single source for the rating-only backtest so it cannot drift from the
    deployed model."""
    def core(d):
        pd = min(db * math.exp(-abs(d) * dd), dcap)
        e = 1.0 / (1.0 + 10.0 ** (-d / 400.0))
        pw = max(e - pd / 2.0, minp)
        pb = max(1.0 - pw - pd, minp)
        return pw, 1.0 - pw - pb, pb
    if sigma <= 0.0:
        return core(diff)
    tau = sigma * math.sqrt(2.0)
    acc = [0.0, 0.0, 0.0]
    for x, w in zip(_GH_X, _GH_W):
        v = core(diff + math.sqrt(2.0) * tau * x)
        for i in range(3):
            acc[i] += w * v[i]
    return tuple(a / _SQRT_PI for a in acc)
