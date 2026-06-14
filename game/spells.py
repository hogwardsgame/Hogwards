"""
All spells data for Hogwarts RPG Bot.
Rarities: common, uncommon, rare, very_rare, epic, legendary, mythical

Добавлено 50+ новых заклинаний относительно оригинала.
Шанс получения mythical/legendary не более 2%.
"""

SPELLS = {
    # ══════════════════════════════════════════════════════
    # COMMON (⚪) — базовые заклинания
    # ══════════════════════════════════════════════════════
    "expelliarmus": {
        "id": "expelliarmus", "emoji": "⚪", "rarity": "common", "type": "attack",
        "mana": 15, "damage": 25,
        "effect": "disarm", "effect_chance": 1.0,
        "desc_ru": "Разоружает противника, лишая его случайного заклинания на ход",
    },
    "stupefy": {
        "id": "stupefy", "emoji": "⚪", "rarity": "common", "type": "attack",
        "mana": 25, "damage": 35,
        "effect": "stun", "effect_chance": 0.4,
        "desc_ru": "Оглушает цель, заставляя пропустить ход",
    },
    "confundus": {
        "id": "confundus", "emoji": "⚪", "rarity": "common", "type": "attack",
        "mana": 20, "damage": 20,
        "effect": "confuse", "effect_chance": 0.3,
        "desc_ru": "Запутывает врага — он атакует сам себя",
    },
    "flipendo": {
        "id": "flipendo", "emoji": "⚪", "rarity": "common", "type": "attack",
        "mana": 20, "damage": 30,
        "effect": None, "effect_chance": 0,
        "desc_ru": "Мощный толчок — без эффектов, чистый урон",
    },
    "protego": {
        "id": "protego", "emoji": "⚪", "rarity": "common", "type": "defense",
        "mana": 20, "damage": 0,
        "effect": "block", "effect_chance": 1.0,
        "desc_ru": "Блокирует 40% входящего урона на этот ход",
    },
    "escudo": {
        "id": "escudo", "emoji": "⚪", "rarity": "common", "type": "heal",
        "mana": 25, "damage": 0, "heal": 20,
        "effect": None, "effect_chance": 0,
        "desc_ru": "Восстанавливает 20 HP",
    },
    "ricochet": {
        "id": "ricochet", "emoji": "⚪", "rarity": "common", "type": "defense",
        "mana": 30, "damage": 0,
        "effect": "reflect", "effect_chance": 1.0,
        "desc_ru": "Отражает 25% урона обратно атакующему",
    },
    "inflammare": {
        "id": "inflammare", "emoji": "⚪", "rarity": "common", "type": "debuff",
        "mana": 25, "damage": 15,
        "effect": "burn", "effect_chance": 1.0,
        "desc_ru": "Поджигает врага — 10 урона в ход на 3 хода",
    },
    "ice_chain": {
        "id": "ice_chain", "emoji": "⚪", "rarity": "common", "type": "debuff",
        "mana": 30, "damage": 10,
        "effect": "freeze", "effect_chance": 1.0,
        "desc_ru": "Замораживает — цель не может защищаться 2 хода",
    },
    "tenebrus": {
        "id": "tenebrus", "emoji": "⚪", "rarity": "common", "type": "debuff",
        "mana": 20, "damage": 10,
        "effect": "blind", "effect_chance": 1.0,
        "desc_ru": "Ослепляет — -50% точности на 2 хода",
    },
    "vulnero": {
        "id": "vulnero", "emoji": "⚪", "rarity": "common", "type": "heal",
        "mana": 30, "damage": 0, "heal": 30,
        "effect": None, "effect_chance": 0,
        "desc_ru": "Лечение на 30 HP",
    },
    "sanacus": {
        "id": "sanacus", "emoji": "⚪", "rarity": "common", "type": "heal",
        "mana": 25, "damage": 0, "heal": 15,
        "effect": "cleanse", "effect_chance": 1.0,
        "desc_ru": "Лечит 15 HP и снимает 1 дебафф",
    },
    "reparo": {
        "id": "reparo", "emoji": "⚪", "rarity": "common", "type": "heal",
        "mana": 20, "damage": 0, "heal": 5,
        "effect": None, "effect_chance": 0,
        "desc_ru": "Минимальное восстановление",
    },
    "levicorpus": {
        "id": "levicorpus", "emoji": "⚪", "rarity": "common", "type": "attack",
        "mana": 20, "damage": 22,
        "effect": "stun", "effect_chance": 0.25,
        "desc_ru": "Подбрасывает врага в воздух",
    },
    "lumos": {
        "id": "lumos", "emoji": "⚪", "rarity": "common", "type": "debuff",
        "mana": 12, "damage": 8,
        "effect": "blind", "effect_chance": 0.5,
        "desc_ru": "Ослепляющая вспышка света",
    },
    "incendio": {
        "id": "incendio", "emoji": "⚪", "rarity": "common", "type": "attack",
        "mana": 22, "damage": 28,
        "effect": "burn", "effect_chance": 0.45,
        "desc_ru": "Выпускает струю огня",
    },

    # ══════════════════════════════════════════════════════
    # UNCOMMON (🔵) — изученные заклинания
    # ══════════════════════════════════════════════════════
    "aqua_eructo": {
        "id": "aqua_eructo", "emoji": "🔵", "rarity": "uncommon", "type": "attack",
        "mana": 30, "damage": 40,
        "effect": "slow", "effect_chance": 0.5,
        "desc_ru": "Поток воды замедляет противника",
    },
    "wingardium_leviosa": {
        "id": "wingardium_leviosa", "emoji": "🔵", "rarity": "uncommon", "type": "debuff",
        "mana": 25, "damage": 5,
        "effect": "stun", "effect_chance": 0.35,
        "desc_ru": "Поднимает врага в воздух, сбивая с толку",
    },
    "alohomora": {
        "id": "alohomora", "emoji": "🔵", "rarity": "uncommon", "type": "attack",
        "mana": 28, "damage": 38,
        "effect": None, "effect_chance": 0,
        "desc_ru": "Пробивающий удар магической энергией",
    },
    "accio": {
        "id": "accio", "emoji": "🔵", "rarity": "uncommon", "type": "attack",
        "mana": 22, "damage": 28,
        "effect": "disarm", "effect_chance": 0.4,
        "desc_ru": "Притягивает предмет — может разоружить",
    },
    "lumos_maxima": {
        "id": "lumos_maxima", "emoji": "🔵", "rarity": "uncommon", "type": "debuff",
        "mana": 30, "damage": 0,
        "effect": "blind", "effect_chance": 1.0,
        "desc_ru": "Мощная вспышка — гарантированное ослепление",
    },
    "petrificus_totalus": {
        "id": "petrificus_totalus", "emoji": "🔵", "rarity": "uncommon", "type": "debuff",
        "mana": 35, "damage": 15,
        "effect": "stun", "effect_chance": 0.6,
        "desc_ru": "Полная петрификация тела",
    },
    "diffindo": {
        "id": "diffindo", "emoji": "🔵", "rarity": "uncommon", "type": "attack",
        "mana": 32, "damage": 45,
        "effect": "burn", "effect_chance": 0.3,
        "desc_ru": "Рассекающее заклинание",
    },
    "locomotor_mortis": {
        "id": "locomotor_mortis", "emoji": "🔵", "rarity": "uncommon", "type": "debuff",
        "mana": 28, "damage": 10,
        "effect": "freeze", "effect_chance": 0.7,
        "desc_ru": "Сковывает ноги противника",
    },
    "silencio": {
        "id": "silencio", "emoji": "🔵", "rarity": "uncommon", "type": "debuff",
        "mana": 30, "damage": 5,
        "effect": "silence", "effect_chance": 0.8,
        "desc_ru": "Молчание — цель не может читать заклинания 2 хода",
    },
    "episkey": {
        "id": "episkey", "emoji": "🔵", "rarity": "uncommon", "type": "heal",
        "mana": 35, "damage": 0, "heal": 40,
        "effect": "cleanse", "effect_chance": 1.0,
        "desc_ru": "Лечит 40 HP и очищает все дебаффы",
    },
    "expecto_patronum": {
        "id": "expecto_patronum", "emoji": "🔵", "rarity": "uncommon", "type": "defense",
        "mana": 40, "damage": 0,
        "effect": "shield", "effect_chance": 1.0, "shield_value": 35,
        "desc_ru": "Патронус создаёт щит, поглощающий 35 урона",
    },
    "nox": {
        "id": "nox", "emoji": "🔵", "rarity": "uncommon", "type": "debuff",
        "mana": 25, "damage": 18,
        "effect": "blind", "effect_chance": 0.8,
        "desc_ru": "Погружает поле боя во тьму",
    },
    "engorgio": {
        "id": "engorgio", "emoji": "🔵", "rarity": "uncommon", "type": "attack",
        "mana": 30, "damage": 42,
        "effect": "slow", "effect_chance": 0.6,
        "desc_ru": "Раздувает противника, замедляя его",
    },
    "reducio": {
        "id": "reducio", "emoji": "🔵", "rarity": "uncommon", "type": "debuff",
        "mana": 28, "damage": 12,
        "effect": "weaken", "effect_chance": 0.7,
        "desc_ru": "Уменьшает — снижает атаку на 20% на 3 хода",
    },

    # ══════════════════════════════════════════════════════
    # RARE (🟣) — редкие заклинания
    # ══════════════════════════════════════════════════════
    "sectumsempra": {
        "id": "sectumsempra", "emoji": "🟣", "rarity": "rare", "type": "attack",
        "mana": 45, "damage": 60,
        "effect": "burn", "effect_chance": 0.7,
        "desc_ru": "Тяжёлое кровотечение — мощный урон и горение",
    },
    "bombarda": {
        "id": "bombarda", "emoji": "🟣", "rarity": "rare", "type": "attack",
        "mana": 50, "damage": 70,
        "effect": "stun", "effect_chance": 0.45,
        "desc_ru": "Взрыв, сбивающий противника",
    },
    "glacius": {
        "id": "glacius", "emoji": "🟣", "rarity": "rare", "type": "debuff",
        "mana": 40, "damage": 20,
        "effect": "freeze", "effect_chance": 1.0,
        "desc_ru": "Полное замораживание",
    },
    "reducto": {
        "id": "reducto", "emoji": "🟣", "rarity": "rare", "type": "attack",
        "mana": 45, "damage": 65,
        "effect": None, "effect_chance": 0,
        "desc_ru": "Мощный разрушительный удар",
    },
    "crucio": {
        "id": "crucio", "emoji": "🟣", "rarity": "rare", "type": "debuff",
        "mana": 50, "damage": 30,
        "effect": "curse", "effect_chance": 0.6,
        "desc_ru": "Непростительное — проклятие боли, блокирует лечение",
    },
    "imperio": {
        "id": "imperio", "emoji": "🟣", "rarity": "rare", "type": "debuff",
        "mana": 55, "damage": 0,
        "effect": "confuse", "effect_chance": 0.7,
        "desc_ru": "Подчиняет волю врага",
    },
    "serpensortia": {
        "id": "serpensortia", "emoji": "🟣", "rarity": "rare", "type": "attack",
        "mana": 48, "damage": 55,
        "effect": "poison", "effect_chance": 0.65,
        "desc_ru": "Вызывает змею — яд 8 урона/ход на 4 хода",
    },
    "morsmordre": {
        "id": "morsmordre", "emoji": "🟣", "rarity": "rare", "type": "attack",
        "mana": 60, "damage": 75,
        "effect": "curse", "effect_chance": 0.5,
        "desc_ru": "Знак Тёмного Лорда — мощная тёмная магия",
    },
    "finite_incantatem": {
        "id": "finite_incantatem", "emoji": "🟣", "rarity": "rare", "type": "heal",
        "mana": 40, "damage": 0, "heal": 25,
        "effect": "dispel", "effect_chance": 1.0,
        "desc_ru": "Снимает все активные эффекты с себя",
    },
    "aguamenti": {
        "id": "aguamenti", "emoji": "🟣", "rarity": "rare", "type": "attack",
        "mana": 42, "damage": 55,
        "effect": "slow", "effect_chance": 0.8,
        "desc_ru": "Мощный поток воды сбивает с ног",
    },
    "depulso": {
        "id": "depulso", "emoji": "🟣", "rarity": "rare", "type": "attack",
        "mana": 38, "damage": 50,
        "effect": "disarm", "effect_chance": 0.6,
        "desc_ru": "Отталкивает врага и оружие из его рук",
    },
    "vipera_evanesca": {
        "id": "vipera_evanesca", "emoji": "🟣", "rarity": "rare", "type": "heal",
        "mana": 45, "damage": 0, "heal": 30,
        "effect": "cleanse", "effect_chance": 1.0,
        "desc_ru": "Нейтрализует яды и снимает проклятья",
    },

    # ══════════════════════════════════════════════════════
    # VERY RARE (🟠) — очень редкие заклинания
    # ══════════════════════════════════════════════════════
    "fiendfyre": {
        "id": "fiendfyre", "emoji": "🟠", "rarity": "very_rare", "type": "attack",
        "mana": 70, "damage": 120,
        "effect": "burn", "effect_chance": 1.0,
        "desc_ru": "Адское пламя — горение 5 ходов",
    },
    "obliviate": {
        "id": "obliviate", "emoji": "🟠", "rarity": "very_rare", "type": "debuff",
        "mana": 60, "damage": 0,
        "effect": "disarm", "effect_chance": 0.8,
        "desc_ru": "Стирает память — враг теряет ВСЕ заклинания на ход",
    },
    "prior_incantato": {
        "id": "prior_incantato", "emoji": "🟠", "rarity": "very_rare", "type": "attack",
        "mana": 65, "damage": 90,
        "effect": "reflect", "effect_chance": 0.5,
        "desc_ru": "Воспроизводит последнее заклинание врага",
    },
    "oppugno": {
        "id": "oppugno", "emoji": "🟠", "rarity": "very_rare", "type": "attack",
        "mana": 65, "damage": 85,
        "effect": "blind", "effect_chance": 0.9,
        "desc_ru": "Нападение — почти гарантированное ослепление",
    },
    "duro": {
        "id": "duro", "emoji": "🟠", "rarity": "very_rare", "type": "defense",
        "mana": 55, "damage": 0,
        "effect": "shield", "effect_chance": 1.0, "shield_value": 60,
        "desc_ru": "Каменный щит — поглощает 60 урона",
    },
    "confringo": {
        "id": "confringo", "emoji": "🟠", "rarity": "very_rare", "type": "attack",
        "mana": 70, "damage": 100,
        "effect": "burn", "effect_chance": 0.8,
        "desc_ru": "Мощный взрыв с горением",
    },
    "flagrante": {
        "id": "flagrante", "emoji": "🟠", "rarity": "very_rare", "type": "attack",
        "mana": 68, "damage": 95,
        "effect": "burn", "effect_chance": 0.9,
        "desc_ru": "Пылающее проклятие — всё, чего касается враг, жжёт его",
    },
    "tergeo": {
        "id": "tergeo", "emoji": "🟠", "rarity": "very_rare", "type": "heal",
        "mana": 55, "damage": 0, "heal": 60,
        "effect": "cleanse", "effect_chance": 1.0,
        "desc_ru": "Мощное очищающее лечение",
    },
    "ventus": {
        "id": "ventus", "emoji": "🟠", "rarity": "very_rare", "type": "attack",
        "mana": 60, "damage": 80,
        "effect": "stun", "effect_chance": 0.6,
        "desc_ru": "Ураганный вихрь сметает врага",
    },
    "specialis_revelio": {
        "id": "specialis_revelio", "emoji": "🟠", "rarity": "very_rare", "type": "debuff",
        "mana": 50, "damage": 10,
        "effect": "expose", "effect_chance": 1.0,
        "desc_ru": "Раскрывает слабости врага — +30% урон следующей атакой",
    },

    # ══════════════════════════════════════════════════════
    # EPIC (🔴) — эпические заклинания
    # ══════════════════════════════════════════════════════
    "avada_kedavra": {
        "id": "avada_kedavra", "emoji": "🔴", "rarity": "epic", "type": "attack",
        "mana": 80, "damage": 0,
        "effect": "instant_kill", "effect_chance": 0.5,
        "min_level": 20,
        "desc_ru": "Смертельное заклинание. 50% шанс мгновенной победы",
    },
    "legilimens": {
        "id": "legilimens", "emoji": "🔴", "rarity": "epic", "type": "debuff",
        "mana": 75, "damage": 40,
        "effect": "confuse", "effect_chance": 1.0,
        "desc_ru": "Проникает в разум — гарантированное замешательство и урон",
    },
    "protego_totalum": {
        "id": "protego_totalum", "emoji": "🔴", "rarity": "epic", "type": "defense",
        "mana": 70, "damage": 0,
        "effect": "shield", "effect_chance": 1.0, "shield_value": 120,
        "desc_ru": "Абсолютный щит — поглощает 120 урона",
    },
    "exarmo_maxima": {
        "id": "exarmo_maxima", "emoji": "🔴", "rarity": "epic", "type": "attack",
        "mana": 85, "damage": 110,
        "effect": "disarm", "effect_chance": 1.0,
        "desc_ru": "Максимальное разоружение с мощным уроном",
    },
    "infernus": {
        "id": "infernus", "emoji": "🔴", "rarity": "epic", "type": "attack",
        "mana": 90, "damage": 130,
        "effect": "burn", "effect_chance": 1.0,
        "desc_ru": "Адский огонь — 6 ходов горения",
    },
    "glacius_maxima": {
        "id": "glacius_maxima", "emoji": "🔴", "rarity": "epic", "type": "debuff",
        "mana": 80, "damage": 50,
        "effect": "freeze", "effect_chance": 1.0,
        "desc_ru": "Абсолютный лёд — заморозка на 4 хода",
    },
    "vortex_animus": {
        "id": "vortex_animus", "emoji": "🔴", "rarity": "epic", "type": "attack",
        "mana": 95, "damage": 140,
        "effect": "stun", "effect_chance": 0.7,
        "desc_ru": "Магический вихрь поглощает душу врага",
    },
    "horcrux_drain": {
        "id": "horcrux_drain", "emoji": "🔴", "rarity": "epic", "type": "attack",
        "mana": 85, "damage": 80,
        "effect": "lifesteal", "effect_chance": 1.0,
        "desc_ru": "Высасывает жизненную силу — восстанавливает 40% урона как HP",
    },

    # ══════════════════════════════════════════════════════
    # LEGENDARY (⭐) — легендарные заклинания (≤2% дроп)
    # ══════════════════════════════════════════════════════
    "tempus_maxima": {
        "id": "tempus_maxima", "emoji": "⭐", "rarity": "legendary", "type": "debuff",
        "mana": 100, "damage": 0,
        "effect": "stun", "effect_chance": 1.0, "stun_turns": 3,
        "desc_ru": "Останавливает время — враг пропускает 3 хода",
    },
    "animus_supremus": {
        "id": "animus_supremus", "emoji": "⭐", "rarity": "legendary", "type": "attack",
        "mana": 155, "damage": 200,
        "effect": "burn", "effect_chance": 1.0,
        "desc_ru": "Высший дух — смертоносный удар чистой магии",
    },
    "phoenix_tear": {
        "id": "phoenix_tear", "emoji": "⭐", "rarity": "legendary", "type": "heal",
        "mana": 100, "damage": 0, "heal": 150,
        "effect": "cleanse", "effect_chance": 1.0,
        "desc_ru": "Слеза феникса — мощнейшее исцеление",
    },
    "elder_wand_surge": {
        "id": "elder_wand_surge", "emoji": "⭐", "rarity": "legendary", "type": "attack",
        "mana": 140, "damage": 180,
        "effect": "disarm", "effect_chance": 1.0,
        "desc_ru": "Мощь Бузинной палочки — огромный урон и разоружение",
    },
    "death_hallow": {
        "id": "death_hallow", "emoji": "⭐", "rarity": "legendary", "type": "attack",
        "mana": 130, "damage": 0,
        "effect": "instant_kill", "effect_chance": 0.65,
        "min_level": 30,
        "desc_ru": "Дар смерти — 65% шанс мгновенной победы",
    },
    "deathly_shield": {
        "id": "deathly_shield", "emoji": "⭐", "rarity": "legendary", "type": "defense",
        "mana": 100, "damage": 0,
        "effect": "shield", "effect_chance": 1.0, "shield_value": 200,
        "desc_ru": "Мантия-невидимка — поглощает 200 урона",
    },

    # ══════════════════════════════════════════════════════
    # MYTHICAL (💫) — мифические заклинания (≤0.5% дроп)
    # ══════════════════════════════════════════════════════
    "fors_omnipotens": {
        "id": "fors_omnipotens", "emoji": "💫", "rarity": "mythical", "type": "attack",
        "mana": 230, "damage": 300,
        "effect": "burn", "effect_chance": 1.0,
        "desc_ru": "Всесильная сила — сокрушительный удар первозданной магии",
    },
    "anima_absoluta": {
        "id": "anima_absoluta", "emoji": "💫", "rarity": "mythical", "type": "attack",
        "mana": 180, "damage": 0,
        "effect": "instant_kill", "effect_chance": 0.8,
        "min_level": 40,
        "desc_ru": "Абсолютная душа — 80% шанс мгновенной победы",
    },
    "tempus_regressus": {
        "id": "tempus_regressus", "emoji": "💫", "rarity": "mythical", "type": "heal",
        "mana": 160, "damage": 0, "heal": 9999,
        "effect": "cleanse", "effect_chance": 1.0,
        "desc_ru": "Возврат времени — полное восстановление HP и снятие всех дебаффов",
    },

    # ── Новые заклинания (дополнение) ─────────────────────────────────────────
    "glacius_maxima": {
        "id": "glacius_maxima", "emoji": "❄️", "rarity": "rare", "type": "attack",
        "mana": 34, "damage": 46, "effect": "freeze", "effect_chance": 0.5,
        "desc_ru": "Мощный ледяной шквал, замораживающий противника",
    },
    "fulgur_storm": {
        "id": "fulgur_storm", "emoji": "⚡", "rarity": "rare", "type": "attack",
        "mana": 36, "damage": 50, "effect": "stun", "effect_chance": 0.4,
        "desc_ru": "Грозовой разряд, оглушающий цель",
    },
    "venenum_nox": {
        "id": "venenum_nox", "emoji": "🟣", "rarity": "uncommon", "type": "attack",
        "mana": 28, "damage": 32, "effect": "poison", "effect_chance": 0.6,
        "desc_ru": "Ядовитое облако тьмы, отравляющее врага",
    },
    "terra_eruptio": {
        "id": "terra_eruptio", "emoji": "🌿", "rarity": "very_rare", "type": "attack",
        "mana": 44, "damage": 62, "effect": "weaken", "effect_chance": 0.5,
        "desc_ru": "Извержение природной силы, ослабляющее противника",
    },
    "sanatio_magna": {
        "id": "sanatio_magna", "emoji": "💚", "rarity": "rare", "type": "heal",
        "mana": 40, "damage": 0, "heal": 110, "effect": "cleanse", "effect_chance": 0.5,
        "desc_ru": "Великое исцеление — восстанавливает много HP и снимает дебаффы",
    },
    "inferno_aeternum": {
        "id": "inferno_aeternum", "emoji": "🔥", "rarity": "epic", "type": "attack",
        "mana": 60, "damage": 85, "effect": "burn", "effect_chance": 0.7,
        "desc_ru": "Вечное пламя, сжигающее всё на своём пути",
    },
}

