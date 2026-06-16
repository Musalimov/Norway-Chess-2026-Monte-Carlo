# tools/viz — HTML dashboard generator

This folder is the final stage of the pipeline: generated model data goes in,
a self-contained static dashboard comes out.

```text
C++ sim  ->  out/timeline_*.json, out/tournament_sim_v4.json
         ->  tools/build_dashboard_data.py  ->  out/dashboard_data.json
         ->  tools/viz/generate_html.py     ->  dashboards/norway2026_dashboard.html
```

## Files

| File | Role |
|------|------|
| `template.html` | HTML shell with `/*__INJECT_CSS__*/`, `/*__INJECT_JS__*/`, and `__INJECT_TITLE__` markers |
| `viz.css` | dashboard design, layout, and Norway-inspired palette |
| `viz.js` | dashboard logic with `/*__INJECT_DATA__*/` and `/*__INJECT_META__*/` markers |
| `generate_html.py` | bundles template + CSS + JS, injects data and metadata, writes one HTML file |
| `names_norway2026.json` | short-name to display-name map, e.g. `Pragg -> Praggnanandhaa` |

No Python dependencies are required beyond the standard library.

## Run

Full publication-style build:

```bash
python tools/viz/generate_html.py \
    --data    out/dashboard_data.json \
    --calib   out/calibrated_params.json \
    --names   tools/viz/names_norway2026.json \
    --venue   "Stavanger · Norway" \
    --dates   "25 May – 5 June 2026" \
    --edition "Vol. XIV · Monte Carlo Edition" \
    --output  dashboards/norway2026_dashboard.html
```

Minimal build:

```bash
python tools/viz/generate_html.py --data out/dashboard_data.json --output dash.html
```

## Data-driven elements

- **Masthead**: tournament name and year come from the `tournament` field.
- **Lead story**: champion, final margin, pre-tournament winner odds, opening favourite, and favourite's final place are computed from generated data.
- **Accuracy stat**: OOS RPS comes from `--calib` when available; otherwise the dashboard uses mean Brier from `metrics`.

`--venue`, `--dates`, `--edition`, `--mast`, `--year`, and `--title` are presentation-only overrides.
