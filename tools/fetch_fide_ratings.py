#!/usr/bin/env python3
"""Build data/fide/speed_ratings.json from FIDE monthly rating-list files.

Only RAPID and BLITZ ratings need collecting: the classical (standard) rating of
every opponent is already in the tournament PGNs (WhiteElo/BlackElo, Variant
"Standard") and in history.json, and the model already uses it. Norway Chess
broadcasts no rapid/blitz games, so those ratings live only in FIDE's monthly
rating lists -> this script.

FIDE IDs are read AUTOMATICALLY from the broadcast PGNs in data/raw/ (the 2023-
2026 broadcasts carry WhiteFideId/BlackFideId). Only the five 2022-only veterans
whose 2022 broadcast lacks FideId tags fall back to MANUAL_IDS below — and even
those are resolved by NAME matching against the FIDE list, so IDs are low-risk.

Handles BOTH FIDE formats: recent COMBINED lists (rating + rapid_rating +
blitz_rating) and older SEPARATE standard/rapid/blitz lists.

HOW TO RUN (manual download + parse):
  1. Download, for each edition month (May 2022-2026), whatever FIDE offers:
     a combined list, or separate standard/rapid/blitz lists.
  2. Put them in data/fide/raw/ as <YYYY-MM>_<type>.<ext>, type in
     combined|standard|rapid|blitz, ext xml/xml.zip/zip/xml.gz. E.g.:
       data/fide/raw/2026-05_combined.xml.zip
       data/fide/raw/2022-05_standard.xml.zip  (+ _rapid, _blitz)
  3. python tools/fetch_fide_ratings.py
Standard library only.
"""
import glob, gzip, io, json, re, zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "fide" / "raw"
PGN_DIR = ROOT / "data" / "raw"
HISTORY = ROOT / "data" / "history.json"
OUT = ROOT / "data" / "fide" / "speed_ratings.json"

EDITION_MONTH = {"2022": "2022-05", "2023": "2023-05", "2024": "2024-05",
                 "2025": "2025-05", "2026": "2026-05"}

# Only needed for players whose broadcast carries no FideId (the 2022 veterans).
# Name matching covers them anyway; these are best-effort hints/overrides.
MANUAL_IDS = {
    "Anand, Viswanathan": 5000017, "Radjabov, Teimour": 13400924,
    "Topalov, Veselin": 2900084, "Vachier-Lagrave, Maxime": 623539,
    "Wang, Hao": 8602883,
}


def norm(name):
    toks = re.split(r"[\s,]+", name.lower().replace(".", ""))
    return " ".join(sorted(t for t in toks if t))


def target_names():
    H = json.loads(HISTORY.read_text())
    s = set()
    for g in H:
        s.add(g["white"]); s.add(g["black"])
    return s


def ids_from_pgn(names):
    """Authoritative name -> FIDE ID from the broadcast PGNs (per-game parse)."""
    counts = defaultdict(lambda: defaultdict(int))
    for f in glob.glob(str(PGN_DIR / "*.pgn")):
        txt = Path(f).read_text(encoding="utf-8", errors="ignore")
        for game in re.split(r"(?=\[Event )", txt):
            def tag(t):
                m = re.search(rf'\[{t} "([^"]*)"\]', game)
                return m.group(1).strip() if m else None
            for col in ("White", "Black"):
                nm, fid = tag(col), tag(col + "FideId")
                if nm in names and fid and fid.isdigit():
                    counts[nm][int(fid)] += 1
    return {nm: max(d, key=d.get) for nm, d in counts.items()}


MONTHS3 = {"jan":"01","feb":"02","mar":"03","apr":"04","may":"05","jun":"06",
           "jul":"07","aug":"08","sep":"09","oct":"10","nov":"11","dec":"12"}


def file_type(f):
    f = f.lower()
    if "combined" in f or "_all" in f: return "combined"
    if "standard" in f or "_std" in f: return "standard"
    if "rapid" in f or "_rpd" in f: return "rapid"
    if "blitz" in f or "_blz" in f: return "blitz"
    return "combined"


def month_of(f):
    m = re.search(r"(\d{4})-(\d{2})", f)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    # FIDE native names like blitz_jun22frl_xml / rapid_jun2024 ...
    m = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\.?(\d{2,4})", f.lower())
    if m:
        yy = m.group(2)
        year = yy if len(yy) == 4 else "20" + yy
        return f"{year}-{MONTHS3[m.group(1)]}"
    return None