# ── Шансы выпадения (drop rates) ──────────────────────────────────────────────
RARITY_DROP_CHANCE = {
    "uncommon":  0.15,
    "rare":      0.08,
    "very_rare": 0.03,
    "epic":      0.012,
    "legendary": 0.005,
    "mythical":  0.002,   # 0.2% — мифические
}

RARITY_EMOJI = {
    "common":    "⚪",
    "uncommon":  "🔵",
    "rare":      "🟣",
    "very_rare": "🟠",
    "epic":      "🔴",
    "legendary": "⭐",
    "mythical":  "💫",
}

RARITY_NAMES_RU = {
    "common":    "Обычное",
    "uncommon":  "Необычное",
    "rare":      "Редкое",
    "very_rare": "Очень редкое",
    "epic":      "Эпическое",
    "legendary": "Легендарное",
    "mythical":  "Мифическое",
}

RARITY_SOURCES = {
    "uncommon":  ["lessons", "quests"],
    "rare":      ["dungeons", "shop"],
    "very_rare": ["deep_dungeons", "events"],
    "epic":      ["bosses", "weekly_event"],
    "legendary": ["final_bosses", "world_bosses"],
    "mythical":  ["world_bosses_top", "tournament_champion"],
}


def get_spell(spell_id: str) -> dict | None:
    return SPELLS.get(spell_id)


