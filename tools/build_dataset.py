#!/usr/bin/env python3
"""Parse Norway Chess PGN broadcasts into data/history.json.

Norway Chess broadcast structure for 2022-2026:
- odd-numbered broadcast rounds contain classical games;
- the following even-numbered broadcast round contains same-day Armageddon games
  for the classical games that were drawn.

The parser supports both 10-player editions (2022/2023, five boards) and
6-player editions (2024-2026, three boards). The year is inferred from the
file name.

Only the Python standard library is required; the parser reads PGN headers and
therefore does not need python-chess.

Run from the project root:

    python3 tools/build_dataset.py
"""
import re, json, glob, os
from collections import defaultdict

RES = {'1-0': 1.0, '1/2-1/2': 0.5, '0-1': 0.0}

def year_from(fname):
    m = re.search(r'(20\d{2})', fname)
    return m.group(1) if m else '????'

def load_headers(path):
    cur, games = {}, []
    for line in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'\[(\w+)\s+"(.*)"\]', line.strip())
        if m:
            cur[m.group(1)] = m.group(2)
        elif line.strip() and not line.startswith('[') and cur.get('Result'):
            games.append(cur); cur = {}
    if cur.get('Result'):
        games.append(cur)
    return games

records = []
for path in sorted(glob.glob('data/raw/*.pgn')):
    year = year_from(os.path.basename(path))
    rounds = defaultdict(list)
    for g in load_headers(path):
        if g.get('Result') not in RES:
            continue
        rounds[int(g['Round'].split('.')[0])].append(g)
    for rnd in sorted(rounds):
        if rnd % 2 == 0:                      # Even rounds are Armageddon games; pair them with classical games.
            continue
        day = (rnd + 1) // 2
        arm = {frozenset((a['White'], a['Black'])): a for a in rounds.get(rnd + 1, [])}
        for g in rounds[rnd]:
            rw = RES[g['Result']]
            rec = {
                'year': year, 'day': day, 'round': rnd,
                'white': g['White'], 'black': g['Black'],
                'white_elo': int(g.get('WhiteElo', 0) or 0),
                'black_elo': int(g.get('BlackElo', 0) or 0),
                'classical_result_white': rw,
                'armageddon': None,
            }
            if rw == 0.5:
                a = arm.get(frozenset((g['White'], g['Black'])))
                if a:
                    rec['armageddon'] = {
                        'white_player': a['White'],
                        'white_won_minimatch': (a['Result'] == '1-0'),
                        'result': a['Result'],
                    }
            records.append(rec)

os.makedirs('data', exist_ok=True)
open('data/history.json', 'w', encoding='utf-8').write(
    json.dumps(records, indent=1, ensure_ascii=False))

# Summary table.
by_year = defaultdict(lambda: [0, 0, 0])   # games, draws, paired Armageddon games
for r in records:
    y = by_year[r['year']]
    y[0] += 1
    y[1] += r['classical_result_white'] == 0.5
    y[2] += r['armageddon'] is not None
print(f"{'year':<6}{'games':>8}{'draws':>8}{'rate':>7}{'paired_arm':>13}")
for yr in sorted(by_year):
    p, d, a = by_year[yr]
    print(f"{yr:<6}{p:>8}{d:>8}{d/p:>7.0%}{a:>13}")
tot = [sum(c) for c in zip(*by_year.values())]
print(f"{'TOTAL':<6}{tot[0]:>8}{tot[1]:>8}{tot[1]/tot[0]:>7.0%}{tot[2]:>13}")

# Consistency check.
assert all(r['armageddon'] is None or r['classical_result_white'] == 0.5 for r in records)
print("\nconsistency check: Armageddon only follows a classical draw: OK")
print("written: data/history.json")
