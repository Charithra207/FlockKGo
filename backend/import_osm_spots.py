"""
import_osm_spots.py — Karnataka spots from OpenStreetMap: fetch once, load on deploy.

Data © OpenStreetMap contributors, licensed ODbL. The site footer and map
show this credit. (We don't scrape Instagram: it isn't open data, and
scraping it breaks their terms.)

Sources
  * OpenStreetMap (Overpass): cafes, and nature spots when the servers cope.
  * Wikidata (CC0): waterfalls, hills/peaks, lakes with coordinates,
    Kannada names and Wikipedia links. Districts are confirmed by reverse
    geocoding with Nominatim, and anything outside Karnataka is dropped.

Two steps, so deploys never depend on the busy public servers:

  fetch  Queries Overpass district by district and writes JSON files in data/:
           data/osm_cafes.json        named, non-chain cafes        -> public
           data/osm_nature.json       named waterfalls, viewpoints, peaks
         For nature spots, famous places become public and lesser-known ones
         become hidden gems (at most --max-hidden, spread across districts).

  load   Upserts those JSON files into the `spots` table (matched on osm_id).
         Idempotent; build.sh runs it on every deploy. It never overwrites
         edits an admin has made (rows with extra.curated = true).

Usage
    python import_osm_spots.py fetch --kind cafe
    python import_osm_spots.py fetch --kind wikidata --sparql-json saved.json   # run first
    python import_osm_spots.py fetch --kind nature --max-hidden 100            # shares the quota
    python import_osm_spots.py fetch --kind cafe --district Kodagu
    WIKIMEDIA_CONTACT=you@example.com python import_osm_spots.py fetch --kind wikidata
    python import_osm_spots.py fetch --kind wikidata --sparql-json saved.json
    python import_osm_spots.py load

Wikimedia's robot policy asks automated clients to send contact details, so a
live Wikidata query needs WIKIMEDIA_CONTACT (an email or URL you choose).
"""

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

import httpx

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

DATA_DIR = backend_dir / "data"
OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
USER_AGENT = "karnataka-spots-importer/1.0"
HUB_RADIUS_KM = 60.0

KINDS = {
    "cafe": {
        "file": "osm_cafes.json",
        "filters": ['["amenity"="cafe"]["name"]'],
    },
    "nature": {
        "file": "osm_nature.json",
        "filters": [
            '["natural"="waterfall"]["name"]',
            '["waterway"="waterfall"]["name"]',
            '["tourism"="viewpoint"]["name"]',
            '["natural"="peak"]["name"]',
        ],
    },
    "wikidata": {"file": "wikidata_nature.json"},
}

# Categories that may be locked as hidden gems (others are always public).
HIDDEN_ELIGIBLE = {"waterfall", "viewpoint", "trek"}

CHAIN_WORDS = [
    "cafe coffee day", "ccd", "starbucks", "costa coffee", "barista", "third wave",
    "chaayos", "tim hortons", "chai point", "mcdonald", "kfc", "domino",
    "coffee day", "dunkin", "blue tokai", "brew bay",
]

# Well-known places: imported as PUBLIC spots, never as hidden gems.
FAMOUS_WORDS = [
    "jog", "abbey", "abbi", "iruppu", "hebbe", "gaganachukki", "bharachukki",
    "shivanasamudra", "chunchi", "gokak", "sathodi", "unchalli", "magod",
    "kalhatti", "manikyadhara", "raja's seat", "rajas seat", "mullayanagiri",
    "kumara parvatha", "pushpagiri", "kodachadri", "nandi", "skandagiri",
    "tadiandamol", "kudremukh", "baba budan", "bababudan", "mallalli",
    "barkana", "kunchikal", "dudhsagar", "lakkavalli", "sunset point",
    "sunrise point", "talakaveri", "brahmagiri", "savandurga", "makalidurga",
    "shivagange", "devarayanadurga", "kemmangundi", "z point", "gopalaswamy",
    "chamundi", "nandi hills", "biligiri", "male mahadeshwara", "kudremukha",
    "irupu", "hogenakal", "hogenakkal", "mekedatu", "mekedaatu", "muthyala",
    "antara gange", "antharagange", "matanga", "chandragiri", "vindhyagiri",
    "barachukki", "madhugiri", "anegundi", "daroji", "ramadevara", "adichunchanagiri",
    "br hills", "bahubali", "sanctuary", "national park",
]

