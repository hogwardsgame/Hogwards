"""
Дуэльные лиги — рейтинг ELO и дивизионы.
Игроки получают/теряют рейтинг за дуэли, поднимаются по дивизионам.
Сезон длится месяц, в конце — награды по дивизиону.
"""
import logging
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import user_exists, get_user, get_conn, execute, fetchrow, fetchall, add_gold, add_xp
from utils.i18n import t

logger = logging.getLogger(__name__)

START_ELO = 1000
K_FACTOR  = 32   # макс. изменение рейтинга за бой

# ── Дивизионы по рейтингу ─────────────────────────────────────────────────────
DIVISIONS = [
    (0,    "🥉 Бронза",    "bronze"),
    (1100, "🥈 Серебро",   "silver"),
    (1300, "🥇 Золото",    "gold"),
    (1500, "💎 Платина",   "platinum"),
    (1750, "💠 Алмаз",     "diamond"),
    (2000, "👑 Мастер",    "master"),
    (2300, "🌟 Легенда",   "legend"),
]

# Награды в конце сезона по дивизиону
SEASON_REWARDS = {
    "bronze":   {"gold": 200,  "xp": 100},
    "silver":   {"gold": 500,  "xp": 300},
    "gold":     {"gold": 1000, "xp": 600},
    "platinum": {"gold": 2000, "xp": 1200, "title": "Дуэлянт-платина"},
    "diamond":  {"gold": 3500, "xp": 2000, "title": "Алмазный дуэлянт"},
    "master":   {"gold": 6000, "xp": 4000, "title": "Мастер дуэлей"},
    "legend":   {"gold": 12000,"xp": 8000, "title": "Легенда арены"},
}

