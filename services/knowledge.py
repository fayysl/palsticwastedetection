"""Plastic knowledge base: turns raw AI detections into consistent guidance.

The AI model tells us *what* it sees; this module decides *what to do about it*,
so actions stay the same no matter which free model answered.
Weights and CO2 factors are rough averages, meant for awareness, not auditing.
"""

# Resin identification codes (the number inside the recycling triangle).
RESINS = {
    1: {"code": "PET", "name": "Polyethylene terephthalate", "recyclable": "widely",
        "examples": "water & soda bottles, food jars"},
    2: {"code": "HDPE", "name": "High-density polyethylene", "recyclable": "widely",
        "examples": "milk jugs, detergent & shampoo bottles"},
    3: {"code": "PVC", "name": "Polyvinyl chloride", "recyclable": "rarely",
        "examples": "pipes, blister packs, cling film"},
    4: {"code": "LDPE", "name": "Low-density polyethylene", "recyclable": "drop-off",
        "examples": "carry bags, bread bags, films"},
    5: {"code": "PP", "name": "Polypropylene", "recyclable": "often",
        "examples": "food tubs, bottle caps, takeaway boxes"},
    6: {"code": "PS", "name": "Polystyrene", "recyclable": "rarely",
        "examples": "foam cups, clamshells, disposable cutlery"},
    7: {"code": "OTHER", "name": "Other / mixed plastics", "recyclable": "rarely",
        "examples": "multi-layer pouches, polycarbonate, bioplastics"},
}

# Recycling savings: ~1.5 kg CO2e avoided per kg of plastic recycled instead of
# landfilled/incinerated (typical LCA range is 1-2.5).
CO2_SAVED_PER_KG = 1.5

CATEGORIES = {
    "bottle": {
        "label": "Plastic bottle", "icon": "🥤", "default_resin": 1, "avg_weight_g": 25,
        "bin": "recycle", "segregation": "Dry recyclables (blue bin)",
        "actions": [
            "Empty any liquid completely.",
            "Rinse quickly, then crush it flat to save space.",
            "Put the cap back on (caps are recycled too) and place it in the blue recycling bin.",
        ],
        "reuse": "Refill it for watering plants or turn it into a planter.",
    },
    "bag": {
        "label": "Plastic bag", "icon": "🛍️", "default_resin": 4, "avg_weight_g": 6,
        "bin": "drop_off", "segregation": "Soft plastics (store drop-off)",
        "actions": [
            "Do NOT put it in the curbside recycling bin — bags jam sorting machines.",
            "Bundle clean, dry bags together inside one bag.",
            "Return them to a supermarket soft-plastic drop-off point.",
        ],
        "reuse": "Reuse it for shopping or as a bin liner; switch to a cloth bag.",
    },
    "food_container": {
        "label": "Food container", "icon": "🥡", "default_resin": 5, "avg_weight_g": 30,
        "bin": "recycle", "segregation": "Dry recyclables (after cleaning)",
        "actions": [
            "Scrape out all food leftovers into the organic/wet bin.",
            "Rinse off grease — dirty containers contaminate whole recycling batches.",
            "Check the resin number: #1, #2, #5 go to recycling; foam #6 goes to general waste.",
        ],
        "reuse": "Clean tubs make great storage for leftovers, screws or seeds.",
    },
    "packaging": {
        "label": "Plastic packaging / wrapper", "icon": "📦", "default_resin": 7, "avg_weight_g": 10,
        "bin": "general", "segregation": "Non-recyclable dry waste",
        "actions": [
            "Chip packets and multi-layer wrappers are usually not recyclable.",
            "Clean films (#4 LDPE) can go with soft-plastic drop-off.",
            "Otherwise place in general dry waste — never burn it.",
        ],
        "reuse": "Choose products with less or recyclable packaging next time.",
    },
    "cup": {
        "label": "Disposable cup", "icon": "🥛", "default_resin": 6, "avg_weight_g": 12,
        "bin": "general", "segregation": "General waste (unless marked #1/#5)",
        "actions": [
            "Foam (#6) cups go to general waste.",
            "Clear #1 PET or #5 PP cups can be rinsed and recycled.",
            "Separate lids and straws before disposal.",
        ],
        "reuse": "Carry a reusable cup or bottle.",
    },
    "cutlery_straw": {
        "label": "Straw / cutlery", "icon": "🥄", "default_resin": 6, "avg_weight_g": 3,
        "bin": "general", "segregation": "General waste",
        "actions": [
            "Too small for recycling machines — put in general waste.",
            "Keep it out of drains and open spaces; it harms wildlife.",
        ],
        "reuse": "Say 'no straw, no cutlery' when ordering takeaway.",
    },
    "container_hdpe": {
        "label": "Jug / detergent bottle", "icon": "🧴", "default_resin": 2, "avg_weight_g": 60,
        "bin": "recycle", "segregation": "Dry recyclables (blue bin)",
        "actions": [
            "Empty and rinse (chemical residue must be removed).",
            "Keep the cap on and place it in the blue recycling bin.",
        ],
        "reuse": "Reuse as a watering can or storage container.",
    },
    "other": {
        "label": "Other plastic item", "icon": "♻️", "default_resin": 7, "avg_weight_g": 20,
        "bin": "general", "segregation": "Check local rules",
        "actions": [
            "Look for the resin number on the item.",
            "#1, #2 and #5 are commonly recyclable; others usually go to general waste.",
            "Large or hard plastics may be accepted at a municipal recycling centre.",
        ],
        "reuse": "Repair or donate if it is still usable.",
    },
}

