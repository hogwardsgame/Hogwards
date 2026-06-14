"""
Mini App API — лёгкий веб-сервер, отдающий данные игрока для Telegram Mini App.

Работает параллельно с ботом (в отдельном потоке).
Безопасность: проверяет подпись Telegram initData, поэтому игрок может
получить ТОЛЬКО свои данные, а не чужие.
"""
import hashlib
import hmac
import json
import logging
import os
import threading
from urllib.parse import parse_qsl

from aiohttp import web

logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")


def _verify_init_data(init_data: str) -> dict | None:
    """Проверяет подпись Telegram initData. Возвращает данные пользователя или None."""
    if not init_data or not BOT_TOKEN:
        return None
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            return None
        # Строка для проверки: все поля кроме hash, отсортированы, через \n
        data_check = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        # Секретный ключ = HMAC-SHA256("WebAppData", bot_token)
        secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calc_hash = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc_hash, received_hash):
            return None
        user_json = parsed.get("user")
        if not user_json:
            return None
        return json.loads(user_json)
    except Exception as e:
        logger.warning("initData verify failed: %s", e)
        return None


# Заголовки CORS (разрешаем запросы со страницы GitHub Pages)
def _cors(resp: web.Response) -> web.Response:
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


async def handle_options(request):
    return _cors(web.Response(text=""))


async def handle_health(request):
    """Проверка живости — открой этот адрес в браузере, должно быть OK."""
    return _cors(web.json_response({"status": "ok", "service": "hogwarts-miniapp-api"}))


async def handle_profile(request):
    """Главный эндпоинт — отдаёт профиль игрока по проверенному initData."""
    try:
        body = await request.json()
    except Exception:
        return _cors(web.json_response({"error": "bad request"}, status=400))

    init_data = body.get("initData", "")
    tg_user = _verify_init_data(init_data)
    if not tg_user:
        return _cors(web.json_response({"error": "unauthorized"}, status=401))

    user_id = tg_user.get("id")
    if not user_id:
        return _cors(web.json_response({"error": "no user id"}, status=400))

    # Импорт здесь, чтобы избежать циклических импортов при старте
    from database import get_user
    from utils.helpers import get_rank, xp_needed_for_level

    user = get_user(int(user_id))
    if not user:
        return _cors(web.json_response({"registered": False}))

    house_names = {
        "gryffindor": "Гриффиндор", "slytherin": "Слизерин",
        "ravenclaw":  "Когтевран",  "hufflepuff": "Пуффендуй",
    }
    house_emojis = {
        "gryffindor": "🦁", "slytherin": "🐍",
        "ravenclaw":  "🦅", "hufflepuff": "🦡",
    }
    house = user.get("house", "gryffindor")

    try:
        xp_need = xp_needed_for_level(user.get("level", 1))
    except Exception:
        xp_need = 150
    try:
        rank = get_rank(user.get("level", 1))
    except Exception:
        rank = "🐣 Первокурсник"

    data = {
        "registered": True,
        "name":       user.get("wizard_name", "Волшебник"),
        "house":      house_names.get(house, "Хогвартс"),
        "houseEmoji": house_emojis.get(house, "🏰"),
        "rank":       rank,
        "level":      user.get("level", 1),
        "hp":         user.get("hp", 100),
        "maxHp":      user.get("max_hp", 100),
        "mana":       user.get("mana", 50),
        "maxMana":    user.get("max_mana", 50),
        "xp":         user.get("xp", 0),
        "maxXp":      xp_need,
        "atk":        user.get("attack", 10),
        "def":        user.get("defense", 5),
        "spd":        user.get("speed", 10),
        "luck":       user.get("luck", 5),
        "gold":       user.get("gold", 0),
        "id":         user_id,
    }

    # Титул
    data["title"] = user.get("title") or ""

    # Винрейт дуэлей
    try:
        from database import get_conn as _gc, fetchrow as _fr
        with _gc() as conn:
            st = _fr(conn, "SELECT pvp_wins, pvp_losses FROM user_stats WHERE user_id=%s", int(user_id))
        wins = (st or {}).get("pvp_wins", 0) or 0
        losses = (st or {}).get("pvp_losses", 0) or 0
        total = wins + losses
        data["pvpWins"] = wins
        data["pvpLosses"] = losses
        data["winrate"] = (str(round(wins / total * 100)) + "%") if total else "—"
    except Exception:
        data["pvpWins"] = 0; data["pvpLosses"] = 0; data["winrate"] = "—"

    # Ранг в дуэльной лиге (ELO + дивизион)
    try:
        from handlers.duel_league import _get_rating, _get_division
        r = _get_rating(int(user_id))
        elo = r.get("elo", 1000)
        div_name, _ = _get_division(elo)
        data["elo"] = elo
        data["division"] = div_name
    except Exception:
        data["elo"] = 0; data["division"] = ""

    # Питомец
    try:
        from handlers.pets import _get_pet, PETS, _get_stage
        pet = _get_pet(int(user_id))
        if pet:
            pinfo = PETS.get(pet.get("pet_id"), {})
            stage = _get_stage(pet.get("level", 1))
            stages = pinfo.get("stages", [])
            pemoji = stages[stage]["emoji"] if stage < len(stages) else pinfo.get("emoji", "🐾")
            pname = stages[stage]["name"] if stage < len(stages) else pinfo.get("name", "Питомец")
            data["pet"] = {"emoji": pemoji, "name": pname, "level": pet.get("level", 1)}
        else:
            data["pet"] = None
    except Exception:
        data["pet"] = None

    return _cors(web.json_response(data))


