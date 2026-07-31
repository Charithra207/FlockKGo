"""
itinerary_builder.py — Daily Itinerary Guide builder for the On-Trip Concierge.

Generates a deterministic hourly itinerary for each day of the trip.
No LLM call — purely rule-based so it works offline and is instant.

Structure per day:
  06:30 – Morning exercise / yoga (if adventure/nature vibes)
  07:00 – Breakfast at group-friendly restaurant
  09:00 – Morning activity block (from destination vibes)
  13:00 – Lunch (family-friendly / local cuisine)
  14:30 – Afternoon activity block
  18:00 – Sunset viewpoint / free time
  20:00 – Dinner at group-friendly restaurant
  22:00 – Evening free time / checklist review

Meal suggestions are derived from destination vibes + India-specific
restaurant categories (Thali, Dhaba, Vegetarian, Seafood, etc.).
"""

from __future__ import annotations

from typing import Any


# ── Activity blocks per vibe ───────────────────────────────────────────────────

_MORNING_ACTIVITIES: dict[str, list[str]] = {
    "adventure":    ["Guided Trek / Hike (depart early for summit views)", "River Rafting (book slots in advance)"],
    "beach":        ["Sunrise beach walk", "Kayaking or paddleboarding session"],
    "wildlife":     ["Morning jungle safari (6–9 AM golden hour)", "Birdwatching walk with local guide"],
    "cultural":     ["Temple / monument visit (cooler in mornings)", "Local market walk and street food exploration"],
    "nature":       ["Nature trail / waterfall hike", "Botanical garden or lake walk"],
    "spiritual":    ["Morning aarti / puja at local temple / ghats", "Yoga or meditation session"],
    "relaxation":   ["Spa / Ayurvedic massage session", "Lazy morning at the property"],
    "food":         ["Cooking class or local food tour", "Breakfast at a famous local joint"],
    "nightlife":    ["Late morning – explore old town bazaars", "Museum or art gallery visit"],
    "city":         ["Metro / auto-rickshaw tour of old quarter", "Heritage walk with a local guide"],
}

_AFTERNOON_ACTIVITIES: dict[str, list[str]] = {
    "adventure":    ["Rock climbing / rappelling session", "Zip-lining or bungee (if available at destination)"],
    "beach":        ["Beach volleyball / frisbee", "Snorkelling or scuba intro dive"],
    "wildlife":     ["Afternoon game drive / boat safari", "Nature photography walk"],
    "cultural":     ["Museum / fort / palace visit", "Craft workshop (pottery, weaving, block-printing)"],
    "nature":       ["Cycling through scenic trails", "Picnic at a scenic viewpoint"],
    "spiritual":    ["Visit to a lesser-known temple or ashram", "Kirtan / bhajan session (open to visitors)"],
    "relaxation":   ["Pool / resort time", "Book reading at a café with a view"],
    "food":         ["Street food crawl", "Visit to a local spice market or farm"],
    "nightlife":    ["Late afternoon: rooftop café with views", "Live music venue or cultural show"],
    "city":         ["Shopping district exploration", "Modern art museum or quirky café district"],
}

_DEFAULT_MORNING = ["Explore the main town / market area", "Visit the most popular local attraction"]
_DEFAULT_AFTERNOON = ["Leisure walk and photography", "Rest time or opt-in activity"]


# ── Meal suggestions ───────────────────────────────────────────────────────────

_BREAKFAST_SPOTS: dict[str, str] = {
    "adventure":    "Local Dhaba serving parathas and chai — fuel up before the trek",
    "beach":        "Beachside shack serving coconut water, idli, and fresh fruit",
    "wildlife":     "Forest lodge breakfast — poha, upma, and omelette station",
    "cultural":     "Heritage café or rooftop restaurant with fort views",
    "nature":       "Hilltop café or riverside breakfast spot",
    "spiritual":    "Ashram prasad breakfast or a vegetarian café near the ghats",
    "relaxation":   "Resort buffet or in-room breakfast",
    "food":         "Iconic local breakfast joint (ask locals for the oldest one in town)",
    "default":      "Group-friendly café or hotel restaurant",
}

_LUNCH_SPOTS: dict[str, str] = {
    "adventure":    "Trail-side Maggi point or local Dhaba (pack sandwiches for summit days)",
    "beach":        "Seafood restaurant on the beach strip — fish thali or prawn curry",
    "wildlife":     "Forest rest house canteen or nearby Dhaba",
    "cultural":     "Vegetarian Thali restaurant in the old quarter",
    "nature":       "Riverside or lakeside Dhaba with local specialties",
    "spiritual":    "100% vegetarian Thali — saatvik food as per local tradition",
    "relaxation":   "Poolside lunch or resort restaurant",
    "food":         "A different local restaurant each day — ask your hotel for recommendations",
    "default":      "Vegetarian / multi-cuisine restaurant that can accommodate the full group",
}

