"""
Admin handler — полная панель администратора.
Все старые команды сохранены + новые для всех систем Этапов 1-6.
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from config import ADMIN_IDS
from database import (
    get_conn, fetchval, fetchall, fetchrow, execute,
    get_user, ban_user, unban_user, add_xp, add_gold, log_admin_action, add_item_to_inventory,
)
from game.items import ITEMS, item_display_name, item_description, item_bonus_text, rarity_label, type_label
from game.spells import SPELLS, spell_display_name, spell_description, spell_stats_text, spell_rarity_label, spell_type_label
from game.monsters import MONSTERS

logger = logging.getLogger(__name__)
_maintenance_mode = False


def admin_only(func):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not ADMIN_IDS or update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Доступ запрещён.")
            return
        return await func(update, ctx)
    wrapper.__name__ = func.__name__
    return wrapper


def is_maintenance() -> bool:
    return _maintenance_mode


# ── /admin — главное меню ──────────────────────────────────────────────────────
@admin_only
async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛠 *Панель администратора*\n\n"
        "*Игроки:*\n"
        "/give\\_gold `<id> <сумма>` — Выдать золото\n"
        "/give\\_xp `<id> <xp>` — Выдать опыт\n"
        "/give\\_item `<id> <item_id>` — Выдать предмет\n"
        "/give\\_spell `<id> <spell_id>` — Выдать заклинание\n"
        "/set\\_level `<id> <lvl>` — Установить уровень\n"
        "/set\\_house `<id> <house>` — Изменить факультет\n"
        "/player\\_info `<id>` — Полная инфо об игроке\n"
        "/ban `<id>` — Заблокировать\n"
        "/unban `<id>` — Разблокировать\n\n"
        "*События:*\n"
        "/admin\\_wb `<boss_id>` — Спавнить мирового босса\n"
        "/admin\\_tournament — Открыть турнир\n"
        "/event\\_start `<boss_id>` — Запустить ивент\n\n"
        "*Управление:*\n"
        "/stats — Статистика бота\n"
        "/broadcast `<текст>` — Рассылка всем\n"
        "/reset\\_daily — Сброс дейли лимитов\n"
        "/reset\\_house\\_cup — Сброс Кубка факультетов\n"
        "/add\\_house\\_pts `<house> <pts>` — Добавить очки факультету\n"
        "/economy\\_info — Состояние экономики\n"
        "/maintenance — Тех. обслуживание вкл/выкл\n"
        "/admin\\_log — Последние действия\n\n"
        "*Контент:*\n"
        "/list\\_items — Список предметов\n"
        "/list\\_spells — Список заклинаний\n"
        "/list\\_bosses — Список боссов",
        parse_mode="Markdown"
    )


# ── Статистика ────────────────────────────────────────────────────────────────
@admin_only
async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    with get_conn() as conn:
        total       = fetchval(conn, "SELECT COUNT(*) FROM users")
        today       = fetchval(conn, "SELECT COUNT(*) FROM users WHERE created_at::date = CURRENT_DATE")
        banned      = fetchval(conn, "SELECT COUNT(*) FROM users WHERE is_banned = TRUE")
        houses      = fetchall(conn, "SELECT house, COUNT(*) as cnt FROM users GROUP BY house ORDER BY cnt DESC")
        pvp_today   = fetchval(conn, "SELECT COUNT(*) FROM duels WHERE started_at::date = CURRENT_DATE")
        pve_today   = fetchval(conn, "SELECT COUNT(*) FROM pve_sessions WHERE created_at::date = CURRENT_DATE")
        total_gold  = fetchval(conn, "SELECT SUM(gold) FROM users")
        avg_level   = fetchval(conn, "SELECT AVG(level)::numeric(5,1) FROM users")
        wb_active   = fetchval(conn, "SELECT COUNT(*) FROM world_bosses WHERE status = 'active'")
        squads      = fetchval(conn, "SELECT COUNT(*) FROM squads")
        active_lots = fetchval(conn, "SELECT COUNT(*) FROM auction_lots WHERE status = 'active'")

    lines = [
        "📊 *Статистика бота*\n",
        f"👥 Всего игроков: {total}",
        f"🆕 Сегодня: {today}",
        f"🔨 Забанено: {banned}",
        f"📈 Средний уровень: {avg_level or 0}",
        f"⚔️ Дуэлей сегодня: {pvp_today}",
        f"🏰 PvE боёв сегодня: {pve_today}",
        f"💰 Золото в обращении: {total_gold or 0:,}",
        f"🌍 Активных мировых боссов: {wb_active}",
        f"🛡️ Отрядов: {squads}",
        f"🏛️ Активных лотов: {active_lots}",
        "\n*Факультеты:*",
    ]
    for row in houses:
        lines.append(f"• {row['house']}: {row['cnt']}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── Игроки ────────────────────────────────────────────────────────────────────
@admin_only
async def cmd_give_gold(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("Использование: /give_gold <user_id> <сумма>")
        return
    try:
        target_id = int(ctx.args[0]); amount = int(ctx.args[1])
    except ValueError:
        await update.message.reply_text("❌ Неверные аргументы."); return
    add_gold(target_id, amount)
    log_admin_action(update.effective_user.id, "give_gold", target_id, str(amount))
    await update.message.reply_text(f"✅ Выдано {amount} 💰 игроку {target_id}.")
    try:
        await ctx.bot.send_message(target_id, f"🎁 Администратор выдал тебе {amount} 💰!")
    except Exception:
        pass


@admin_only
async def cmd_give_xp(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("Использование: /give_xp <user_id> <xp>")
        return
    try:
        target_id = int(ctx.args[0]); xp = int(ctx.args[1])
    except ValueError:
        await update.message.reply_text("❌ Неверные аргументы."); return
    new_level, leveled = add_xp(target_id, xp)
    log_admin_action(update.effective_user.id, "give_xp", target_id, str(xp))
    lvl_text = f" (повышение до {new_level}!)" if leveled else ""
    await update.message.reply_text(f"✅ Выдано {xp} XP игроку {target_id}{lvl_text}.")
    try:
        await ctx.bot.send_message(target_id, f"🎁 Администратор выдал тебе {xp} XP!" + lvl_text)
    except Exception:
        pass


@admin_only
async def cmd_give_item(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("Использование: /give_item <user_id> <item_id>")
        return
    try:
        target_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Неверный user_id."); return
    item_id = ctx.args[1]
    item = ITEMS.get(item_id)
    if not item:
        await update.message.reply_text(f"❌ Предмет '{item_id}' не найден."); return
    add_item_to_inventory(target_id, item_id, 1)
    name = item_display_name(item, "ru")
    log_admin_action(update.effective_user.id, "give_item", target_id, item_id)
    await update.message.reply_text(f"✅ Предмет {name} выдан игроку {target_id}.")
    try:
        await ctx.bot.send_message(target_id, f"🎁 Администратор выдал тебе предмет: *{name}*!", parse_mode="Markdown")
    except Exception:
        pass


@admin_only
async def cmd_give_spell(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("Использование: /give_spell <user_id> <spell_id>")
        return
    try:
        target_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Неверный user_id."); return
    spell_id = ctx.args[1]
    spell = SPELLS.get(spell_id)
    if not spell:
        await update.message.reply_text(f"❌ Заклинание '{spell_id}' не найдено."); return
    with get_conn() as conn:
        execute(conn, "INSERT INTO user_spells (user_id, spell_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", target_id, spell_id)
    name = spell_display_name(spell_id, "ru")
    log_admin_action(update.effective_user.id, "give_spell", target_id, spell_id)
    await update.message.reply_text(f"✅ Заклинание {name} выдано игроку {target_id}.")
    try:
        await ctx.bot.send_message(target_id, f"🎁 Администратор выдал тебе заклинание: *{name}*!", parse_mode="Markdown")
    except Exception:
        pass


@admin_only
async def cmd_set_level(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("Использование: /set_level <user_id> <level>")
        return
    try:
        target_id = int(ctx.args[0]); level = int(ctx.args[1])
    except ValueError:
        await update.message.reply_text("❌ Неверные аргументы."); return
    if level < 1 or level > 100:
        await update.message.reply_text("❌ Уровень должен быть от 1 до 100."); return
    with get_conn() as conn:
        execute(conn, "UPDATE users SET level = %s, xp = 0 WHERE user_id = %s", level, target_id)
    log_admin_action(update.effective_user.id, "set_level", target_id, str(level))
    await update.message.reply_text(f"✅ Уровень игрока {target_id} установлен: {level}.")


@admin_only
async def cmd_set_house(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("Использование: /set_house <user_id> <gryffindor/slytherin/ravenclaw/hufflepuff>")
        return
    try:
        target_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Неверный user_id."); return
    house = ctx.args[1].lower()
    if house not in ("gryffindor", "slytherin", "ravenclaw", "hufflepuff"):
        await update.message.reply_text("❌ Неверный факультет."); return
    with get_conn() as conn:
        execute(conn, "UPDATE users SET house = %s WHERE user_id = %s", house, target_id)
    log_admin_action(update.effective_user.id, "set_house", target_id, house)
    await update.message.reply_text(f"✅ Факультет игрока {target_id} изменён на {house}.")


@admin_only
async def cmd_player_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Использование: /player_info <user_id>")
        return
    try:
        target_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Неверный user_id."); return
    user = get_user(target_id)
    if not user:
        await update.message.reply_text("❌ Игрок не найден."); return
    with get_conn() as conn:
        stats    = fetchrow(conn, "SELECT * FROM user_stats WHERE user_id = %s", target_id)
        spells   = fetchval(conn, "SELECT COUNT(*) FROM user_spells WHERE user_id = %s", target_id)
        items    = fetchval(conn, "SELECT COUNT(*) FROM inventory WHERE user_id = %s", target_id)
        titles   = fetchval(conn, "SELECT COUNT(*) FROM user_titles WHERE user_id = %s", target_id)
        achievements = fetchval(conn, "SELECT COUNT(*) FROM achievements WHERE user_id = %s", target_id)

    lines = [
        f"👤 *Игрок {user['wizard_name']}*\n",
        f"ID: `{target_id}`",
        f"Уровень: {user['level']} | XP: {user['xp']}",
        f"Факультет: {user['house']}",
        f"HP: {user['hp']}/{user['max_hp']} | Мана: {user['mana']}/{user['max_mana']}",
        f"Атака: {user['attack']} | Защита: {user['defense']}",
        f"Золото: {user['gold']:,}",
        f"Забанен: {'Да' if user['is_banned'] else 'Нет'}",
        f"Титул: {user.get('title','нет')}",
        f"\n*Статистика:*",
        f"PvP победы: {stats['pvp_wins'] if stats else 0}",
        f"PvE убийства: {stats['pve_kills'] if stats else 0}",
        f"Боссы: {stats['boss_kills'] if stats else 0}",
        f"Уроки: {stats['lessons_done'] if stats else 0}",
        f"Зелий сварено: {stats['potions_brewed'] if stats else 0}",
        f"\n*Инвентарь:*",
        f"Заклинаний: {spells} | Предметов: {items}",
        f"Достижений: {achievements} | Титулов: {titles}",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@admin_only
async def cmd_ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Использование: /ban <user_id>"); return
    try:
        target_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Неверный user_id."); return
    ban_user(target_id)
    log_admin_action(update.effective_user.id, "ban", target_id, "")
    await update.message.reply_text(f"🔨 Игрок {target_id} заблокирован.")
    try:
        await ctx.bot.send_message(target_id, "⛔ Вы заблокированы.")
    except Exception:
        pass


@admin_only
async def cmd_unban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Использование: /unban <user_id>"); return
    try:
        target_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Неверный user_id."); return
    unban_user(target_id)
    log_admin_action(update.effective_user.id, "unban", target_id, "")
    await update.message.reply_text(f"✅ Игрок {target_id} разблокирован.")
    try:
        await ctx.bot.send_message(target_id, "✅ Блокировка снята.")
    except Exception:
        pass


# ── События ───────────────────────────────────────────────────────────────────
@admin_only
async def cmd_admin_wb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from handlers.world_bosses import WORLD_BOSSES, spawn_world_boss
    if not ctx.args:
        bosses = list(WORLD_BOSSES.keys())
        await update.message.reply_text(f"Использование: /admin_wb <boss_id>\nДоступные: {', '.join(bosses)}")
        return
    boss_id = ctx.args[0]
    if boss_id not in WORLD_BOSSES:
        await update.message.reply_text(f"❌ Мировой босс '{boss_id}' не найден.")
        return
    ok = await spawn_world_boss(boss_id, ctx)
    if ok:
        log_admin_action(update.effective_user.id, "spawn_wb", None, boss_id)
        await update.message.reply_text(f"✅ Мировой босс {boss_id} заспавнен!")
    else:
        await update.message.reply_text("❌ Уже есть активный мировой босс.")


@admin_only
async def cmd_admin_tournament(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from handlers.tournament import open_tournament_registration
    await open_tournament_registration(ctx)
    log_admin_action(update.effective_user.id, "open_tournament", None, "")
    await update.message.reply_text("✅ Регистрация на турнир открыта!")


@admin_only
async def cmd_event_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    boss_id = ctx.args[0] if ctx.args else "aragog"
    if boss_id not in MONSTERS:
        bosses = [bid for bid, m in MONSTERS.items() if m.get("is_boss")]
        await update.message.reply_text(f"❌ Босс не найден. Доступные: {', '.join(bosses)}")
        return
    from handlers.events import start_weekly_event
    await start_weekly_event(ctx.bot, boss_id)
    log_admin_action(update.effective_user.id, "event_start", None, boss_id)
    await update.message.reply_text(f"✅ Ивент с боссом {boss_id} запущен!")


# ── Управление ────────────────────────────────────────────────────────────────
@admin_only
async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Использование: /broadcast <текст>"); return
    text = " ".join(ctx.args)
    with get_conn() as conn:
        user_ids = fetchall(conn, "SELECT user_id FROM users WHERE is_banned = FALSE")
    sent = failed = 0
    for row in user_ids:
        try:
            await ctx.bot.send_message(row["user_id"], text)
            sent += 1
        except Exception:
            failed += 1
    log_admin_action(update.effective_user.id, "broadcast", None, f"sent={sent}")
    await update.message.reply_text(f"✅ Отправлено: {sent}\n❌ Ошибок: {failed}")


@admin_only
async def cmd_reset_daily(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    with get_conn() as conn:
        execute(conn, "DELETE FROM daily_limits WHERE date = CURRENT_DATE")
    log_admin_action(update.effective_user.id, "reset_daily", None, "")
    await update.message.reply_text("✅ Дейли лимиты сброшены.")


@admin_only
async def cmd_reset_house_cup(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from database import reset_house_cup_points
    reset_house_cup_points()
    log_admin_action(update.effective_user.id, "reset_house_cup", None, "")
    await update.message.reply_text("✅ Кубок факультетов сброшен. Новый сезон начат.")


@admin_only
async def cmd_add_house_pts(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("Использование: /add_house_pts <house> <points>"); return
    house = ctx.args[0].lower()
    if house not in ("gryffindor", "slytherin", "ravenclaw", "hufflepuff"):
        await update.message.reply_text("❌ Неверный факультет."); return
    try:
        pts = int(ctx.args[1])
    except ValueError:
        await update.message.reply_text("❌ Неверные очки."); return
    with get_conn() as conn:
        execute(conn, "UPDATE house_points SET points = points + %s WHERE house = %s", pts, house)
    log_admin_action(update.effective_user.id, "add_house_pts", None, f"{house}+{pts}")
    await update.message.reply_text(f"✅ {house} +{pts} очков.")


@admin_only
async def cmd_economy_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    with get_conn() as conn:
        total_gold = fetchval(conn, "SELECT SUM(gold) FROM users") or 0
        max_gold   = fetchval(conn, "SELECT MAX(gold) FROM users") or 0
        avg_gold   = fetchval(conn, "SELECT AVG(gold)::numeric(10,0) FROM users") or 0
        rich_players = fetchall(conn, "SELECT wizard_name, gold FROM users ORDER BY gold DESC LIMIT 5")
        trades_today = fetchval(conn, "SELECT COUNT(*) FROM trade_log WHERE created_at::date = CURRENT_DATE") or 0
        trade_vol    = fetchval(conn, "SELECT SUM(amount) FROM trade_log WHERE created_at::date = CURRENT_DATE") or 0

    lines = [
        "💰 *Экономика*\n",
        f"Всего золота: {total_gold:,}",
        f"Среднее: {avg_gold:,}",
        f"Максимум: {max_gold:,}",
        f"Переводов сегодня: {trades_today} ({trade_vol:,} 💰)",
        "\n*Топ богачей:*",
    ]
    for r in rich_players:
        lines.append(f"• {r['wizard_name']}: {r['gold']:,} 💰")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@admin_only
async def cmd_maintenance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global _maintenance_mode
    _maintenance_mode = not _maintenance_mode
    status = "включён" if _maintenance_mode else "выключен"
    log_admin_action(update.effective_user.id, "maintenance", None, str(_maintenance_mode))
    await update.message.reply_text(f"🛠 Тех. обслуживание {status}.")


@admin_only
async def cmd_admin_log(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    with get_conn() as conn:
        rows = fetchall(conn, """
            SELECT admin_id, action, target_id, details, created_at
            FROM admin_log ORDER BY created_at DESC LIMIT 15
        """)
    if not rows:
        await update.message.reply_text("Лог пуст.")
        return
    lines = ["📋 *Последние действия:*\n"]
    for r in rows:
        dt = r["created_at"].strftime("%d.%m %H:%M")
        lines.append(f"`{dt}` [{r['admin_id']}] {r['action']} → {r['target_id']} {r['details'] or ''}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── Контент ───────────────────────────────────────────────────────────────────
@admin_only
async def cmd_list_items(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rows = sorted(ITEMS.items())
    lines = [f"🎒 Список предметов ({len(rows)}):\n"]
    for iid, item in rows:
        bonus = item_bonus_text(item, "ru")
        bonus_inline = f" | {bonus.replace(chr(10), '; ')}" if bonus else ""
        lines.append(
            f"• `{iid}` — *{item_display_name(item, 'ru')}*\n"
            f"  ⭐ {rarity_label(item.get('rarity', 'common'), 'ru')} · {type_label(item.get('type', 'item'), 'ru')}{bonus_inline}\n"
            f"  📜 {item_description(item, 'ru')}"
        )

    text = "\n".join(lines)
    for i in range(0, len(text), 3900):
        await update.message.reply_text(text[i:i + 3900], parse_mode="Markdown")


@admin_only
async def cmd_list_spells(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rows = sorted(SPELLS.items())
    lines = [f"✨ Список заклинаний ({len(rows)}):\n"]
    for sid, spell in rows:
        stats = spell_stats_text(spell, "ru").replace("\n", " | ")
        lines.append(
            f"• `{sid}` — *{spell_display_name(sid, 'ru')}*\n"
            f"  ⭐ {spell_rarity_label(spell.get('rarity', 'common'), 'ru')} · {spell_type_label(spell.get('type', ''), 'ru')}\n"
            f"  📜 {spell_description(spell, 'ru')}\n"
            f"  {stats}"
        )

    text = "\n".join(lines)
    for i in range(0, len(text), 3900):
        await update.message.reply_text(text[i:i + 3900], parse_mode="Markdown")



@admin_only
async def cmd_list_bosses(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from handlers.world_bosses import WORLD_BOSSES
    regular_bosses = [bid for bid, m in MONSTERS.items() if m.get("is_boss")]
    wb_list = list(WORLD_BOSSES.keys())
    # Boss IDs содержат _ поэтому не используем Markdown
    lines = [
        f"👑 Обычные боссы: {', '.join(regular_bosses)}",
        f"\n🌍 Мировые боссы: {', '.join(wb_list)}",
    ]
    await update.message.reply_text("\n".join(lines))


def register_admin_handlers(app):
    app.add_handler(CommandHandler("admin",           cmd_admin))
    app.add_handler(CommandHandler("stats",           cmd_stats))
    app.add_handler(CommandHandler("broadcast",       cmd_broadcast))
    app.add_handler(CommandHandler("give_gold",       cmd_give_gold))
    app.add_handler(CommandHandler("give_xp",         cmd_give_xp))
    app.add_handler(CommandHandler("give_item",       cmd_give_item))
    app.add_handler(CommandHandler("give_spell",      cmd_give_spell))
    app.add_handler(CommandHandler("set_level",       cmd_set_level))
    app.add_handler(CommandHandler("set_house",       cmd_set_house))
    app.add_handler(CommandHandler("player_info",     cmd_player_info))
    app.add_handler(CommandHandler("ban",             cmd_ban))
    app.add_handler(CommandHandler("unban",           cmd_unban))
    app.add_handler(CommandHandler("admin_wb",        cmd_admin_wb))
    app.add_handler(CommandHandler("admin_tournament",cmd_admin_tournament))
    app.add_handler(CommandHandler("event_start",     cmd_event_start))
    app.add_handler(CommandHandler("reset_daily",     cmd_reset_daily))
    app.add_handler(CommandHandler("reset_house_cup", cmd_reset_house_cup))
    app.add_handler(CommandHandler("add_house_pts",   cmd_add_house_pts))
    app.add_handler(CommandHandler("economy_info",    cmd_economy_info))
    app.add_handler(CommandHandler("maintenance",     cmd_maintenance))
    app.add_handler(CommandHandler("admin_log",       cmd_admin_log))
    app.add_handler(CommandHandler("list_items",      cmd_list_items))
    app.add_handler(CommandHandler("list_spells",     cmd_list_spells))
    app.add_handler(CommandHandler("list_bosses",     cmd_list_bosses))
    app.add_handler(CommandHandler("list_boses",      cmd_list_bosses))
