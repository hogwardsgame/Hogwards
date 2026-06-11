"""
Гринготтс-банк.
Вклад под 1% в день, снятие, история транзакций.
Золото на вкладе защищено от дуэльных штрафов.
"""
import logging
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from database import get_user, user_exists, get_conn, execute, fetchrow, fetchall
from utils.i18n import t

logger = logging.getLogger(__name__)

INTEREST_RATE  = 0.01   # 1% в день
MIN_DEPOSIT    = 100
MAX_DEPOSIT    = 1_000_000
INTEREST_CAP   = 10_000  # максимум процентов в день

def _ensure_tables():
    try:
        with get_conn() as conn:
            execute(conn, """
                CREATE TABLE IF NOT EXISTS gringotts (
                    user_id      BIGINT PRIMARY KEY,
                    balance      INT DEFAULT 0,
                    last_interest TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            execute(conn, """
                CREATE TABLE IF NOT EXISTS gringotts_log (
                    id        SERIAL PRIMARY KEY,
                    user_id   BIGINT NOT NULL,
                    action    TEXT NOT NULL,
                    amount    INT NOT NULL,
                    balance   INT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
    except Exception as e:
        logger.warning("gringotts tables: %s", e)

def _get_account(user_id: int) -> dict:
    _ensure_tables()
    try:
        with get_conn() as conn:
            row = fetchrow(conn, "SELECT * FROM gringotts WHERE user_id=%s", user_id)
        return row or {"user_id": user_id, "balance": 0, "last_interest": datetime.now(timezone.utc)}
    except Exception:
        return {"user_id": user_id, "balance": 0, "last_interest": datetime.now(timezone.utc)}

def _calc_interest(account: dict) -> tuple[int, int]:
    """Возвращает (проценты_к_начислению, дней_прошло)."""
    if account["balance"] <= 0:
        return 0, 0
    last = account["last_interest"]
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    now   = datetime.now(timezone.utc)
    days  = max(0, int((now - last).total_seconds() / 86400))
    if days == 0:
        return 0, 0
    total_interest = 0
    balance = account["balance"]
    for _ in range(min(days, 30)):  # не более 30 дней накопления
        daily = min(int(balance * INTEREST_RATE), INTEREST_CAP)
        total_interest += daily
        balance += daily
    return total_interest, days

def _apply_interest(user_id: int, account: dict):
    interest, days = _calc_interest(account)
    if interest <= 0:
        return 0
    try:
        with get_conn() as conn:
            execute(conn, """
                UPDATE gringotts SET balance=balance+%s, last_interest=NOW()
                WHERE user_id=%s
            """, interest, user_id)
            execute(conn, """
                INSERT INTO gringotts_log (user_id, action, amount, balance)
                VALUES (%s, 'interest', %s, (SELECT balance FROM gringotts WHERE user_id=%s))
            """, user_id, interest, user_id)
    except Exception:
        pass
    return interest

def _gringotts_text(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    account  = _get_account(user_id)
    interest, days = _calc_interest(account)
    balance  = account["balance"]
    user     = get_user(user_id)
    wallet   = user["gold"]

    next_interest = int(balance * INTEREST_RATE)
    daily_text    = f"+{min(next_interest, INTEREST_CAP)} 💰 завтра" if balance > 0 else "—"

    pending = f"\n⏳ Накоплено процентов: +{interest} 💰 за {days} дн." if interest > 0 else ""

    text = (
        f"🏦 *Банк Гринготтс*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 На руках: {wallet:,} золота\n"
        f"🏦 На вкладе: {balance:,} золота\n"
        f"📈 Ставка: {int(INTEREST_RATE*100)}% в день (макс. {INTEREST_CAP:,}/день)\n"
        f"💵 Следующие проценты: {daily_text}"
        f"{pending}\n\n"
        f"_Золото на вкладе защищено. Минимальный вклад: {MIN_DEPOSIT} 💰_"
    )
    buttons = []
    if interest > 0:
        buttons.append([InlineKeyboardButton(f"💰 Получить проценты +{interest}", callback_data="gb_collect")])
    buttons.append([InlineKeyboardButton("📥 Внести золото", callback_data="gb_deposit")])
    if balance > 0:
        buttons.append([InlineKeyboardButton("📤 Снять золото", callback_data="gb_withdraw")])
    buttons.append([InlineKeyboardButton("📋 История", callback_data="gb_history")])
    return text, InlineKeyboardMarkup(buttons)

async def cmd_gringotts(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return
    text, markup = _gringotts_text(user_id)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)

async def cb_gb_collect(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    account = _get_account(user_id)
    earned  = _apply_interest(user_id, account)
    if earned > 0:
        await query.answer(f"✅ Получено {earned} 💰 процентов!", show_alert=True)
    text, markup = _gringotts_text(user_id)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)

async def cb_gb_deposit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    ctx.user_data["gb_action"] = "deposit"
    user    = get_user(user_id)
    await query.edit_message_text(
        f"📥 *Внести золото*\n\n"
        f"На руках: {user['gold']:,} 💰\n"
        f"Минимум: {MIN_DEPOSIT} | Максимум: {MAX_DEPOSIT:,}\n\n"
        f"Введи сумму:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Отмена", callback_data="gb_cancel")
        ]])
    )

async def cb_gb_withdraw(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    account = _get_account(user_id)
    ctx.user_data["gb_action"] = "withdraw"
    await query.edit_message_text(
        f"📤 *Снять золото*\n\n"
        f"На вкладе: {account['balance']:,} 💰\n\n"
        f"Введи сумму:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📤 Снять всё", callback_data="gb_withdraw_all"),
            InlineKeyboardButton("❌ Отмена",    callback_data="gb_cancel"),
        ]])
    )