def spells_by_rarity(rarity: str) -> list[dict]:
    return [s for s in SPELLS.values() if s["rarity"] == rarity]


def basic_spells() -> list[dict]:
    return [s for s in SPELLS.values() if s["rarity"] == "common"]


def spell_display_name(spell_id: str, lang: str = "ru") -> str:
    names = {
        "expelliarmus":     {"ru": "Экспеллиармус"},
        "stupefy":          {"ru": "Ступефай"},
        "confundus":        {"ru": "Конфундус"},
        "flipendo":         {"ru": "Флипендо"},
        "protego":          {"ru": "Протего"},
        "escudo":           {"ru": "Эскудо"},
        "ricochet":         {"ru": "Рикошет"},
        "inflammare":       {"ru": "Инфламмаре"},
        "ice_chain":        {"ru": "Ледяная цепь"},
        "tenebrus":         {"ru": "Тенебрус"},
        "vulnero":          {"ru": "Вулнеро"},
        "sanacus":          {"ru": "Санакус"},
        "reparo":           {"ru": "Репаро"},
        "levicorpus":       {"ru": "Левикорпус"},
        "lumos":            {"ru": "Люмос"},
        "incendio":         {"ru": "Инцендио"},
        "aqua_eructo":      {"ru": "Аква Эрукто"},
        "wingardium_leviosa": {"ru": "Вингардиум Левиоса"},
        "alohomora":        {"ru": "Алохомора"},
        "accio":            {"ru": "Акцио"},
        "lumos_maxima":     {"ru": "Люмос Максима"},
        "petrificus_totalus": {"ru": "Петрификус Тоталус"},
        "diffindo":         {"ru": "Диффиндо"},
        "locomotor_mortis": {"ru": "Локомотор Мортис"},
        "silencio":         {"ru": "Силенцио"},
        "episkey":          {"ru": "Эпискей"},
        "expecto_patronum": {"ru": "Экспекто Патронум"},
        "nox":              {"ru": "Нокс"},
        "engorgio":         {"ru": "Энгорджио"},
        "reducio":          {"ru": "Редуцио"},
        "sectumsempra":     {"ru": "Сектумсемпра"},
        "bombarda":         {"ru": "Бомбарда"},
        "glacius":          {"ru": "Глациус"},
        "reducto":          {"ru": "Редукто"},
        "crucio":           {"ru": "Крусиатус"},
        "imperio":          {"ru": "Империо"},
        "serpensortia":     {"ru": "Серпенсортиа"},
        "morsmordre":       {"ru": "Морсмордре"},
        "finite_incantatem": {"ru": "Фините Инкантатем"},
        "aguamenti":        {"ru": "Агуаменти"},
        "depulso":          {"ru": "Депульсо"},
        "vipera_evanesca":  {"ru": "Вайпера Эванеска"},
        "fiendfyre":        {"ru": "Фиендфайр"},
        "obliviate":        {"ru": "Обливиэйт"},
        "prior_incantato":  {"ru": "Приор Инкантато"},
        "oppugno":          {"ru": "Оппугно"},
        "duro":             {"ru": "Дуро"},
        "confringo":        {"ru": "Конфринго"},
        "flagrante":        {"ru": "Флагранте"},
        "tergeo":           {"ru": "Теркео"},
        "ventus":           {"ru": "Вентус"},
        "specialis_revelio": {"ru": "Спекциалис Ревелио"},
        "avada_kedavra":    {"ru": "Авада Кедавра"},
        "legilimens":       {"ru": "Легилименс"},
        "protego_totalum":  {"ru": "Протего Тоталум"},
        "exarmo_maxima":    {"ru": "Экзармо Максима"},
        "infernus":         {"ru": "Инфернус"},
        "glacius_maxima":   {"ru": "Глациус Максима"},
        "vortex_animus":    {"ru": "Вортекс Анимус"},
        "horcrux_drain":    {"ru": "Крестраж-слив"},
        "tempus_maxima":    {"ru": "Темпус Максима"},
        "animus_supremus":  {"ru": "Анимус Супремус"},
        "phoenix_tear":     {"ru": "Слеза Феникса"},
        "elder_wand_surge": {"ru": "Мощь Бузинной Палочки"},
        "death_hallow":     {"ru": "Дар Смерти"},
        "deathly_shield":   {"ru": "Мантия Смерти"},
        "fors_omnipotens":  {"ru": "Форс Омнипотенс"},
        "anima_absoluta":   {"ru": "Анима Абсолюта"},
        "tempus_regressus": {"ru": "Темпус Регрессус"},
    }
    entry = names.get(spell_id, {})
    return entry.get(lang, entry.get("ru", spell_id.replace("_", " ").title()))