def _ensure_table():
    try:
        with get_conn() as conn:
            execute(conn, """
                CREATE TABLE IF NOT EXISTS duel_league (
                    user_id    BIGINT PRIMARY KEY,
                    elo        INT DEFAULT 1000,
                    wins       INT DEFAULT 0,
                    losses     INT DEFAULT 0,
                    peak_elo   INT DEFAULT 1000,
                    season     INT DEFAULT 1,
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
    except Exception as e:
        logger.warning("duel_league table: %s", e)

def _get_division(elo: int) -> tuple[str, str]:
    div_name, div_id = DIVISIONS[0][1], DIVISIONS[0][2]
    for threshold, name, did in DIVISIONS:
        if elo >= threshold:
            div_name, div_id = name, did
    return div_name, div_id

def _next_division(elo: int):
    for threshold, name, did in DIVISIONS:
        if elo < threshold:
            return name, threshold
    return None

def _get_rating(user_id: int) -> dict:
    _ensure_table()
    try:
        with get_conn() as conn:
            row = fetchrow(conn, "SELECT * FROM duel_league WHERE user_id=%s", user_id)
            if not row:
                execute(conn, "INSERT INTO duel_league (user_id, elo, peak_elo) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                        user_id, START_ELO, START_ELO)
                row = {"user_id": user_id, "elo": START_ELO, "wins": 0, "losses": 0, "peak_elo": START_ELO}
        return row
    except Exception:
        return {"user_id": user_id, "elo": START_ELO, "wins": 0, "losses": 0, "peak_elo": START_ELO}

def _expected_score(elo_a: int, elo_b: int) -> float:
    return 1 / (1 + 10 ** ((elo_b - elo_a) / 400))

def update_elo(winner_id: int, loser_id: int):
    """Обновить ELO после дуэли. Вызывается из duel.py."""
    if not winner_id or not loser_id or winner_id == loser_id:
        return
    _ensure_table()
    w = _get_rating(winner_id)
    l = _get_rating(loser_id)
    exp_w = _expected_score(w["elo"], l["elo"])
    exp_l = _expected_score(l["elo"], w["elo"])
    new_w = round(w["elo"] + K_FACTOR * (1 - exp_w))
    new_l = max(0, round(l["elo"] + K_FACTOR * (0 - exp_l)))
    try:
        with get_conn() as conn:
            execute(conn, """
                UPDATE duel_league SET elo=%s, wins=wins+1,
                    peak_elo=GREATEST(peak_elo,%s), updated_at=NOW() WHERE user_id=%s
            """, new_w, new_w, winner_id)
            execute(conn, """
                UPDATE duel_league SET elo=%s, losses=losses+1, updated_at=NOW() WHERE user_id=%s
            """, new_l, loser_id)
    except Exception as e:
        logger.warning("update_elo: %s", e)
    return new_w - w["elo"], new_l - l["elo"]

async def cmd_league(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return
    r = _get_rating(user_id)
    elo = r["elo"]
    div_name, div_id = _get_division(elo)
    total = r["wins"] + r["losses"]
    wr = f"{int(r['wins']/total*100)}%" if total else "—"

    from utils.helpers import progress_bar
    nxt = _next_division(elo)
    if nxt:
        nxt_name, nxt_thr = nxt
        prev_thr = max((t for t,_,_ in DIVISIONS if t <= elo), default=0)
        prog = progress_bar(elo - prev_thr, nxt_thr - prev_thr)
        next_line = f"\n📈 До {nxt_name}: {prog} {elo}/{nxt_thr}"
    else:
        next_line = "\n👑 Высший дивизион достигнут!"

    text = (
        f"⚔️ *Дуэльная лига*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Дивизион: *{div_name}*\n"
        f"📊 Рейтинг: *{elo}* ELO\n"
        f"🏔️ Пик сезона: {r['peak_elo']} ELO\n"
        f"⚔️ Побед/Поражений: {r['wins']}/{r['losses']} ({wr})"
        f"{next_line}\n\n"
        f"_Побеждай в дуэлях, поднимай рейтинг и дивизион!_\n"
        f"_В конце сезона — награды по дивизиону._"
    )
    await update.message.reply_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏆 Таблица лидеров", callback_data="league_top")
        ]])
    )

async def cb_league_top(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    from config import ADMIN_IDS
    admin_ids = list(ADMIN_IDS) if ADMIN_IDS else [0]
    try:
        with get_conn() as conn:
            rows = fetchall(conn, """
                SELECT dl.user_id, dl.elo, dl.wins, dl.losses, u.wizard_name, u.house
                FROM duel_league dl JOIN users u ON u.user_id = dl.user_id
                WHERE dl.user_id != ALL(%s)
                ORDER BY dl.elo DESC LIMIT 15
            """, admin_ids)
    except Exception:
        rows = []

    from utils.helpers import house_emoji, medal
    lines = ["🏆 *Топ дуэлянтов сезона*\n━━━━━━━━━━━━━━━━━━━━"]
    if not rows:
        lines.append("_Пока нет участников._")
    for i, r in enumerate(rows, 1):
        div_name, _ = _get_division(r["elo"])
        lines.append(f"{medal(i)} {house_emoji(r['house'])} {r['wizard_name']} — {r['elo']} ELO {div_name.split()[0]}")

    await query.edit_message_text(
        "\n".join(lines), parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Назад", callback_data="league_back")
        ]])
    )

async def cb_league_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Переоткрываем как cmd_league
    class _W:
        def __init__(self,q): self._q=q
        @property
        def effective_user(self): return self._q.from_user
        @property
        def message(self): return self._q.message
    await cmd_league(_W(query), ctx)

async def finalize_season(bot):
    """Выдать награды по дивизионам и сбросить сезон. Вызывается планировщиком 1-го числа."""
    _ensure_table()
    try:
        with get_conn() as conn:
            players = fetchall(conn, "SELECT user_id, elo FROM duel_league WHERE wins+losses > 0")
    except Exception:
        return
    for p in players:
        _, div_id = _get_division(p["elo"])
        reward = SEASON_REWARDS.get(div_id, {})
        if reward:
            add_gold(p["user_id"], reward.get("gold", 0))
            add_xp(p["user_id"], reward.get("xp", 0))
            if reward.get("title"):
                try:
                    with get_conn() as conn:
                        execute(conn, "INSERT INTO user_titles (user_id, title) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                                p["user_id"], reward["title"])
                except Exception:
                    pass
            try:
                await bot.send_message(p["user_id"],
                    f"🏆 *Сезон дуэльной лиги завершён!*\n\n"
                    f"Твой дивизион: {_get_division(p['elo'])[0]}\n"
                    f"Награда: +{reward.get('gold',0)} 💰, +{reward.get('xp',0)} XP"
                    + (f"\nТитул: «{reward['title']}»" if reward.get('title') else ""),
                    parse_mode="Markdown")
            except Exception:
                pass
    # Мягкий сброс: ELO стремится к 1000 (soft reset)
    try:
        with get_conn() as conn:
            execute(conn, "UPDATE duel_league SET elo = (elo + 1000)/2, wins=0, losses=0, season=season+1, peak_elo=(elo+1000)/2")
    except Exception:
        pass

def register_duel_league_handlers(app):
    app.add_handler(CommandHandler("league", cmd_league))
    app.add_handler(CallbackQueryHandler(cb_league_top,  pattern=r"^league_top$"))
    app.add_handler(CallbackQueryHandler(cb_league_back, pattern=r"^league_back$"))
