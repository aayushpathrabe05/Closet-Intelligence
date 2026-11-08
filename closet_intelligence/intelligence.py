from collections import Counter
from itertools import islice, product

WEIGHTS = {"colour": 0.30, "occasion": 0.25, "weather": 0.20, "preference": 0.15, "diversity": 0.10}
ALIASES = {"off-white": "cream", "ivory": "cream", "charcoal": "grey", "gray": "grey", "denim": "blue", "tan": "beige", "camel": "beige", "wine": "burgundy"}
NEUTRALS = {"black", "white", "cream", "beige", "brown", "grey", "navy"}
COMPATIBLE = {"black": NEUTRALS | {"red", "green", "olive", "pink", "burgundy", "yellow"}, "white": NEUTRALS | {"blue", "green", "olive", "red", "pink", "purple", "yellow", "orange", "burgundy"}, "cream": NEUTRALS | {"blue", "green", "olive", "burgundy", "pink", "orange"}, "beige": NEUTRALS | {"blue", "green", "olive", "burgundy", "brown", "orange"}, "brown": NEUTRALS | {"cream", "beige", "blue", "green", "olive", "burgundy", "orange"}, "grey": NEUTRALS | {"blue", "green", "olive", "pink", "burgundy", "red", "purple"}, "navy": NEUTRALS | {"blue", "green", "olive", "red", "pink", "yellow", "orange"}, "blue": NEUTRALS | {"green", "olive", "yellow", "orange", "burgundy", "pink"}, "green": NEUTRALS | {"blue", "olive", "yellow", "orange", "pink", "burgundy"}, "olive": NEUTRALS | {"blue", "green", "yellow", "orange", "burgundy"}, "red": NEUTRALS | {"blue", "navy", "green", "olive", "pink", "burgundy"}, "burgundy": NEUTRALS | {"blue", "navy", "green", "olive", "pink", "red"}, "pink": NEUTRALS | {"blue", "navy", "green", "olive", "red", "burgundy", "purple"}, "purple": NEUTRALS | {"blue", "pink", "green"}, "yellow": NEUTRALS | {"blue", "navy", "green", "olive", "purple"}, "orange": NEUTRALS | {"blue", "navy", "green", "olive", "purple"}}
TARGET_FORMALITY = {"formal event": 5, "wedding": 5, "interview": 4, "office": 4, "party": 4, "festive event": 4, "date": 3, "college": 2, "casual": 2, "travel": 2}


def normalize_colour(value):
    value = " ".join((value or "").casefold().strip().split())
    return ALIASES.get(value, value)


def colour_score(items):
    colours = list(dict.fromkeys(normalize_colour(value) for item in items for value in (getattr(item, "primary_colour", ""), getattr(item, "secondary_colour", "")) if value))
    if len(colours) <= 1:
        return 78
    pairs = [(a, b) for a, b in product(colours, colours) if a != b]
    compatible = sum(b in COMPATIBLE.get(a, set()) or a in COMPATIBLE.get(b, set()) for a, b in pairs)
    return round(55 + 45 * compatible / max(1, len(pairs)))


def occasion_score(items, occasion):
    target = TARGET_FORMALITY.get(occasion.casefold(), 3)
    matching = sum(occasion.casefold() in {value.casefold() for value in item.occasion_list()} for item in items)
    average = sum(max(1, min(5, item.formality or 3)) for item in items) / len(items)
    return round(min(100, max(0, 100 - abs(average - target) * 22) + matching * 10))


def weather_score(items, weather):
    temperature = int(weather.get("temperature", 20))
    categories = {item.category.casefold() for item in items}
    seasons = {getattr(item, "season", "all season").casefold() for item in items}
    score = 82
    if temperature < 12:
        score += 12 if "outerwear" in categories else -18
        score += 5 if "autumn/winter" in seasons else 0
    if temperature > 27:
        score -= 18 if "outerwear" in categories else 0
        score += 5 if "spring/summer" in seasons else 0
    if weather.get("rain") and "outerwear" in categories:
        score += 8
    return max(0, min(100, score))