def _maybe_decompress(data, name):
    if data[:2] == b"PK":  # zip (handles .zip and extension-hidden names)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            nm = next((n for n in z.namelist() if n.lower().endswith("xml")), z.namelist()[0])
            return z.read(nm)
    if data[:2] == b"\x1f\x8b":
        return gzip.decompress(data)
    return data


def read_list_bytes(path):
    """Read FIDE list bytes from a file (zip/gz/xml, with or without extension)
    or from an already-extracted folder."""
    p = Path(path)
    if p.is_dir():
        cands = [c for c in sorted(p.rglob("*")) if c.is_file()]
        xml = next((c for c in cands if c.name.lower().endswith("xml")), None)
        target = xml or (cands[0] if cands else None)
        if target is None:
            raise FileNotFoundError(f"empty folder {p}")
        return _maybe_decompress(target.read_bytes(), target.name)
    return _maybe_decompress(p.read_bytes(), p.name)


def parse_file(xml_bytes, ftype, out_month, id_to_name, norm_to_name):
    def field(el, *tags):
        for t in tags:
            v = el.findtext(t)
            if v not in (None, "", "0"):
                try: return int(v)
                except ValueError: return None
        return None
    for _ev, el in ET.iterparse(io.BytesIO(xml_bytes), events=("end",)):
        if el.tag != "player":
            continue
        fid = el.findtext("fideid") or el.findtext("id")
        fid = int(fid) if (fid and fid.isdigit()) else None
        fname = (el.findtext("name") or "").strip()
        hist = id_to_name.get(fid) or norm_to_name.get(norm(fname))
        if hist:
            rec = out_month.setdefault(hist, {"std": None, "rapid": None, "blitz": None,
                                              "_fide_name": fname, "_fide_id": fid})
            if ftype == "combined":
                rec["std"] = field(el, "rating", "srtng") or rec["std"]
                rec["rapid"] = field(el, "rapid_rating", "rrtng") or rec["rapid"]
                rec["blitz"] = field(el, "blitz_rating", "brtng") or rec["blitz"]
            else:
                rec[{"standard": "std"}.get(ftype, ftype)] = field(el, "rating", "srtng", "rrtng", "brtng")
        el.clear()


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    names = target_names()
    ids = dict(MANUAL_IDS)
    ids.update(ids_from_pgn(names))           # PGN wins over manual where present
    id_to_name = {fid: nm for nm, fid in ids.items()}
    norm_to_name = {norm(nm): nm for nm in names}
    print(f"FIDE IDs: {len(ids_from_pgn(names))} from PGNs, "
          f"{len(set(names) - set(ids))} unresolved (rely on name match).")

    files = sorted(glob.glob(str(RAW / "*")))
    if not files:
        print(f"\nNo files in {RAW}. Download FIDE May lists for 2022-2026 (combined, or")
        print("separate standard/rapid/blitz), name them <YYYY-MM>_<type>.xml.zip, re-run.")
        return
    months = {}
    for path in files:
        fn = Path(path).name
        mo = month_of(fn)
        if not mo:
            print(f"  ignoring (no YYYY-MM in name): {fn}"); continue
        ft = file_type(fn)
        print(f"  parsing {fn}  ->  {mo}, {ft}")
        try:
            parse_file(read_list_bytes(path), ft,
                       months.setdefault(mo, {}), id_to_name, norm_to_name)
        except Exception as e:
            print(f"    ERROR: {e}")

    monthly = {}
    for mo in sorted(months):
        print(f"\n[{mo}]")
        for nm in sorted(names):
            rec = months[mo].get(nm)
            if not rec or all(rec[k] is None for k in ("std", "rapid", "blitz")):
                print(f"  MISSING  {nm}")
                continue
            print(f"  ok  {nm:<26} STD{rec['std']} R{rec['rapid']} B{rec['blitz']}  ({rec['_fide_name']})")
            monthly.setdefault(nm, {})[mo] = {k: rec[k] for k in ("std", "rapid", "blitz")}

    by_edition = {y: {nm: monthly.get(nm, {}).get(mo) for nm in names if monthly.get(nm, {}).get(mo)}
                  for y, mo in EDITION_MONTH.items()}
    OUT.write_text(json.dumps({
        "_note": "Auto-built by tools/fetch_fide_ratings.py. Classical comes from the PGNs; "
                 "this file supplies rapid/blitz. Keys match history.json names.",
        "fide_ids": ids, "by_edition": by_edition,
        "monthly": {nm: dict(sorted(v.items())) for nm, v in monthly.items()},
    }, indent=1, ensure_ascii=False))
    print(f"\nwrote {OUT}  ({sum(len(v) for v in by_edition.values())}/38 edition cells)")


if __name__ == "__main__":
    main()