# Names that don't tell a visitor what or where the place is.
GENERIC_NAME_RE = re.compile(r"^(city\s+)?view\s*(point|tower)?$|^view (on|of) |^(sunset|sunrise) point$|^peak$|^hill$", re.I)


def _is_generic(name: str) -> bool:
    from app.core.karnataka import normalize_district
    n = name.strip()
    return bool(GENERIC_NAME_RE.search(n)) or normalize_district(n) is not None or normalize_district(n.rstrip("i")) is not None

HUB_PUBLIC_RADIUS_KM = 1.5   # this close to a catalog hub (Hampi, Coorg...) = well known
DUPLICATE_RADIUS_KM = 1.5    # same category this close = the same place, spelled differently

# OSM district names sometimes differ from ours (e.g. "Shimoga").
OSM_NAME_HINT = {
    "Shivamogga": "Shivamogga|Shimoga", "Mysuru": "Mysuru|Mysore", "Bagalkot": "Bagalko",
    "Ballari": "Ballari|Bellary", "Belagavi": "Belagavi|Belgaum",
    "Vijayapura": "Vijayapura|Bijapur", "Kalaburagi": "Kalaburagi|Gulbarga",
    "Tumakuru": "Tumakuru|Tumkur", "Chikkamagaluru": "Chikkamagal|Chikmagal",
    "Bengaluru South": "Bengaluru South|Ramanagar", "Bengaluru Urban": "Bengaluru Urban|Bangalore Urban",
    "Bengaluru Rural": "Bengaluru Rural|Bangalore Rural", "Chikkaballapura": "Chikkaballapur|Chikballapur",
    "Davanagere": "Davanagere|Davangere", "Yadgir": "Yadgir|Yadagiri",
}

KEEP_TAGS = (
    "opening_hours", "website", "phone", "cuisine", "addr:street", "addr:city",
    "name:kn", "outdoor_seating", "internet_access", "diet:vegetarian",
    "ele", "height", "wikidata", "wikipedia", "access", "intermittent",
)


# ── fetch ─────────────────────────────────────────────────────────────────────

def _query(district: str, filters: list[str]) -> str:
    hint = OSM_NAME_HINT.get(district, district)
    parts = "".join(f"node{f}(area.d);way{f}(area.d);" for f in filters)
    return (
        "[out:json][timeout:120];"
        'area["ISO3166-2"="IN-KA"]->.ka;'
        f'rel(area.ka)["boundary"="administrative"]["admin_level"="5"]["name"~"^({hint})",i];'
        "map_to_area->.d;"
        f"({parts});"
        "out center tags;"
    )


def _post(query: str) -> dict:
    delay = 5
    for attempt in range(8):
        server = OVERPASS_SERVERS[attempt % len(OVERPASS_SERVERS)]
        host = server.split("/")[2]
        try:
            r = httpx.post(server, data={"data": query}, headers={"User-Agent": USER_AGENT}, timeout=150)
            if r.status_code == 200 and r.text.lstrip().startswith("{"):
                return r.json()
            print(f"    {host} busy ({r.status_code}), retrying in {delay}s")
        except httpx.HTTPError as e:
            print(f"    {host} {e.__class__.__name__}, retrying in {delay}s")
        time.sleep(delay)
        delay = min(delay * 2, 60)
    raise RuntimeError("all Overpass servers busy")


def _category(tags: dict) -> str:
    if tags.get("amenity") == "cafe":
        return "cafe"
    if tags.get("natural") == "waterfall" or tags.get("waterway") == "waterfall":
        return "waterfall"
    if tags.get("tourism") == "viewpoint":
        return "viewpoint"
    return "trek"  # natural=peak


def _is_chain(tags: dict) -> bool:
    if tags.get("brand") or tags.get("brand:wikidata"):
        return True
    name = (tags.get("name:en") or tags.get("name") or "").lower()
    return any(w in name for w in CHAIN_WORDS)


def _is_famous(name: str) -> bool:
    n = name.lower()
    return any(w in n for w in FAMOUS_WORDS)


