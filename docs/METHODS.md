# Methods & Parameters

A complete reference for every method and parameter in the model: what it is, how
it is computed, and why it exists. The pipeline runs from a player's effective
rating → a single game's outcome probabilities → a simulated tournament → how the
parameters are chosen → how everything is scored.

All fitted parameters live in one place, `out/calibrated_params.json`, and are
read by both the C++ engine and the Python evaluation through `src/nc_common.py`,
so the simulated model and the evaluated model cannot drift apart.

---

## 1. Effective rating (model input)

```
eff0 = classical + live_adj + 2·trend_mo  [ + CC·(speed_gap − field_mean) ]
```

| Term | Meaning | Why |
| --- | --- | --- |
| `classical` | FIDE standard rating at event time (from the broadcast PGNs) | base strength |
| `live_adj` | manual live-rating adjustment | results not yet in the official list |
| `trend_mo` | monthly rating trend, applied ×2 (~2-month look-ahead) | who is rising/falling |
| `CC·(gap − mean)` | optional speed cross-control, **CC = 0** (rejected) | not in the deployed model |

The absolute level of `eff0` is irrelevant; only the *difference* between two
players enters a game.

---

## 2. Single-game probability model (the core)

For White `W` vs Black `B`, compute the rating difference and then three
outcomes:

```
Δ  = effW − effB + WA
E  = 1 / (1 + 10^(−Δ/400))                      # Elo expected score = pw + ½·pd
pd = min(DBASE · exp(−|Δ|·DDEC) · styleW · styleB, DCAP)
pw = max(E − pd/2, MINP)
pb = max(1 − pw − pd, MINP)
pd = 1 − pw − pb                                # renormalise
```

**Why this construction.** `E` is the Elo-implied expected score, i.e.
`win + ½·draw`. We carve out the draw mass `pd` and split the remainder so the
mean score stays `E` — hence `pw = E − pd/2`. The floor/cap keep every outcome
strictly inside (0, 1).

| Parameter | Value | What / why |
| --- | --- | --- |
| `WA` (white_advantage) | **35** | White's first-move edge (Elo), added to Δ |
| `DBASE` (draw_base) | **0.75** | baseline draw probability between equals; elite chess is draw-heavy |
| `DDEC` (draw_decay) | **0.0018** | how fast draws fall off as the gap grows: `exp(−|Δ|·DDEC)` |
| `DCAP` (draw_probability_cap) | **0.85** | hard ceiling on `pd`; stops degenerate ~1.0 draw odds for near-equals |
| `MINP` (min_outcome_probability) | **0.01** | floor on win/loss; no zero-probability outcomes (upsets happen; keeps log-loss/RPS finite) |
| `style` | per-player | draw-tendency multiplier = player's historical draw share ÷ field average (≥10 games); some play sharper |

---

## 3. Norway Chess scoring & the Armageddon

Norway Chess: classical win = **3**; a drawn classical goes to an Armageddon
tiebreak, whose winner gets **1.5** and loser **1**; classical loss = **0**. This
rewards decisive classical play, and the model encodes it directly (the
reference model it was inspired by does not).

So each game has four outcomes `[3, 1.5, 1, 0]`. With `p_arm` the probability
White wins the Armageddon:

```
p_arm = E(armW − armB − ARM_H)
game4 = [ pw, pd·p_arm, pd·(1 − p_arm), pb ]
```

| Parameter | Value | What / why |
| --- | --- | --- |
| `ARM_H` (armageddon_handicap) | **−30** | enters as `armW − armB − ARM_H`; with ARM_H = −30 White gets a net **+30 Elo** in the Armageddon expectation, fit to the observed ~56% White Armageddon score (54/96 historically) |
| `armageddon_strength` | **"rapidblitz"** | which rating drives `armW/armB`: classical / rapid / blitz / rapid-blitz average |

---

## 4. In-event form (momentum)

After each simulated game, the player's rating updates by the Elo rule:

```
eff += FORM_K · (S − E)        # S = actual score, E = expected
```

| Parameter | Value | What / why |
| --- | --- | --- |
| `FORM_K` (form_k) | **32** | standard Elo K; models hot/cold streaks within an event. LOYO showed the gain is small but it does no harm, so it stays at the textbook value (structural, not calibrated). |

---

## 5. Strength sampling (the main v4→v5 upgrade)

At the start of each simulated tournament, each player's strength for that
event is drawn **once**:

```
eff = eff0 + N(0, SIGMA)        # one draw per player per simulated tournament
```

