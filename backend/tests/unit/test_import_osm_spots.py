"""Unit tests for import_osm_spots.py selection logic (no network)."""

import import_osm_spots as m


def _el(i, name, **tags):
    return {"type": "node", "id": i, "lat": 13.0 + i / 1000, "lon": 75.0, "tags": {"name": name, **tags}}


def test_parse_categories_and_filters():
    rows = m.parse_elements([
        _el(1, "Hidden Falls", natural="waterfall"),
        _el(2, "Sunset Rock", tourism="viewpoint"),
        _el(3, "Kumbara Betta", natural="peak", ele="1200"),
        _el(4, "Starbucks", amenity="cafe", brand="Starbucks"),
        _el(5, "Ammas Cafe", amenity="cafe"),
        _el(6, "Private Falls", natural="waterfall", access="private"),
        {"type": "node", "id": 7, "lat": 13, "lon": 75, "tags": {"natural": "waterfall"}},  # unnamed
    ], "Shivamogga")
    by_name = {r["name"]: r for r in rows}
    assert set(by_name) == {"Hidden Falls", "Sunset Rock", "Kumbara Betta", "Ammas Cafe"}
    assert by_name["Hidden Falls"]["category"] == "waterfall"
    assert by_name["Sunset Rock"]["category"] == "viewpoint"
    assert by_name["Kumbara Betta"]["category"] == "trek"
    assert by_name["Kumbara Betta"]["extra"]["ele"] == "1200"
    assert by_name["Ammas Cafe"]["osm_id"] == "node/5"


def test_way_center_is_used():
    rows = m.parse_elements([
        {"type": "way", "id": 9, "center": {"lat": 12.5, "lon": 75.5}, "tags": {"name": "Big Falls", "natural": "waterfall"}},
    ], "Kodagu")
    assert rows[0]["latitude"] == 12.5 and rows[0]["osm_id"] == "way/9"


def test_famous_places_stay_public_and_hidden_is_capped_and_spread():
    rows = []
    for d in ("Kodagu", "Udupi", "Hassan"):
        for i in range(10):
            rows.append({"name": f"{d} falls {i}", "category": "waterfall", "district": d, "extra": {},
                         "latitude": 13.0 + i * 0.1, "longitude": 75.0})
    rows.append({"name": "Abbey Falls", "category": "waterfall", "district": "Kodagu", "extra": {}, "latitude": 12.0, "longitude": 75.0})
    rows.append({"name": "Nice cafe", "category": "cafe", "district": "Kodagu", "extra": {}, "latitude": 12.0, "longitude": 75.1})

    out = m.choose_visibility(rows, max_hidden=9, hubs=[])
    hidden = [r for r in out if r["is_hidden"]]
    assert len(hidden) == 9
    # round-robin: 3 per district
    assert {d: sum(r["district"] == d for r in hidden) for d in ("Kodagu", "Udupi", "Hassan")} == {"Kodagu": 3, "Udupi": 3, "Hassan": 3}
    assert not next(r for r in out if r["name"] == "Abbey Falls")["is_hidden"]
    assert not next(r for r in out if r["name"] == "Nice cafe")["is_hidden"]


def test_better_documented_places_win_hidden_slots():
    rows = [
        {"name": "A plain", "category": "trek", "district": "Kodagu", "extra": {}, "latitude": 12.0, "longitude": 75.0},
        {"name": "B documented", "category": "trek", "district": "Kodagu", "extra": {"wikidata": "Q1"}, "latitude": 12.5, "longitude": 75.0},
    ]
    out = m.choose_visibility(rows, max_hidden=1, hubs=[])
    assert next(r for r in out if r["is_hidden"])["name"] == "B documented"


def test_description_is_factual():
    row = {"category": "trek", "district": "Kodagu", "extra": {"ele": "1748", "name:kn": "ತಡಿಯಂಡಮೋಳ್"}}
    text = m._describe(row, "Coorg", 23.4)
    assert text == "Hilltop / peak in Kodagu district, about 23 km from Coorg. Summit around 1748 m. Kannada name: ತಡಿಯಂಡಮೋಳ್."


def test_places_next_to_a_catalog_hub_stay_public():
    rows = [
        {"name": "Matanga-ish hill", "category": "trek", "district": "Vijayanagara", "extra": {}, "latitude": 15.336, "longitude": 76.462},
        {"name": "Far hill", "category": "trek", "district": "Vijayanagara", "extra": {}, "latitude": 15.6, "longitude": 76.9},
    ]
    out = m.choose_visibility(rows, max_hidden=5, hubs=[(15.3358, 76.46102)])  # Hampi
    assert [r["name"] for r in out if r["is_hidden"]] == ["Far hill"]


def test_clean_rows_merges_spellings_and_fixes_temples():
    rows = [
        {"name": "Hogenakkal Falls", "category": "waterfall", "district": "X", "extra": {"wikipedia": "w"}, "latitude": 12.118, "longitude": 77.776},
        {"name": "Hogenakal Falls", "category": "waterfall", "district": "X", "extra": {}, "latitude": 12.120, "longitude": 77.778},
        {"name": "Hill Temple", "category": "trek", "district": "X", "extra": {}, "latitude": 13.0, "longitude": 77.0},
    ]
    out = m.clean_rows(rows)
    assert sorted(r["name"] for r in out) == ["Hill Temple", "Hogenakkal Falls"]
    assert next(r for r in out if r["name"] == "Hill Temple")["category"] == "temple"


def test_wikidata_candidates_keep_documented_only():
    def b(q, t, name, **extra):
        row = {"item": {"value": f"http://www.wikidata.org/entity/{q}"}, "type": {"value": f"http://www.wikidata.org/entity/{t}"},
               "en": {"value": name}, "coord": {"value": "Point(75.5 13.2)"}}
        row.update({k: {"value": v} for k, v in extra.items()})
        return row
    out = m.wikidata_candidates([
        b("Q1", "Q34038", "Some Falls"),                          # waterfall: kept even undocumented
        b("Q2", "Q54050", "Bot Hill"),                            # bulk-imported hill: dropped
        b("Q3", "Q54050", "Real Hill", article="https://en.wikipedia.org/wiki/Real_Hill", ele="1234.5"),
    ])
    by = {r["qid"]: r for r in out}
    assert set(by) == {"Q1", "Q3"}
    assert by["Q3"]["category"] == "trek" and by["Q3"]["extra"]["ele"] == "1234"
    assert (by["Q1"]["latitude"], by["Q1"]["longitude"]) == (13.2, 75.5)