SPELL_TYPE_LABELS = {
    "ru": {"attack": "Атака", "defense": "Защита", "heal": "Лечение", "debuff": "Контроль/ослабление"},
    "en": {"attack": "Attack", "defense": "Defense", "heal": "Healing", "debuff": "Control/debuff"},
    "es": {"attack": "Ataque", "defense": "Defensa", "heal": "Curación", "debuff": "Control/debilitación"},
    "de": {"attack": "Angriff", "defense": "Verteidigung", "heal": "Heilung", "debuff": "Kontrolle/Schwächung"},
    "pt": {"attack": "Ataque", "defense": "Defesa", "heal": "Cura", "debuff": "Controle/enfraquecimento"},
}

SPELL_EFFECT_LABELS = {
    "ru": {"disarm": "разоружение", "stun": "оглушение", "confuse": "замешательство", "block": "блок урона", "reflect": "отражение урона", "burn": "горение", "freeze": "заморозка", "blind": "ослепление", "cleanse": "очищение", "slow": "замедление", "silence": "молчание", "shield": "щит", "weaken": "ослабление", "curse": "проклятие", "poison": "яд", "dispel": "снятие эффектов", "instant_kill": "мгновенная победа", "lifesteal": "вампиризм"},
    "en": {"disarm": "disarm", "stun": "stun", "confuse": "confusion", "block": "damage block", "reflect": "damage reflect", "burn": "burn", "freeze": "freeze", "blind": "blind", "cleanse": "cleanse", "slow": "slow", "silence": "silence", "shield": "shield", "weaken": "weaken", "curse": "curse", "poison": "poison", "dispel": "dispel", "instant_kill": "instant win", "lifesteal": "lifesteal"},
    "es": {}, "de": {}, "pt": {},
}

