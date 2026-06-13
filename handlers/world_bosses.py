"""
World Bosses — мировые боссы.
Появляются по расписанию (12:00 и 20:00 UTC).
Общий запас HP — все игроки бьют вместе.
Награды зависят от вклада игрока.
"""
import logging
import random
import asyncio
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import (
    get_user, user_exists, add_xp, add_gold, add_house_points,
    get_active_world_boss, record_world_boss_damage, get_world_boss_top,
    get_daily_limit, increment_daily, get_conn, execute, fetchrow, fetchall,
)
from game.battle_engine import format_hp_bar
from game.spells import SPELLS
from utils.i18n import t
from config import (
    DAILY_LIMITS, WORLD_BOSS_DURATION_MINUTES,
    WORLD_BOSS_SCHEDULE_HOURS,
    XP_REWARDS, GOLD_REWARDS, HOUSE_POINTS_REWARDS,
)

logger = logging.getLogger(__name__)

# ── Каталог мировых боссов ─────────────────────────────────────────────────────
WORLD_BOSSES: dict[str, dict] = {
    "basilisk_ancient": {
        "emoji":   "🐍💀",
        "hp":      50_000,
        "attack":  80,
        "defense": 40,
        "weakness": "🔥 Огонь",
        "weakness_key": "fire",
        "special_cooldown": 5,
        "special_spell":    "killing_gaze",
        "passive_dmg":      [8, 15],
        "unique_drop_chance": 0.05,
        "unique_drop": "gloves_basilisk",
        # ── Локализованные имена и описания ───────────────────────────────────
        "names": {
            "ru": "Древний Василиск",
            "en": "Ancient Basilisk",
            "de": "Antike Basilisk",
            "es": "Basilisco Antiguo",
            "pt": "Basilisco Antigo",
        },
        "descs": {
            "ru": "Первый Василиск, созданный самим Слизерином. Его взгляд обращает в камень целые армии.",
            "en": "The first Basilisk, created by Salazar Slytherin himself. Its gaze turns entire armies to stone.",
            "de": "Der erste Basilisk, erschaffen von Salazar Slytherin selbst. Sein Blick verwandelt ganze Armeen zu Stein.",
            "es": "El primer Basilisco, creado por el propio Salazar Slytherin. Su mirada convierte ejércitos enteros en piedra.",
            "pt": "O primeiro Basilisco, criado pelo próprio Salazar Sonserina. Seu olhar transforma exércitos inteiros em pedra.",
        },
        "special_descs": {
            "ru": "💀 Смертоносный взгляд — 50 урона всем атакующим!",
            "en": "💀 Lethal Gaze — 50 damage to all attackers!",
            "de": "💀 Tödlicher Blick — 50 Schaden an alle Angreifer!",
            "es": "💀 Mirada Letal — ¡50 de daño a todos los atacantes!",
            "pt": "💀 Olhar Letal — 50 de dano a todos os atacantes!",
        },
        "phases": [
            {"threshold": 1.00, "names": {"ru": "Дремлющий",    "en": "Dormant",   "de": "Schlafend",   "es": "Dormido",     "pt": "Adormecido"  }, "dmg_mult": 1.0},
            {"threshold": 0.70, "names": {"ru": "Пробудившийся","en": "Awakened",  "de": "Erwacht",     "es": "Despierto",   "pt": "Desperto"    }, "dmg_mult": 1.3},
            {"threshold": 0.40, "names": {"ru": "Разъярённый",  "en": "Enraged",   "de": "Wütend",      "es": "Enfurecido",  "pt": "Enfurecido"  }, "dmg_mult": 1.6},
            {"threshold": 0.15, "names": {"ru": "Агония",       "en": "Agony",     "de": "Agonie",      "es": "Agonía",      "pt": "Agonia"      }, "dmg_mult": 2.0},
        ],
        "drop_table": {
            "top1":   {"xp": 2000, "gold": 1000, "title": "Гроза Василисков"},
            "top3":   {"xp": 1500, "gold": 700},
            "top10":  {"xp": 1000, "gold": 400},
            "others": {"xp": 400,  "gold": 150},
        },
    },

    "ancient_dementor": {
        "emoji":   "👻💀",
        "hp":      40_000,
        "attack":  70,
        "defense": 20,
        "weakness": "✨ Патронус",
        "weakness_key": "patronus",
        "special_cooldown": 4,
        "special_spell":    "dementor_kiss",
        "passive_dmg":      [10, 20],
        "unique_drop_chance": 0.05,
        "unique_drop": "amulet_horcrux",
        "names": {
            "ru": "Древний Дементор",
            "en": "Ancient Dementor",
            "de": "Antike Dementor",
            "es": "Dementor Antiguo",
            "pt": "Dementor Antigo",
        },
        "descs": {
            "ru": "Первый дементор — источник всей тьмы Азкабана. Высасывает надежду из мира.",
            "en": "The first Dementor — the source of all darkness in Azkaban. It drains hope from the world.",
            "de": "Der erste Dementor — die Quelle aller Dunkelheit in Askaban. Er saugt die Hoffnung aus der Welt.",
            "es": "El primer Dementor, la fuente de toda la oscuridad en Azkaban. Extrae la esperanza del mundo.",
            "pt": "O primeiro Dementor — fonte de toda a escuridão em Azkaban. Suga a esperança do mundo.",
        },
        "special_descs": {
            "ru": "💧 Массовый поцелуй — все атакующие теряют 30 маны!",
            "en": "💧 Mass Kiss — all attackers lose 30 mana!",
            "de": "💧 Massenkuss — alle Angreifer verlieren 30 Mana!",
            "es": "💧 Beso masivo — ¡todos los atacantes pierden 30 de maná!",
            "pt": "💧 Beijo em Massa — todos os atacantes perdem 30 de mana!",
        },
        "phases": [
            {"threshold": 1.00, "names": {"ru": "Тень",        "en": "Shadow",    "de": "Schatten",  "es": "Sombra",    "pt": "Sombra"     }, "dmg_mult": 1.0},
            {"threshold": 0.60, "names": {"ru": "Голод",       "en": "Hunger",    "de": "Hunger",    "es": "Hambre",    "pt": "Fome"       }, "dmg_mult": 1.4},
            {"threshold": 0.25, "names": {"ru": "Поглощение",  "en": "Devouring", "de": "Verschlingen","es": "Absorción","pt": "Absorção"  }, "dmg_mult": 1.8},
        ],
        "drop_table": {
            "top1":   {"xp": 1800, "gold": 900, "title": "Защитник от тьмы"},
            "top3":   {"xp": 1200, "gold": 600},
            "top10":  {"xp": 800,  "gold": 350},
            "others": {"xp": 300,  "gold": 120},
        },
    },

    "hungarian_horntail": {
        "emoji":   "🐉🔥",
        "hp":      60_000,
        "attack":  100,
        "defense": 50,
        "weakness": "🧊 Лёд",
        "weakness_key": "ice",
        "special_cooldown": 6,
        "special_spell":    "inferno",
        "passive_dmg":      [12, 22],
        "unique_drop_chance": 0.04,
        "unique_drop": "robe_auror",
        "names": {
            "ru": "Венгерская Хвосторога",
            "en": "Hungarian Horntail",
            "de": "Ungarischer Hornschwanz",
            "es": "Cola de Cornisa Húngara",
            "pt": "Rabudo Húngaro",
        },
        "descs": {
            "ru": "Самый опасный дракон в мире. Огонь плавит сталь, хвост с шипами крушит стены замков.",
            "en": "The most dangerous dragon in the world. Its fire melts steel, its spiked tail shatters castle walls.",
            "de": "Der gefährlichste Drache der Welt. Sein Feuer schmilzt Stahl, sein Stachelschwanz zerstört Mauern.",
            "es": "El dragón más peligroso del mundo. Su fuego derrite el acero y su cola destruye muros de castillos.",
            "pt": "O dragão mais perigoso do mundo. Seu fogo derrete aço, sua cauda espinhosa destrói muros de castelos.",
        },
        "special_descs": {
            "ru": "🔥 Инфернальный огонь — 80 урона всем, кто атакует!",
            "en": "🔥 Infernal Fire — 80 damage to all attackers!",
            "de": "🔥 Höllisches Feuer — 80 Schaden an alle Angreifer!",
            "es": "🔥 Fuego Infernal — ¡80 de daño a todos los atacantes!",
            "pt": "🔥 Fogo Infernal — 80 de dano a todos os atacantes!",
        },
        "phases": [
            {"threshold": 1.00, "names": {"ru": "Спящая",     "en": "Sleeping",  "de": "Schlafend",  "es": "Dormida",   "pt": "Dormindo"   }, "dmg_mult": 1.0},
            {"threshold": 0.65, "names": {"ru": "Разбуженная","en": "Awakened",  "de": "Erwacht",    "es": "Despierta", "pt": "Desperta"   }, "dmg_mult": 1.4},
            {"threshold": 0.30, "names": {"ru": "Ярость",     "en": "Fury",      "de": "Raserei",    "es": "Furia",     "pt": "Fúria"      }, "dmg_mult": 1.8},
            {"threshold": 0.10, "names": {"ru": "Бешенство",  "en": "Frenzy",    "de": "Wahnsinn",   "es": "Frenesí",   "pt": "Frenesi"    }, "dmg_mult": 2.2},
        ],
        "drop_table": {
            "top1":   {"xp": 2500, "gold": 1200, "title": "Победитель Хвосторогой"},
            "top3":   {"xp": 1800, "gold": 800},
            "top10":  {"xp": 1200, "gold": 500},
            "others": {"xp": 500,  "gold": 200},
        },
    },

    "giant_troll": {
        "emoji":   "👹⚡",
        "hp":      35_000,
        "attack":  90,
        "defense": 60,
        "weakness": "✨ Магия",
        "weakness_key": "magic",
        "special_cooldown": 3,
        "special_spell":    "club_smash",
        "passive_dmg":      [6, 12],
        "unique_drop_chance": 0.06,
        "unique_drop": "wand_oak_dragon",
        "names": {
            "ru": "Гигантский Тролль",
            "en": "Giant Troll",
            "de": "Riesiger Troll",
            "es": "Trol Gigante",
            "pt": "Troll Gigante",
        },
        "descs": {
            "ru": "Тролль размером с башню. Его дубина крушит всё вокруг, земля дрожит под его шагами.",
            "en": "A troll the size of a tower. Its club smashes everything, the earth trembles beneath its steps.",
            "de": "Ein Troll so groß wie ein Turm. Seine Keule zerstört alles, die Erde bebt unter seinen Schritten.",
            "es": "Un trol del tamaño de una torre. Su maza lo destruye todo y la tierra tiembla bajo sus pasos.",
            "pt": "Um troll do tamanho de uma torre. Seu porrete esmaga tudo ao redor, a terra treme sob seus passos.",
        },
        "special_descs": {
            "ru": "💫 Удар дубиной — все игроки оглушены на 1 ход!",
            "en": "💫 Club Smash — all players stunned for 1 turn!",
            "de": "💫 Keulensmash — alle Spieler für 1 Runde betäubt!",
            "es": "💫 Golpe de maza — ¡todos los jugadores aturdidos por 1 turno!",
            "pt": "💫 Pancada de Porrete — todos os jogadores atordoados por 1 turno!",
        },
        "phases": [
            {"threshold": 1.00, "names": {"ru": "Злобный",  "en": "Vicious",  "de": "Bösartig", "es": "Malicioso","pt": "Malicioso" }, "dmg_mult": 1.0},
            {"threshold": 0.50, "names": {"ru": "Бешеный",  "en": "Frenzied", "de": "Rasend",   "es": "Frenético","pt": "Furioso"  }, "dmg_mult": 1.5},
            {"threshold": 0.20, "names": {"ru": "Агония",   "en": "Agony",    "de": "Agonie",   "es": "Agonía",   "pt": "Agonia"  }, "dmg_mult": 2.0},
        ],
        "drop_table": {
            "top1":   {"xp": 1500, "gold": 700},
            "top3":   {"xp": 1000, "gold": 450},
            "top10":  {"xp": 700,  "gold": 300},
            "others": {"xp": 250,  "gold": 100},
        },
    },

    "dark_lord": {
        "emoji":   "💀👑",
        "hp":      100_000,
        "attack":  120,
        "defense": 70,
        "weakness": "❤️ Любовь",
        "weakness_key": "love",
        "special_cooldown": 5,
        "special_spell":    "avada_kedavra",
        "passive_dmg":      [15, 30],
        "unique_drop_chance": 0.03,
        "unique_drop": "wand_elder",
        "names": {
            "ru": "Тёмный Лорд",
            "en": "The Dark Lord",
            "de": "Der Dunkle Lord",
            "es": "El Señor Oscuro",
            "pt": "O Lorde das Trevas",
        },
        "descs": {
            "ru": "Сам Волдеморт во плоти. Тот-Кого-Нельзя-Называть. Величайший тёмный маг всех времён.",
            "en": "Voldemort himself in the flesh. He-Who-Must-Not-Be-Named. The greatest dark wizard of all time.",
            "de": "Voldemort selbst in Person. Der-dessen-Name-nicht-genannt-werden-darf. Der größte dunkle Magier aller Zeiten.",
            "es": "El mismísimo Voldemort en persona. El-que-no-debe-ser-nombrado. El mayor mago oscuro de todos los tiempos.",
            "pt": "O próprio Voldemort em pessoa. Aquele-Que-Não-Deve-Ser-Nomeado. O maior bruxo das trevas de todos os tempos.",
        },
        "special_descs": {
            "ru": "☠️ Авада Кедавра — случайный игрок получает 200 урона!",
            "en": "☠️ Avada Kedavra — a random player takes 200 damage!",
            "de": "☠️ Avada Kedavra — ein zufälliger Spieler erleidet 200 Schaden!",
            "es": "☠️ Avada Kedavra — ¡un jugador aleatorio recibe 200 de daño!",
            "pt": "☠️ Avada Kedavra — um jogador aleatório recebe 200 de dano!",
        },
        "phases": [
            {"threshold": 1.00, "names": {"ru": "Тёмный лорд",    "en": "Dark Lord",      "de": "Dunkler Lord",    "es": "Señor Oscuro",    "pt": "Lorde das Trevas"  }, "dmg_mult": 1.0},
            {"threshold": 0.70, "names": {"ru": "Гнев",           "en": "Wrath",          "de": "Zorn",            "es": "Ira",             "pt": "Ira"               }, "dmg_mult": 1.3},
            {"threshold": 0.40, "names": {"ru": "Крестраж",       "en": "Horcrux",        "de": "Horkrux",         "es": "Horrocrux",       "pt": "Horcrux"           }, "dmg_mult": 1.7},
            {"threshold": 0.15, "names": {"ru": "Последний вздох","en": "Last Breath",    "de": "Letzter Atemzug", "es": "Último aliento",  "pt": "Último Fôlego"     }, "dmg_mult": 2.5},
        ],
        "drop_table": {
            "top1":   {"xp": 5000, "gold": 2500, "title": "Победитель Тёмного Лорда"},
            "top3":   {"xp": 3000, "gold": 1500, "title": "Герой магического мира"},
            "top10":  {"xp": 2000, "gold": 1000},
            "others": {"xp": 800,  "gold": 300},
        },
    },
}

