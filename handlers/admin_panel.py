"""
Админ-панель на инлайн-кнопках.
Категории → действия. Команды с аргументами запрашивают ввод пошагово.
Команды без аргументов выполняются мгновенно.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import ADMIN_IDS
from database import (
    get_user, get_conn, execute, fetchrow, fetchall, fetchval,
    add_gold, add_xp, add_item_to_inventory, ban_user, unban_user,
    add_house_points,
)

logger = logging.getLogger(__name__)

def _is_admin(user_id: int) -> bool:
    return bool(ADMIN_IDS) and user_id in ADMIN_IDS

# ── Описание команд, требующих ввода ──────────────────────────────────────────
# key: (заголовок, [список_шагов], подсказка_формата)
# Каждый шаг — (имя_поля, текст_запроса)
INPUT_COMMANDS = {
    "give_gold":   {"title": "💰 Выдать золото",   "steps": [("user_id","ID игрока"), ("amount","Сумма золота")]},
    "give_xp":     {"title": "✨ Выдать опыт",       "steps": [("user_id","ID игрока"), ("amount","Количество XP")]},
    "give_item":   {"title": "🎁 Выдать предмет",    "steps": [("user_id","ID игрока"), ("item_id","ID предмета"), ("qty","Количество")]},
    "give_spell":  {"title": "✨ Выдать заклинание", "steps": [("user_id","ID игрока"), ("spell_id","ID заклинания")]},
    "set_level":   {"title": "📊 Задать уровень",    "steps": [("user_id","ID игрока"), ("level","Новый уровень")]},
    "set_house":   {"title": "🏠 Сменить факультет", "steps": [("user_id","ID игрока"), ("house","Факультет (gryffindor/slytherin/ravenclaw/hufflepuff)")]},
    "player_info": {"title": "🔍 Инфо об игроке",    "steps": [("user_id","ID игрока")]},
    "ban":         {"title": "🚫 Забанить",          "steps": [("user_id","ID игрока для бана")]},
    "unban":       {"title": "✅ Разбанить",         "steps": [("user_id","ID игрока для разбана")]},
    "reset_player":{"title": "♻️ Обнулить игрока",   "steps": [("user_id","ID игрока для ПОЛНОГО сброса")]},
    "add_house_pts":{"title": "🏆 Очки факультету",  "steps": [("house","Факультет"), ("points","Очки")]},
    "broadcast":   {"title": "📢 Рассылка всем",     "steps": [("message","Текст сообщения для всех игроков")]},
    "set_maint_msg":{"title": "✏️ Текст о техработах", "steps": [("message","Что увидят игроки во время техработ")]},
}

# ── Категории панели ──────────────────────────────────────────────────────────
CATEGORIES = {
    "players": {
        "title": "👥 Игроки",
        "buttons": [
            ("give_gold",   "💰 Выдать золото"),
            ("give_xp",     "✨ Выдать опыт"),
            ("give_item",   "🎁 Выдать предмет"),
            ("give_spell",  "📜 Выдать заклинание"),
            ("set_level",   "📊 Задать уровень"),
            ("set_house",   "🏠 Сменить факультет"),
            ("player_info", "🔍 Инфо об игроке"),
            ("ban",         "🚫 Забанить"),
            ("unban",       "✅ Разбанить"),
            ("reset_player","♻️ Обнулить игрока"),
        ],
    },
    "economy": {
        "title": "💰 Экономика и статистика",
        "buttons": [
            ("stats",        "📊 Общая статистика"),
            ("economy_info", "💰 Экономика"),
            ("reset_daily",  "🔄 Сброс дневных лимитов"),
        ],
    },
    "events": {
        "title": "🎉 События",
        "buttons": [
            ("spawn_boss",       "🐉 Призвать босса"),
            ("start_tournament", "🏆 Запустить турнир"),
            ("add_house_pts",    "🏆 Очки факультету"),
            ("reset_house_cup",  "🔄 Сброс Кубка факультетов"),
            ("trigger_ambush",   "⚔️ Запустить атаки"),
        ],
    },
    "content": {
        "title": "📋 Контент",
        "buttons": [
            ("list_items",  "🎒 Список предметов"),
            ("list_spells", "📜 Список заклинаний"),
            ("list_bosses", "🐉 Список боссов"),
        ],
    },
    "manage": {
        "title": "⚙️ Управление",
        "buttons": [
            ("broadcast",   "📢 Рассылка всем"),
            ("admin_log",   "📋 Журнал действий"),
            ("maintenance",     "🔧 Режим обслуживания вкл/выкл"),
            ("set_maint_msg",   "✏️ Текст сообщения о техработах"),
            ("manage_images",   "🖼️ Картинки бота"),
        ],
    },
}

def _main_keyboard() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(cat["title"], callback_data=f"apanel:cat:{cid}")]
            for cid, cat in CATEGORIES.items()]
    return InlineKeyboardMarkup(rows)

def _category_keyboard(cat_id: str) -> InlineKeyboardMarkup:
    cat = CATEGORIES.get(cat_id)
    rows = [[InlineKeyboardButton(label, callback_data=f"apanel:act:{action}")]
            for action, label in cat["buttons"]]
    rows.append([InlineKeyboardButton("◀️ К разделам", callback_data="apanel:main")])
    return InlineKeyboardMarkup(rows)

async def cmd_admin_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _is_admin(user_id):
        return
    await update.message.reply_text(
        "🛠️ *Админ-панель*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Выбери раздел:",
        parse_mode="Markdown",
        reply_markup=_main_keyboard()
    )

async def cb_apanel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user_id = query.from_user.id
    if not _is_admin(user_id):
        await query.answer("Нет доступа.", show_alert=True)
        return
    await query.answer()

    parts = query.data.split(":")
    action = parts[1]

    if action == "resetconfirm":
        tid = int(parts[2])
        from database import reset_player
        try:
            target = get_user(tid)
            name = target["wizard_name"] if target else str(tid)
            reset_player(tid)
            try:
                with get_conn() as conn:
                    execute(conn,
                        "INSERT INTO admin_log (admin_id, action, target_id, details) VALUES (%s,%s,%s,%s)",
                        user_id, "reset_player", tid, name)
            except Exception:
                pass
            await query.edit_message_text(
                f"♻️ *Игрок обнулён*\n\n"
                f"{name} (ID {tid}) полностью сброшен.\n"
                f"При следующем /start он пройдёт регистрацию как новый игрок.",
                parse_mode="Markdown"
            )
            # Уведомим игрока
            try:
                await ctx.bot.send_message(tid,
                    "♻️ Твой персонаж был сброшен администратором.\n"
                    "Отправь /start чтобы начать игру заново!")
            except Exception:
                pass
        except Exception as e:
            logger.exception("reset_player: %s", e)
            await query.edit_message_text(f"⚠️ Ошибка при обнулении: {str(e)[:120]}")
        return

    if action == "main":
        await query.edit_message_text(
            "🛠️ *Админ-панель*\n━━━━━━━━━━━━━━━━━━━━\nВыбери раздел:",
            parse_mode="Markdown", reply_markup=_main_keyboard()
        )
        return

    if action == "cat":
        cat_id = parts[2]
        cat = CATEGORIES.get(cat_id)
        if not cat:
            await query.edit_message_text("❌ Раздел не найден.")
            return
        await query.edit_message_text(
            f"{cat['title']}\n━━━━━━━━━━━━━━━━━━━━\nВыбери действие:",
            parse_mode="Markdown", reply_markup=_category_keyboard(cat_id)
        )
        return

    if action == "act":
        cmd = parts[2]
        # Команды с вводом → запускаем пошаговый сбор аргументов
        if cmd in INPUT_COMMANDS:
            await _start_input_flow(query, ctx, cmd)
        else:
            # Мгновенные команды
            await _run_instant_command(query, ctx, cmd)
        return

async def _start_input_flow(query, ctx, cmd: str):
    spec = INPUT_COMMANDS[cmd]
    ctx.user_data["apanel_cmd"]   = cmd
    ctx.user_data["apanel_step"]  = 0
    ctx.user_data["apanel_data"]  = {}
    first_step = spec["steps"][0]
    await query.edit_message_text(
        f"{spec['title']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Шаг 1/{len(spec['steps'])}\n\n"
        f"Введи: *{first_step[1]}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Отмена", callback_data="apanel:cancel")
        ]])
    )

async def cb_apanel_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Отменено")
    ctx.user_data.pop("apanel_cmd", None)
    ctx.user_data.pop("apanel_step", None)
    ctx.user_data.pop("apanel_data", None)
    await query.edit_message_text(
        "🛠️ *Админ-панель*\n━━━━━━━━━━━━━━━━━━━━\nВыбери раздел:",
        parse_mode="Markdown", reply_markup=_main_keyboard()
    )

async def handle_apanel_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовый ввод для пошаговых команд."""
    user_id = update.effective_user.id
    if not _is_admin(user_id):
        return
    cmd = ctx.user_data.get("apanel_cmd")
    if not cmd:
        return  # не в режиме ввода — пропускаем

    spec  = INPUT_COMMANDS[cmd]
    step  = ctx.user_data.get("apanel_step", 0)
    data  = ctx.user_data.get("apanel_data", {})

    field_name = spec["steps"][step][0]
    data[field_name] = update.message.text.strip()
    ctx.user_data["apanel_data"] = data

    # Ещё есть шаги?
    if step + 1 < len(spec["steps"]):
        ctx.user_data["apanel_step"] = step + 1
        next_step = spec["steps"][step + 1]
        await update.message.reply_text(
            f"{spec['title']}\n"
            f"Шаг {step+2}/{len(spec['steps'])}\n\n"
            f"Введи: *{next_step[1]}*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="apanel:cancel")
            ]])
        )
        return

    # Все шаги собраны — выполняем
    ctx.user_data.pop("apanel_cmd", None)
    ctx.user_data.pop("apanel_step", None)
    ctx.user_data.pop("apanel_data", None)
    await _execute_input_command(update, ctx, cmd, data)