async def handle_leaderboard(request):
    """Топ игроков. Категория через ?cat=level|gold|pvp. Публичный."""
    cat = request.query.get("cat", "level")
    if cat not in ("level", "gold", "pvp"):
        cat = "level"
    try:
        from database import get_leaderboard
        rows = get_leaderboard(cat, 15)
    except Exception as e:
        logger.warning("leaderboard: %s", e)
        rows = []
    house_emojis = {
        "gryffindor": "🦁", "slytherin": "🐍",
        "ravenclaw":  "🦅", "hufflepuff": "🦡",
    }
    top = []
    for i, r in enumerate(rows, 1):
        if cat == "gold":
            metric = str(r.get("gold", 0)) + " 💰"
        elif cat == "pvp":
            metric = str(r.get("pvp_wins", 0)) + " 🏆"
        else:
            metric = "ур. " + str(r.get("level", 1))
        top.append({
            "place": i,
            "name":  r.get("wizard_name", "—"),
            "house": house_emojis.get(r.get("house"), "🏰"),
            "metric": metric,
        })
    return _cors(web.json_response({"top": top, "cat": cat}))


async def handle_inventory(request):
    """Инвентарь игрока — требует авторизации (initData)."""
    try:
        body = await request.json()
    except Exception:
        return _cors(web.json_response({"error": "bad request"}, status=400))

    tg_user = _verify_init_data(body.get("initData", ""))
    if not tg_user or not tg_user.get("id"):
        return _cors(web.json_response({"error": "unauthorized"}, status=401))

    user_id = int(tg_user["id"])
    from database import get_conn, fetchall
    from game.items import ITEMS, item_display_name

    try:
        with get_conn() as conn:
            rows = fetchall(conn,
                "SELECT item_id, quantity FROM inventory WHERE user_id=%s ORDER BY acquired_at DESC",
                user_id)
    except Exception as e:
        logger.warning("inventory: %s", e)
        rows = []

    rarity_emoji = {
        "common": "⚪", "uncommon": "🟢", "rare": "🔵", "very_rare": "🟣",
        "epic": "🟠", "legendary": "🔴", "mythical": "🌟", "abyssal": "⚫",
    }
    items = []
    for r in rows:
        iid = r.get("item_id")
        item = ITEMS.get(iid, {})
        try:
            nm = item_display_name(item, "ru") if item else iid
        except Exception:
            nm = iid
        rarity = item.get("rarity", "common")
        items.append({
            "name":   nm,
            "emoji":  item.get("emoji", "📦"),
            "rarity": rarity_emoji.get(rarity, "⚪"),
            "qty":    r.get("quantity", 1),
        })
    return _cors(web.json_response({"items": items}))


