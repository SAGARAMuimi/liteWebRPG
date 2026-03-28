"""
utils/helpers.py - 汎用ユーティリティ関数
"""

from config import CLASS_NAMES


def class_display_name(class_type: str) -> str:
    """class_type -> 日本語表示名"""
    return CLASS_NAMES.get(class_type, class_type)


def hp_bar(current: int, maximum: int, width: int = 20) -> str:
    """テキストベースの HP バーを生成する"""
    if maximum <= 0:
        return "[" + "░" * width + "]"
    ratio = max(0.0, min(1.0, current / maximum))
    filled = int(ratio * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {current}/{maximum}"


def seed_initial_data(db) -> None:
    """
    DB にダンジョン・敵・スキルの初期データが存在しない場合に投入する。
    SQLite の場合は db_init.sql を直接実行する代わりにこの関数を使う。
    """
    from models.dungeon import Dungeon
    from models.enemy import Enemy
    from models.skill import Skill
    from models.equipment import Equipment

    has_dungeon = db.query(Dungeon).count() > 0
    has_equipment = db.query(Equipment).count() > 0

    # ダンジョン/敵/スキル/アイテムは「初回のみ」投入
    if not has_dungeon:
        # ダンジョン
        db.add(Dungeon(id=1, name="暗黒の洞窟", floor=3))

        # 敵（1F）
        db.add_all([
            Enemy(name="スライム",    dungeon_id=1, floor=1, hp=20, attack=5,  defense=2, exp_reward=10,  gold_reward=8,   is_boss=False, intelligence=1),
            Enemy(name="コウモリ",    dungeon_id=1, floor=1, hp=15, attack=7,  defense=1, exp_reward=12,  gold_reward=10,  is_boss=False, intelligence=1),
        ])
        # 敵（2F）
        db.add_all([
            Enemy(name="ゴブリン",    dungeon_id=1, floor=2, hp=35, attack=10, defense=4, exp_reward=20,  gold_reward=15,  is_boss=False, intelligence=2),
            Enemy(name="オーク",      dungeon_id=1, floor=2, hp=40, attack=12, defense=5, exp_reward=25,  gold_reward=20,  is_boss=False, intelligence=2),
        ])
        # 敵（3F 通常）
        db.add_all([
            Enemy(name="ドラゴン",    dungeon_id=1, floor=3, hp=60, attack=14, defense=6, exp_reward=35,  gold_reward=30,  is_boss=False, intelligence=2),
        ])
        # ボス
        db.add_all([
            Enemy(name="ゴブリンキング", dungeon_id=1, floor=1, hp=60,  attack=10, defense=5,  exp_reward=50,  gold_reward=40,  is_boss=True,  status_resistance="stun", intelligence=3),
            Enemy(name="オークチーフ",   dungeon_id=1, floor=2, hp=90,  attack=15, defense=8,  exp_reward=80,  gold_reward=65,  is_boss=True,  status_resistance="stun", intelligence=3),
            Enemy(name="ダークロード",   dungeon_id=1, floor=3, hp=120, attack=20, defense=10, exp_reward=100, gold_reward=100, is_boss=True,  status_resistance="stun", intelligence=3),
        ])
        # スキル（既存4クラス）
        db.add_all([
            Skill(name="ファイア",     class_type="mage",    mp_cost=10, power=30, effect_type="attack"),
            Skill(name="ヒール",       class_type="priest",  mp_cost=8,  power=40, effect_type="heal"),
            Skill(name="バックスタブ", class_type="thief",   mp_cost=6,  power=25, effect_type="attack"),
            Skill(name="チャージ",     class_type="warrior", mp_cost=5,  power=20, effect_type="attack"),
            Skill(name="ポーション",   class_type="all",     mp_cost=0,  power=30, effect_type="heal"),
        ])
        # スキル（追加4クラス）
        db.add_all([
            # 騎士
            Skill(name="挑発",           class_type="knight", mp_cost=4,  power=5,  effect_type="buff_def", target_type="self",       duration=3),
            Skill(name="シールドバッシュ", class_type="knight", mp_cost=6,  power=15, effect_type="attack",   target_type="enemy",      duration=0),
            # 弓使い
            Skill(name="連射",   class_type="archer", mp_cost=7,  power=28, effect_type="attack",   target_type="enemy",      duration=0),
            Skill(name="矢雨",   class_type="archer", mp_cost=10, power=35, effect_type="attack",   target_type="enemy",      duration=0),
            # 武道家
            Skill(name="気合い", class_type="monk",   mp_cost=0,  power=4,  effect_type="buff_atk", target_type="self",       duration=3),
            Skill(name="連打",   class_type="monk",   mp_cost=0,  power=12, effect_type="attack",   target_type="enemy",      duration=0),
            # 吟遊詩人
            Skill(name="鼓舞の歌", class_type="bard", mp_cost=8,  power=3,  effect_type="buff_atk", target_type="all_allies", duration=3),
            Skill(name="癒しの歌", class_type="bard", mp_cost=14, power=55, effect_type="heal",     target_type="ally",       duration=0),
        ])
        # スキル（状態異常システム）
        db.add_all([
            Skill(name="浄化",   class_type="priest",  mp_cost=5,  power=0, effect_type="cure",     target_type="ally",         duration=0),
            Skill(name="毒霧",   class_type="mage",    mp_cost=10, power=0, effect_type="poison",   target_type="all_enemies",  duration=3),
            Skill(name="目眩まし", class_type="thief",   mp_cost=7,  power=0, effect_type="silence",  target_type="enemy",        duration=2),
            Skill(name="毒矢",   class_type="archer",  mp_cost=6,  power=0, effect_type="poison",   target_type="enemy",        duration=3),
            Skill(name="鎧裂き", class_type="warrior", mp_cost=8,  power=0, effect_type="def_down", target_type="enemy",        duration=3),
        ])

        # アイテムマスタ（6種）— 明示的 ID を持つため merge() でUPSERT
        from models.item import Item
        _items = [
            Item(id=1, name="ポーション",       description="HPを30回復する",           effect_type="heal_hp",  power=30, target_type="ally", duration=0, price=50),
            Item(id=2, name="ハイポーション",   description="HPを80回復する",           effect_type="heal_hp",  power=80, target_type="ally", duration=0, price=150),
            Item(id=3, name="エーテル",         description="MPを20回復する",           effect_type="heal_mp",  power=20, target_type="ally", duration=0, price=80),
            Item(id=4, name="万能薬",           description="状態異常を全て回復する",   effect_type="cure",     power=0,  target_type="ally", duration=0, price=100),
            Item(id=5, name="フェニックスの羽", description="戦闘不能を蘇生（HP30%）",  effect_type="revive",   power=30, target_type="ally", duration=0, price=200),
            Item(id=6, name="活力の薬",         description="ATKを3上昇（3ターン）",    effect_type="buff_atk", power=3,  target_type="self", duration=3, price=120),
        ]
        for _item in _items:
            db.merge(_item)

    # 装備マスタは、DB種別に依存しないよう ORM で投入（空の場合のみ）
    if not has_equipment:
        initial_equips = [
            # (id, name, description, slot, atk_bonus, def_bonus, hp_bonus, mp_bonus, price, required_class)
            (1,  "銅の剣",       "軽くて扱いやすい銅製の剣",           "weapon",    3, 0,  0,  0, 100, ""),
            (2,  "鋼の剣",       "頑丈な鋼製の両手剣。戦士・騎士向け", "weapon",    6, 0,  0,  0, 280, "warrior,knight"),
            (3,  "魔法の杖",     "魔力を込めた杖。MPも強化される",     "weapon",    3, 0,  0, 10, 200, "mage,priest,bard"),
            (4,  "短刀",         "素早い連撃に特化した短刀",           "weapon",    5, 0,  0,  0, 150, "thief,archer"),
            (5,  "鉄の拳",       "武道家専用の鉄製グローブ",           "weapon",    5, 2,  0,  0, 180, "monk"),
            (6,  "皮の鎧",       "軽くて動きやすい革製の鎧",           "armor",     0, 3, 10,  0, 120, ""),
            (7,  "鎖かたびら",   "重厚な鎖製の鎧。重戦士向け",         "armor",     0, 7, 25,  0, 320, "warrior,knight,monk"),
            (8,  "魔法のローブ", "魔力を高める特殊素材のローブ",       "armor",     0, 2,  5, 20, 220, "mage,priest,bard"),
            (9,  "軽革鎧",       "弓手や盗賊向けの軽量装甲",           "armor",     0, 4, 15,  5, 230, "thief,archer"),
            (10, "体力のリング", "最大HPを上昇させる不思議な指輪",     "accessory", 0, 0, 20,  0, 150, ""),
            (11, "魔力のリング", "最大MPを上昇させる不思議な指輪",     "accessory", 0, 0,  0, 15, 150, ""),
            (12, "鋼の腕輪",     "腕力を高める金属製の腕輪",           "accessory", 2, 0,  0,  0, 130, ""),
        ]
        for row in initial_equips:
            db.merge(Equipment(
                id=row[0],
                name=row[1],
                description=row[2],
                slot=row[3],
                atk_bonus=row[4],
                def_bonus=row[5],
                hp_bonus=row[6],
                mp_bonus=row[7],
                price=row[8],
                required_class=row[9],
            ))

    db.commit()


def give_starter_items(db, user_id: int) -> None:
    """
    新規ユーザーにポーション×3を付与する。
    既にインベントリが存在する場合は付与しない（重複防止）。
    """
    from models.inventory import Inventory
    existing = db.query(Inventory).filter(Inventory.user_id == user_id).first()
    if existing:
        return  # 既に付与済み
    Inventory.add_item(db, user_id, item_id=1, quantity=3)  # ポーション×3