_active_sessions: dict[int, dict] = {}   # world_boss_db_id → session


def _boss_name(boss_data: dict, lang: str = "ru") -> str:
    return boss_data["names"].get(lang) or boss_data["names"]["ru"]


def _boss_desc(boss_data: dict, lang: str = "ru") -> str:
    return boss_data["descs"].get(lang) or boss_data["descs"]["ru"]


def _boss_special_desc(boss_data: dict, lang: str = "ru") -> str:
    return boss_data["special_descs"].get(lang) or boss_data["special_descs"]["ru"]


def _get_phase(boss_data: dict, hp_ratio: float) -> dict:
    phases = boss_data.get("phases", [])
    active = phases[0]
    for phase in phases:
        if hp_ratio <= phase["threshold"]:
            active = phase
    return active


def _phase_name(phase: dict, lang: str = "ru") -> str:
    return phase["names"].get(lang) or phase["names"]["ru"]


def _next_spawn_info() -> tuple[str, str]:
    """
    Возвращает (время_до_следующего_спавна, время_до_конца_если_активен).
    Оба значения — человекочитаемые строки.
    """
    now = datetime.now(timezone.utc)
    schedule = sorted(WORLD_BOSS_SCHEDULE_HOURS)

    # Найти ближайшее время спавна сегодня или завтра
    candidates = []
    for h in schedule:
        t_today = now.replace(hour=h, minute=0, second=0, microsecond=0)
        candidates.append(t_today)
        candidates.append(t_today + timedelta(days=1))

    future = [c for c in candidates if c > now]
    if not future:
        next_dt = candidates[0] + timedelta(days=1)
    else:
        next_dt = min(future)

    delta = next_dt - now
    total_sec = int(delta.total_seconds())
    hours, remainder = divmod(total_sec, 3600)
    minutes = remainder // 60

    if hours > 0:
        until_str = f"{hours} ч {minutes} мин"
    else:
        until_str = f"{minutes} мин"

    # Сколько длится каждый спавн
    duration_h = WORLD_BOSS_DURATION_MINUTES // 60
    duration_m = WORLD_BOSS_DURATION_MINUTES % 60
    if duration_h > 0:
        dur_str = f"{duration_h} ч {duration_m} мин" if duration_m else f"{duration_h} ч"
    else:
        dur_str = f"{duration_m} мин"

    schedule_str = " и ".join(f"{h:02d}:00" for h in schedule)
    return until_str, dur_str, schedule_str, next_dt.strftime("%H:%M UTC %d.%m")