async def _execute_input_command(update, ctx, cmd: str, data: dict):
    """Выполняет команду с собранными аргументами."""
    reply = update.message.reply_text
    admin_id = update.effective_user.id

    def _log(action, target="", details=""):
        try:
            # target_id — BIGINT, поэтому нечисловые цели (факультет) пишем в details
            target_num = None
            try:
                target_num = int(target) if target != "" else None
            except (ValueError, TypeError):
                details = f"{target} {details}".strip()
            with get_conn() as conn:
                execute(conn,
                    "INSERT INTO admin_log (admin_id, action, target_id, details) VALUES (%s,%s,%s,%s)",
                    admin_id, action, target_num, details)
        except Exception:
            pass

    try:
        if cmd == "give_gold":
            tid, amt = int(data["user_id"]), int(data["amount"])
            add_gold(tid, amt); _log("give_gold", tid, str(amt))
            await reply(f"✅ Выдано {amt} 💰 игроку {tid}.")
            try: await ctx.bot.send_message(tid, f"🎁 Администратор выдал тебе {amt} 💰!")
            except Exception: pass

        elif cmd == "give_xp":
            tid, amt = int(data["user_id"]), int(data["amount"])
            add_xp(tid, amt); _log("give_xp", tid, str(amt))
            await reply(f"✅ Выдано {amt} XP игроку {tid}.")
            try: await ctx.bot.send_message(tid, f"✨ Администратор выдал тебе {amt} опыта!")
            except Exception: pass

        elif cmd == "give_item":
            tid = int(data["user_id"]); iid = data["item_id"]; qty = int(data.get("qty", 1))
            add_item_to_inventory(tid, iid, qty); _log("give_item", tid, f"{iid}x{qty}")
            await reply(f"✅ Выдано {qty}× {iid} игроку {tid}.")

        elif cmd == "give_spell":
            tid = int(data["user_id"]); sid = data["spell_id"]
            with get_conn() as conn:
                execute(conn, "INSERT INTO user_spells (user_id, spell_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", tid, sid)
            _log("give_spell", tid, sid)
            await reply(f"✅ Выдано заклинание {sid} игроку {tid}.")

        elif cmd == "set_level":
            tid, lvl = int(data["user_id"]), int(data["level"])
            with get_conn() as conn:
                execute(conn, "UPDATE users SET level=%s WHERE user_id=%s", lvl, tid)
            _log("set_level", tid, str(lvl))
            await reply(f"✅ Уровень игрока {tid} установлен на {lvl}.")

        elif cmd == "set_house":
            tid = int(data["user_id"]); house = data["house"].lower()
            if house not in ("gryffindor","slytherin","ravenclaw","hufflepuff"):
                await reply("❌ Неверный факультет."); return
            with get_conn() as conn:
                execute(conn, "UPDATE users SET house=%s WHERE user_id=%s", house, tid)
            _log("set_house", tid, house)
            await reply(f"✅ Игрок {tid} переведён в {house}.")

        elif cmd == "player_info":
            tid = int(data["user_id"])
            u = get_user(tid)
            if not u:
                await reply("❌ Игрок не найден."); return
            await reply(
                f"🔍 *Игрок {tid}*\n"
                f"Имя: {u['wizard_name']}\n"
                f"Факультет: {u['house']}\n"
                f"Уровень: {u['level']} | XP: {u['xp']}\n"
                f"HP: {u['hp']}/{u['max_hp']} | Мана: {u['mana']}/{u['max_mana']}\n"
                f"Атака: {u['attack']} | Защита: {u['defense']}\n"
                f"Золото: {u['gold']}\n"
                f"Бан: {'да' if u.get('is_banned') else 'нет'}",
                parse_mode="Markdown"
            )

        elif cmd == "ban":
            tid = int(data["user_id"])
            ban_user(tid); _log("ban", tid)
            await reply(f"🚫 Игрок {tid} забанен.")

        elif cmd == "unban":
            tid = int(data["user_id"])
            unban_user(tid); _log("unban", tid)
            await reply(f"✅ Игрок {tid} разбанен.")

        elif cmd == "reset_player":
            tid = int(data["user_id"])
            # Подтверждение через инлайн-кнопку — действие необратимо
            target = get_user(tid)
            if not target:
                await reply(f"❌ Игрок {tid} не найден.")
                return
            await update.message.reply_text(
                f"⚠️ *Подтверждение обнуления*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"Игрок: *{target['wizard_name']}* (ID {tid})\n"
                f"Уровень: {target['level']}, золото: {target['gold']}\n\n"
                f"❗ Все данные игрока будут *удалены безвозвратно*.\n"
                f"При следующем /start он начнёт игру заново с выбора имени.\n\n"
                f"Ты уверен?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("♻️ Да, обнулить", callback_data=f"apanel:resetconfirm:{tid}"),
                    InlineKeyboardButton("❌ Отмена",       callback_data="apanel:main"),
                ]])
            )

        elif cmd == "add_house_pts":
            house = data["house"].lower(); pts = int(data["points"])
            if house not in ("gryffindor","slytherin","ravenclaw","hufflepuff"):
                await reply("❌ Неверный факультет."); return
            with get_conn() as conn:
                execute(conn, "UPDATE house_points SET points=points+%s WHERE house=%s", pts, house)
            _log("add_house_pts", house, str(pts))
            await reply(f"✅ Факультету {house} добавлено {pts} очков.")

        elif cmd == "broadcast":
            msg = data["message"]
            with get_conn() as conn:
                users = fetchall(conn, "SELECT user_id FROM users WHERE COALESCE(is_banned,FALSE)=FALSE")
            sent = 0
            for row in users:
                try:
                    await ctx.bot.send_message(row["user_id"], f"📢 *Объявление*\n\n{msg}", parse_mode="Markdown")
                    sent += 1
                except Exception:
                    pass
            _log("broadcast", "", f"{sent} users")
            await reply(f"✅ Рассылка отправлена {sent} игрокам.")

        elif cmd == "set_maint_msg":
            from database import set_setting
            set_setting("maintenance_msg", data["message"])
            _log("set_maint_msg", "", data["message"][:50])
            await reply(
                f"✅ Сообщение о техработах обновлено:\n\n_{data['message']}_",
                parse_mode="Markdown"
            )

    except ValueError:
        await reply("❌ Неверный формат данных. Попробуй снова через панель.")
    except Exception as e:
        logger.exception("apanel execute %s: %s", cmd, e)
        await reply(f"⚠️ Ошибка: {str(e)[:150]}")

