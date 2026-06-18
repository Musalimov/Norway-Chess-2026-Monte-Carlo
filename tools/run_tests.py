#!/usr/bin/env python3
"""Test suite for the Norway Chess project.
Runs the C++ model unit-test binary, then Python unit tests for parsing,
scoring/tie-break, the C++<->Python probability mirror, leakage guard, and
the dashboard data builder. Plain asserts, no framework.

Run from project root:  python3 tools/run_tests.py
"""
import json, math, subprocess, sys, os, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
fails = 0
def check(name, ok):
    global fails
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    if not ok: fails += 1
def approx(a,b,t=1e-6): return abs(a-b)<t

# ---- 0. ensure binaries ----
if not Path("sim").exists():
    subprocess.run(["g++","-O2","-std=c++17","src/sim.cpp","-o","sim"],check=True)
Path("bin").mkdir(exist_ok=True)
subprocess.run(["g++","-O2","-std=c++17","src/test_model.cpp","-o","bin/test_model"],check=True)

# ---- 1. C++ model unit tests ----
print("== C++ model unit tests (bin/test_model) ==")
r = subprocess.run(["./bin/test_model"],capture_output=True,text=True)
print("   "+r.stdout.strip().splitlines()[-1])
check("C++ model binary: all pass", r.returncode==0)

# ---- 2. Python model <-> C++ engine cross-check (real, not assumed) ----
print("== C++ <-> Python probability mirror ==")
sys.path.insert(0, str(ROOT / "src"))
from nc_common import Model  # noqa: E402

M = Model()  # single source: calibrated params + model_v4 config + norway2026

# invariants of the shared Python model
pa = M.game4("carlsen", "gukesh")
check("python game4 sums to 1", approx(sum(pa), 1.0))
check("white edge favours white (pw>pb at equalish)", pa[0] > pa[3])
check("armageddon: equal strength, ARM_H<0 -> white >0.5",
      M.expect(0 - 0 - M.ARM_H) > 0.5)

# Real cross-check: build a 2-player, 1-game tournament, simulate it in C++,
# and compare the empirical finish distribution to the analytic Python model.
# With one game there are no ties, so P(p1 first) = game4[0] + game4[1].
import collections as _c
two = _c.OrderedDict(name="XCheck 2026", players=[
    dict(M.players["carlsen"]), dict(M.players["gukesh"])])
two["rounds"] = [{"round": 1, "games": [{
    "p1": "carlsen", "p2": "gukesh", "color": "p1_white",
    "result": {"type": "classical", "p1_points": 3.0}}]}]  # result ignored at after_round=0
with tempfile.TemporaryDirectory() as td:
    tf = Path(td) / "two.json"
    tf.write_text(json.dumps(two))
    inp = subprocess.run([sys.executable, "tools/make_sim_input.py", str(tf),
                          "configs/model_v4.json"], capture_output=True, text=True).stdout
    sim = json.loads(subprocess.run(["./sim", "full", "400000", "7", "0"],
                                    input=inp, capture_output=True, text=True).stdout)
emp = {p["name"]: p["p_win"] for p in sim["players"]}
g = M.game4("carlsen", "gukesh")
analytic_first = g[0] + g[1]
check(f"C++ p_win matches Python game4 (sim {emp['Carlsen']:.3f} vs analytic {analytic_first:.3f})",
      approx(emp["Carlsen"], analytic_first, 6e-3))
check("C++ + Python agree the rest goes to the other player",
      approx(emp["Gukesh"], 1 - analytic_first, 6e-3))

# Fitted params now have a single home; the config must not silently re-introduce them.
cfg_raw = json.load(open("configs/model_v4.json"))
check("config carries no fitted params (single source = calibrated_params.json)",
      not any(k in cfg_raw for k in
              ("white_advantage", "draw_base", "draw_decay", "armageddon_handicap", "strength_sigma")))

# Strength-sampling path: the analytic Gauss-Hermite marginalisation must match
# the engine's per-iteration N(0, sigma) sampling.
Ms = Model(tournament=ROOT / "data/tournaments/norway2026.json")
Ms.STRENGTH_SIGMA = 60.0
two_s = _c.OrderedDict(name="XCheck sigma", players=[
    dict(Ms.players["carlsen"]), dict(Ms.players["gukesh"])])
