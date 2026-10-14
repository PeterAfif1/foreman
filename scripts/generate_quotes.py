"""Generate the synthetic past-quotes set the estimator searches.

    uv run python -m scripts.generate_quotes

SYNTHETIC: every job and price here is made up for the demo. The price bands are
plausible for Southern California residential work, but they are not market data
and nobody should quote from them. A real install would load the contractor's own
past quotes instead.

Each quote belongs to a "family" (a kind of job with a price band). The family is
the answer key for the retrieval eval and is never shown to the model.
"""

import json
import random
from pathlib import Path

OUT = Path(__file__).parent.parent / "foreman" / "knowledge" / "quotes_synthetic.jsonl"
SEED = 471

PLACES = [
    "Burbank",
    "Glendale",
    "Pasadena",
    "Encino",
    "Sherman Oaks",
    "Studio City",
    "Van Nuys",
    "Northridge",
    "Tarzana",
    "Woodland Hills",
    "Reseda",
    "Alhambra",
]

# family: (size range or None, job_types, price band, how many quotes, description variants)
# Price grows with size inside the band, so a bigger job really costs more.
FAMILIES = {
    "shower_retile": (
        (40, 120),
        ["bathroom"],
        (4500, 9000),
        4,
        [
            "Retile walk-in shower walls and pan, new grout and caulk, {size} sq ft of tile.",
            "Tear out cracked shower tile, waterproof, retile {size} sq ft with porcelain.",
            "Shower retile: demo old tile, new backer board, {size} sq ft subway tile.",
        ],
    ),
    "full_bathroom": (
        (45, 120),
        ["bathroom"],
        (18000, 35000),
        4,
        [
            "Full {room} bathroom remodel: new tub/shower, vanity, toilet, tile floor, lighting.",
            "Gut and rebuild {room} bathroom, {size} sq ft, new plumbing fixtures and tile.",
            "Complete {room} bath renovation with walk-in shower, double vanity, heated floor.",
        ],
    ),
    "vanity_toilet": (
        None,
        ["bathroom"],
        (2500, 5500),
        3,
        [
            "Replace vanity, faucet and toilet in {room} bathroom, patch and paint.",
            "Swap out bathroom vanity and toilet, new supply lines and shutoffs.",
        ],
    ),
    "kitchen_refresh": (
        (12, 30),
        ["kitchen"],
        (8000, 16000),
        4,
        [
            "Paint kitchen cabinets, new hardware, quartz countertops, {size} linear ft.",
            "Kitchen refresh: refinish cabinets, new laminate counters and backsplash.",
            "Replace countertops ({size} linear ft) and backsplash, paint cabinet boxes.",
        ],
    ),
    "full_kitchen": (
        (150, 300),
        ["kitchen"],
        (45000, 90000),
        4,
        [
            "Full kitchen remodel: new cabinets, quartz counters, appliances, flooring, lighting.",
            "Gut kitchen, move sink to island, new cabinets and counters, {size} sq ft.",
            "Complete kitchen renovation with custom cabinets and new electrical.",
        ],
    ),
    "roof_replacement": (
        (1200, 2400),
        ["roofing"],
        (14000, 26000),
        4,
        [
            "Tear off and replace asphalt shingle roof, {size} sq ft, new underlayment.",
            "Full roof replacement on {story} house, {size} sq ft, architectural shingles.",
            "Reroof {size} sq ft, replace damaged decking, new flashing and vents.",
        ],
    ),
    "roof_repair": (
        (20, 80),
        ["roofing", "repair"],
        (800, 3500),
        3,
        [
            "Repair roof leak: replace damaged shingles and flashing around chimney.",
            "Patch roof over bedroom, replace {size} sq ft of decking and shingles.",
        ],
    ),
    "storm_damage": (
        None,
        ["roofing", "repair"],
        (1500, 6500),
        3,
        [
            "Storm damage: emergency tarp, remove fallen branch, repair roof decking.",
            "Tree limb through roof, tarp same day, frame repair and reshingle area.",
        ],
    ),
    "gutters": (
        (60, 180),
        ["repair", "other"],
        (1200, 3500),
        3,
        [
            "Replace {size} linear ft of gutters and downspouts, reattach fascia.",
            "New seamless aluminum gutters, {size} linear ft, with guards.",
        ],
    ),
    "lvp_flooring": (
        (350, 900),
        ["flooring"],
        (4000, 9000),
        4,
        [
            "Install luxury vinyl plank in {rooms}, {size} sq ft, remove carpet.",
            "LVP flooring in {rooms}, {size} sq ft, new baseboards.",
        ],
    ),
    "hardwood": (
        (500, 1200),
        ["flooring"],
        (10000, 22000),
        3,
        [
            "Engineered hardwood in {rooms}, {size} sq ft, remove carpet and level subfloor.",
            "Install oak hardwood floors, {size} sq ft, stain and finish.",
        ],
    ),
    "carpet_stairs": (
        (120, 300),
        ["flooring"],
        (2000, 4500),
        3,
        [
            "New carpet on stairs and hallway, {size} sq ft, new pad.",
            "Carpet stairs and upstairs landing, remove old carpet and tack strip.",
        ],
    ),
    "room_addition": (
        (300, 500),
        ["addition"],
        (95000, 170000),
        3,
        [
            "Room addition, {size} sq ft bedroom and full bath off the back of the house.",
            "Build {size} sq ft addition with bedroom and bathroom, permits and plans included.",
        ],
    ),
    "sunroom": (
        (150, 300),
        ["addition"],
        (40000, 80000),
        3,
        [
            "Sunroom addition off the back, {size} sq ft, slab, windows on three sides.",
            "Enclosed patio sunroom, {size} sq ft, insulated roof and new electrical.",
        ],
    ),
    "water_heater": (
        None,
        ["repair"],
        (1800, 3800),
        4,
        [
            "Replace failed 50 gallon gas water heater, new expansion tank, haul away old unit.",
            "Water heater replacement (40 gallon), new seismic straps and venting.",
            "Swap leaking water heater in garage, new shutoff valve and drain pan.",
        ],
    ),
    "pipe_repair": (
        None,
        ["repair"],
        (500, 2500),
        3,
        [
            "Repair burst pipe under kitchen sink, replace section of supply line, dry out.",
            "Fix leaking pipe in wall, open drywall, replace copper section, patch.",
        ],
    ),
    "fence_repair": (
        (20, 80),
        ["repair", "other"],
        (800, 3200),
        3,
        [
            "Rebuild {size} ft of wood fence blown down in wind, new posts set in concrete.",
            "Replace fence panels and two posts on side yard, {size} ft.",
        ],
    ),
    "deck": (
        (150, 450),
        ["other"],
        (12000, 32000),
        4,
        [
            "Build new {size} sq ft composite deck off the back of the house with railing.",
            "Pressure-treated wood deck, {size} sq ft, stairs to the yard.",
            "Replace rotted deck with new {size} sq ft deck, footings and joists.",
        ],
    ),
    "drainage": (
        (40, 120),
        ["other"],
        (5000, 15000),
        3,
        [
            "Regrade backyard and install French drain, {size} linear ft, to fix standing water.",
            "Backyard drainage: channel drains and dry well, regrade side yard.",
        ],
    ),
    "exterior_trim": (
        None,
        ["other"],
        (3000, 7500),
        3,
        [
            "Repaint exterior trim, fascia and doors, minor wood repair, {story} house.",
            "Scrape, prime and paint exterior trim and window frames.",
        ],
    ),
    "handrail": (
        None,
        ["other", "repair"],
        (500, 1600),
        3,
        [
            "Install handrail on front steps, metal, set in concrete.",
            "Add code-compliant handrail to back porch stairs.",
        ],
    ),
}