RARITY_NAMES_LOCALIZED = {
    "ru": RARITY_NAMES_RU,
    "en": {"common": "Common", "uncommon": "Uncommon", "rare": "Rare", "very_rare": "Very rare", "epic": "Epic", "legendary": "Legendary", "mythical": "Mythical"},
    "es": {"common": "Común", "uncommon": "Poco común", "rare": "Raro", "very_rare": "Muy raro", "epic": "Épico", "legendary": "Legendario", "mythical": "Mítico"},
    "de": {"common": "Gewöhnlich", "uncommon": "Ungewöhnlich", "rare": "Selten", "very_rare": "Sehr selten", "epic": "Episch", "legendary": "Legendär", "mythical": "Mythisch"},
    "pt": {"common": "Comum", "uncommon": "Incomum", "rare": "Raro", "very_rare": "Muito raro", "epic": "Épico", "legendary": "Lendário", "mythical": "Mítico"},
}


def _lang(lang: str) -> str:
    return lang if lang in ("ru", "en", "es", "de", "pt") else "ru"


def spell_rarity_label(rarity: str, lang: str = "ru") -> str:
    lang = _lang(lang)
    return RARITY_NAMES_LOCALIZED.get(lang, RARITY_NAMES_LOCALIZED["ru"]).get(rarity, rarity)