two_s["rounds"] = [{"round": 1, "games": [{
    "p1": "carlsen", "p2": "gukesh", "color": "p1_white",
    "result": {"type": "classical", "p1_points": 3.0}}]}]
with tempfile.TemporaryDirectory() as td:
    tf2 = Path(td) / "two_sigma.json"
    tf2.write_text(json.dumps(two_s))
    Ms2 = Model(tournament=tf2); Ms2.STRENGTH_SIGMA = 60.0
    sim_s = json.loads(subprocess.run(["./sim", "full", "400000", "11", "0"],
                                      input=Ms2.sim_input(), capture_output=True, text=True).stdout)
emp_s = {p["name"]: p["p_win"] for p in sim_s["players"]}
gs = Ms2.game4("carlsen", "gukesh")
check(f"sigma=60: engine matches marginalised model (sim {emp_s['Carlsen']:.3f} vs {gs[0]+gs[1]:.3f})",
      approx(emp_s["Carlsen"], gs[0] + gs[1], 6e-3))

# Shared 3-way classical core (used by the multi-year backtest) must match the
# deployed model's per-game core at style 1.
from nc_common import classical_wdl  # noqa: E402
_m = Model()
for d in (-200.0, 0.0, 150.0):
    pw, pd, pb = classical_wdl(d + _m.WA, _m.DBASE, _m.DDEC, _m.DCAP, _m.MINP, 0.0)
    g = _m._core(d + _m.WA, 1.0, 1.0, 0.5)  # parm=0.5 splits draw evenly
    check(f"classical_wdl matches Model core at d={d:.0f}",
          approx(pw, g[0]) and approx(pb, g[3]) and approx(pd, g[1] + g[2]))
check("classical_wdl sums to 1", approx(sum(classical_wdl(40.0, 0.7, 0.0018)), 1.0))

# ---- 3. parsing (synthetic odd/even PGN) ----
print("== PGN parsing ==")
with tempfile.TemporaryDirectory() as td:
    raw=Path(td)/"data"/"raw"; raw.mkdir(parents=True)
    (raw/"nc2099_test.pgn").write_text(
"""[Event "Norway Chess 2099"]
[Date "2099.05.27"]
[Round "1.1"]
[White "A, A"]
[Black "B, B"]
[WhiteElo "2800"]
[BlackElo "2700"]
[TimeControl "7200+30"]
[Result "1/2-1/2"]

1. e4 e5 1/2-1/2

[Event "Norway Chess 2099"]
[Date "2099.05.27"]
[Round "1.2"]
[White "C, C"]
[Black "D, D"]
[WhiteElo "2750"]
[BlackElo "2740"]
[TimeControl "7200+30"]
[Result "1-0"]

1. d4 d5 1-0

[Event "Norway Chess 2099"]
[Date "2099.05.27"]
[Round "2.1"]
[White "B, B"]
[Black "A, A"]
[WhiteElo "2700"]
[BlackElo "2800"]
[TimeControl "600+10"]
[Result "1-0"]

1. e4 c5 1-0
""")
    # minimal header parser identical in spirit to build_dataset
    import re
    def heads(p):
        cur={};out=[]
        for line in open(p):
            m=re.match(r'\[(\w+)\s+"(.*)"\]',line.strip())
            if m: cur[m.group(1)]=m.group(2)
            elif line.strip() and not line.startswith('[') and cur.get('Result'):
                out.append(cur); cur={}
        return out
    from collections import defaultdict
    rounds=defaultdict(list)
    for h in heads(raw/"nc2099_test.pgn"):
        rounds[int(h['Round'].split('.')[0])].append(h)
    # round1 classical, round2 armageddon; pair the A-B draw with its armageddon
    r1=rounds[1]; r2={frozenset((a['White'],a['Black'])):a for a in rounds[2]}
    ab=[g for g in r1 if g['Result']=='1/2-1/2'][0]
    arm=r2.get(frozenset((ab['White'],ab['Black'])))
    check("draw paired with its armageddon", arm is not None)
    check("armageddon winner read (B won as White)", arm and arm['Result']=='1-0')
    cd=[g for g in r1 if g['Result']=='1-0'][0]
    check("decisive game has no armageddon", frozenset((cd['White'],cd['Black'])) not in r2)