| Parameter | Value | What / why |
| --- | --- | --- |
| `SIGMA` | **60** (Elo) | whole-event form variance. Chosen by cross-validation on 2022–2025 (clear minimum at 60), and close to the empirical ~50 Elo standard error of a single-event performance. |

**Why.** Point ratings made the model overconfident (favourite 57%, eventual
champion 2.5%). Sampling strength once per event widens the distribution
(→ 47% / 4.6%) and improves calibration at both game and tournament level. It is
a *tail-risk hedge*, not a free lunch (see the multi-year backtest): it helps in
upset years and costs a little in chalk years.

The C++ engine implements this by sampling per iteration. The analytic per-game
model in `nc_common.game4` reproduces the same marginal by integrating over the
sampling distribution with **Gauss–Hermite quadrature** (next section). A unit
test checks the two agree to Monte-Carlo tolerance.

### 5.1 Why Gauss–Hermite, and the math

With strength sampling, each player's strength is `X ~ N(eff0, σ²)`. For one
game the rating difference becomes

```
Δ = Δ0 + (εW − εB),   εW, εB ~ N(0, σ²)  independent
  = Δ0 + z,           z ~ N(0, τ²),  τ = σ·√2
```

so the *marginal* per-game outcome vector is the expectation of the deterministic
game function `g(·)` over that noise:

```
marginal = E_z[ g(Δ0 + z) ] = ∫ g(Δ0 + z) · φ(z; 0, τ²) dz
```

There is no closed form — `g` contains a logistic, an `exp` draw term, and the
floor/cap clamps. Two ways to evaluate the integral:

* **Monte Carlo** — draw many `z`, average. This is what the *engine* does,
  because it samples the whole *correlated* tournament (a player is hot/cold
  across all their games at once), which only a joint simulation captures.
* **Quadrature** — for the *per-game marginal* we need only this one smooth
  1-D Gaussian integral, and Gauss–Hermite is the natural tool for
  `∫ f(x) e^{−x²} dx`.