async def handle_housecup(request):
    """Очки факультетов (Кубок). Публичный."""
    try:
        from database import get_house_points
        rows = get_house_points()
    except Exception as e:
        logger.warning("housecup: %s", e)
        rows = []
    house_names = {
        "gryffindor": "Гриффиндор", "slytherin": "Слизерин",
        "ravenclaw":  "Когтевран",  "hufflepuff": "Пуффендуй",
    }
    house_emojis = {
        "gryffindor": "🦁", "slytherin": "🐍",
        "ravenclaw":  "🦅", "hufflepuff": "🦡",
    }
    houses = []
    for r in rows:
        h = r.get("house")
        houses.append({
            "name":   house_names.get(h, h),
            "emoji":  house_emojis.get(h, "🏰"),
            "points": r.get("points", 0),
        })
    return _cors(web.json_response({"houses": houses}))


async def handle_feed_pet(request):
    """Покормить питомца. Требует авторизации."""
    try:
        body = await request.json()
    except Exception:
        return _cors(web.json_response({"error": "bad request"}, status=400))
    tg_user = _verify_init_data(body.get("initData", ""))
    if not tg_user or not tg_user.get("id"):
        return _cors(web.json_response({"error": "unauthorized"}, status=401))

    user_id = int(tg_user["id"])
    from datetime import datetime, timezone
    from database import get_conn, fetchrow, execute

    try:
        with get_conn() as conn:
            pet = fetchrow(conn, "SELECT * FROM user_pets WHERE user_id=%s", user_id)
        if not pet:
            return _cors(web.json_response({"ok": False, "msg": "У тебя нет питомца"}))
        fed = pet.get("fed_at")
        if fed:
            if fed.tzinfo is None:
                fed = fed.replace(tzinfo=timezone.utc)
            hours = (datetime.now(timezone.utc) - fed).total_seconds() / 3600
            if hours < 6:
                left = int(6 - hours) + 1
                return _cors(web.json_response({"ok": False, "msg": f"Питомец не голоден. Покорми через ~{left} ч."}))
        new_h = min(100, (pet.get("happiness", 50) or 50) + 30)
        with get_conn() as conn:
            execute(conn, "UPDATE user_pets SET happiness=%s, fed_at=NOW() WHERE user_id=%s", new_h, user_id)
        # немного опыта питомцу
        try:
            from handlers.pets import add_pet_xp
            add_pet_xp(user_id, 15)
        except Exception:
            pass
        return _cors(web.json_response({"ok": True, "msg": f"Питомец накормлен! Счастье: {new_h}/100"}))
    except Exception as e:
        logger.warning("feed_pet: %s", e)
        return _cors(web.json_response({"ok": False, "msg": "Ошибка"}))


async def handle_claim_daily(request):
    """Забрать ежедневный бонус. Требует авторизации."""
    try:
        body = await request.json()
    except Exception:
        return _cors(web.json_response({"error": "bad request"}, status=400))
    tg_user = _verify_init_data(body.get("initData", ""))
    if not tg_user or not tg_user.get("id"):
        return _cors(web.json_response({"error": "unauthorized"}, status=401))

    user_id = int(tg_user["id"])
    from datetime import datetime, timezone, timedelta
    from database import get_conn, execute, add_gold, add_xp, add_item_to_inventory
    try:
        from handlers.daily_bonus import _get_login_streak, _get_login_reward, _ensure_tables
        _ensure_tables()
        today = datetime.now(timezone.utc).date()
        streak_row = _get_login_streak(user_id)
        last_login = streak_row.get("last_login")
        if last_login == today:
            return _cors(web.json_response({"ok": False, "msg": "Бонус за сегодня уже получен!"}))
        yesterday = today - timedelta(days=1)
        new_streak = (streak_row.get("streak", 0) + 1) if last_login == yesterday else 1
        reward = _get_login_reward(new_streak)
        if reward.get("gold"): add_gold(user_id, reward["gold"])
        if reward.get("xp"):   add_xp(user_id, reward["xp"])
        if reward.get("item"): add_item_to_inventory(user_id, reward["item"], 1)
        with get_conn() as conn:
            execute(conn, """
                INSERT INTO login_streaks (user_id, streak, last_login, total_logins)
                VALUES (%s, %s, %s, 1)
                ON CONFLICT (user_id) DO UPDATE
                SET streak=EXCLUDED.streak, last_login=EXCLUDED.last_login,
                    total_logins=login_streaks.total_logins+1
            """, user_id, new_streak, today)
        return _cors(web.json_response({"ok": True, "msg": f"🎁 Получено: {reward['label']} (серия: {new_streak})"}))
    except Exception as e:
        logger.warning("claim_daily: %s", e)
        return _cors(web.json_response({"ok": False, "msg": "Ошибка"}))