def _time_left_str(wb_row: dict) -> str:
    """Сколько времени осталось до конца текущего боса."""
    if "started_at" not in wb_row or not wb_row.get("started_at"):
        return "неизвестно"
    started_at = wb_row["started_at"]
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    ends_at = started_at + timedelta(minutes=WORLD_BOSS_DURATION_MINUTES)
    now = datetime.now(timezone.utc)
    if ends_at <= now:
        return "0 мин"
    delta = ends_at - now
    total_sec = int(delta.total_seconds())
    hours, remainder = divmod(total_sec, 3600)
    minutes = remainder // 60
    if hours > 0:
        return f"{hours} ч {minutes} мин"
    return f"{minutes} мин"


def _format_wb_panel(boss_data: dict, wb_row: dict, top: list,
                     user_dmg: int = 0, lang: str = "ru") -> str:
    hp     = wb_row["current_hp"]
    max_hp = wb_row["max_hp"]
    ratio  = hp / max_hp if max_hp else 0
    phase  = _get_phase(boss_data, ratio)
    bar    = format_hp_bar(hp, max_hp, 14)
    time_left = _time_left_str(wb_row)

    top_lines = []
    for i, row in enumerate(top[:5], 1):
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        top_lines.append(f"{medals[i-1]} {row['wizard_name']}: {row['damage']:,} урона")

    phase_name = _phase_name(phase, lang)
    boss_name  = _boss_name(boss_data, lang)
    special    = _boss_special_desc(boss_data, lang)

    return (
        f"{boss_data['emoji']} *{boss_name}*\n"
        f"⚠️ Фаза: *{phase_name}* (×{phase['dmg_mult']} урон)\n"
        f"❤️ `[{bar}]` {hp:,}/{max_hp:,}\n"
        f"⏳ Осталось времени: *{time_left}*\n"
        f"⚔️ Атака: {boss_data['attack']} | 🛡️ Защита: {boss_data['defense']}\n"
        f"💥 Слабость: {boss_data['weakness']}\n"
        f"🎯 Спецатака: _{special}_\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        + ("\n".join(top_lines) if top_lines else "Нет атак пока")
        + (f"\n\n⚔️ Твой урон: {user_dmg:,}" if user_dmg else "")
    )


