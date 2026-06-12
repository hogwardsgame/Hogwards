import re
import random
from config import HOUSES, HOUSE_SPELLS, XP_CURVE_BASE, XP_CURVE_POWER, XP_CURVE_LINEAR


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

    Должна совпадать с формулой в database.add_xp().
    """
    return int(XP_CURVE_BASE * (level ** XP_CURVE_POWER) + XP_CURVE_LINEAR * level)


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


# ── ВИЗУАЛЬНЫЕ ХЕЛПЕРЫ ─────────────────────────────────────────────────────────

def progress_bar(current: int, maximum: int, length: int = 10,
                 fill: str = "█", empty: str = "░") -> str:
    """Текстовый прогресс-бар: ████████░░"""
    if maximum <= 0:
        return empty * length
    ratio = max(0.0, min(1.0, current / maximum))
    filled = int(round(ratio * length))
    return fill * filled + empty * (length - filled)


def hp_bar(current: int, maximum: int, length: int = 10) -> str:
    """Полоска здоровья с цветовым индикатором."""
    ratio = current / maximum if maximum > 0 else 0
    if ratio > 0.6:
        fill = "🟩"
    elif ratio > 0.3:
        fill = "🟨"
    else:
        fill = "🟥"
    filled = int(round(max(0.0, min(1.0, ratio)) * length))
    return fill * filled + "⬛" * (length - filled)


# Ранги по уровню — видимая цель прогресса
RANK_TIERS = [
    (1,  "🐣 Первокурсник"),
    (5,  "📗 Второкурсник"),
    (8,  "📘 Третьекурсник"),
    (11, "📙 Четверокурсник"),
    (14, "🎓 Пятикурсник"),
    (17, "⭐ Староста"),
    (20, "🌟 Староста школы"),
    (24, "🏅 Выпускник"),
    (28, "🧙 Маг"),
    (32, "🔮 Архимаг"),
    (38, "👑 Мастер магии"),
    (45, "✨ Легенда Хогвартса"),
]

def get_rank(level: int) -> str:
    """Звание игрока по уровню."""
    rank = RANK_TIERS[0][1]
    for lvl, name in RANK_TIERS:
        if level >= lvl:
            rank = name
        else:
            break
    return rank

def next_rank(level: int) -> tuple[str, int] | None:
    """Следующее звание и на каком уровне. None если максимум."""
    for lvl, name in RANK_TIERS:
        if level < lvl:
            return name, lvl
    return None


def section(title: str) -> str:
    """Единый заголовок секции с разделителем."""
    return f"{title}\n━━━━━━━━━━━━━━━━━━━━"


def stat_line(emoji: str, label: str, value, bar: str = "") -> str:
    """Единая строка характеристики."""
    bar_part = f"  {bar}" if bar else ""
    return f"{emoji} {label}: {value}{bar_part}"