def spell_type_label(spell_type: str, lang: str = "ru") -> str:
    lang = _lang(lang)
    return SPELL_TYPE_LABELS.get(lang, SPELL_TYPE_LABELS["ru"]).get(spell_type, spell_type)


def spell_effect_label(effect: str | None, lang: str = "ru") -> str:
    if not effect:
        return "—"
    lang = _lang(lang)
    return SPELL_EFFECT_LABELS.get(lang, SPELL_EFFECT_LABELS["ru"]).get(effect) or SPELL_EFFECT_LABELS["ru"].get(effect, effect)


def spell_description(spell: dict, lang: str = "ru") -> str:
    lang = _lang(lang)
    if spell.get(f"desc_{lang}"):
        return spell[f"desc_{lang}"]
    if lang == "ru":
        return spell.get("desc_ru") or "Описание пока не добавлено."
    # Human-readable fallback for all supported languages, so descriptions are never empty.
    templates = {
        "en": "Battle spell with clear mana cost, damage, healing and effect values.",
        "es": "Hechizo de combate con coste de maná, daño, curación y efecto claros.",
        "de": "Kampfzauber mit klaren Mana-, Schadens-, Heilungs- und Effektwerten.",
        "pt": "Feitiço de combate com custo de mana, dano, cura e efeitos claros.",
    }
    return templates.get(lang, spell.get("desc_ru") or "Описание пока не добавлено.")