async def cb_gb_withdraw_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    account = _get_account(user_id)
    amount  = account["balance"]
    if amount <= 0:
        await query.answer("Вклад пуст.", show_alert=True)
        return
    _apply_interest(user_id, account)
    with get_conn() as conn:
        execute(conn, "UPDATE users SET gold=gold+%s WHERE user_id=%s", amount, user_id)
        execute(conn, "UPDATE gringotts SET balance=0 WHERE user_id=%s", user_id)
        execute(conn, "INSERT INTO gringotts_log (user_id, action, amount, balance) VALUES (%s,'withdraw',%s,0)", user_id, amount)
    ctx.user_data.pop("gb_action", None)
    await query.answer(f"✅ Снято {amount:,} 💰", show_alert=True)
    text, markup = _gringotts_text(user_id)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)

async def cb_gb_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    ctx.user_data.pop("gb_action", None)
    text, markup = _gringotts_text(user_id)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)

async def cb_gb_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    try:
        with get_conn() as conn:
            rows = fetchall(conn,
                "SELECT action, amount, balance, created_at FROM gringotts_log "
                "WHERE user_id=%s ORDER BY created_at DESC LIMIT 10", user_id)
    except Exception:
        rows = []

    action_labels = {"deposit":"📥 Вклад","withdraw":"📤 Снятие","interest":"💹 Проценты"}
    lines = ["📋 *История операций*\n━━━━━━━━━━━━━━━━━━━━"]
    if not rows:
        lines.append("_Операций пока нет_")
    for r in rows:
        label = action_labels.get(r["action"], r["action"])
        dt    = r["created_at"].strftime("%d.%m %H:%M") if r.get("created_at") else ""
        sign  = "+" if r["action"] != "withdraw" else "-"
        lines.append(f"{label}: {sign}{r['amount']:,} 💰  `{dt}`")

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Назад", callback_data="gb_back")
        ]])
    )

async def cb_gb_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    text, markup = _gringotts_text(user_id)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)

async def handle_gb_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод суммы для вклада/снятия."""
    user_id = update.effective_user.id
    action  = ctx.user_data.get("gb_action")
    if not action:
        return

    text_in = update.message.text.strip().replace(" ", "").replace(",", "")
    if not text_in.isdigit():
        await update.message.reply_text("❌ Введи число.")
        return

    amount = int(text_in)
    user   = get_user(user_id)
    account = _get_account(user_id)

    if action == "deposit":
        if amount < MIN_DEPOSIT:
            await update.message.reply_text(f"❌ Минимальный вклад: {MIN_DEPOSIT} 💰")
            return
        if amount > user["gold"]:
            await update.message.reply_text(f"❌ У тебя только {user['gold']:,} 💰")
            return
        if amount + account["balance"] > MAX_DEPOSIT:
            amount = MAX_DEPOSIT - account["balance"]
            if amount <= 0:
                await update.message.reply_text(f"❌ Вклад уже максимальный ({MAX_DEPOSIT:,}).")
                return
        _apply_interest(user_id, account)
        with get_conn() as conn:
            execute(conn, "UPDATE users SET gold=gold-%s WHERE user_id=%s", amount, user_id)
            execute(conn, """
                INSERT INTO gringotts (user_id, balance, last_interest)
                VALUES (%s,%s,NOW())
                ON CONFLICT (user_id) DO UPDATE SET balance=gringotts.balance+%s
            """, user_id, amount, amount)
            execute(conn, """
                INSERT INTO gringotts_log (user_id, action, amount, balance)
                VALUES (%s,'deposit',%s,(SELECT balance FROM gringotts WHERE user_id=%s))
            """, user_id, amount, user_id)
        await update.message.reply_text(f"✅ Внесено {amount:,} 💰 на вклад!")

    elif action == "withdraw":
        if amount > account["balance"]:
            await update.message.reply_text(f"❌ На вкладе только {account['balance']:,} 💰")
            return
        _apply_interest(user_id, account)
        with get_conn() as conn:
            execute(conn, "UPDATE users SET gold=gold+%s WHERE user_id=%s", amount, user_id)
            execute(conn, "UPDATE gringotts SET balance=balance-%s WHERE user_id=%s", amount, user_id)
            execute(conn, """
                INSERT INTO gringotts_log (user_id, action, amount, balance)
                VALUES (%s,'withdraw',%s,(SELECT balance FROM gringotts WHERE user_id=%s))
            """, user_id, amount, user_id)
        await update.message.reply_text(f"✅ Снято {amount:,} 💰 с вклада!")

    ctx.user_data.pop("gb_action", None)

def register_gringotts_handlers(app):
    from telegram.ext import MessageHandler, filters
    app.add_handler(CommandHandler("gringotts", cmd_gringotts))
    app.add_handler(CommandHandler("bank",      cmd_gringotts))
    app.add_handler(CallbackQueryHandler(cb_gb_collect,      pattern=r"^gb_collect$"))
    app.add_handler(CallbackQueryHandler(cb_gb_deposit,      pattern=r"^gb_deposit$"))
    app.add_handler(CallbackQueryHandler(cb_gb_withdraw,     pattern=r"^gb_withdraw$"))
    app.add_handler(CallbackQueryHandler(cb_gb_withdraw_all, pattern=r"^gb_withdraw_all$"))
    app.add_handler(CallbackQueryHandler(cb_gb_cancel,       pattern=r"^gb_cancel$"))
    app.add_handler(CallbackQueryHandler(cb_gb_history,      pattern=r"^gb_history$"))
    app.add_handler(CallbackQueryHandler(cb_gb_back,         pattern=r"^gb_back$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_gb_input), group=14)
