"""
Персональный ежедневный магазин.

У каждого игрока свой набор предметов, генерируется детерминированно
из user_id + текущей даты. Каждый день — новый набор.
"""
import random
import datetime

SHOP_SIZE = 6  # предметов в персональном магазине


def _today_seed(user_id):
    today = datetime.date.today().isoformat()
    return hash(f"{user_id}_{today}") & 0x7FFFFFFF


def _rarity_price(item):
    rarity_prices = {
        "common": 50, "uncommon": 120, "rare": 300, "very_rare": 700,
        "epic": 1500, "legendary": 4000, "mythical": 10000, "abyssal": 25000,
    }
    base = rarity_prices.get(item.get("rarity", "common"), 100)
    if item.get("type") == "consumable":
        base = item.get("price", base)
    return int(base)


def get_personal_shop(user_id):
    """Детерминированный набор предметов на сегодня для игрока."""
    from game.items import ITEMS
    # пул покупаемых предметов (не квестовые, не уникальные)
    pool = []
    for iid, item in ITEMS.items():
        t = item.get("type", "")
        if t in ("consumable", "equipment", "ingredient", "weapon", "armor", "accessory"):
            # исключаем зелья маны (мы их убрали)
            if "mana_potion" in iid:
                continue
            pool.append(iid)
    pool.sort()  # стабильный порядок до перемешивания
    rng = random.Random(_today_seed(user_id))
    rng.shuffle(pool)
    chosen = pool[:SHOP_SIZE]
    # зелье улучшения умений — всегда в наборе
    if "ability_upgrade_potion" in ITEMS and "ability_upgrade_potion" not in chosen:
        chosen = ["ability_upgrade_potion"] + chosen[:SHOP_SIZE-1]
    out = []
    for iid in chosen:
        item = ITEMS.get(iid, {})
        out.append({
            "id": iid,
            "price": _rarity_price(item),
            "always": iid == "ability_upgrade_potion",
        })
    return out
