"""
Система случайных атак (Ambush) — удержание игроков.
Раз в день на неактивного (>2ч) игрока «нападает» монстр.
Уведомление в активные часы (10:00–22:00 UTC). Окно ответа 2 часа.
Шанс победы ~80%. Поражение НИКОГДА ничего не отнимает.
Награды масштабируются по уровню игрока.
"""
import logging
import random
import asyncio
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from database import (
    get_user, get_conn, execute, fetchrow, fetchall,
    add_xp, add_gold, add_item_to_inventory, get_inactive_users,
)
from game.items import ITEMS, item_display_name
from utils.i18n import t

logger = logging.getLogger(__name__)

# ── Настройки ───────────────────────────────────────────────────────────────
INACTIVITY_HOURS    = 2      # атакуем тех, кто не заходил >2ч
RESPONSE_WINDOW_MIN = 120    # окно ответа — 2 часа
ACTIVE_HOUR_START   = 10     # окно рассылки UTC (включительно)
ACTIVE_HOUR_END     = 22
WIN_CHANCE          = 0.80   # базовый шанс победы
BATCH_SIZE          = 25     # рассылка пачками
BATCH_DELAY_SEC     = 2      # пауза между пачками

# ── Шанс выпадения предмета по редкости (при победе) ──────────────────────────
# Первые 3 редкости — частые, дальше резко падает (<2%).
ITEM_DROP_TABLE = [
    ("common",     0.30),   # 30%
    ("uncommon",   0.18),   # 18%
    ("rare",       0.10),   # 10%
    ("very_rare",  0.018),  # 1.8%
    ("epic",       0.010),  # 1.0%
    ("legendary",  0.004),  # 0.4%
    ("mythical",   0.001),  # 0.1%
]
# Итого шанс получить ХОТЬ какой-то предмет ≈ 61.3%, из них львиная доля — common/uncommon/rare.

# ── Нападающие монстры (флейвор) ──────────────────────────────────────────────
ATTACKERS = [
    {"id": "dementor",   "emoji": "🦇", "name": {"ru":"Дементор","en":"Dementor","es":"Dementor","de":"Dementor","pt":"Dementador"},
     "intro": {"ru":"Дементор выследил тебя в тёмном коридоре!","en":"A Dementor tracked you down in a dark corridor!",
               "es":"¡Un Dementor te ha rastreado en un pasillo oscuro!","de":"Ein Dementor hat dich in einem dunklen Korridor aufgespürt!",
               "pt":"Um Dementador te encontrou num corredor escuro!"}},
    {"id": "acromantula","emoji": "🕷️", "name": {"ru":"Акромантул","en":"Acromantula","es":"Acromántula","de":"Acromantula","pt":"Acromântula"},
     "intro": {"ru":"Гигантский паук выполз из теней!","en":"A giant spider crawled out of the shadows!",
               "es":"¡Una araña gigante salió de las sombras!","de":"Eine riesige Spinne kroch aus dem Schatten!",
               "pt":"Uma aranha gigante saiu das sombras!"}},
    {"id": "death_eater","emoji": "💀", "name": {"ru":"Пожиратель смерти","en":"Death Eater","es":"Mortífago","de":"Todesser","pt":"Comensal da Morte"},
     "intro": {"ru":"Пожиратель смерти аппарировал прямо перед тобой!","en":"A Death Eater apparated right in front of you!",
               "es":"¡Un Mortífago se apareció justo frente a ti!","de":"Ein Todesser ist direkt vor dir appariert!",
               "pt":"Um Comensal da Morte aparatou bem na sua frente!"}},
    {"id": "troll",      "emoji": "👹", "name": {"ru":"Горный тролль","en":"Mountain Troll","es":"Trol de montaña","de":"Bergtroll","pt":"Troll das montanhas"},
     "intro": {"ru":"Горный тролль с дубиной преградил путь!","en":"A mountain troll with a club blocked your path!",
               "es":"¡Un trol de montaña con una maza te cerró el paso!","de":"Ein Bergtroll mit einer Keule versperrte dir den Weg!",
               "pt":"Um troll das montanhas com um porrete bloqueou seu caminho!"}},
    {"id": "werewolf",   "emoji": "🐺", "name": {"ru":"Оборотень","en":"Werewolf","es":"Hombre lobo","de":"Werwolf","pt":"Lobisomem"},
     "intro": {"ru":"Оборотень выскочил из Запретного леса!","en":"A werewolf burst out of the Forbidden Forest!",
               "es":"¡Un hombre lobo salió del Bosque Prohibido!","de":"Ein Werwolf brach aus dem Verbotenen Wald hervor!",
               "pt":"Um lobisomem saiu da Floresta Proibida!"}},
]

