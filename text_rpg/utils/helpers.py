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

    if db.query(Dungeon).count() > 0:
        return  # 既にデータあり

    # ダンジョン
    db.add(Dungeon(id=1, name="暗黒の洞窟", floor=3))

    # 敵（1F）
    db.add_all([
        Enemy(name="スライム",    dungeon_id=1, floor=1, hp=20, attack=5,  defense=2, exp_reward=10,  is_boss=False),
        Enemy(name="コウモリ",    dungeon_id=1, floor=1, hp=15, attack=7,  defense=1, exp_reward=12,  is_boss=False),
    ])
    # 敵（2F）
    db.add_all([
        Enemy(name="ゴブリン",    dungeon_id=1, floor=2, hp=35, attack=10, defense=4, exp_reward=20,  is_boss=False),
        Enemy(name="オーク",      dungeon_id=1, floor=2, hp=40, attack=12, defense=5, exp_reward=25,  is_boss=False),
    ])
    # 敵（3F 通常）
    db.add_all([
        Enemy(name="ドラゴン",    dungeon_id=1, floor=3, hp=60, attack=14, defense=6, exp_reward=35,  is_boss=False),
    ])
    # ボス
    db.add_all([
        Enemy(name="ゴブリンキング", dungeon_id=1, floor=1, hp=60,  attack=10, defense=5,  exp_reward=50,  is_boss=True),
        Enemy(name="オークチーフ",   dungeon_id=1, floor=2, hp=90,  attack=15, defense=8,  exp_reward=80,  is_boss=True),
        Enemy(name="ダークロード",   dungeon_id=1, floor=3, hp=120, attack=20, defense=10, exp_reward=100, is_boss=True),
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

    db.commit()