def parse_elements(elements: list[dict], district: str) -> list[dict]:
    out = []
    for e in elements:
        tags = e.get("tags", {})
        name = (tags.get("name:en") or tags.get("name") or "").strip()
        if not name or tags.get("access") in ("private", "no"):
            continue
        cat = _category(tags)
        if cat == "cafe" and _is_chain(tags):
            continue
        lat = e.get("lat") or (e.get("center") or {}).get("lat")
        lng = e.get("lon") or (e.get("center") or {}).get("lon")
        if lat is None or lng is None:
            continue
        out.append({
            "osm_id": f"{e['type']}/{e['id']}",
            "name": name[:200],
            "category": cat,
            "latitude": round(float(lat), 6),
            "longitude": round(float(lng), 6),
            "district": district,
            "extra": {k: tags[k] for k in KEEP_TAGS if k in tags},
        })
    return out


def _score(row: dict) -> int:
    """Prefer better-documented places when picking hidden gems."""
    x = row["extra"]
    return 3 * bool(x.get("wikidata") or x.get("wikipedia")) + bool(x.get("name:kn")) + bool(x.get("ele") or x.get("height"))


def _catalog_hubs() -> list[tuple[float, float]]:
    try:
        from seed_destinations import DESTINATION_CATALOG
    except Exception:  # pragma: no cover - seed file unavailable
        return []
    return [(d["lat"], d["lng"]) for d in DESTINATION_CATALOG]


def clean_rows(rows: list[dict]) -> list[dict]:
    """Fix obvious category mistakes and merge near-duplicate spellings."""
    from app.core.karnataka import haversine_km

    for r in rows:
        if "temple" in r["name"].lower():
            r["category"] = "temple"
    # Prefer better-documented rows when merging duplicates.
    rows = sorted(rows, key=lambda r: (-_score(r), len(r["name"]), r["name"]))
    kept: list[dict] = []
    for r in rows:
        dup = any(
            k["category"] == r["category"]
            and haversine_km(k["latitude"], k["longitude"], r["latitude"], r["longitude"]) <= DUPLICATE_RADIUS_KM
            for k in kept
        )
        if not dup:
            kept.append(r)
    return kept


def choose_visibility(rows: list[dict], max_hidden: int, hubs: Optional[list] = None) -> list[dict]:
    """Famous or next to a catalog hub -> public. Others compete for hidden slots, round-robin by district."""
    from app.core.karnataka import haversine_km

    hubs = _catalog_hubs() if hubs is None else hubs

    def near_hub(r):
        return any(haversine_km(r["latitude"], r["longitude"], la, lo) <= HUB_PUBLIC_RADIUS_KM for la, lo in hubs)

    by_district = defaultdict(list)
    for r in rows:
        r["is_hidden"] = False
        if r["category"] in HIDDEN_ELIGIBLE and not _is_famous(r["name"]) and not _is_generic(r["name"]) and not near_hub(r):
            by_district[r["district"]].append(r)
    for lst in by_district.values():
        lst.sort(key=lambda r: (-_score(r), r["name"]))
    chosen = 0
    while chosen < max_hidden and any(by_district.values()):
        for d in sorted(by_district):
            if by_district[d] and chosen < max_hidden:
                by_district[d].pop(0)["is_hidden"] = True
                chosen += 1
    return rows


def fetch(kind: str, districts: list[str], max_hidden: int) -> None:
    from app.core.karnataka import KARNATAKA_DISTRICTS  # noqa: F401  (validated by caller)

    cfg = KINDS[kind]
    path = DATA_DIR / cfg["file"]
    DATA_DIR.mkdir(exist_ok=True)
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    keep = [r for r in existing if r["district"] not in districts]  # replace re-fetched districts
    seen = {r["osm_id"] for r in keep}
    fetched, failed = [], []
    for d in districts:
        print(f"→ {d}", flush=True)
        try:
            rows = parse_elements(_post(_query(d, cfg["filters"])).get("elements", []), d)
        except RuntimeError as e:
            print(f"    skipped: {e}")
            failed.append(d)
            keep += [r for r in existing if r["district"] == d]  # keep old data for it
            continue
        rows = [r for r in rows if r["osm_id"] not in seen and not seen.add(r["osm_id"])]
        print(f"    {len(rows)} places", flush=True)
        fetched += rows
        time.sleep(2)  # be polite to the public servers
    rows = keep + fetched
    if kind == "nature":
        # Pick hidden gems over the whole state (deterministic: same data, same picks).
        rows = choose_visibility(clean_rows(rows), max_hidden)
    rows.sort(key=lambda r: (r["district"], r["category"], r["name"]))
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    hidden = sum(r.get("is_hidden", False) for r in rows)
    print(f"✓ wrote {len(rows)} rows ({hidden} hidden) to {path.relative_to(backend_dir)}")
    if failed:
        print(f"! Overpass was busy for: {', '.join(failed)}. Re-run with --district to retry.")