def _ensure_table():
    try:
        with get_conn() as conn:
            execute(conn, """
                CREATE TABLE IF NOT EXISTS ambushes (
                    id          SERIAL PRIMARY KEY,
                    user_id     BIGINT NOT NULL,
                    attacker_id TEXT NOT NULL,
                    xp_reward   INT NOT NULL,
                    gold_reward INT NOT NULL,
                    created_at  TIMESTAMPTZ DEFAULT NOW(),
                    expires_at  TIMESTAMPTZ NOT NULL,
                    status      TEXT DEFAULT 'pending'  -- pending/won/lost/expired
                )
            """)
            execute(conn, "CREATE INDEX IF NOT EXISTS ambush_user_idx ON ambushes(user_id, status)")
    except Exception as e:
        logger.warning("ambush table: %s", e)

def _already_ambushed_today(user_id: int) -> bool:
    try:
        with get_conn() as conn:
            row = fetchrow(conn, """
                SELECT 1 FROM ambushes
                WHERE user_id=%s AND created_at::date = (NOW() AT TIME ZONE 'UTC')::date
                LIMIT 1
            """, user_id)
        return row is not None
    except Exception:
        return False

def _scale_rewards(level: int) -> tuple[int, int]:
    """Награды масштабируются по уровню: чем выше уровень — тем больше."""
    xp   = int(40 + level * 12)        # ур1≈52, ур10≈160, ур30≈400
    gold = int(20 + level * 6)         # ур1≈26, ур10≈80, ур30≈200
    # Небольшой разброс ±15%
    xp   = int(xp   * random.uniform(0.85, 1.15))
    gold = int(gold * random.uniform(0.85, 1.15))
    return xp, gold

def _roll_item() -> str | None:
    """Бросок на выпадение предмета по таблице редкостей."""
    for rarity, chance in ITEM_DROP_TABLE:
        if random.random() < chance:
            candidates = [iid for iid, it in ITEMS.items()
                          if it.get("rarity") == rarity and it.get("type") in ("equipment", "consumable")]
            if candidates:
                return random.choice(candidates)
    return None

def _ambush_keyboard(ambush_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚔️ Дать отпор!", callback_data=f"ambush_fight:{ambush_id}")],
        [InlineKeyboardButton("🏃 Убежать",     callback_data=f"ambush_flee:{ambush_id}")],
    ])

async def send_ambushes(bot):
    """Главная функция — рассылает атаки неактивным игрокам. Вызывается планировщиком."""
    _ensure_table()

    # Только в активные часы UTC
    hour = datetime.now(timezone.utc).hour
    if not (ACTIVE_HOUR_START <= hour < ACTIVE_HOUR_END):
        return

    inactive = get_inactive_users(hours=INACTIVITY_HOURS, limit=BATCH_SIZE * 4)
    if not inactive:
        return

    sent = 0
    for i, u in enumerate(inactive):
        uid = u["user_id"]
        if _already_ambushed_today(uid):
            continue

        level    = u["level"]
        lang     = u.get("lang") or "ru"
        attacker = random.choice(ATTACKERS)
        xp, gold = _scale_rewards(level)

        expires = datetime.now(timezone.utc) + timedelta(minutes=RESPONSE_WINDOW_MIN)
        try:
            with get_conn() as conn:
                row = fetchrow(conn, """
                    INSERT INTO ambushes (user_id, attacker_id, xp_reward, gold_reward, expires_at, status)
                    VALUES (%s, %s, %s, %s, %s, 'pending')
                    RETURNING id
                """, uid, attacker["id"], xp, gold, expires)
            ambush_id = row["id"]
        except Exception as e:
            logger.warning("ambush insert uid=%s: %s", uid, e)
            continue

        name  = attacker["name"].get(lang) or attacker["name"]["ru"]
        intro = attacker["intro"].get(lang) or attacker["intro"]["ru"]
        text = (
            f"{attacker['emoji']} *Нападение!*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{intro}\n\n"
            f"Противник: {attacker['emoji']} *{name}*\n"
            f"💰 Награда за победу: +{xp} XP, +{gold} 💰\n"
            f"🎁 Шанс на трофей при победе!\n\n"
            f"⏳ У тебя 2 часа чтобы дать отпор.\n"
            f"_Проигрыш ничем не грозит — ты ничего не потеряешь._"
        )
        try:
            await bot.send_message(uid, text, parse_mode="Markdown",
                                   reply_markup=_ambush_keyboard(ambush_id))
            sent += 1
        except Exception:
            # Заблокировал бота / удалил чат — помечаем ambush истёкшим
            try:
                with get_conn() as conn:
                    execute(conn, "UPDATE ambushes SET status='expired' WHERE id=%s", ambush_id)
            except Exception:
                pass

        # Рассылка пачками с задержкой — защита от флуд-лимита Telegram
        if sent > 0 and sent % BATCH_SIZE == 0:
            await asyncio.sleep(BATCH_DELAY_SEC)

    if sent:
        logger.info("Ambush: отправлено %d атак", sent)