def fill(template: str, size: int | None, rng: random.Random) -> str:
    return template.format(
        size=size,
        room=rng.choice(["master", "hall", "guest", "upstairs"]),
        rooms=rng.choice(
            ["living room and hallway", "three bedrooms", "living room", "downstairs"]
        ),
        story=rng.choice(["one-story", "two-story"]),
    )


def main() -> None:
    rng = random.Random(SEED)
    quotes = []
    n = 1
    for family, (size_range, job_types, (low, high), count, templates) in FAMILIES.items():
        for i in range(count):
            if size_range:
                smin, smax = size_range
                size = round(rng.uniform(smin, smax) / 10) * 10
                share = (size - smin) / (smax - smin)
            else:
                size, share = None, rng.random()
            noise = rng.uniform(-0.08, 0.08) * (high - low)
            price = min(high, max(low, low + share * (high - low) + noise))
            year, month, day = (
                rng.choice([2024, 2025, 2026]),
                rng.randint(1, 12),
                rng.randint(1, 28),
            )
            quotes.append(
                {
                    "id": f"Q-{n:03d}",
                    "synthetic": True,
                    "family": family,  # answer key only, never shown to the model
                    "date": f"{year}-{month:02d}-{day:02d}",
                    "job_types": job_types,
                    "location": rng.choice(PLACES),
                    "description": fill(templates[i % len(templates)], size, rng),
                    "price_total": round(price / 50) * 50,
                }
            )
            n += 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(json.dumps(q) + "\n" for q in quotes))
    print(f"{len(quotes)} synthetic quotes in {len(FAMILIES)} families -> {OUT}")


if __name__ == "__main__":
    main()
