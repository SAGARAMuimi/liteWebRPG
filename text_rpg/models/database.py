"""models/database.py - DB接続・セッション管理"""

import ssl
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import DATABASE_URL


def _normalize_database_url(database_url: str) -> str:
    """PostgreSQL URL に pg8000 ドライバを強制する。

    SQLAlchemy は postgresql:// の場合にデフォルトドライバ（psycopg 系）を期待するため、
    psycopg を入れない運用では postgresql+pg8000:// に正規化して動作させる。
    """
    url = (database_url or "").strip()

    # Heroku などで使われる短縮スキームを正規化
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]

    # ドライバ未指定の postgresql:// を pg8000 に寄せる
    if url.startswith("postgresql://") and "postgresql+" not in url:
        url = url.replace("postgresql://", "postgresql+pg8000://", 1)

    return url


def _strip_sslmode_query(url: str) -> tuple[str, str | None]:
    """URL クエリの sslmode を除去して値を返す。

    psycopg 系の URL でよく使われる `sslmode=require` は pg8000 では未対応で、
    そのまま渡すと TypeError になるため取り除く。
    """
    parts = urlsplit(url)
    if not parts.query:
        return url, None

    sslmode: str | None = None
    kept: list[tuple[str, str]] = []
    for k, v in parse_qsl(parts.query, keep_blank_values=True):
        if k.lower() == "sslmode":
            sslmode = v
            continue
        kept.append((k, v))

    new_query = urlencode(kept)
    new_url = urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))
    return new_url, sslmode


def _sanitize_pg8000_query(url: str) -> tuple[str, str | None]:
    """pg8000 で受け取れないクエリパラメータを取り除く。

    Neon などが発行する libpq/psycopg 向け URL には `sslmode` や `channel_binding` 等が
    付くことがあるが、pg8000.connect() はこれらを受け取れず TypeError になる。
    """
    url, sslmode = _strip_sslmode_query(url)
    parts = urlsplit(url)
    if not parts.query:
        return url, sslmode

    allowed_simple_keys = {
        "application_name",
        "timeout",
        "tcp_keepalive",
        "replication",
    }
    drop_keys = {
        "channel_binding",
        # libpq 系の SSL パラメータ（pg8000 は別方式）
        "sslrootcert",
        "sslcert",
        "sslkey",
        "sslpassword",
    }

    kept: list[tuple[str, str]] = []
    for k, v in parse_qsl(parts.query, keep_blank_values=True):
        kl = k.lower()
        if kl in drop_keys:
            continue
        if kl in allowed_simple_keys:
            kept.append((k, v))
            continue
        # それ以外は pg8000 に渡すと落ちる可能性が高いので除去

    new_query = urlencode(kept)
    new_url = urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))
    return new_url, sslmode


def _build_connect_args(db_url: str, sslmode: str | None) -> dict:
    if db_url.startswith("sqlite"):
        return {"check_same_thread": False}

    # pg8000 は sslmode を受け取れないため、必要に応じて ssl_context を設定する
    if db_url.startswith("postgresql") and sslmode:
        mode = sslmode.strip().lower()
        if mode in {"require", "verify-ca", "verify-full"}:
            return {"ssl_context": ssl.create_default_context()}

    return {}

_db_url = _normalize_database_url(DATABASE_URL)
if _db_url.startswith("postgresql"):
    _db_url, _sslmode = _sanitize_pg8000_query(_db_url)
else:
    _db_url, _sslmode = _strip_sslmode_query(_db_url)
