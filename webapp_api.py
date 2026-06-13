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