# ── Nature via one bbox query (the per-district area queries time out) ───────

def fetch_nature_bbox(max_hidden: int, overpass_json: Optional[str]) -> None:
    """
    One light Overpass query over the Karnataka rectangle, then confirm each
    place's state + district by reverse geocoding (drops Goa/Kerala/... slivers).
    Skips places already in wikidata_nature.json, and shares the hidden quota
    with it so the total stays at --max-hidden.
    """
    from app.core.karnataka import KARNATAKA_BBOX_OVERPASS, haversine_km, normalize_district

    if overpass_json:
        data = json.loads(Path(overpass_json).read_text(encoding="utf-8"))
    else:
        parts = "".join(
            f"node{f}({KARNATAKA_BBOX_OVERPASS});way{f}({KARNATAKA_BBOX_OVERPASS});"
            for f in KINDS["nature"]["filters"]
        )
        data = _post(f"[out:json][timeout:170];({parts});out center tags;")

    wd_path = DATA_DIR / KINDS["wikidata"]["file"]
    wd_rows = json.loads(wd_path.read_text(encoding="utf-8")) if wd_path.exists() else []
    path = DATA_DIR / KINDS["nature"]["file"]
    old = {r["osm_id"]: r for r in json.loads(path.read_text(encoding="utf-8"))} if path.exists() else {}

    def dup_of_wikidata(r):
        n = r["name"].strip().lower()
        for w in wd_rows:
            d = haversine_km(r["latitude"], r["longitude"], w["latitude"], w["longitude"])
            if (w["category"] == r["category"] and d <= DUPLICATE_RADIUS_KM) or (w["name"].strip().lower() == n and d <= 5):
                return True
        return False

    cands = [r for r in parse_elements(data.get("elements", []), district="?") if not dup_of_wikidata(r)]
    print(f"{len(cands)} new candidates; confirming districts (≈{round(len(cands) * 1.1 / 60)} min)…", flush=True)
    rows, dropped = [], 0
    for i, r in enumerate(cands, 1):
        if r["osm_id"] in old:
            rows.append({**old[r["osm_id"]], "name": r["name"], "extra": r["extra"]})
            continue
        state, district = _reverse_geocode(r["latitude"], r["longitude"])
        district = normalize_district(district)
        if state != "Karnataka" or not district:
            dropped += 1
        else:
            rows.append({**r, "district": district})
        if i % 50 == 0:
            print(f"    {i}/{len(cands)}", flush=True)

    quota = max(0, max_hidden - sum(w.get("is_hidden", False) for w in wd_rows))
    rows = choose_visibility(clean_rows(rows), quota)
    rows.sort(key=lambda r: (r["district"], r["category"], r["name"]))
    DATA_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    hidden = sum(r["is_hidden"] for r in rows)
    _save_geo_cache()
    print(f"✓ wrote {len(rows)} Karnataka places ({hidden} hidden), dropped {dropped} outside Karnataka")


# ── Cafes via one bbox query + grid-cached geocoding ──────────────────────────

GRID_DEG = 0.05  # ~5 km cells: one reverse-geocode per cell, reused for every cafe in it


