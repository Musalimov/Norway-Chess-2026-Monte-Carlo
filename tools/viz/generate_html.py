#!/usr/bin/env python3
"""Build a self-contained Norway Chess dashboard from dashboard_data.json.

The generator bundles:

    template.html   HTML shell with /*__INJECT_CSS__*/ and /*__INJECT_JS__*/
    viz.css         dashboard styles
    viz.js          dashboard logic with /*__INJECT_DATA__*/ and /*__INJECT_META__*/
    dashboard_data  generated model output

No external Python dependencies are required.

Full example:

    python tools/viz/generate_html.py \
        --data    out/dashboard_data.json \
        --calib   out/calibrated_params.json \
        --names   tools/viz/names_norway2026.json \
        --venue   "Stavanger · Norway" \
        --dates   "25 May – 5 June 2026" \
        --edition "Vol. XIV · Monte Carlo Edition" \
        --output  dashboards/norway2026_dashboard.html

Minimal example:

    python tools/viz/generate_html.py --data out/dashboard_data.json --output dash.html
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_json(path: Path) -> dict:
    """Load JSON or JSONC with // comments stripped."""
    text = re.sub(r"//[^\n]*", "", Path(path).read_text(encoding="utf-8"))
    return json.loads(text)


def derive_meta(data: dict, args: argparse.Namespace) -> dict:
    """Derive masthead metadata from data, with CLI flags as presentation overrides."""
    tour = data.get("tournament", "Tournament")

    years = re.findall(r"\d{4}", tour)
    year = args.year or (years[-1] if years else "")

    base = re.sub(r"\s*\d{4}\s*", " ", tour).strip()  # tournament name without year
    if args.mast:
        mast = [p.strip() for p in args.mast.split("|") if p.strip()]
    else:
        w = base.split()
        mast = [" ".join(w[:-1]), w[-1]] if len(w) > 1 else [base]

    meta: dict = {
        "mast": mast,
        "year": year,
        "venue": args.venue or "",
        "dates": args.dates or "",
        "edition": args.edition or "Monte Carlo Edition",
    }

    if args.names:
        meta["names"] = load_json(args.names)

    # Use calibrated OOS RPS in the front-page stats when available.
    if args.calib and Path(args.calib).exists():
        calib = load_json(args.calib)
        rps = calib.get("oos_2026_rps", calib.get("oos_rps"))
        if rps is not None:
            meta["oos_rps"] = rps

    return meta


def bundle(template: str, css: str, js: str, data: dict, meta: dict, title: str) -> str:
    js = js.replace("/*__INJECT_DATA__*/", json.dumps(data, separators=(",", ":")), 1)
    js = js.replace("/*__INJECT_META__*/", json.dumps(meta, ensure_ascii=False, separators=(",", ":")), 1)
    html = template.replace("/*__INJECT_CSS__*/", css, 1)
    html = html.replace("/*__INJECT_JS__*/", js, 1)
    html = html.replace("__INJECT_TITLE__", title, 1)
    return html


def main() -> None:
    default_data = HERE.parent.parent / "out" / "dashboard_data.json"

    ap = argparse.ArgumentParser(
        description="Generate the self-contained Norway Chess Monte Carlo dashboard."
    )
    ap.add_argument("--data", type=Path, default=default_data,
                    help="dashboard_data.json; defaults to out/dashboard_data.json")
    ap.add_argument("--output", type=Path, required=True, help="output HTML path")
    ap.add_argument("--calib", type=Path, default=None,
                    help="calibrated_params.json; adds OOS RPS to the lead stats")
    ap.add_argument("--names", type=Path, default=None,
                    help="JSON map from short names to display names, e.g. Pragg -> Praggnanandhaa")
    ap.add_argument("--title", default=None, help="HTML <title>")
    ap.add_argument("--mast", default=None,
                    help='masthead split by |, e.g. "Norway|Chess"; the second part is styled red')
    ap.add_argument("--year", default=None, help="masthead year; otherwise derived from tournament name")
    ap.add_argument("--venue", default=None, help='venue, e.g. "Stavanger · Norway"')
    ap.add_argument("--dates", default=None, help='date range, e.g. "25 May – 5 June 2026"')
    ap.add_argument("--edition", default=None, help="edition label in the top line")
    ap.add_argument("--template-dir", type=Path, default=HERE,
                    help="folder containing template.html / viz.css / viz.js")
    args = ap.parse_args()

    if not args.data.exists():
        sys.exit(f"Error: data file not found: {args.data}")

    data = load_json(args.data)

    td = args.template_dir
    for fn in ("template.html", "viz.css", "viz.js"):
        if not (td / fn).exists():
            sys.exit(f"Error: {fn} not found in {td}")
    template = (td / "template.html").read_text(encoding="utf-8")
    css = (td / "viz.css").read_text(encoding="utf-8")
    js = (td / "viz.js").read_text(encoding="utf-8")

    meta = derive_meta(data, args)
    title = args.title or f"{data.get('tournament', 'Tournament')} · Monte Carlo"

    html = bundle(template, css, js, data, meta, title)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")

    kb = len(html.encode("utf-8")) / 1024
    rounds = len(data.get("checkpoints", [])) - 1
    print(f"✓ wrote {args.output}  ({kb:.0f} KB · "
          f"{len(data.get('players', []))} players · {rounds} rounds · "
          f"{len(data.get('models', []))} models)")


if __name__ == "__main__":
    main()