engine = create_engine(
    _db_url,
    connect_args=_build_connect_args(_db_url, _sslmode),
    # Neon など クラウド DB はアイドル時に接続を切断するため、
    # プールから取り出す前に死活確認して自動再接続させる。
    pool_pre_ping=True,
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


def _add_column_if_not_exists(conn, table: str, column: str, definition: str) -> None:
    """カラムが存在しない場合のみ ALTER TABLE ADD COLUMN を実行する（方言共通）。"""
    from sqlalchemy import text
    dialect = engine.dialect.name
    try:
        if dialect == "sqlite":
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
        else:
            # PostgreSQL / MySQL: 存在確認してから追加
            conn.execute(text(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {definition}"
            ))
        conn.commit()
    except Exception:
        conn.rollback()


def _migrate_postgresql(conn) -> None:
    """PostgreSQL (Neon) 向けのスキーマ追加マイグレーション。

    init_db() で Base.metadata.create_all() が実行されるため新規テーブルは自動作成済み。
    ここでは既存テーブルへの「カラム追加のみ」を冪等に行う。
    """
    from sqlalchemy import text

    add = lambda t, c, d: _add_column_if_not_exists(conn, t, c, d)  # noqa: E731

    # dungeons
    add("dungeons", "map_type", "VARCHAR(16) NOT NULL DEFAULT 'linear'")

    # dungeon_progress
    add("dungeon_progress", "current_x", "INTEGER NOT NULL DEFAULT -1")
    add("dungeon_progress", "current_y", "INTEGER NOT NULL DEFAULT -1")

    # users
    add("users", "gold",               "INTEGER NOT NULL DEFAULT 0")
    add("users", "meta_gold",          "INTEGER NOT NULL DEFAULT 0")
    add("users", "meta_titles",        "VARCHAR(512) NOT NULL DEFAULT ''")
    add("users", "meta_upgrade_ranks", "VARCHAR(512) NOT NULL DEFAULT '{}'")
    add("users", "is_admin",           "INTEGER NOT NULL DEFAULT 0")

    # enemies
    add("enemies", "gold_reward",        "INTEGER NOT NULL DEFAULT 0")
    add("enemies", "status_resistance",  "VARCHAR(64) NOT NULL DEFAULT ''")
    add("enemies", "intelligence",       "INTEGER NOT NULL DEFAULT 2")

    # skills
    add("skills", "target_type", "VARCHAR(16) NOT NULL DEFAULT 'self'")
    add("skills", "duration",    "INTEGER NOT NULL DEFAULT 0")
    add("skills", "cooldown",    "INTEGER NOT NULL DEFAULT 0")

    # characters
    add("characters", "intelligence", "INTEGER NOT NULL DEFAULT 2")

    # equipments
    add("equipments", "disposable", "INTEGER NOT NULL DEFAULT 0")

    # feedbacks
    add("feedbacks", "contact_email", "VARCHAR(254)")
    add("feedbacks", "needs_reply",   "INTEGER NOT NULL DEFAULT 0")
    add("feedbacks", "is_anonymous",  "INTEGER NOT NULL DEFAULT 0")


def migrate_db() -> None:
    """
    既存 DB へのスキーマ変更・データ修正を冪等に実行する。
    init_db() の直後に呼び出すこと。
    """
    from sqlalchemy import text

    if engine.dialect.name == "postgresql":
        with engine.connect() as conn:
            _migrate_postgresql(conn)
        return

    if engine.dialect.name != "sqlite":
        return

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
            "ALTER TABLE skills ADD COLUMN cooldown INTEGER NOT NULL DEFAULT 0",
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

        # 各スキルのクールダウン値を設定（DEFAULT 0 のままのもののみを更新）
        skill_cooldowns = [
            (1,  2),  # ファイア（mage 強力攻撃）
            (2,  2),  # ヒール（priest 回復）
            (3,  1),  # バックスタブ（thief）
            (4,  1),  # チャージ（warrior）
            # id=5 ポーション：0（クールダウンなし）
            (6,  3),  # 挑発（knight バフ）
            (7,  1),  # シールドバッシュ（knight）
            (8,  1),  # 連射（archer）
            (9,  2),  # 矢雨（archer 高威力）
            (10, 3),  # 気合い（monk バフ）
            (11, 1),  # 連打（monk）
            (12, 3),  # 鼓舞の歌（bard 全体バフ）
            (13, 2),  # 癌しの歌（bard 回復）
            (14, 2),  # 浄化（priest）
            (15, 3),  # 毒霧（mage 全体毒）
            (16, 2),  # 目眩まし（thief）
            (17, 2),  # 毒矢（archer）
            (18, 2),  # 鹾裂き（warrior）
        ]
        for sid, cd in skill_cooldowns:
            conn.execute(text(f"UPDATE skills SET cooldown={cd} WHERE id={sid}"))
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
                required_class  VARCHAR(128) NOT NULL DEFAULT '',
                disposable      INTEGER      NOT NULL DEFAULT 0
            )
        """))
        conn.commit()

        # equipments テーブルに disposable カラム追加（既存 DB 対応）
        try:
            conn.execute(text(
                "ALTER TABLE equipments ADD COLUMN disposable INTEGER NOT NULL DEFAULT 0"
            ))
            conn.commit()
        except Exception:
            conn.rollback()

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

        # character_inventories テーブル作成（存在しない場合）
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS character_inventories (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id    INTEGER NOT NULL REFERENCES characters(id),
                equipment_id    INTEGER NOT NULL REFERENCES equipments(id),
                quantity        INTEGER NOT NULL DEFAULT 1,
                UNIQUE(character_id, equipment_id)
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
        # ── R-13 味方AI知性値 ───────────────────────────────────────────

        # characters テーブルに intelligence カラム追加（既存 DB 対応）
        try:
            conn.execute(text(
                "ALTER TABLE characters ADD COLUMN intelligence INTEGER NOT NULL DEFAULT 2"
            ))
            conn.commit()
        except Exception:
            conn.rollback()

        # ── R-12 敵AI 知性値拡張 ────────────────────────────────────────────

        # enemies テーブルに intelligence カラム追加（既存 DB 対応）
        try:
            conn.execute(text(
                "ALTER TABLE enemies ADD COLUMN intelligence INTEGER NOT NULL DEFAULT 2"
            ))
            conn.commit()
        except Exception:
            conn.rollback()

        # ── R-15 メタ進行（恒久解放）──────────────────────────────────────

        # users テーブルにメタ進行用カラムを追加（既存 DB 対応）
        try:
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN meta_gold INTEGER NOT NULL DEFAULT 0"
            ))
            conn.commit()
        except Exception:
            conn.rollback()

        try:
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN meta_titles VARCHAR(512) NOT NULL DEFAULT ''"
            ))
            conn.commit()
        except Exception:
            conn.rollback()

        try:
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN meta_upgrade_ranks VARCHAR(512) NOT NULL DEFAULT '{}'"
            ))
            conn.commit()
        except Exception:
            conn.rollback()

        # ── FEEDBACK 不具合報告・改善要望 ─────────────────────────────────────

        # users テーブルに管理者フラグを追加（既存 DB 対応）
        try:
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0"
            ))
            conn.commit()
        except Exception:
            conn.rollback()

        # feedbacks テーブルを作成（既存 DB 対応）
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS feedbacks (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER REFERENCES users(id),
                category     VARCHAR(16)  NOT NULL,
                title        VARCHAR(128) NOT NULL,
                body         TEXT         NOT NULL,
                contact_email VARCHAR(254),
                needs_reply  INTEGER      NOT NULL DEFAULT 0,
                is_anonymous INTEGER      NOT NULL DEFAULT 0,
                page_context VARCHAR(64)  NOT NULL DEFAULT '',
                severity     VARCHAR(16)  NOT NULL DEFAULT 'normal',
                status       VARCHAR(16)  NOT NULL DEFAULT 'open',
                admin_note   TEXT         NOT NULL DEFAULT '',
                created_at   DATETIME     NOT NULL,
                updated_at   DATETIME     NOT NULL
            )
        """))
        conn.commit()

        # feedbacks テーブルに contact_email カラム追加（既存 DB 対応）
        try:
            conn.execute(text(
                "ALTER TABLE feedbacks ADD COLUMN contact_email VARCHAR(254)"
            ))
            conn.commit()
        except Exception:
            conn.rollback()

        # feedbacks テーブルに needs_reply / is_anonymous カラム追加（既存 DB 対応）
        for ddl in [
            "ALTER TABLE feedbacks ADD COLUMN needs_reply INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE feedbacks ADD COLUMN is_anonymous INTEGER NOT NULL DEFAULT 0",
        ]:
            try:
                conn.execute(text(ddl))
                conn.commit()
            except Exception:
                conn.rollback()
