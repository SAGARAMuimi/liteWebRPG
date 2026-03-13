"""
models/database.py - DB接続・セッション管理
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """DB セッションを返すコンテキストマネージャー"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """全テーブルを作成する（アプリ起動時に呼び出す）"""
    import models  # noqa: F401 - 全モデルを依存順に登録する
    Base.metadata.create_all(bind=engine)


def migrate_db() -> None:
    """
    既存 DB へのスキーマ変更・データ修正を冪等に実行する。
    init_db() の直後に呼び出すこと。
    """
    from sqlalchemy import text
    with engine.connect() as conn:
        # users テーブルに gold カラム追加
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN gold INTEGER NOT NULL DEFAULT 0"))
            conn.commit()
        except Exception:
            conn.rollback()

        # enemies テーブルに gold_reward カラム追加
        try:
            conn.execute(text("ALTER TABLE enemies ADD COLUMN gold_reward INTEGER NOT NULL DEFAULT 0"))
            conn.commit()
        except Exception:
            conn.rollback()

        # 戦闘報酬のゴールド初期値を設定（未設定のもののみ）
        gold_data = [
            ("'\u30b9ライム'",    8),
            ("'コウモリ'",    10),
            ("'ゴブリン'",    15),
            ("'オーク'",      20),
            ("'ドラゴン'",    30),
            ("'ゴブリンキング'", 40),
            ("'オークチーフ'",   65),
            ("'ダークロード'",   100),
        ]
        for name, gold in gold_data:
            conn.execute(text(
                f"UPDATE enemies SET gold_reward={gold} WHERE name={name} AND gold_reward=0"
            ))
        conn.commit()

        # skills テーブルへのカラム追加（存在しない場合のみ）
        for ddl in [
            "ALTER TABLE skills ADD COLUMN target_type VARCHAR(16) DEFAULT 'self'",
            "ALTER TABLE skills ADD COLUMN duration INTEGER DEFAULT 0",
        ]:
            try:
                conn.execute(text(ddl))
                conn.commit()
            except Exception:
                conn.rollback()  # カラムが既に存在する場合は無視

        # バフスキルの effect_type / target_type / duration を正しい値に更新
        updates = [
            ("UPDATE skills SET effect_type='buff_def', target_type='self', duration=3, power=5 "
             "WHERE name='挑発' AND class_type='knight'"),
            ("UPDATE skills SET effect_type='buff_atk', target_type='self', duration=3, power=4 "
             "WHERE name='気合い' AND class_type='monk'"),
            ("UPDATE skills SET effect_type='buff_atk', target_type='all_allies', duration=3, power=3 "
             "WHERE name='鼓舞の歌' AND class_type='bard'"),
        ]
        for sql in updates:
            conn.execute(text(sql))
        conn.commit()

        # enemies テーブルへ status_resistance カラム追加
        try:
            conn.execute(text("ALTER TABLE enemies ADD COLUMN status_resistance VARCHAR(64) DEFAULT ''"))
            conn.commit()
        except Exception:
            conn.rollback()

        # ボスにスタン耐性を付与（未設定のもののみ）
        conn.execute(text(
            "UPDATE enemies SET status_resistance='stun' "
            "WHERE is_boss=1 AND (status_resistance IS NULL OR status_resistance='')"
        ))
        conn.commit()

        # 状態異常スキルを追加（既存 DB への冪等 INSERT）
        status_skills = [
            (14, "浄化",     "priest",  5,  0, "cure",     "ally",        0),
            (15, "毒霧",     "mage",   10,  0, "poison",   "all_enemies", 3),
            (16, "目眩まし", "thief",   7,  0, "silence",  "enemy",       2),
            (17, "毒矢",     "archer",  6,  0, "poison",   "enemy",       3),
            (18, "鎧裂き",   "warrior", 8,  0, "def_down", "enemy",       3),
        ]
        for row in status_skills:
            conn.execute(text(
                "INSERT OR IGNORE INTO skills "
                "(id, name, class_type, mp_cost, power, effect_type, target_type, duration) "
                "VALUES (:id,:name,:ct,:mp,:pw,:et,:tt,:dur)"
            ), {"id": row[0], "name": row[1], "ct": row[2], "mp": row[3],
                "pw": row[4], "et": row[5], "tt": row[6], "dur": row[7]})
        conn.commit()

        # items テーブル作成（存在しない場合）
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        VARCHAR(64)  NOT NULL,
                description VARCHAR(256) NOT NULL DEFAULT '',
                effect_type VARCHAR(16)  NOT NULL,
                power       INTEGER      NOT NULL DEFAULT 0,
                target_type VARCHAR(16)  NOT NULL DEFAULT 'ally',
                duration    INTEGER      NOT NULL DEFAULT 0,
                price       INTEGER      NOT NULL DEFAULT 0
            )
        """))
        conn.commit()

        # inventories テーブル作成（存在しない場合）
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS inventories (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id  INTEGER NOT NULL REFERENCES users(id),
                item_id  INTEGER NOT NULL REFERENCES items(id),
                quantity INTEGER NOT NULL DEFAULT 0,
                UNIQUE(user_id, item_id)
            )
        """))
        conn.commit()

        # アイテム初期データ（INSERT OR IGNORE で冪等）
        initial_items = [
            (1, "ポーション",       "HPを30回復する",               "heal_hp",  30, "ally", 0,  50),
            (2, "ハイポーション",   "HPを80回復する",               "heal_hp",  80, "ally", 0, 150),
            (3, "エーテル",         "MPを20回復する",               "heal_mp",  20, "ally", 0,  80),
            (4, "万能薬",           "状態異常を全て回復する",       "cure",      0, "ally", 0, 100),
            (5, "フェニックスの羽", "戦闘不能を蘇生（HP30%）",     "revive",   30, "ally", 0, 200),
            (6, "活力の薬",         "ATKを3上昇（3ターン）",       "buff_atk",  3, "self", 3, 120),
        ]
        for row in initial_items:
            conn.execute(text(
                "INSERT OR IGNORE INTO items "
                "(id, name, description, effect_type, power, target_type, duration, price) "
                "VALUES (:id,:nm,:desc,:et,:pw,:tt,:dur,:price)"
            ), {"id": row[0], "nm": row[1], "desc": row[2], "et": row[3],
                "pw": row[4], "tt": row[5], "dur": row[6], "price": row[7]})
        conn.commit()

        # ── R-11 装備システム ───────────────────────────────────────────

        # equipments テーブル作成（存在しない場合）
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS equipments (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            VARCHAR(64)  NOT NULL,
                description     VARCHAR(256) NOT NULL DEFAULT '',
                slot            VARCHAR(16)  NOT NULL,
                atk_bonus       INTEGER      NOT NULL DEFAULT 0,
                def_bonus       INTEGER      NOT NULL DEFAULT 0,
                hp_bonus        INTEGER      NOT NULL DEFAULT 0,
                mp_bonus        INTEGER      NOT NULL DEFAULT 0,
                price           INTEGER      NOT NULL DEFAULT 0,
                required_class  VARCHAR(128) NOT NULL DEFAULT ''
            )
        """))
        conn.commit()

        # character_equipments テーブル作成（存在しない場合）
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS character_equipments (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id    INTEGER NOT NULL REFERENCES characters(id),
                equipment_id    INTEGER NOT NULL REFERENCES equipments(id),
                slot            VARCHAR(16) NOT NULL,
                UNIQUE(character_id, slot)
            )
        """))
        conn.commit()

        # 装備マスタ初期データ（INSERT OR IGNORE で冪等）
        # (id, name, description, slot, atk_bonus, def_bonus, hp_bonus, mp_bonus, price, required_class)
        initial_equips = [
            # ── 武器 ──
            (1,  "銅の剣",      "軽くて扱いやすい銅製の剣",          "weapon",    3, 0,  0,  0, 100, ""),
            (2,  "鋼の剣",      "頑丈な鋼製の両手剣。戦士・騎士向け", "weapon",    6, 0,  0,  0, 280, "warrior,knight"),
            (3,  "魔法の杖",    "魔力を込めた杖。MPも強化される",     "weapon",    3, 0,  0, 10, 200, "mage,priest,bard"),
            (4,  "短刀",        "素早い連撃に特化した短刀",           "weapon",    5, 0,  0,  0, 150, "thief,archer"),
            (5,  "鉄の拳",      "武道家専用の鉄製グローブ",           "weapon",    5, 2,  0,  0, 180, "monk"),
            # ── 防具 ──
            (6,  "皮の鎧",      "軽くて動きやすい革製の鎧",           "armor",     0, 3, 10,  0, 120, ""),
            (7,  "鎖かたびら",  "重厚な鎖製の鎧。重戦士向け",         "armor",     0, 7, 25,  0, 320, "warrior,knight,monk"),
            (8,  "魔法のローブ","魔力を高める特殊素材のローブ",       "armor",     0, 2,  5, 20, 220, "mage,priest,bard"),
            (9,  "軽革鎧",      "弓手や盗賊向けの軽量装甲",           "armor",     0, 4, 15,  5, 230, "thief,archer"),
            # ── アクセサリ ──
            (10, "体力のリング","最大HPを上昇させる不思議な指輪",     "accessory", 0, 0, 20,  0, 150, ""),
            (11, "魔力のリング","最大MPを上昇させる不思議な指輪",     "accessory", 0, 0,  0, 15, 150, ""),
            (12, "鋼の腕輪",    "腕力を高める金属製の腕輪",           "accessory", 2, 0,  0,  0, 130, ""),
        ]
        for row in initial_equips:
            conn.execute(text(
                "INSERT OR IGNORE INTO equipments "
                "(id, name, description, slot, atk_bonus, def_bonus, hp_bonus, mp_bonus, price, required_class) "
                "VALUES (:id,:nm,:desc,:slot,:atk,:def,:hp,:mp,:price,:req)"
            ), {"id": row[0], "nm": row[1], "desc": row[2], "slot": row[3],
                "atk": row[4], "def": row[5], "hp": row[6], "mp": row[7],
                "price": row[8], "req": row[9]})
        conn.commit()