async def handle_equip_best(request):
    """Надеть лучшее снаряжение. Требует авторизации."""
    try:
        body = await request.json()
    except Exception:
        return _cors(web.json_response({"error": "bad request"}, status=400))
    tg_user = _verify_init_data(body.get("initData", ""))
    if not tg_user or not tg_user.get("id"):
        return _cors(web.json_response({"error": "unauthorized"}, status=401))
    user_id = int(tg_user["id"])
    try:
        from handlers.inventory import auto_equip_best
        changes = auto_equip_best(user_id)
        if not changes:
            return _cors(web.json_response({"ok": False, "msg": "Лучшее снаряжение уже надето (или его нет)"}))
        return _cors(web.json_response({"ok": True, "msg": f"⚡ Надето лучшее в {len(changes)} слот(ов)!"}))
    except Exception as e:
        logger.warning("equip_best: %s", e)
        return _cors(web.json_response({"ok": False, "msg": "Ошибка"}))


async def handle_battle(request):
    """PvE-бой: action = start|cast|state|flee."""
    try:
        body = await request.json()
    except Exception:
        return _cors(web.json_response({"error": "bad request"}, status=400))
    tg_user = _verify_init_data(body.get("initData", ""))
    if not tg_user or not tg_user.get("id"):
        return _cors(web.json_response({"error": "unauthorized"}, status=401))
    user_id = int(tg_user["id"])
    action = body.get("action", "state")

    import webapp_battle as wb
    try:
        if action == "start":
            zone = body.get("zone") or None
            return _cors(web.json_response(wb.start_battle(user_id, zone)))
        elif action == "zones":
            return _cors(web.json_response(wb.list_zones(user_id)))
        elif action == "cast":
            spell_id = body.get("spell", "")
            return _cors(web.json_response(wb.cast(user_id, spell_id)))
        elif action == "flee":
            return _cors(web.json_response(wb.flee(user_id)))
        else:
            return _cors(web.json_response(wb.get_state(user_id)))
    except Exception as e:
        logger.warning("battle %s: %s", action, e)
        return _cors(web.json_response({"active": False, "error": "server"}))