**Gauss–Hermite quadrature** approximates `∫_{−∞}^{∞} f(x) e^{−x²} dx ≈ Σ wᵢ f(xᵢ)`
with `n` nodes `xᵢ` (roots of the physicists' Hermite polynomial `Hₙ`) and
weights `wᵢ`, chosen so the rule is **exact for polynomials up to degree 2n−1**.

To map our Gaussian integral onto this form, substitute `z = √2·τ·u`:

```
∫ g(Δ0 + z) (1/(τ√(2π))) e^{−z²/(2τ²)} dz
   = (1/√π) ∫ g(Δ0 + √2·τ·u) e^{−u²} du
   ≈ (1/√π) Σ wᵢ · g(Δ0 + √2·τ·xᵢ)
```

Since `τ = σ√2`, the evaluation offsets are `√2·τ·xᵢ = 2σ·xᵢ`. The code uses a
**7-point** rule:

```
nodes  xᵢ = 0, ±0.8162878829, ±1.6735516288, ±2.6519613568
weights wᵢ = 0.8102646176, 0.4256072526, 0.0545155828, 0.0009717812
Σ wᵢ = √π ≈ 1.7724539      # so the (1/√π) factor normalises to 1
```

**Why 7 points is enough.** The rule is exact to polynomial degree 13, and the
integrand (a bounded logistic plus a bounded draw term) is smooth and nearly
polynomial over the relevant range — the widest node reaches `2σ·2.65 ≈ 5.3σ`
(≈318 Elo at σ=60), well into the tail. In practice it matches the engine's
Monte-Carlo win rate to ~1×10⁻⁴ (the cross-check test asserts agreement within
6×10⁻³). More nodes give no measurable improvement.

**Why quadrature on the analytic side at all.** It is deterministic (no
Monte-Carlo noise → byte-reproducible dashboards), fast (7 evaluations vs.
thousands of samples), and exact to tolerance. The engine keeps Monte Carlo
because it needs the *joint* tournament distribution, not just per-game
marginals.

---

## 6. Monte Carlo engine

* **1,000,000 iterations**, `mt19937_64` RNG, single-threaded, no JSON dependency
  (flat whitespace stdin). Simulates every game on the schedule, applies form
  updates and strength sampling, and accumulates win / rank / points
  distributions and tiebreaks.
* **Modes:** `full` (final standings distribution) and `timeline` (re-forecast
  after each played round, conditioning on actual results so far).
* First-place ties are resolved with an Armageddon-strength approximation.

---

## 7. Calibration — how the parameters are chosen

Not a raw maximum-likelihood fit (which overfits 180 games), but:

* **RPS objective (Ranked Probability Score)** on ordered outcomes
  (win > draw > loss): penalises a prediction more the further, in ordinal
  terms, it sits from the actual result. Ordinal-aware and robust — preferred
  over log-loss for this.
* **MAP regularisation:** `+ λ·[ ((WA−WA0)/WSC)² + ((DDEC−DD0)/DSC)² ]`, pulling
  parameters toward priors `WA0 = 35`, `DD0 = 0.0017` (scales `WSC = 15`,
  `DSC = 0.0015`). Without it, naïve fitting pushes `WA` absurdly high on the
  small sample.
* **`λ` (lambda) = 0.1**, chosen by **leave-one-tournament-out cross-validation**.
* **Grid search** over `(WA, DBASE, DDEC, SIGMA)`.
* **Bootstrap** (resampling games) for parameter-stability confidence intervals
  — e.g. it shows `SIGMA` is weakly identified (90% CI roughly [0, 100]),
  which is why `SIGMA` is chosen by the CV curve, not by a point fit.
* **`ARM_H`** is fit separately on the historical Armageddon mini-matches
  (least squares + a mild prior).

Deployed values: `WA = 35`, `DBASE = 0.75`, `DDEC = 0.0018`, `ARM_H = −30`,
`SIGMA = 60`, `λ = 0.1`.

---

## 8. Evaluation metrics

| Metric | Definition | Reads as |
| --- | --- | --- |
| **Brier** (4-way) | `Σ (pᵢ − yᵢ)²` | calibration + sharpness; uniform baseline 0.75 |
| **RPS** | ordinal squared CDF error (win>draw>loss) | main score; uniform ≈ 0.208 (3-way) |
| **Log-loss** (bits) | `−log₂(p_actual)` | surprise of the realised outcome |
| **Reliability / ECE** | predicted vs observed frequency by bin | are 30% calls right ~30% of the time? |
| **Result-class hit** | modal class (win/draw/loss) matches | coarse "did we call it" |
| **Directional** | on decisive games, winner had the higher win prob | sharpness on the games that resolve |

Every metric is reported against the **uniform baseline**, because on a
near-random domain beating uniform at all is the real test.

---

## 9. Multi-year backtest (leave-one-year-out)

Each edition 2022–2026 is independent. For each year the model is fit on the
other four and scored out-of-sample, at two levels: per-game (RPS / Brier /
log-loss vs uniform) and tournament (probability assigned to the actual
champion; surprise in bits). It confirms the per-game edge over uniform
(RPS 0.148 vs 0.175 across 180 games) generalises to every edition, and
characterises strength sampling as a tournament-level tail-risk hedge.

---

## 10. Tested and rejected (not in the deployed model)

| Parameter | Idea | Verdict |
| --- | --- | --- |
| `AGG` | standings-aware draw dynamics: `exp(−AGG·lateness·pressure)` shrinks draws in late, high-stakes games | LOYO set **AGG = 0** in every fold. The draw band preserves the favourite ordering, so it can't fix directional accuracy; cutting draws only worsens calibration. "Draw over-firing" was a misdiagnosis. |
| `CC` | speed cross-control: add `CC·(field-centred speed gap)` to the rating | LOYO gave **CC ≈ 0**; directional unchanged (46/69). The speed gap is mostly a permanent per-player trait already priced into the classical rating. Rejected on evidence after collecting the FIDE data. |

A consistent finding across all three experiments: strength sampling, draw
dynamics and cross-control all leave directional accuracy at ~46/69 — the
residual decisive-game error is genuine upsets near the irreducible ceiling of
the problem, not a missing feature.

---

## 11. Parameter quick reference

| Name | Value | Source | Role |
| --- | --- | --- | --- |
| `WA` | 35 | fitted | White advantage (Elo) |
| `DBASE` | 0.75 | fitted | baseline draw probability |
| `DDEC` | 0.0018 | fitted | draw decay with rating gap |
| `ARM_H` | −30 | fitted | Armageddon White edge term |
| `SIGMA` | 60 | fitted (CV) | whole-event strength sampling SD |
| `λ` | 0.1 | fitted (CV) | MAP regularisation strength |
| `DCAP` | 0.85 | structural | draw probability cap |
| `MINP` | 0.01 | structural | min win/loss probability |
| `FORM_K` | 32 | structural | in-event Elo update |
| `armageddon_strength` | rapidblitz | structural | rating used for the tiebreak |
| `CC` | 0 | rejected | speed cross-control (off) |
| `AGG` | 0 | rejected | draw dynamics (off) |
| `style` | per-player | derived | draw-tendency multiplier |

Fitted parameters live only in `out/calibrated_params.json`; structural ones in
`configs/`. Both feed the engine and the evaluation through `src/nc_common.py`.