async def _run_instant_command(query, ctx, cmd: str):
    """Мгновенные команды без аргументов — переиспользуем логику admin.py."""
    from handlers import admin as A

    # Обёртка чтобы admin.py-функции (ждут update.message) работали из callback
    class _Wrap:
        def __init__(self, q):
            self._q = q
        @property
        def effective_user(self): return self._q.from_user
        @property
        def message(self): return self._q.message
        @property
        def callback_query(self): return None

    wrap = _Wrap(query)

    INSTANT = {
        "stats":           A.cmd_stats,
        "economy_info":    A.cmd_economy_info,
        "reset_daily":     A.cmd_reset_daily,
        "reset_house_cup": A.cmd_reset_house_cup,
        "maintenance":     A.cmd_maintenance,
        "admin_log":       A.cmd_admin_log,
        "list_items":      A.cmd_list_items,
        "list_spells":     A.cmd_list_spells,
        "list_bosses":     A.cmd_list_bosses,
    }

    if cmd in INSTANT:
        try:
            await INSTANT[cmd](wrap, ctx)
        except Exception as e:
            logger.exception("instant %s: %s", cmd, e)
            await query.message.reply_text(f"⚠️ Ошибка: {str(e)[:150]}")
        return

    if cmd == "spawn_boss":
        from handlers.world_bosses import WORLD_BOSSES, spawn_world_boss
        boss_id = list(WORLD_BOSSES.keys())[0]
        try:
            await spawn_world_boss(boss_id, ctx)
            await query.message.reply_text(f"🐉 Призван босс: {boss_id}")
        except Exception as e:
            await query.message.reply_text(f"⚠️ Ошибка призыва: {str(e)[:120]}")
        return

    if cmd == "start_tournament":
        try:
            from handlers.tournament import open_tournament_registration
            await open_tournament_registration(ctx)
            await query.message.reply_text("🏆 Регистрация на турнир открыта!")
        except Exception as e:
            await query.message.reply_text(f"⚠️ {str(e)[:120]}")
        return

    if cmd == "manage_images":
        try:
            from handlers.images import cmd_images
            class _WImg:
                def __init__(self, q): self._q = q
                @property
                def effective_user(self): return self._q.from_user
                @property
                def message(self): return self._q.message
            await cmd_images(_WImg(query), ctx)
        except Exception as e:
            await query.message.reply_text(f"⚠️ {str(e)[:120]}")
        return

    if cmd == "trigger_ambush":
        try:
            from handlers.ambush import send_ambushes
            # Принудительный запуск + тестовая атака на самого админа,
            # чтобы можно было сразу проверить как выглядит нападение.
            await send_ambushes(ctx.bot, force=True, target_user_id=query.from_user.id)
            await send_ambushes(ctx.bot, force=True)
            await query.message.reply_text(
                "⚔️ Атаки разосланы! Тебе тоже отправлено тестовое нападение — проверь сообщения."
            )
        except Exception as e:
            await query.message.reply_text(f"⚠️ {str(e)[:120]}")
        return

    await query.message.reply_text("❓ Неизвестная команда.")

def register_admin_panel_handlers(app):
    app.add_handler(CommandHandler("admin", cmd_admin_panel))
    app.add_handler(CommandHandler("panel", cmd_admin_panel))
    app.add_handler(CallbackQueryHandler(cb_apanel_cancel, pattern=r"^apanel:cancel$"))
    app.add_handler(CallbackQueryHandler(cb_apanel,        pattern=r"^apanel:"))
    # Текстовый ввод для пошаговых команд — group=3 (после основного роутера)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_apanel_input), group=3)