async def handle_pet(request):
    """Инфо о питомце или тренировка. action = info|train|feed."""
    try:
        body = await request.json()
    except Exception:
        return _cors(web.json_response({"error": "bad request"}, status=400))
    tg_user = _verify_init_data(body.get("initData", ""))
    if not tg_user or not tg_user.get("id"):
        return _cors(web.json_response({"error": "unauthorized"}, status=401))
    user_id = int(tg_user["id"])
    action = body.get("action", "info")

    from database import get_user, get_conn, fetchrow, execute
    try:
        from handlers.pets import (
            _get_pet, PETS, _get_stage, _pet_xp_needed, _bonus_desc,
            _add_pet_xp, PET_MAX_LEVEL, EVOLVE_LEVELS,
        )
    except Exception as e:
        logger.warning("pet import: %s", e)
        return _cors(web.json_response({"hasPet": False}))

    def _pet_payload(msg=None, ok=True):
        pet = _get_pet(user_id)
        if not pet:
            return {"hasPet": False, "ok": ok, "msg": msg}
        pid = pet.get("pet_id")
        pinfo = PETS.get(pid, {})
        level = pet.get("level", 1)
        stage = _get_stage(level)
        stages = pinfo.get("stages", [])
        if stage < len(stages):
            pemoji = stages[stage].get("emoji", pinfo.get("emoji", "🐾"))
            pname  = stages[stage].get("name", pinfo.get("name", "Питомец"))
        else:
            pemoji = pinfo.get("emoji", "🐾"); pname = pinfo.get("name", "Питомец")
        xp = pet.get("xp", 0)
        xp_need = _pet_xp_needed(level)
        try:
            bonus = _bonus_desc(pid, level)
        except Exception:
            bonus = ""
        # След. эволюция
        next_evo = None
        for lvl in EVOLVE_LEVELS:
            if level < lvl:
                next_evo = lvl; break
        return {
            "hasPet": True, "ok": ok, "msg": msg,
            "emoji": pemoji, "name": pname,
            "level": level, "maxLevel": PET_MAX_LEVEL,
            "xp": xp, "maxXp": xp_need,
            "happiness": pet.get("happiness", 100),
            "stage": stage + 1,
            "bonus": bonus,
            "nextEvo": next_evo,
        }

    try:
        if action == "train":
            pet = _get_pet(user_id)
            if not pet:
                return _cors(web.json_response({"hasPet": False, "ok": False, "msg": "Нет питомца"}))
            user = get_user(user_id)
            if user["gold"] < 50:
                return _cors(web.json_response(_pet_payload("❌ Нужно 50 золота", ok=False)))
            if pet.get("level", 1) >= PET_MAX_LEVEL:
                return _cors(web.json_response(_pet_payload("Питомец уже максимального уровня!", ok=False)))
            with get_conn() as conn:
                execute(conn, "UPDATE users SET gold=gold-50 WHERE user_id=%s", user_id)
            leveled, evolved, new_level = _add_pet_xp(user_id, 40)
            if evolved:   msg = f"🎉 Эволюция! Питомец достиг {new_level} уровня!"
            elif leveled: msg = f"⬆️ Питомец вырос до {new_level} уровня!"
            else:         msg = "✅ +40 опыта питомцу!"
            return _cors(web.json_response(_pet_payload(msg, ok=True)))
        else:
            return _cors(web.json_response(_pet_payload()))
    except Exception as e:
        logger.warning("pet action: %s", e)
        return _cors(web.json_response({"hasPet": False, "ok": False, "msg": "Ошибка"}))