# ---- 4. scoring / tie-break rules ----
print("== Scoring & format rules ==")
fmt=json.load(open("data/formats/norway_chess.json"))
check("classical win = 3", fmt["classical_win"]==3.0)
check("armageddon white = 1.5", fmt["draw_white_armageddon_win"]==1.5)
check("armageddon black = 1.0", fmt["draw_black_armageddon_win"]==1.0)
check("armageddon only after draw", fmt["armageddon_after_classical_draw"] is True)
# points pair always sums correctly
def pair_points(outcome):
    return {0:(3.0,0.0),1:(1.5,1.0),2:(1.0,1.5),3:(0.0,3.0)}[outcome]
check("classical pair sums to 3", approx(sum(pair_points(0)),3.0) and approx(sum(pair_points(3)),3.0))
check("armageddon pair sums to 2.5", approx(sum(pair_points(1)),2.5) and approx(sum(pair_points(2)),2.5))

# ---- 5. tournament data consistency ----
print("== Tournament data ==")
tour=json.load(open("data/tournaments/norway2026.json"))
idx={p["id"]:p["name"] for p in tour["players"]}
pts={p["name"]:0.0 for p in tour["players"]}
for rd in tour["rounds"]:
    for g in rd["games"]:
        r=g["result"]; p1=r["p1_points"]
        p2=(3.0-p1) if r["type"]=="classical" else (2.5-p1)
        pts[idx[g["p1"]]]+=p1; pts[idx[g["p2"]]]+=p2
check("standings reproduce official table",
      pts=={"Pragg":18.0,"So":17.0,"Firouzja":15.5,"Carlsen":13.0,"Keymer":11.0,"Gukesh":8.0})

# ---- 6. engine leakage guard ----
print("== Engine leakage guard (--after-round) ==")
def run(mode,iters,seed,after=0):
    inp=subprocess.run([sys.executable,"tools/make_sim_input.py","data/tournaments/norway2026.json","configs/model_v4.json"],capture_output=True,text=True).stdout
    return json.loads(subprocess.run(["./sim",mode,str(iters),str(seed),str(after)],input=inp,capture_output=True,text=True).stdout)
final=run("full",30000,1,10)
champ=max(final["players"],key=lambda p:p["p_win"])
check("after_round=10 -> champion=Pragg P=1.0", champ["name"]=="Pragg" and champ["p_win"]>0.999)
pre=run("full",30000,1,0)
check("after_round=0 -> nobody at P=1.0", all(p["p_win"]<0.99 for p in pre["players"]))
check("p_win sums to 1", approx(sum(p["p_win"] for p in pre["players"]),1.0,5e-3))
for p in pre["players"]:
    if not approx(sum(p["rank_dist"]),1.0,5e-3): check("rank_dist sums to 1",False);break
else: check("rank_dist sums to 1", True)

# ---- 7. dashboard data builder invariants ----
print("== Dashboard data ==")
dd=json.load(open("out/dashboard_data.json"))
check("checkpoints = rounds+1", len(dd["checkpoints"])==len(tour["rounds"])+1)
bad=0
for m in dd["models"]:
    for rd in dd["rounds_pred"][m]:
        for g in rd["games"]:
            if not approx(sum(g["probs"]),1.0,1e-3): bad+=1
check("all per-game 4-way probs sum to 1", bad==0)
check("metrics present (reliability+brier)", "reliability" in dd["metrics"] and "per_round_brier" in dd["metrics"])
check("mean Brier below uniform", dd["metrics"]["mean_brier"] < dd["metrics"]["uniform_brier"])

print(f"\n{'ALL TESTS PASS' if fails==0 else str(fails)+' TEST(S) FAILED'}")
sys.exit(1 if fails else 0)