def _all_bosses_text(lang: str = "ru") -> str:
    """Карточки всех боссов для команды /worldboss когда нет активного."""
    lines = []
    for bid, b in WORLD_BOSSES.items():
        name  = _boss_name(b, lang)
        desc  = _boss_desc(b, lang)
        phase_names = " → ".join(_phase_name(p, lang) for p in b["phases"])
        lines.append(
            f"{b['emoji']} *{name}*\n"
            f"❤️ HP: {b['hp']:,}  ⚔️ Атака: {b['attack']}  🛡️ Защита: {b['defense']}\n"
            f"💥 Слабость: {b['weakness']}\n"
            f"📖 _{desc}_\n"
            f"🔄 Фазы: {phase_names}\n"
        )
    return "\n".join(lines)


def _get_user_lang(user_id: int) -> str:
    try:
        with get_conn() as conn:
            from database import fetchrow as fr
            row = fr(conn, "SELECT lang FROM users WHERE user_id = %s", user_id)
            return row["lang"] if row and row.get("lang") else "ru"
    except Exception:
        return "ru"


async def cmd_worldboss(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/worldboss — атаковать активного мирового босса."""
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    lang = _get_user_lang(user_id)
    wb = get_active_world_boss()

    if not wb:
        until_str, dur_str, schedule_str, next_time = _next_spawn_info()
        bosses_info = _all_bosses_text(lang)
        await update.message.reply_text(
            f"🌍 *Мировых боссов сейчас нет*\n\n"
            f"🕐 Следующий появится через: *{until_str}*\n"
            f"📅 Расписание спавна: {schedule_str} UTC\n"
            f"⏱ Следующий старт: {next_time}\n"
            f"⌛ Каждый босс держится: *{dur_str}*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📖 *Возможные боссы:*\n\n"
            f"{bosses_info}",
            parse_mode="Markdown"
        )
        return

    if wb["current_hp"] <= 0:
        await update.message.reply_text("💀 Мировой босс уже повержен!")
        return

    used = get_daily_limit(user_id, "world_boss")
    if used >= DAILY_LIMITS["world_boss"]:
        await update.message.reply_text("⚔️ Ты уже атаковал мирового босса сегодня!")
        return

    boss_data = WORLD_BOSSES.get(wb["boss_id"])
    if not boss_data:
        await update.message.reply_text("❌ Данные босса не найдены.")
        return

    top      = get_world_boss_top(wb["id"])
    user_row = next((r for r in top if r.get("user_id") == user_id), None)
    user_dmg = user_row["damage"] if user_row else 0

    from database import get_user_spells
    spells = [r["spell_id"] for r in get_user_spells(user_id)][:6]
    from game.spells import spell_display_name, RARITY_EMOJI
    buttons = []
    for sid in spells:
        spell = SPELLS.get(sid)
        if not spell:
            continue
        rarity_e = RARITY_EMOJI.get(spell.get("rarity", "common"), "⚪")
        name     = spell_display_name(sid, lang)
        dmg      = spell.get("damage", 0)
        buttons.append([InlineKeyboardButton(
            f"{rarity_e}{name} ⚔️{dmg}",
            callback_data=f"wb_attack:{wb['id']}:{sid}"
        )])

    if not buttons:
        await update.message.reply_text(
            "❌ У тебя нет заклинаний для атаки!\n"
            "Выучи заклинания через 📚 Уроки."
        )
        return

    markup = InlineKeyboardMarkup(buttons)
    panel  = _format_wb_panel(boss_data, wb, top, user_dmg, lang)
    await update.message.reply_text(panel, parse_mode="Markdown", reply_markup=markup)


async def cb_wb_attack(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    user_id  = query.from_user.id
    parts    = query.data.split(":")
    wb_id    = int(parts[1])
    spell_id = parts[2]
    lang     = _get_user_lang(user_id)

    wb = get_active_world_boss()
    if not wb or wb["id"] != wb_id or wb["current_hp"] <= 0:
        await query.edit_message_text("💀 Мировой босс уже повержен!")
        return

    used = get_daily_limit(user_id, "world_boss")
    if used >= DAILY_LIMITS["world_boss"]:
        await query.answer("⚔️ Ты уже атаковал сегодня!", show_alert=True)
        return

    user      = get_user(user_id)
    boss_data = WORLD_BOSSES.get(wb["boss_id"])
    spell     = SPELLS.get(spell_id)
    if not spell or not boss_data:
        await query.edit_message_text("❌ Ошибка.")
        return

    # Рассчитываем урон
    hp_ratio  = wb["current_hp"] / wb["max_hp"]
    base_dmg  = spell.get("damage", 10)
    atk_mult  = 1 + (user["attack"] - 10) * 0.02
    luck_crit = 0.05 + user.get("luck", 5) * 0.005
    is_crit   = random.random() < luck_crit
    crit_mult = 1.5 if is_crit else 1.0
    dmg       = max(1, int(base_dmg * atk_mult * crit_mult))

    record_world_boss_damage(wb_id, user_id, dmg)
    increment_daily(user_id, "world_boss")

    wb_updated = get_active_world_boss()
    top        = get_world_boss_top(wb_id)
    user_row   = next((r for r in top if r.get("wizard_name") == user["wizard_name"]), None)
    total_dmg  = user_row["damage"] if user_row else dmg
    passive    = random.randint(*boss_data["passive_dmg"])
    crit_text  = " 💥 КРИТ!" if is_crit else ""
    log_line   = (
        f"⚔️ {dmg} урона{crit_text}\n"
        f"🐉 Босс наносит {passive} урона в ответ"
    )

    if wb_updated and wb_updated["current_hp"] <= 0:
        boss_name = _boss_name(boss_data, lang)
        await query.edit_message_text(
            f"💀 *{boss_name} повержен!*\n\n"
            f"Твой удар: {dmg}{crit_text}\n"
            f"Твой общий урон: {total_dmg:,}\n\n"
            f"🏆 Награды рассчитываются...",
            parse_mode="Markdown"
        )
        await _distribute_wb_rewards(wb_id, boss_data, ctx)
        return

    panel = _format_wb_panel(boss_data, wb_updated, top, total_dmg, lang)
    panel += f"\n\n{log_line}"

    await query.edit_message_text(
        panel,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Обновить", callback_data=f"wb_refresh:{wb_id}"),
        ]])
    )


async def cb_wb_refresh(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    wb_id   = int(query.data.split(":")[1])
    lang    = _get_user_lang(user_id)

    wb = get_active_world_boss()
    if not wb or wb["id"] != wb_id:
        await query.edit_message_text("💀 Мировой босс уже завершён.")
        return

    boss_data = WORLD_BOSSES.get(wb["boss_id"])
    top       = get_world_boss_top(wb_id)
    user      = get_user(user_id)
    user_row  = next((r for r in top if r.get("wizard_name") == user["wizard_name"]), None)
    user_dmg  = user_row["damage"] if user_row else 0

    panel = _format_wb_panel(boss_data, wb, top, user_dmg, lang)
    await query.edit_message_text(
        panel,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Обновить", callback_data=f"wb_refresh:{wb_id}"),
        ]])
    )


async def _distribute_wb_rewards(wb_id: int, boss_data: dict, ctx):
    """Раздать награды после победы над мировым боссом."""
    top   = get_world_boss_top(wb_id, limit=100)
    drop  = boss_data.get("drop_table", {})

    with get_conn() as conn:
        execute(conn, "UPDATE world_bosses SET status = 'defeated', ended_at = NOW() WHERE id = %s", wb_id)
        execute(conn,
            "UPDATE user_stats SET world_boss_kills = world_boss_kills + 1 "
            "WHERE user_id IN (SELECT user_id FROM world_boss_damage WHERE world_boss_id = %s)", wb_id)

    for i, row in enumerate(top):
        with get_conn() as conn:
            u = fetchrow(conn, "SELECT user_id, house FROM users WHERE wizard_name = %s", row["wizard_name"])
        if not u:
            continue
        uid = u["user_id"]
        lang = _get_user_lang(uid)

        if i == 0:
            reward = drop.get("top1", {})
        elif i < 3:
            reward = drop.get("top3", {})
        elif i < 10:
            reward = drop.get("top10", {})
        else:
            reward = drop.get("others", {})

        xp    = reward.get("xp", 200)
        gold  = reward.get("gold", 80)
        title = reward.get("title")

        add_xp(uid, xp)
        add_gold(uid, gold)
        add_house_points(uid, u["house"], HOUSE_POINTS_REWARDS.get("world_boss", 10), "world_boss")

        if title:
            with get_conn() as conn:
                execute(conn,
                    "INSERT INTO user_titles (user_id, title_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    uid, title)

        unique_text = ""
        if i == 0 and random.random() < boss_data.get("unique_drop_chance", 0.05):
            udrop = boss_data.get("unique_drop")
            if udrop:
                with get_conn() as conn:
                    execute(conn,
                        "INSERT INTO inventory (user_id, item_id, quantity) VALUES (%s, %s, 1) "
                        "ON CONFLICT (user_id, item_id) DO UPDATE SET quantity = inventory.quantity + 1",
                        uid, udrop)
                unique_text = f"\n🌟 *Уникальный дроп:* `{udrop}`!"

        boss_name  = _boss_name(boss_data, lang)
        place_text = f"#{i+1}" if i >= 3 else ["🥇", "🥈", "🥉"][i]
        try:
            await ctx.bot.send_message(
                uid,
                f"🌍 *{boss_name} повержен!*\n\n"
                f"Твоё место: {place_text} ({row['damage']:,} урона)\n"
                f"+{xp} XP | +{gold} 💰"
                + (f"\n🎭 Титул: *{title}*" if title else "")
                + unique_text,
                parse_mode="Markdown"
            )
        except Exception:
            pass


async def spawn_world_boss(boss_id: str, ctx) -> bool:
    """Заспавнить мирового босса. Вызывается планировщиком или /admin_wb."""
    boss_data = WORLD_BOSSES.get(boss_id)
    if not boss_data:
        return False

    wb = get_active_world_boss()
    if wb:
        return False

    with get_conn() as conn:
        execute(conn, """
            INSERT INTO world_bosses (boss_id, max_hp, current_hp, status)
            VALUES (%s, %s, %s, 'active')
        """, boss_id, boss_data["hp"], boss_data["hp"])
        wb_row = fetchrow(conn, "SELECT id FROM world_bosses ORDER BY id DESC LIMIT 1")
    wb_id = wb_row["id"]

    with get_conn() as conn:
        users = fetchall(conn, "SELECT user_id, lang FROM users WHERE is_banned = FALSE")

    _, dur_str, _, _ = _next_spawn_info()
    # Пересчитаем dur_str через WORLD_BOSS_DURATION_MINUTES напрямую
    dh = WORLD_BOSS_DURATION_MINUTES // 60
    dm = WORLD_BOSS_DURATION_MINUTES % 60
    dur_str = f"{dh} ч {dm} мин" if dh > 0 and dm > 0 else (f"{dh} ч" if dh > 0 else f"{dm} мин")

    for row in users[:200]:
        uid  = row["user_id"]
        lang = row.get("lang") or "ru"
        boss_name = _boss_name(boss_data, lang)
        boss_desc = _boss_desc(boss_data, lang)
        special   = _boss_special_desc(boss_data, lang)
        text = (
            f"⚠️ *МИРОВОЙ БОСС ПОЯВИЛСЯ!*\n\n"
            f"{boss_data['emoji']} *{boss_name}*\n"
            f"❤️ {boss_data['hp']:,} HP\n"
            f"⚔️ Атака: {boss_data['attack']} | 🛡️ Защита: {boss_data['defense']}\n"
            f"💥 Слабость: {boss_data['weakness']}\n\n"
            f"_{boss_desc}_\n\n"
            f"🎯 Спецатака: _{special}_\n\n"
            f"Используй /worldboss чтобы атаковать!\n"
            f"⌛ Босс исчезнет через *{dur_str}*."
        )
        try:
            from handlers.images import send_with_image, get_image
            _boss_img = {
                "basilisk_ancient":   "boss_basilisk",
                "hungarian_horntail": "boss_dragon",
                "ancient_dementor":   "boss_wraith",
            }
            slot = _boss_img.get(boss_id)
            if slot and get_image(slot):
                await send_with_image(ctx.bot, uid, slot, text)
            else:
                await ctx.bot.send_message(uid, text, parse_mode="Markdown")
        except Exception:
            try:
                await ctx.bot.send_message(uid, text, parse_mode="Markdown")
            except Exception:
                pass
    async def _auto_expire():
        await asyncio.sleep(WORLD_BOSS_DURATION_MINUTES * 60)
        wb_check = get_active_world_boss()
        if wb_check and wb_check["id"] == wb_id and wb_check["current_hp"] > 0:
            with get_conn() as conn:
                execute(conn, "UPDATE world_bosses SET status = 'expired', ended_at = NOW() WHERE id = %s", wb_id)
            for row in users[:200]:
                uid  = row["user_id"]
                lang = row.get("lang") or "ru"
                boss_name = _boss_name(boss_data, lang)
                try:
                    await ctx.bot.send_message(
                        uid,
                        f"⏰ *{boss_name} скрылся!*\n\nВремя вышло. Следи за появлением нового!",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
    asyncio.get_event_loop().create_task(_auto_expire())
    return True


def register_world_boss_handlers(app):
    app.add_handler(CommandHandler("worldboss", cmd_worldboss))
    app.add_handler(CallbackQueryHandler(cb_wb_attack,  pattern=r"^wb_attack:"))
    app.add_handler(CallbackQueryHandler(cb_wb_refresh, pattern=r"^wb_refresh:"))