def fetch_cafes_bbox(overpass_json: Optional[str]) -> None:
    from app.core.karnataka import KARNATAKA_BBOX_OVERPASS, normalize_district

    if overpass_json:
        data = json.loads(Path(overpass_json).read_text(encoding="utf-8"))
    else:
        f = KINDS["cafe"]["filters"][0]
        bb = KARNATAKA_BBOX_OVERPASS
        data = _post(f"[out:json][timeout:170];(node{f}({bb});way{f}({bb}););out center tags;")
    cands = parse_elements(data.get("elements", []), district="?")
    path = DATA_DIR / KINDS["cafe"]["file"]
    old = {r["osm_id"]: r for r in json.loads(path.read_text(encoding="utf-8"))} if path.exists() else {}

    cells: dict[tuple, tuple] = {}
    for r in old.values():  # reuse districts we already confirmed
        cells.setdefault((round(r["latitude"] / GRID_DEG), round(r["longitude"] / GRID_DEG)), ("Karnataka", r["district"]))
    todo = {(round(r["latitude"] / GRID_DEG), round(r["longitude"] / GRID_DEG)) for r in cands} - set(cells)
    print(f"{len(cands)} cafes in {len(todo)} new map cells; confirming districts (≈{round(len(todo) * 1.1 / 60)} min)…", flush=True)
    for i, (a, b) in enumerate(sorted(todo), 1):
        state, district = _reverse_geocode(a * GRID_DEG, b * GRID_DEG)
        cells[(a, b)] = (state, normalize_district(district))
        if i % 50 == 0:
            print(f"    {i}/{len(todo)}", flush=True)

    rows, dropped = [], 0
    for r in cands:
        state, district = cells[(round(r["latitude"] / GRID_DEG), round(r["longitude"] / GRID_DEG))]
        if state != "Karnataka" or not district:
            dropped += 1
            continue
        rows.append({**r, "district": district, "is_hidden": False})
    rows = clean_rows(rows)
    rows.sort(key=lambda r: (r["district"], r["name"]))
    DATA_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    _save_geo_cache()
    print(f"✓ wrote {len(rows)} Karnataka cafes, dropped {dropped} outside Karnataka")


# ── Wikidata ──────────────────────────────────────────────────────────────────

WIKIDATA_TYPES = {
    "Q34038": "waterfall", "Q8502": "trek", "Q54050": "trek",
    "Q23397": "lake", "Q131681": "lake", "Q1364700": "viewpoint",
}

SPARQL = """
SELECT ?item ?en ?kn ?type ?coord ?desc ?article ?ele WHERE {
  SERVICE wikibase:box {
    ?item wdt:P625 ?coord .
    bd:serviceParam wikibase:cornerSouthWest "Point(74.0 11.5)"^^geo:wktLiteral .
    bd:serviceParam wikibase:cornerNorthEast "Point(78.6 18.5)"^^geo:wktLiteral .
  }
  VALUES ?type { wd:Q34038 wd:Q8502 wd:Q54050 wd:Q23397 wd:Q1364700 wd:Q131681 }
  ?item wdt:P31 ?type .
  ?item rdfs:label ?en . FILTER(LANG(?en) = "en")
  OPTIONAL { ?item rdfs:label ?kn FILTER(LANG(?kn) = "kn") }
  OPTIONAL { ?item schema:description ?desc FILTER(LANG(?desc) = "en") }
  OPTIONAL { ?article schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> }
  OPTIONAL { ?item wdt:P2044 ?ele }
}
"""


