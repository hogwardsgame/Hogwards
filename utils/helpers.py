import re
import random
from config import HOUSES, HOUSE_SPELLS, XP_PER_LEVEL_BASE, XP_LEVEL_MULT


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
    """Сколько опыта нужно для перехода с текущего уровня на следующий.

    Важно: эта формула должна быть такой же, как в database.add_xp().
    Раньше здесь стояла старая формула 500/1.15, а в database.py — новая
    1200/1.20. Из-за этого в профиле могло быть написано, что опыта уже
    хватает, но уровень не повышался.
    """
    return int(XP_PER_LEVEL_BASE * level * (XP_LEVEL_MULT ** (level - 1)))


def house_emoji(house: str) -> str:
    return {
        "gryffindor": "⚡",
        "slytherin":  "🐍",
        "ravenclaw":  "🦅",
        "hufflepuff": "🦡",
    }.get(house, "🏰")


def medal(pos: int) -> str:
    return {1: "🥇", 2: "🥈", 3: "🥉"}.get(pos, f"{pos}.")


def md_escape(text: str) -> str:
    """Экранирует спецсимволы Markdown v1 для безопасного использования в parse_mode='Markdown'."""
    # В Markdown v1 нужно экранировать: _ * ` [
    for ch in ('_', '*', '`', '['):
        text = text.replace(ch, '\\' + ch)
    return str(text)
