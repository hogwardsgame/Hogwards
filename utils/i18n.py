
cached_lang = {}

def set_cached_lang(user_id: int, lang: str):
    """Сохраняет выбранный язык для пользователя"""
    cached_lang[user_id] = lang

def get_cached_lang(user_id: int):
    """Возвращает язык пользователя"""
    return cached_lang.get(user_id, "en")  # по умолчанию английский

# Примеры переводов для кнопок
translations = {
    "duel": {
        "en": "Duel",
        "ru": "Дуэль",
        "de": "Duell",
        "es": "Duelo",
        "pt": "Duelo"
    },
    "help": {
        "en": "Help",
        "ru": "Помощь",
        "de": "Hilfe",
        "es": "Ayuda",
        "pt": "Ajuda"
    },
    "profile": {
        "en": "Profile",
        "ru": "Профиль",
        "de": "Profil",
        "es": "Perfil",
        "pt": "Perfil"
    }
}

def t(key: str, lang: str):
    """Возвращает перевод для ключа"""
    return translations.get(key, {}).get(lang, key)