async def cb_ambush_fight(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query     = update.callback_query
    user_id   = query.from_user.id
    ambush_id = int(query.data.split(":")[1])
    _ensure_table()

    # Активность засчитана — игрок вернулся
    try:
        from database import touch_user_activity
        touch_user_activity(user_id)
    except Exception:
        pass

    with get_conn() as conn:
        amb = fetchrow(conn, "SELECT * FROM ambushes WHERE id=%s AND user_id=%s", ambush_id, user_id)
    if not amb:
        await query.answer("Это нападение не найдено.", show_alert=True)
        return
    if amb["status"] != "pending":
        await query.answer("Это нападение уже завершено.", show_alert=True)
        return

    # Проверка окна
    expires = amb["expires_at"]
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires:
        with get_conn() as conn:
            execute(conn, "UPDATE ambushes SET status='expired' WHERE id=%s", ambush_id)
        await query.edit_message_text("⏰ Слишком поздно — противник скрылся.")
        return

    await query.answer()
    user     = get_user(user_id)
    attacker = next((a for a in ATTACKERS if a["id"] == amb["attacker_id"]), ATTACKERS[0])
    lang     = user.get("lang") or "ru"
    name     = attacker["name"].get(lang) or attacker["name"]["ru"]

    # Шанс победы 80% + небольшой бонус от удачи игрока
    luck_bonus = min(0.15, user.get("luck", 5) * 0.005)
    win        = random.random() < (WIN_CHANCE + luck_bonus)

    if win:
        xp   = amb["xp_reward"]
        gold = amb["gold_reward"]
        add_xp(user_id, xp)
        add_gold(user_id, gold)

        item_line = ""
        dropped = _roll_item()
        if dropped:
            add_item_to_inventory(user_id, dropped, 1)
            it = ITEMS.get(dropped, {})
            item_line = f"\n🎁 Трофей: {it.get('emoji','📦')} *{item_display_name(it, lang)}*!"

        with get_conn() as conn:
            execute(conn, "UPDATE ambushes SET status='won' WHERE id=%s", ambush_id)
        try:
            with get_conn() as conn:
                execute(conn, """
                    INSERT INTO player_journal (user_id, event_type, title, description, xp_gained, gold_gained, item_gained)
                    VALUES (%s,'ambush',%s,%s,%s,%s,%s)
                """, user_id, f"Отбил атаку: {name}", "Победа над напавшим монстром",
                    xp, gold, dropped or "")
        except Exception:
            pass

        await query.edit_message_text(
            f"⚔️ *Победа!*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Ты дал отпор {attacker['emoji']} {name}!\n\n"
            f"🎁 +{xp} XP  •  +{gold} 💰{item_line}\n\n"
            f"_С возвращением в Хогвартс!_",
            parse_mode="Markdown"
        )
    else:
        with get_conn() as conn:
            execute(conn, "UPDATE ambushes SET status='lost' WHERE id=%s", ambush_id)
        await query.edit_message_text(
            f"💨 *{name} ускользнул!*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"В этот раз противник был хитрее и сбежал.\n\n"
            f"✅ *Ты ничего не потерял.*\n"
            f"Не расстраивайся — в следующий раз повезёт!",
            parse_mode="Markdown"
        )

async def cb_ambush_flee(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query     = update.callback_query
    user_id   = query.from_user.id
    ambush_id = int(query.data.split(":")[1])
    await query.answer()

    try:
        from database import touch_user_activity
        touch_user_activity(user_id)
    except Exception:
        pass

    with get_conn() as conn:
        amb = fetchrow(conn, "SELECT status FROM ambushes WHERE id=%s AND user_id=%s", ambush_id, user_id)
        if amb and amb["status"] == "pending":
            execute(conn, "UPDATE ambushes SET status='expired' WHERE id=%s", ambush_id)

    await query.edit_message_text(
        "🏃 Ты благоразумно скрылся.\n\n"
        "Ничего не потеряно — но и наград нет. В другой раз дай отпор!"
    )

def setup_ambush_jobs(scheduler, bot):
    """Добавить рассылку атак в планировщик — 3 раза в день в активные часы."""
    from apscheduler.triggers.cron import CronTrigger
    # 11:00, 16:00, 21:00 UTC — попадают в окно 10-22
    for h in (11, 16, 21):
        scheduler.add_job(
            lambda: asyncio.get_event_loop().create_task(send_ambushes(bot)),
            CronTrigger(hour=h, minute=0, timezone="UTC"),
            id=f"ambush_{h}", replace_existing=True
        )
    logger.info("Ambush jobs registered (11:00, 16:00, 21:00 UTC)")

def register_ambush_handlers(app):
    app.add_handler(CallbackQueryHandler(cb_ambush_fight, pattern=r"^ambush_fight:"))
    app.add_handler(CallbackQueryHandler(cb_ambush_flee,  pattern=r"^ambush_flee:"))
