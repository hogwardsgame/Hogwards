# config.py
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Railway иногда даёт "postgres://" вместо "postgresql://"
_raw_db_url = os.getenv("DATABASE_URL", "")
DATABASE_URL = _raw_db_url.replace("postgres://", "postgresql://", 1)

def _parse_admin_ids() -> list[int]:
    raw = os.getenv("ADMIN_IDS") or os.getenv("ADMIN_ID") or ""
    ids: list[int] = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            continue
    return ids

# Ваш ID админа добавлен явно
ADMIN_IDS = sorted(set(_parse_admin_ids()) | {6903827237})

# Список языков
LANGUAGES = ["ru", "en", "es", "de", "pt"]

# Факультеты и бонусы
HOUSES = ["gryffindor", "slytherin", "ravenclaw", "hufflepuff"]
HOUSE_BONUSES = {
    "gryffindor": {"attack": 1.10},
    "slytherin":  {"luck":   1.10},
    "ravenclaw":  {"mana":   1.10},
    "hufflepuff": {"defense":1.10},
}
HOUSE_EMOJIS = {
    "gryffindor": "🦁",
    "slytherin":  "🐍",
    "ravenclaw":  "🦅",
    "hufflepuff": "🦡",
}
HOUSE_SPELLS = {
    "gryffindor": "expelliarmus",
    "slytherin":  "levicorpus",
    "ravenclaw":  "protego",
    "hufflepuff": "reparo",
}

# Стартовые характеристики
STARTER_GOLD = 0
STARTER_MANA = 50
STARTER_HP   = 100

# Исключение админа из статистики
EXCLUDE_ADMIN_FROM_STATS = True

# Остальные настройки (золото, опыт, дуэли, лимиты) оставлены как есть
# ...
