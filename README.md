# Norway Chess 2026 — Monte Carlo Simulation

A Monte Carlo model for **Norway Chess 2026** and its Armageddon scoring system. It runs
**1,000,000** simulated tournaments, re-forecasts after every round, and grades its own
predictions with proper scoring rules. The 2026 edition produced a near-total rank inversion:
the model's last-place pick (**Praggnanandhaa, 2.4 %**) won; its **56.3 %** favorite
(**Carlsen**) finished 4th.

A classical win scores `3 / 0`. A classical **draw** is resolved by an **Armageddon** tiebreak,
where White must win but Black needs only a draw; the drawn-then-Armageddon outcome scores
`1.5 / 1`. Every game has four possible results, and the model predicts all four.

The repository is self-contained: engine, calibration tooling, five years of historical PGN
data, every generated JSON output, and one static HTML dashboard. It renders on clone and
reproduces from source.

![engine](https://img.shields.io/badge/engine-C%2B%2B17-blue) ![tooling](https://img.shields.io/badge/tooling-Python%203-green) ![runtime%20deps](https://img.shields.io/badge/runtime%20deps-none-brightgreen) ![tests](https://img.shields.io/badge/tests-passing-success)

---

## Table of contents

- [What it does](#what-it-does)
- [Results](#results)
  - [The one-line story](#the-one-line-story)
  - [Forecast vs. reality](#forecast-vs-reality)
  - [How the title race moved](#how-the-title-race-moved)
  - [What the model got right and wrong](#what-the-model-got-right-and-wrong)
  - [Round-by-round commentary](#round-by-round-commentary)
- [How it works](#how-it-works)
- [How to run](#how-to-run)
- [Methodology and parameters](#methodology-and-parameters)
- [Architecture](#architecture)
- [Validation](#validation)
- [Acknowledgements](#acknowledgements)

---

## What it does

The model treats final standings as a random variable and estimates its distribution by
simulation:

1. **Pre-tournament forecast.** From the opening position, runs 1,000,000 simulated
   tournaments; reports per-player win probability, expected final score, and the full
   finishing-place distribution.
2. **Live re-forecast.** Conditions on games already played and simulates only the remainder,
   producing a round-by-round title-probability trajectory.
3. **Per-game prediction.** Emits a four-way probability —
   *P1 wins / P1 wins Armageddon / P2 wins Armageddon / P2 wins* — under any of four Armageddon
   speed-rating assumptions.
4. **Self-grading.** Scores its own forecasts with Brier, Ranked Probability Score, and
   reliability bins.

Output bundles into one static dashboard, openable locally or via GitHub Pages.

---

## Results

Six players, ten rounds, Stavanger, **25 May – 5 June 2026**. The forecast was almost perfectly
rank-inverted against the result.

### The one-line story

> **The model's least likely champion won the tournament.** Praggnanandhaa entered with a
> **2.4 %** title probability — dead last of six — and finished first. Carlsen, the **56.3 %**
> favorite, finished fourth.

### Forecast vs. reality

Pre-tournament win probabilities are from one million simulations at `after_round = 0`.
*Δ is actual minus expected points: positive means the player beat the model's projection.*

| Player              | Elo (classical) | Model win prob.   | Exp. pts | Actual pts | Δ          | Finish |
|---------------------|----------------:|:------------------|---------:|-----------:|:----------:|:------:|
| **Praggnanandhaa**  | 2733            | **2.4 %** (6th)   | 11.0     | **18.0**   | **+7.0** ⬆ | 🥇 1st |
| So                  | 2754            | 6.9 % (5th)       | 13.3     | 17.0       | **+3.7** ⬆ | 🥈 2nd |
| Firouzja            | 2759            | 7.4 % (4th)       | 12.4     | 15.5       | **+3.1** ⬆ | 🥉 3rd |
| **Carlsen**         | 2840            | **56.3 %** (1st)  | 17.7     | 13.0       | **−4.7** ⬇ | 4th    |
| Keymer              | 2765            | 16.6 % (2nd)      | 14.3     | 11.0       | −3.3 ⬇     | 5th    |
| Gukesh              | 2734            | 10.4 % (3rd)      | 12.0     | 8.0        | −4.0 ⬇     | 6th    |

The model's entire top half (Carlsen, Keymer, Gukesh) finished in the bottom half; its entire
bottom half (Firouzja, So, Pragg) finished in the top half. In rank terms the forecast was
almost perfectly inverted.

### How the title race moved

Win probability (%) after each round. **So** became a runaway favorite from R6 and peaked at
**77.5 %** with one round left — and did not win. **Pragg** sat at or near **0 %** as late as
R7 before storming home.

| After  | Carlsen | Keymer | Firouzja |     So     |  Gukesh  |   Pragg   |
|:------:|--------:|-------:|---------:|:----------:|:--------:|:---------:|
| Start  | 56.3    | 16.6   | 7.4      | 6.9        | 10.4     | 2.4       |
| R1     | 32.4    | 14.7   | 28.3     | 6.8        | 13.7     | 4.1       |
| R2     | 21.7    | 12.8   | 50.8     | 3.5        | 10.4     | 0.7       |
| R3     | 7.0     | 11.6   | 61.4     | 6.0        | 8.3      | 5.7       |
| R4     | 17.4    | 6.8    | 60.1     | 5.4        | 3.0      | 7.4       |
| R5     | 2.8     | 3.2    | 57.9     | 27.5       | 7.9      | 0.7       |
| R6     | 5.1     | 5.0    | 24.0     | 64.0       | 2.0      | ~0        |
| R7     | 8.8     | 4.4    | 8.1      | **76.6**   | 1.5      | 0.5       |
| R8     | ~0      | 0.6    | 16.4     | 75.2       | ~0       | 7.8       |
| R9     | ~0      | ~0     | 4.9      | 77.5       | ~0       | **17.6**  |
| Final  | —       | —      | —        | —          | —        | **100** 🥇|

Three players held the model's top win probability at different points (Firouzja → So → Pragg).
Carlsen led only at the start.

### What the model got right and wrong

Across **30** games the four-way forecasts beat the uniform baseline; the title call missed by
about the maximum the field allows.

**Aggregate scorecard**

| Metric                                   |  Value | Baseline / note                 |
|------------------------------------------|-------:|---------------------------------|
| Mean Brier (per game, 4-way)             | 0.7273 | 0.75 uniform — model is sharper |
| Out-of-sample RPS (2026)                 | 0.1902 | from `calibrate.py`             |
| Best-calibrated round (lowest Brier)     | R4: 0.541 | clean read of the round      |
| Worst round (highest Brier)              | R1: 0.879 | opening-round surprises      |
| Modal-outcome hit rate                   | 18/30 = 60 % | which of 4 outcomes was likeliest |
| Directional accuracy on decisive games   | 7/15 = 47 % | when a game was won, was the winner favored |

**Good calls**

- **Calibrated.** Observed frequencies track predictions: 11.2 % → 17.4 %, 28.5 % → 24.1 %,
  47.1 % → 45.0 %. No systematic over- or under-confidence.
- **Beats uniform.** Mean Brier **0.7273** < **0.75** flat-25 % guess, in most rounds.
- **Tracks real leads.** Firouzja's early surge, So's mid-event dominance, and Pragg's late
  climb all appear in the trajectory.

**Poor calls**

- **Under-rates the champion throughout.** In Pragg's three decisive *wins* the model gave
  classical-win probabilities of **2 % (R3 vs. Carlsen)**, **1 % (R8 vs. Carlsen)**, and
  **8 % (R10 vs. Keymer)**. A player can win the event out of results the model treats as
  near-impossible — the central lesson of 2026.
- **Draw model over-fires.** A draw was the single most likely call in **21/30 (70 %)** games;
  draws occurred in **15/30 (50 %)**. The model's top pick was a draw in 8 of the 15 decisive
  games. `draw_probability_cap` keeps elite draw rates plausible on average but blunts
  decisive-game calls.
- **Form update reacts too slowly.** The `form_k` term corrects a stumbling favorite or a
  surging underdog only gradually, so Carlsen's collapse and Pragg's run both lagged reality by
  a round or two.

**Takeaway:** well-calibrated on average and good at ordering outcomes within a game; too
draw-prone and too slow on in-event form. A **2.4 %** event is not a **0 %** event.

### Round-by-round commentary

Full game log with predictions and outcomes. ✓ = the model's most likely call matched the
result class (decisive vs. drawn); ✗ = it did not. Probabilities are `P[win] / P[draw] / P[win]`
under the `rapidblitz` Armageddon variant.

<details>
<summary><b>Round 1</b> — opening surprises, worst round (Brier 0.879)</summary>

- ✗ **Firouzja 1–0 Carlsen** · 0.08 / **0.67** / 0.25 — top seed lost with White to a heavy
  model underdog.
- ✗ **Keymer–Gukesh → Armageddon (Gukesh)** · 0.36 / 0.42 / 0.22 — drawn, taken by Gukesh in the
  tiebreak; model leaned Keymer.
- ✓ **So–Pragg → Armageddon (Pragg)** · 0.12 / **0.84** / 0.05 — draw called correctly; Pragg
  took the Armageddon.

</details>

<details>
<summary><b>Round 2</b> — Firouzja announces himself</summary>

- ✗ **Firouzja 1–0 Pragg** · 0.17 / **0.71** / 0.12 — second straight win lifts Firouzja to
  **50.8 %** by R2.
- ✓ **Carlsen–Keymer → Armageddon (Carlsen)** · 0.32 / 0.63 / 0.05 — drawn, Carlsen edged the
  tiebreak.
- ✓ **Gukesh–So → Armageddon (So)** · 0.17 / 0.56 / 0.26 — drawn; So banked the Armageddon point.

</details>

<details>
<summary><b>Round 3</b> — Pragg shocks Carlsen</summary>

- ✗ **Pragg 1–0 Carlsen** · **0.02** / 0.65 / 0.32 — model gave Pragg **2 %** to win outright;
  he won. Carlsen's title odds **21.7 % → 7.0 %**.
- ✓ **Keymer–So → Armageddon (So)** · 0.17 / **0.82** / 0.01 — draw called correctly.
- ✗ **Gukesh–Firouzja → Armageddon (Firouzja)** · 0.30 / 0.45 / 0.26 — Firouzja now a clear model
  favorite at **61.4 %**.

</details>

<details>
<summary><b>Round 4</b> — cleanest round (Brier 0.541)</summary>

- ✓ **Gukesh 0–1 Carlsen** · 0.17 / 0.43 / **0.40** — a decisive game leaned correctly; Carlsen
  converted with White.
- ✓ **Keymer–Pragg → Armageddon (Pragg)** · 0.29 / 0.65 / 0.05 — drawn, Pragg took the tiebreak.
- ✓ **So–Firouzja → Armageddon (So)** · 0.15 / **0.83** / 0.02 — draw called correctly.

</details>

<details>
<summary><b>Round 5</b> — So wakes up</summary>

- ✗ **Carlsen 0–1 So** · 0.27 / **0.72** / 0.01 — So beat Carlsen from a position the model rated
  **1 %** for him; So's odds jump to **27.5 %**.
- ✗ **Pragg–Gukesh, Gukesh 1–0** · 0.31 / 0.47 / 0.21 — Gukesh's only classical win of the event.
- ✓ **Keymer–Firouzja → Armageddon (Firouzja)** · 0.22 / 0.65 / 0.13 — drawn; Firouzja still
  leads at **57.9 %**.

</details>

<details>
<summary><b>Round 6</b> — three decisive games, the race reshapes</summary>

- ✗ **So 1–0 Pragg** · 0.17 / **0.82** / 0.01 — So overtakes the field; odds leap to **64.0 %**.
- ✓ **Carlsen 1–0 Firouzja** · **0.38** / 0.59 / 0.03 — Carlsen halts Firouzja's run.
- ✓ **Keymer 1–0 Gukesh** · **0.42** / 0.40 / 0.18 — favored side won; Gukesh fades to **2.0 %**.

</details>

<details>
<summary><b>Round 7</b> — So takes command (76.6 %)</summary>

- ✗ **Pragg 1–0 Firouzja** · 0.12 / **0.71** / 0.17 — Pragg stays alive at **0.5 %**.
- ✓ **So–Gukesh → Armageddon (Gukesh)** · 0.26 / 0.56 / 0.17 — drawn.
- ✓ **Keymer–Carlsen → Armageddon (Carlsen)** · 0.10 / **0.71** / 0.18 — drawn; Carlsen now a
  long shot.

</details>

<details>
<summary><b>Round 8</b> — Pragg topples Carlsen again</summary>

- ✗ **Carlsen 0–1 Pragg** · **0.39** / 0.60 / **0.01** — model gave Pragg **1 %** to win; he won,
  igniting his charge (odds up to **7.8 %**).
- ✓ **Firouzja 1–0 Gukesh** · **0.31** / 0.43 / 0.26 — Firouzja stays in the hunt.
- ✓ **So–Keymer → Armageddon (So)** · 0.05 / **0.84** / 0.11 — drawn; So commands at **75.2 %**.

</details>

<details>
<summary><b>Round 9</b> — Pragg surges, So still favored</summary>

- ✓ **So–Carlsen → Armageddon (So)** · 0.01 / **0.85** / 0.14 — drawn; So holds top odds at
  **77.5 %**.
- ✗ **Gukesh 0–1 Pragg** · 0.21 / 0.47 / **0.31** — Pragg's fourth win climbs him to **17.6 %**.
- ✓ **Keymer–Firouzja → Armageddon (Firouzja)** · 0.29 / 0.61 / 0.10 — drawn.

</details>

<details>
<summary><b>Round 10</b> — Pragg wins the title</summary>

- ✗ **Pragg 1–0 Keymer** · 0.08 / **0.70** / 0.22 — the decisive final-round win that sealed the
  title, from a game the model rated **8 %** for Pragg.
- ✓ **Carlsen 1–0 Gukesh** · **0.46** / 0.40 / 0.14 — consolation win for the pre-tournament
  favorite.
- ✓ **Firouzja–So → Armageddon (So)** · 0.07 / **0.84** / 0.09 — drawn; So finishes clear second.

**Final: Praggnanandhaa 18.0, So 17.0, Firouzja 15.5, Carlsen 13.0, Keymer 11.0, Gukesh 8.0.**

</details>

---

## How it works

**Short version.** Each player carries an effective rating: classical level plus a small live
adjustment and a monthly trend. Before each simulated game that rating — adjusted for White,
drawing style, and the four-way Armageddon structure — becomes win/draw/loss probabilities. A
result is sampled, ratings are nudged toward whoever over- or under-performed, and the next game
is played. One tournament is 30 such games; run it a million times, and a player's share of
tournaments won is their title probability.

**Per-game inputs:**

- **Effective rating** = `classical + live_adj + 2·trend_mo`, so a rising player enters slightly
  stronger than their static rating.
- **White advantage** — a flat Elo bonus to whoever holds White.
- **Style multiplier** — per player, widens or narrows the drawing band: decisive players (low
  style) produce more wins, solid players (high style) more draws.
- **Four-way outcome** — classical win, draw-then-Armageddon won by either side, classical loss;
  the Armageddon resolved from a chosen *speed* rating, not the classical one.
- **Form update** — after every game, feeds streaks forward into later rounds.
- **Reproducible RNG** — seeded from the command line.

The C++ engine holds only this logic; everything situational lives in JSON and is streamed in.

---

## How to run

**Requirements:** a C++17 compiler and Python 3. No third-party Python packages; standard
library only.

```bash
# 1. Build and test
g++ -O2 -std=c++17 src/sim.cpp -o sim
python3 tools/run_tests.py            # ends with "ALL TESTS PASS"

# 2. Pre-tournament forecast — 1,000,000 iterations, after_round = 0
python3 tools/make_sim_input.py data/tournaments/norway2026.json configs/model_v4.json \
  | ./sim full 1000000 20260525 0 > out/tournament_sim_v4.json

# 3. Round-by-round title-race trajectory
python3 tools/make_sim_input.py data/tournaments/norway2026.json configs/model_v4.json \
  | ./sim timeline 1000000 20260525 > out/timeline_rapidblitz.json

# 4. Rebuild dashboard data + the single static HTML file
python3 tools/build_dashboard_data.py
python3 tools/viz/generate_html.py \
  --data    out/dashboard_data.json \
  --calib   out/calibrated_params.json \
  --names   tools/viz/names_norway2026.json \
  --venue   "Stavanger · Norway" \
  --dates   "25 May – 5 June 2026" \
  --edition "Vol. XIV · Monte Carlo Edition" \
  --output  dashboards/norway2026_dashboard.html
```

`sim` takes `MODE ITERATIONS SEED [AFTER_ROUND]`. `full` reports final win probabilities and
rank distributions; `timeline` reports the after-each-round trajectory. The seed makes every run
bit-for-bit reproducible.

To re-derive the calibrated parameters from the historical record:

```bash
python3 tools/build_dataset.py        # parse 2022–2026 Norway Chess PGNs → data/history.json
python3 tools/calibrate.py            # writes out/calibrated_params.json
```

---

## Methodology and parameters

The forecast (model **v4**) has four components.

**1. Classical outcome.** Win/draw/loss probabilities derive from the Elo expected score, with a
White-advantage term `WA` added to whoever has White.

**2. Draw probability.** Draws follow

```text
P(draw) = DBASE · exp(−|Δrating| · DDEC) · style_i · style_j
```

capped at `draw_probability_cap`. A larger rating gap lowers the draw rate; each player's `style`
multiplier scales it (Gukesh 0.66 is comparatively decisive, So 1.30 more draw-prone).

**3. Armageddon tiebreak.** When a classical game is drawn, the Armageddon is resolved from a
*speed* rating chosen by `armageddon_strength` — `classical`, `rapid`, `blitz`, or combined
`rapidblitz`. Black's draw-odds advantage is encoded as a White-side handicap `ARM_H` (a negative
Elo penalty on White).

**4. Form update.** After each classical game, a player's effective rating is updated by
`form_k · (score − expected_score)`, carrying hot and cold streaks forward.

Unknown colors are simulated as a 50/50 mixture; ties for first are resolved by a blitz-strength
playoff approximation; every single-game outcome is floored at `min_outcome_probability`, so
nothing is treated as strictly impossible.

### Calibrated parameters (`out/calibrated_params.json`)

| Parameter            | Symbol   | Value       | What it means                                       |
|----------------------|----------|-------------|-----------------------------------------------------|
| White advantage      | `WA`     | **35 Elo**  | Edge for holding the white pieces                   |
| Draw base            | `DBASE`  | **0.70**    | Baseline classical draw rate between equals         |
| Draw decay           | `DDEC`   | **0.0018**  | How fast draws fall off as the rating gap grows     |
| Armageddon handicap  | `ARM_H`  | **−30 Elo** | White's Armageddon penalty (Black holds draw odds)  |
| Form K               | `form_k` | **32**      | Strength of the per-game rating update              |
| Draw cap             | —        | **0.85**    | Ceiling on any classical draw probability           |
| Min outcome prob     | —        | **0.01**    | Floor on any single-game outcome                    |
| Regularization       | `λ`      | **0.10**    | MAP pull toward physically plausible priors         |

**Calibration.** Parameters are fit on Norway Chess games from **2022–2026**. The objective is
**Ranked Probability Score** — which respects the ordinal nature of win / draw-with-Armageddon /
loss — not raw log-loss. A **MAP regularization** term pulls estimates toward plausible priors;
its strength is chosen by **leave-one-tournament-out cross-validation**. The fit scored an
out-of-sample **RPS of 0.1902** on the 2026 edition.

### Armageddon-variant sensitivity

The Armageddon can resolve from any of four speed-rating assumptions. The headline barely moves —
the upset is not an artifact of one tiebreak setting:

| Variant      | Carlsen win prob. | Pragg win prob. |
|--------------|------------------:|----------------:|
| classical    | 52.5 %            | 2.6 %           |
| rapid        | 56.1 %            | 2.4 %           |
| blitz        | 56.5 %            | 2.5 %           |
| rapidblitz   | 56.2 %            | 2.5 %           |

---

## Architecture

```text
data/tournaments/norway2026.json      players, ratings, schedule, actual results
configs/model_v4*.json                model parameters + Armageddon-rating variant
data/formats/norway_chess.json        scoring rules
data/raw/*.pgn                        Norway Chess broadcasts, 2022–2026
out/*.json                            generated simulation + dashboard data
dashboards/norway2026_dashboard.html  generated, self-contained dashboard
```

```text
src/
  model.hpp          probability model: Elo, draw band, Armageddon probability
  sim.cpp            data-driven tournament simulator
  test_model.cpp     unit tests for the probability model
  eval_oos.py        out-of-sample scoring report
  eval_v4.py         prequential form-update evaluation
  eval_rounds.py     round-by-round prediction report

tools/
  make_sim_input.py        JSON → flat C++ input bridge
  build_dataset.py         historical PGN parser → data/history.json
  calibrate.py             RPS + MAP parameter calibration
  build_dashboard_data.py  combines generated JSON outputs for the dashboard
  run_tests.py             project smoke / unit tests
  viz/                     self-contained HTML dashboard generator
```

`bin/` holds no source. It is reserved for compiled binaries such as `bin/test_model`, which the
test runner builds locally and `.gitignore` excludes — as are the top-level `sim` binary and
Python caches.

### Generated outputs (committed on purpose)

The dashboard is part of the deliverable, so its inputs stay in the repo:

```text
out/tournament_sim_v4.json   out/timeline_*.json
out/variant_*.json           out/variants_combined.json
out/dashboard_data.json      dashboards/norway2026_dashboard.html
```

The dashboard is a single static HTML file — open it directly or serve it via GitHub Pages. Its
palette (light glacier-gray background, Norway red and navy accents) is generated from the CSS
variables in `tools/viz/viz.css`, so regenerating the HTML keeps the look consistent.

---

## Validation

```bash
python3 tools/run_tests.py
```

Checks model invariants, scoring rules, tournament-data consistency, no-look-ahead leakage, and
dashboard-data integrity. A clean run ends with `ALL TESTS PASS`.

---

## Acknowledgements

Modeling an elite chess event as a Monte Carlo object — originally for the Candidates Tournament
— comes from **[vltanh](https://github.com/vltanh)**. This project adapts it to Norway Chess and
its Armageddon format with its own engine, calibration, and dashboard.