def _wikidata_query() -> dict:
    import os
    contact = os.environ.get("WIKIMEDIA_CONTACT")
    if not contact:
        sys.exit("Set WIKIMEDIA_CONTACT (an email or URL) — Wikimedia's robot policy asks for it.")
    r = httpx.post(
        "https://query.wikidata.org/sparql", data={"query": SPARQL},
        headers={"User-Agent": f"{USER_AGENT} ({contact})", "Accept": "application/sparql-results+json"},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


def wikidata_candidates(bindings: list[dict]) -> list[dict]:
    """Merge SPARQL rows per item and keep the well-documented ones."""
    items: dict[str, dict] = {}
    for b in bindings:
        qid = b["item"]["value"].rsplit("/", 1)[1]
        t = WIKIDATA_TYPES.get(b["type"]["value"].rsplit("/", 1)[1])
        if not t:
            continue
        it = items.setdefault(qid, {"qid": qid, "name": b["en"]["value"], "category": t, "coord": b["coord"]["value"], "extra": {"wikidata": qid}})
        if t == "waterfall":
            it["category"] = "waterfall"  # an item typed both hill and waterfall is a waterfall
        if "kn" in b:
            it["extra"]["name:kn"] = b["kn"]["value"]
        if "article" in b:
            it["extra"]["wikipedia"] = b["article"]["value"]
        if "desc" in b:
            it["extra"]["description_en"] = b["desc"]["value"]
        if "ele" in b:
            try:
                it["extra"]["ele"] = str(round(float(b["ele"]["value"])))
            except ValueError:
                pass
    out = []
    for it in items.values():
        x = it["extra"]
        documented = bool(x.get("wikipedia") or x.get("name:kn"))
        # Waterfalls are explicitly typed, so keep them all; bulk-imported hills/lakes
        # without any article or Kannada label are too uncertain to publish.
        if it["category"] != "waterfall" and not documented:
            continue
        # "Point(lon lat)"
        lon, lat = it.pop("coord").removeprefix("Point(").rstrip(")").split()
        it["latitude"], it["longitude"] = round(float(lat), 6), round(float(lon), 6)
        out.append(it)
    return out


GEOCODE_CACHE = DATA_DIR / "geocode_cache.json"
_geo_cache: Optional[dict] = None


def _reverse_geocode(lat: float, lon: float) -> tuple[Optional[str], Optional[str]]:
    """(state, district), cached in data/geocode_cache.json so re-runs skip known points."""
    global _geo_cache
    if _geo_cache is None:
        _geo_cache = json.loads(GEOCODE_CACHE.read_text(encoding="utf-8")) if GEOCODE_CACHE.exists() else {}
    key = f"{lat:.4f},{lon:.4f}"
    if key not in _geo_cache:
        _geo_cache[key] = list(_reverse_geocode_live(lat, lon))
        if len(_geo_cache) % 25 == 0:
            _save_geo_cache()
    return tuple(_geo_cache[key])


def _save_geo_cache() -> None:
    if _geo_cache is not None:
        DATA_DIR.mkdir(exist_ok=True)
        GEOCODE_CACHE.write_text(json.dumps(_geo_cache, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _reverse_geocode_live(lat: float, lon: float) -> tuple[Optional[str], Optional[str]]:
    """(state, district) from Nominatim, 1 request/second per their usage policy.

    Retries network errors; raises if Nominatim stays unreachable, so a failed
    lookup is never cached as "outside Karnataka".
    """
    delay = 5
    for attempt in range(5):
        try:
            r = httpx.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 10, "addressdetails": 1},
                headers={"User-Agent": USER_AGENT}, timeout=30,
            )
            time.sleep(1.1)
            if r.status_code == 200:
                a = r.json().get("address", {})
                return a.get("state"), a.get("state_district") or a.get("county") or a.get("city_district")
            if r.status_code not in (429, 500, 502, 503, 504):
                return None, None
        except httpx.HTTPError:
            pass
        print(f"    geocoder hiccup, retrying in {delay}s", flush=True)
        time.sleep(delay)
        delay *= 2
    raise RuntimeError("Nominatim unreachable; re-run later (progress is cached)")


def fetch_wikidata(max_hidden: int, sparql_json: Optional[str]) -> None:
    from app.core.karnataka import normalize_district

    data = json.loads(Path(sparql_json).read_text(encoding="utf-8")) if sparql_json else _wikidata_query()
    cands = wikidata_candidates(data["results"]["bindings"])
    print(f"{len(cands)} documented candidates; confirming districts (≈{len(cands)} s)…", flush=True)
    path = DATA_DIR / KINDS["wikidata"]["file"]
    old = {r["osm_id"]: r for r in json.loads(path.read_text(encoding="utf-8"))} if path.exists() else {}
    rows, dropped = [], 0
    for c in cands:
        key = f"wikidata:{c['qid']}"
        if key in old:  # already confirmed earlier: keep its district, refresh facts
            rows.append({**old[key], "name": c["name"], "extra": c["extra"]})
            continue
        state, district = _reverse_geocode(c["latitude"], c["longitude"])
        district = normalize_district(district)
        if state != "Karnataka" or not district:
            dropped += 1
            continue
        rows.append({
            "osm_id": key, "source": "wikidata", "name": c["name"][:200], "category": c["category"],
            "latitude": c["latitude"], "longitude": c["longitude"], "district": district, "extra": c["extra"],
        })
    rows = choose_visibility(clean_rows(rows), max_hidden)
    rows.sort(key=lambda r: (r["district"], r["category"], r["name"]))
    DATA_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    hidden = sum(r["is_hidden"] for r in rows)
    _save_geo_cache()
    print(f"✓ wrote {len(rows)} Karnataka places ({hidden} hidden), dropped {dropped} outside Karnataka")


# ── load ──────────────────────────────────────────────────────────────────────

def _describe(row: dict, hub_name: str | None, hub_km: float | None) -> str:
    x = row["extra"]
    noun = {"waterfall": "Waterfall", "viewpoint": "Viewpoint", "trek": "Hilltop / peak",
            "cafe": "Cafe", "lake": "Lake"}.get(row["category"], "Place")
    bits = [f"{noun} in {row['district']} district"]
    if hub_name and hub_km is not None and hub_km >= 1:  # "about 0 km from X" reads oddly
        bits[0] += f", about {round(hub_km)} km from {hub_name}"
    text = bits[0] + "."
    if x.get("description_en"):
        d = x["description_en"].strip()
        text += f" {d[0].upper()}{d[1:]}" + ("" if d.endswith(".") else ".")
    if x.get("ele"):
        text += f" Summit around {x['ele']} m."
    if x.get("height"):
        text += f" Drop of about {x['height']} m."
    if x.get("name:kn"):
        text += f" Kannada name: {x['name:kn']}."
    if x.get("intermittent") == "yes":
        text += " Seasonal, flows mainly after the monsoon."
    return text


def load() -> None:
    import app.models  # noqa: F401
    from app.core.karnataka import haversine_km
    from app.db.database import SessionLocal
    from app.models.destination import Destination
    from app.models.spot import Spot

    db = SessionLocal()
    try:
        hubs = db.query(Destination).filter(
            Destination.is_active == True, Destination.latitude.isnot(None)  # noqa: E712
        ).all()

        def nearest(lat, lng):
            best, best_d = None, HUB_RADIUS_KM
            for h in hubs:
                d = haversine_km(lat, lng, h.latitude, h.longitude)
                if d <= best_d:
                    best, best_d = h, d
            return best, (best_d if best else None)

        existing = {s.osm_id: s for s in db.query(Spot).filter(Spot.osm_id.isnot(None)).all()}
        new = updated = 0
        for kind, cfg in KINDS.items():
            path = DATA_DIR / cfg["file"]
            if not path.exists():
                continue
            for r in json.loads(path.read_text(encoding="utf-8")):
                hub, km = nearest(r["latitude"], r["longitude"])
                s = existing.get(r["osm_id"])
                if s is not None:
                    if (s.extra or {}).get("curated"):
                        continue  # an admin edited it; leave it alone
                    s.name, s.latitude, s.longitude = r["name"], r["latitude"], r["longitude"]
                    s.extra = {**(s.extra or {}), **r["extra"]}
                    if r["category"] != "cafe":
                        s.description = _describe(r, hub.name if hub else None, km)
                    updated += 1
                    continue
                db.add(Spot(
                    name=r["name"], category=r["category"],
                    latitude=r["latitude"], longitude=r["longitude"], district=r["district"],
                    destination_id=hub.id if hub else None,
                    description=None if r["category"] == "cafe" else _describe(r, hub.name if hub else None, km),
                    is_hidden=bool(r.get("is_hidden")), status="approved", source=r.get("source", "osm"),
                    osm_id=r["osm_id"], best_months=[], tags=[], extra=r["extra"],
                ))
                new += 1
        db.commit()
        print(f"✓ OSM spots: {new} new, {updated} updated")
    finally:
        db.close()


def main() -> None:
    try:
        _main()
    finally:
        _save_geo_cache()


def _main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--kind", choices=list(KINDS), required=True)
    f.add_argument("--district")
    f.add_argument("--max-hidden", type=int, default=100)
    f.add_argument("--sparql-json", help="wikidata: use a saved SPARQL JSON result instead of querying")
    f.add_argument("--overpass-json", help="cafe/nature: use a saved Overpass JSON result instead of querying")
    f.add_argument("--by-district", action="store_true", help="old per-district area queries (slow; often times out)")
    sub.add_parser("load")
    args = p.parse_args()

    if args.cmd == "load":
        load()
        return
    if args.kind == "wikidata":
        fetch_wikidata(args.max_hidden, args.sparql_json)
        return
    if args.kind == "cafe" and not args.by_district and not args.district:
        fetch_cafes_bbox(args.overpass_json)
        return
    if args.kind == "nature" and not args.by_district and not args.district:
        fetch_nature_bbox(args.max_hidden, args.overpass_json)
        return
    from app.core.karnataka import KARNATAKA_DISTRICTS, normalize_district
    if args.district:
        d = normalize_district(args.district)
        if not d:
            sys.exit(f"Unknown Karnataka district: {args.district}")
        districts = [d]
    else:
        districts = KARNATAKA_DISTRICTS
    fetch(args.kind, districts, args.max_hidden)


if __name__ == "__main__":
    main()