def _candidate_combinations(groups, limit=500):
    tops, bottoms, dresses, shoes = (groups.get(key, []) for key in ("Tops", "Bottoms", "Dresses", "Shoes"))
    additions = groups.get("Outerwear", []) + groups.get("Bags", []) + groups.get("Accessories", [])
    base = list(islice(product(tops, bottoms, shoes), limit))
    base.extend(islice(product(dresses, shoes), max(0, limit - len(base))))
    for combo in base:
        yield list(combo)
        for addition in additions[:3]:
            yield list(combo) + [addition]


def recommend(items, occasion="Casual", weather=None, profile=None, recent_item_ids=None, excluded_categories=None):
    weather = weather or {"temperature": 20, "rain": False}
    recent_item_ids = set(recent_item_ids or set())
    excluded_categories = set(excluded_categories or set())
    clean = [item for item in items if item.availability == "Clean" and item.category not in excluded_categories]
    groups = {category: sorted([item for item in clean if item.category == category], key=lambda item: (getattr(item, "worn_count", 0) or 0, item.id)) for category in ("Tops", "Bottoms", "Dresses", "Shoes", "Outerwear", "Bags", "Accessories")}
    preferred_colours = {normalize_colour(value) for value in (profile.get("preferred_colours") if profile else [])}
    preferred_styles = {value.casefold() for value in (profile.get("preferred_styles") if profile else [])}
    preferred_occasions = {value.casefold() for value in (profile.get("preferred_occasions") if profile else [])}
    scored = []
    for combo in _candidate_combinations(groups):
        categories = {item.category for item in combo}
        if not ("Shoes" in categories and ("Dresses" in categories or {"Tops", "Bottoms"} <= categories)):
            continue
        c, a, w = colour_score(combo), occasion_score(combo, occasion), weather_score(combo, weather)
        colours = {normalize_colour(item.primary_colour) for item in combo}
        styles = {getattr(item, "style", "").casefold() for item in combo if getattr(item, "style", "")}
        preference = 55 + (20 if preferred_colours & colours else 0) + (15 if preferred_styles & styles else 0) + (10 if occasion.casefold() in preferred_occasions else 0)
        diversity = max(20, 100 - len(recent_item_ids & {item.id for item in combo}) * 22)
        breakdown = {"colour": c, "occasion": a, "weather": w, "preference": min(100, preference), "diversity": diversity}
        final = round(sum(breakdown[key] * WEIGHTS[key] for key in WEIGHTS), 1)
        reasons = ["the colours coordinate naturally" if c >= 80 else "the colour contrast is intentional", f"it suits a {occasion.casefold()} setting" if a >= 80 else "it balances the requested formality", "the pieces fit the selected weather" if w >= 80 else "the weather score was considered", "your saved preferences are represented" if preference >= 70 else "it introduces some wardrobe variety", "recently worn pieces were avoided" if diversity >= 75 else "the look includes recently used pieces with a lighter penalty"]
        scored.append((final, combo, breakdown, "This look was selected because " + ", ".join(reasons) + "."))
    scored.sort(key=lambda result: result[0], reverse=True)
    selected, signatures = [], set()
    for result in scored:
        signature = frozenset(item.id for item in result[1])
        if signature in signatures or any(len(signature ^ other) <= 1 for other in signatures):
            continue
        selected.append(result)
        signatures.add(signature)
        if len(selected) == 5:
            break
    return selected


def gap_analysis(items):
    counts = Counter(item.category for item in items)
    suggestions = []
    if counts["Bottoms"] < max(2, counts["Tops"] // 2):
        suggestions.append({"title": "A versatile bottom", "text": "Your tops are asking for more partners. A neutral trouser or tailored skirt would unlock new combinations.", "category": "Bottoms"})
    if counts["Shoes"] < 2:
        suggestions.append({"title": "A second shoe story", "text": "A refined everyday shoe would give your current pieces more range across occasions.", "category": "Shoes"})
    if not suggestions:
        suggestions.append({"title": "Keep discovering", "text": "Your wardrobe has a healthy balance. Try rotating your least-worn pieces before adding anything new.", "category": "Use what you own"})
    return suggestions