BINS = {
    "recycle": {"label": "Recycle", "color": "#2563eb"},
    "drop_off": {"label": "Drop-off point", "color": "#d97706"},
    "general": {"label": "General waste", "color": "#6b7280"},
}

POINTS = {"recycle": 10, "drop_off": 8, "general": 3}

LEVELS = [
    (0, "none", "No plastic detected"),
    (1, "low", "Low — a single item"),
    (4, "medium", "Medium — several items, segregate before disposal"),
    (10, "high", "High — heavy plastic waste, consider a clean-up drive / bulk drop-off"),
]


def _as_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _level_for(count):
    level = LEVELS[0]
    for threshold, key, text in LEVELS:
        if count >= threshold:
            level = (threshold, key, text)
    return {"key": level[1], "text": level[2]}


def enrich(detection):
    """Merge a raw AI detection with the knowledge base.

    `detection` is the model's JSON: {"items": [...], "summary": str, ...}.
    Returns the full analysis the frontend renders and the store saves.
    """
    items = []
    for raw in detection.get("items") or []:
        if not isinstance(raw, dict):
            continue
        cat_key = raw.get("category") if raw.get("category") in CATEGORIES else "other"
        cat = CATEGORIES[cat_key]
        resin = _as_int(raw.get("resin_code"), cat["default_resin"])
        if resin not in RESINS:
            resin = cat["default_resin"]
        count = max(1, min(_as_int(raw.get("count"), 1), 500))
        bin_key = cat["bin"]
        # A food container made of foam is not recyclable even though the category usually is.
        if cat_key == "food_container" and resin in (3, 6, 7):
            bin_key = "general"
        if cat_key == "cup" and resin in (1, 5):
            bin_key = "recycle"
        weight_kg = cat["avg_weight_g"] * count / 1000
        co2 = weight_kg * CO2_SAVED_PER_KG if bin_key != "general" else 0.0
        try:
            confidence = float(raw.get("confidence", 0.7))
        except (TypeError, ValueError):
            confidence = 0.7
        items.append({
            "name": str(raw.get("name") or cat["label"])[:80],
            "category": cat_key,
            "icon": cat["icon"],
            "count": count,
            "confidence": round(max(0.0, min(confidence, 1.0)), 2),
            "condition": str(raw.get("condition") or "unknown")[:30],
            "resin": {"number": resin, **RESINS[resin]},
            "bin": {"key": bin_key, **BINS[bin_key]},
            "segregation": cat["segregation"],
            "actions": cat["actions"],
            "reuse": cat["reuse"],
            "weight_kg": round(weight_kg, 3),
            "co2_saved_kg": round(co2, 3),
            "points": POINTS[bin_key] * count,
        })

    total = sum(i["count"] for i in items)
    tips = [str(t)[:200] for t in (detection.get("tips") or []) if t][:3]
    return {
        "plastic_detected": total > 0,
        "summary": str(detection.get("summary") or "")[:400],
        "items": items,
        "total_items": total,
        "level": _level_for(total),
        "recyclable_items": sum(i["count"] for i in items if i["bin"]["key"] != "general"),
        "total_weight_kg": round(sum(i["weight_kg"] for i in items), 3),
        "co2_saved_kg": round(sum(i["co2_saved_kg"] for i in items), 3),
        "points": sum(i["points"] for i in items),
        "tips": tips,
    }
