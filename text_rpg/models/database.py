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
