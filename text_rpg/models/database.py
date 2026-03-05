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