def spell_stats_text(spell: dict, lang: str = "ru") -> str:
    lang = _lang(lang)
    mana = int(spell.get("mana", 0) or 0)
    damage = int(spell.get("damage", 0) or 0)
    heal = int(spell.get("heal", 0) or 0)
    effect = spell_effect_label(spell.get("effect"), lang)
    chance = spell.get("effect_chance", 0) or 0
    chance_text = f"{int(chance * 100)}%" if chance else "—"
    shield = spell.get("shield_value")
    min_level = spell.get("min_level")
    if lang == "ru":
        lines = [f"💧 Мана: {mana}", f"⚔️ Урон: {damage}", f"💚 Лечение: {heal}", f"✨ Эффект: {effect} ({chance_text})"]
        if shield is not None:
            lines.append(f"🛡️ Щит: {shield}")
        if min_level is not None:
            lines.append(f"🔒 Уровень: {min_level}+")
    else:
        lines = [f"💧 Mana: {mana}", f"⚔️ Damage: {damage}", f"💚 Heal: {heal}", f"✨ Effect: {effect} ({chance_text})"]
        if shield is not None:
            lines.append(f"🛡️ Shield: {shield}")
        if min_level is not None:
            lines.append(f"🔒 Level: {min_level}+")
    return "\n".join(lines)


def spell_card_text(spell_id: str, lang: str = "ru", include_id: bool = False) -> str:
    spell = SPELLS[spell_id]
    rarity = spell.get("rarity", "common")
    lines = [
        f"{spell.get('emoji', RARITY_EMOJI.get(rarity, '✨'))} *{spell_display_name(spell_id, lang)}*",
        f"⭐ {spell_rarity_label(rarity, lang)} · {spell_type_label(spell.get('type', ''), lang)}",
        f"📜 {spell_description(spell, lang)}",
        spell_stats_text(spell, lang),
    ]
    if include_id:
        lines.append(f"ID: `{spell_id}`")
    return "\n".join(lines)


for _spell in SPELLS.values():
    _spell.setdefault("desc_en", spell_description(_spell, "en"))
    _spell.setdefault("desc_es", spell_description(_spell, "es"))
    _spell.setdefault("desc_de", spell_description(_spell, "de"))
    _spell.setdefault("desc_pt", spell_description(_spell, "pt"))