async def handle_potions(request):
    """Зелья: action = list|brew|collect. Требует авторизации."""
    try:
        body = await request.json()
    except Exception:
        return _cors(web.json_response({"error": "bad request"}, status=400))
    tg_user = _verify_init_data(body.get("initData", ""))
    if not tg_user or not tg_user.get("id"):
        return _cors(web.json_response({"error": "unauthorized"}, status=401))
    user_id = int(tg_user["id"])
    action = body.get("action", "list")

    from datetime import datetime, timezone
    try:
        from handlers.potion_system import (
            RECIPES, _can_brew, _spend_ingredients, _get_inventory_item_count,
            _unlock_starter_recipes,
        )
        from config import POTION_BREW_TIME_MINUTES
        from database import (
            get_user_recipes, get_brewing_queue, add_item_to_inventory,
            get_conn, execute, fetchall,
        )
        from game.items import ITEMS, item_display_name
    except Exception as e:
        logger.warning("potions import: %s", e)
        return _cors(web.json_response({"recipes": [], "queue": []}))

    try:
        _unlock_starter_recipes(user_id)
    except Exception:
        pass

    def _queue_payload():
        try:
            q = get_brewing_queue(user_id)
        except Exception:
            q = []
        now = datetime.now(timezone.utc)
        out = []
        for item in q:
            ra = item["ready_at"]
            if ra.tzinfo is None:
                ra = ra.replace(tzinfo=timezone.utc)
            rid = item["recipe_id"]
            rc = RECIPES.get(rid, {})
            remaining = int((ra - now).total_seconds())
            out.append({
                "recipe": rid,
                "name": rc.get("name", rid),
                "emoji": rc.get("emoji", "🧪"),
                "ready": remaining <= 0,
                "remaining": max(0, remaining),
            })
        return out

    def _recipes_payload():
        try:
            known = {r["recipe_id"] for r in get_user_recipes(user_id)}
        except Exception:
            known = set()
        out = []
        for rid, rc in RECIPES.items():
            if rid not in known and rc.get("unlock") != "start":
                continue
            ings = []
            can = True
            for iid, need in rc["ingredients"].items():
                have = _get_inventory_item_count(user_id, iid)
                if have < need: can = False
                idata = ITEMS.get(iid, {})
                ings.append({
                    "name": item_display_name(idata, "ru") if idata else iid,
                    "have": have, "need": need,
                })
            out.append({
                "id": rid, "name": rc.get("name", rid), "emoji": rc.get("emoji", "🧪"),
                "time": POTION_BREW_TIME_MINUTES.get(rc.get("rarity"), 5),
                "ingredients": ings, "canBrew": can,
            })
        return out

    try:
        if action == "brew":
            rid = body.get("recipe", "")
            rc = RECIPES.get(rid)
            if not rc:
                return _cors(web.json_response({"ok": False, "msg": "Рецепт не найден"}))
            ok, missing = _can_brew(user_id, rc)
            if not ok:
                return _cors(web.json_response({"ok": False, "msg": "Не хватает ингредиентов"}))
            from datetime import timedelta
            brew_time = POTION_BREW_TIME_MINUTES.get(rc.get("rarity"), 5)
            ready_at = datetime.now(timezone.utc) + timedelta(minutes=brew_time)
            _spend_ingredients(user_id, rc)
            with get_conn() as conn:
                execute(conn, "INSERT INTO brewing_queue (user_id, recipe_id, ready_at) VALUES (%s,%s,%s)",
                        user_id, rid, ready_at)
            return _cors(web.json_response({"ok": True, "msg": f"🔥 Варка началась! Готово через {brew_time} мин.",
                                            "recipes": _recipes_payload(), "queue": _queue_payload()}))
        elif action == "collect":
            now = datetime.now(timezone.utc)
            collected = []
            q = get_brewing_queue(user_id)
            for item in q:
                ra = item["ready_at"]
                if ra.tzinfo is None: ra = ra.replace(tzinfo=timezone.utc)
                if now >= ra:
                    rc = RECIPES.get(item["recipe_id"], {})
                    result_item = rc.get("result_item")
                    if result_item:
                        add_item_to_inventory(user_id, result_item, 1)
                        collected.append(rc.get("name", item["recipe_id"]))
                    with get_conn() as conn:
                        execute(conn, "DELETE FROM brewing_queue WHERE id=%s", item["id"])
            msg = ("✅ Собрано: " + ", ".join(collected)) if collected else "Пока нечего собирать"
            return _cors(web.json_response({"ok": bool(collected), "msg": msg,
                                            "recipes": _recipes_payload(), "queue": _queue_payload()}))
        else:
            return _cors(web.json_response({"recipes": _recipes_payload(), "queue": _queue_payload()}))
    except Exception as e:
        logger.warning("potions action: %s", e)
        return _cors(web.json_response({"recipes": [], "queue": [], "ok": False, "msg": "Ошибка"}))


def _build_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", handle_health)
    app.router.add_get("/health", handle_health)
    app.router.add_post("/api/profile", handle_profile)
    app.router.add_options("/api/profile", handle_options)
    app.router.add_get("/api/leaderboard", handle_leaderboard)
    app.router.add_options("/api/leaderboard", handle_options)
    app.router.add_post("/api/inventory", handle_inventory)
    app.router.add_options("/api/inventory", handle_options)
    app.router.add_get("/api/housecup", handle_housecup)
    app.router.add_options("/api/housecup", handle_options)
    app.router.add_post("/api/feedpet", handle_feed_pet)
    app.router.add_options("/api/feedpet", handle_options)
    app.router.add_post("/api/claimdaily", handle_claim_daily)
    app.router.add_options("/api/claimdaily", handle_options)
    app.router.add_post("/api/equipbest", handle_equip_best)
    app.router.add_options("/api/equipbest", handle_options)
    app.router.add_post("/api/battle", handle_battle)
    app.router.add_options("/api/battle", handle_options)
    app.router.add_post("/api/pet", handle_pet)
    app.router.add_options("/api/pet", handle_options)
    app.router.add_post("/api/potions", handle_potions)
    app.router.add_options("/api/potions", handle_options)
    return app


def run_api_server():
    """Запускает API-сервер в отдельном потоке (со своим event loop)."""
    import asyncio
    port = int(os.environ.get("PORT", "8080"))

    def _serve():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        runner = web.AppRunner(_build_app())
        loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, "0.0.0.0", port)
        loop.run_until_complete(site.start())
        logger.info("Mini App API запущен на порту %s", port)
        loop.run_forever()

    t = threading.Thread(target=_serve, daemon=True)
    t.start()
