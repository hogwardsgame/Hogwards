import re
import random
from config import HOUSES, HOUSE_SPELLS


def validate_wizard_name(name: str) -> str | None:
    """Returns error key or None if valid."""
    name = name.strip()
    if len(name) < 2:
        return "name_too_short"
    if len(name) > 24:
        return "name_too_long"
    if not re.match(r"^[\w\s\-]+$", name, re.UNICODE):
        return "name_invalid"
    return None


def pick_house(house_counts: dict) -> str:
    """Weighted random house selection — under-populated houses get +5% chance."""
    total_players = sum(house_counts.values()) or 1
    avg = total_players / len(HOUSES)

    weights = {}
    for house in HOUSES:
        count = house_counts.get(house, 0)
        base = 1.0
        if count < avg:
            base += 0.05 * (avg - count)
        weights[house] = base

    houses = list(weights.keys())
    w = list(weights.values())
    return random.choices(houses, weights=w, k=1)[0]


def get_starter_spell(house: str) -> str:
    return HOUSE_SPELLS.get(house, "expelliarmus")


def xp_needed_for_level(level: int) -> int:
    return int(500 * level * (1.15 ** (level - 1)))


def house_emoji(house: str) -> str:
    return {
        "gryffindor": "⚡",
        "slytherin":  "🐍",
        "ravenclaw":  "🦅",
        "hufflepuff": "🦡",
    }.get(house, "🏰")


def medal(pos: int) -> str:
    return {1: "🥇", 2: "🥈", 3: "🥉"}.get(pos, f"{pos}.")