_DINNER_SPOTS: dict[str, str] = {
    "adventure":    "Bonfire dinner at camp / lodge with barbeque",
    "beach":        "Sunset rooftop restaurant or shack on the beach",
    "wildlife":     "Candle-lit outdoor dinner at the resort",
    "cultural":     "Traditional regional Thali dinner with cultural performance",
    "nature":       "Hilltop restaurant for valley views at dusk",
    "spiritual":    "Ghat-side café or rooftop with river view (satvik options available)",
    "relaxation":   "Fine-dining restaurant at the resort",
    "food":         "Progressive dinner — starters at one place, mains and dessert at others",
    "default":      "Group table at a family-friendly multi-cuisine restaurant",
}


def build_itinerary(
    destination_name: str,
    duration_days: int,
    vibes: list[str] | None = None,
    group_size: int = 4,
    has_kids: bool = False,
) -> list[dict[str, Any]]:
    """
    Build a day-by-day hourly itinerary.

    Parameters
    ----------
    destination_name: str    — For display only
    duration_days: int       — Number of days at the destination
    vibes: list[str]         — Destination vibes (beach, adventure, etc.)
    group_size: int          — Number of people (affects activity suggestions)
    has_kids: bool           — If True, skips nightlife / adventure extremes

    Returns
    -------
    list[dict]
        One dict per day: {day_number, date_label, slots: [{time, activity, type}]}
    """
    vibes = vibes or []
    primary_vibe = vibes[0] if vibes else "default"
    secondary_vibe = vibes[1] if len(vibes) > 1 else primary_vibe

    # Pick a vibe key present in our dicts, falling back to "default"
    def _pick(d: dict, vibe: str) -> str:
        return d.get(vibe) or d.get("default") or list(d.values())[0]

    morning_acts = _MORNING_ACTIVITIES.get(primary_vibe, _DEFAULT_MORNING)
    afternoon_acts = _AFTERNOON_ACTIVITIES.get(secondary_vibe, _DEFAULT_AFTERNOON)

    days = []
    for day_num in range(1, min(duration_days, 14) + 1):
        # Rotate activity suggestions across days
        morning_act = morning_acts[(day_num - 1) % len(morning_acts)]
        afternoon_act = afternoon_acts[(day_num - 1) % len(afternoon_acts)]

        # First and last day have travel buffers
        is_arrival = (day_num == 1)
        is_departure = (day_num == duration_days)

        slots = []

        if is_arrival:
            slots.append({"time": "12:00", "activity": "Check-in and freshen up at accommodation", "type": "logistics"})
            slots.append({"time": "13:00", "activity": _pick(_LUNCH_SPOTS, primary_vibe), "type": "meal"})
            slots.append({"time": "15:00", "activity": "Orientation walk — explore the neighbourhood", "type": "leisure"})
            slots.append({"time": "18:00", "activity": "Sunset at the main viewpoint / promenade", "type": "leisure"})
            slots.append({"time": "20:00", "activity": _pick(_DINNER_SPOTS, primary_vibe), "type": "meal"})
        elif is_departure:
            slots.append({"time": "07:00", "activity": _pick(_BREAKFAST_SPOTS, primary_vibe), "type": "meal"})
            slots.append({"time": "09:00", "activity": "Last-minute souvenir shopping / market visit", "type": "leisure"})
            slots.append({"time": "11:00", "activity": "Check-out and luggage storage at hotel", "type": "logistics"})
            slots.append({"time": "12:30", "activity": _pick(_LUNCH_SPOTS, "default"), "type": "meal"})
            slots.append({"time": "14:00", "activity": "Head to bus / train / airport (confirm departure time)", "type": "logistics"})
        else:
            slots.append({"time": "06:30", "activity": "Morning warm-up / stretch or yoga on terrace", "type": "wellness"})
            slots.append({"time": "07:30", "activity": _pick(_BREAKFAST_SPOTS, primary_vibe), "type": "meal"})
            slots.append({"time": "09:00", "activity": morning_act, "type": "activity"})
            slots.append({"time": "13:00", "activity": _pick(_LUNCH_SPOTS, primary_vibe), "type": "meal"})
            slots.append({"time": "14:30", "activity": afternoon_act, "type": "activity"})
            slots.append({"time": "17:30", "activity": "Sunset viewpoint or free leisure time", "type": "leisure"})
            slots.append({"time": "19:30", "activity": "Group checklist review + plan for tomorrow", "type": "admin"})
            slots.append({"time": "20:00", "activity": _pick(_DINNER_SPOTS, primary_vibe), "type": "meal"})

        days.append({
            "day_number": day_num,
            "day_label": f"Day {day_num}" + (" (Arrival)" if is_arrival else " (Departure)" if is_departure else ""),
            "destination": destination_name,
            "slots": slots,
        })

    return days
