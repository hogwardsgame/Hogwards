import json
import os
from functools import lru_cache

_cache: dict[str, dict] = {}


@lru_cache(maxsize=10)
def _load_locale(lang: str) -> dict:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "locales", f"{lang}.json")
    fallback = os.path.join(base, "locales", "ru.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        with open(fallback, encoding="utf-8") as f:
            return json.load(f)


# user_id → lang mapping (in-memory cache, refreshed from DB on demand)
_user_lang: dict[int, str] = {}


def set_cached_lang(user_id: int, lang: str):
    _user_lang[user_id] = lang


def get_cached_lang(user_id: int) -> str:
    return _user_lang.get(user_id, "ru")


def t(user_id: int, key: str, **kwargs) -> str:
    lang = _user_lang.get(user_id, "ru")
    locale = _load_locale(lang)
    text = locale.get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return text


def t_lang(lang: str, key: str, **kwargs) -> str:
    locale = _load_locale(lang)
    text = locale.get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return text
