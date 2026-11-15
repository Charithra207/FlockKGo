"""
import_osm_cafes.py — Import Karnataka cafes from OpenStreetMap into `spots`.

Why OpenStreetMap (and not Instagram):
  OSM data is openly licensed (ODbL) with real coordinates. Instagram isn't
  open data, and scraping it breaks their terms. "Famous" comes from people
  instead: users vouch for cafes, and admins can mark them featured.

  ODbL requires attribution: the site footer and map show
  "© OpenStreetMap contributors".

What it does
  * Queries Overpass one district at a time, so every cafe gets the correct
    Karnataka district.
  * Skips unnamed cafes and big chains (CCD, Starbucks...). Pass
    --include-chains to keep them.
  * Imports as public (not hidden), approved, source="osm". Re-running it
    updates existing rows (matched on osm_id) instead of duplicating them.

Usage
    python import_osm_cafes.py                       # all districts
    python import_osm_cafes.py --district Kodagu     # just one
    python import_osm_cafes.py --dry-run
"""

import argparse
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))

import app.models  # noqa: E402,F401
from app.core.karnataka import KARNATAKA_DISTRICTS, haversine_km, normalize_district  # noqa: E402
from app.db.database import SessionLocal  # noqa: E402
from app.models.destination import Destination  # noqa: E402
from app.models.spot import Spot  # noqa: E402

OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
USER_AGENT = "karnataka-spots-importer/1.0"
HUB_RADIUS_KM = 60.0

CHAIN_WORDS = [
    "cafe coffee day", "ccd", "starbucks", "costa coffee", "barista", "third wave",
    "chaayos", "tim hortons", "chai point", "mcdonald", "kfc", "domino",
    "cafe amudham", "brew bay", "coffee day", "dunkin", "blue tokai",
]

QUERY_ONE = """
[out:json][timeout:120];
area["ISO3166-2"="IN-KA"]->.ka;
rel(area.ka)["boundary"="administrative"]["admin_level"="5"]["name"~"^{name}",i];
map_to_area->.d;
(node["amenity"="cafe"](area.d); way["amenity"="cafe"](area.d););
out center tags;
"""

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


def _is_chain(tags: dict) -> bool:
    if tags.get("brand") or tags.get("brand:wikidata"):
        return True
    name = (tags.get("name:en") or tags.get("name") or "").lower()
    return any(w in name for w in CHAIN_WORDS)


def _post(query: str) -> dict:
    delay = 5
    for attempt in range(6):
        server = OVERPASS_SERVERS[attempt % len(OVERPASS_SERVERS)]
        try:
            r = httpx.post(server, data={"data": query}, headers={"User-Agent": USER_AGENT}, timeout=150)
            if r.status_code == 200 and r.text.lstrip().startswith("{"):
                return r.json()
            print(f"    {server.split('/')[2]} busy ({r.status_code}), retrying in {delay}s")
        except httpx.HTTPError as e:
            print(f"    {server.split('/')[2]} error ({e.__class__.__name__}), retrying in {delay}s")
        time.sleep(delay)
        delay = min(delay * 2, 60)
    raise RuntimeError("All Overpass servers are busy. Try again later.")


def _hubs(db):
    return db.query(Destination).filter(
        Destination.is_active == True, Destination.latitude.isnot(None)  # noqa: E712
    ).all()


def _nearest_hub_id(hubs, lat, lng):
    best, best_d = None, HUB_RADIUS_KM
    for h in hubs:
        d = haversine_km(lat, lng, h.latitude, h.longitude)
        if d <= best_d:
            best, best_d = h.id, d
    return best


def parse_elements(elements: list[dict], district: str, include_chains: bool) -> list[dict]:
    out = []
    for e in elements:
        tags = e.get("tags", {})
        name = tags.get("name:en") or tags.get("name")
        if not name:
            continue
        if not include_chains and _is_chain(tags):
            continue
        lat = e.get("lat") or (e.get("center") or {}).get("lat")
        lng = e.get("lon") or (e.get("center") or {}).get("lon")
        if lat is None or lng is None:
            continue
        extra = {k: tags[k] for k in ("opening_hours", "website", "phone", "cuisine", "addr:street",
                                      "addr:city", "name:kn", "outdoor_seating", "internet_access",
                                      "diet:vegetarian") if k in tags}
        out.append({
            "osm_id": f"{e['type']}/{e['id']}", "name": name.strip()[:200],
            "lat": float(lat), "lng": float(lng), "district": district, "extra": extra,
        })
    return out


def import_district(db, district: str, hubs, include_chains: bool, dry_run: bool) -> tuple[int, int]:
    hint = OSM_NAME_HINT.get(district, district)
    data = _post(QUERY_ONE.replace("{name}", f"({hint})"))
    rows = parse_elements(data.get("elements", []), district, include_chains)
    inserted = updated = 0
    for r in rows:
        existing = db.query(Spot).filter(Spot.osm_id == r["osm_id"]).first()
        if dry_run:
            inserted += 0 if existing else 1
            continue
        if existing:
            existing.name, existing.latitude, existing.longitude = r["name"], r["lat"], r["lng"]
            existing.extra = {**(existing.extra or {}), **r["extra"]}
            updated += 1
            continue
        db.add(Spot(
            name=r["name"], category="cafe", latitude=r["lat"], longitude=r["lng"],
            district=r["district"], destination_id=_nearest_hub_id(hubs, r["lat"], r["lng"]),
            is_hidden=False, status="approved", source="osm", osm_id=r["osm_id"],
            best_months=[], tags=[], extra=r["extra"],
        ))
        inserted += 1
    if not dry_run:
        db.commit()
    return inserted, updated


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--district", help="Only this district")
    p.add_argument("--include-chains", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.district:
        d = normalize_district(args.district)
        if not d:
            sys.exit(f"Unknown Karnataka district: {args.district}")
        districts = [d]
    else:
        districts = KARNATAKA_DISTRICTS

    db = SessionLocal()
    total_new = total_upd = 0
    try:
        hubs = _hubs(db)
        for d in districts:
            print(f"→ {d}")
            try:
                n, u = import_district(db, d, hubs, args.include_chains, args.dry_run)
            except RuntimeError as e:
                print(f"    skipped: {e}")
                continue
            print(f"    {n} new, {u} updated")
            total_new += n
            total_upd += u
            time.sleep(2)  # be polite to the public Overpass servers
    finally:
        db.close()
    print(f"✓ Cafes: {total_new} new, {total_upd} updated{' (dry run)' if args.dry_run else ''}")


if __name__ == "__main__":
    main()
