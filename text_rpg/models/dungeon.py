"""
models/dungeon.py - Dungeon / DungeonProgress モデル
"""

from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, Session
from models.database import Base


class Dungeon(Base):
    __tablename__ = "dungeons"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    floor: Mapped[int] = mapped_column(nullable=False)  # 最大階層数
    map_type: Mapped[str] = mapped_column(String(16), default="linear", nullable=False)  # R-14: 'linear' or 'grid'

    @property
    def is_grid(self) -> bool:
        """グリッドマップ型ダンジョンかどうか（R-14）"""
        return self.map_type == "grid"

    @staticmethod
    def get_all(db: Session) -> list["Dungeon"]:
        return db.query(Dungeon).all()

    @staticmethod
    def get_by_id(db: Session, dungeon_id: int) -> "Dungeon | None":
        return db.query(Dungeon).filter(Dungeon.id == dungeon_id).first()


class DungeonProgress(Base):
    __tablename__ = "dungeon_progress"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    dungeon_id: Mapped[int] = mapped_column(ForeignKey("dungeons.id"), nullable=False)
    current_floor: Mapped[int] = mapped_column(default=1, nullable=False)
    current_x: Mapped[int] = mapped_column(default=-1, nullable=False)  # R-14: グリッド座標X（linear では -1）
    current_y: Mapped[int] = mapped_column(default=-1, nullable=False)  # R-14: グリッド座標Y（linear では -1）
    is_cleared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    @staticmethod
    def get_or_create(db: Session, user_id: int, dungeon_id: int) -> "DungeonProgress":
        prog = (
            db.query(DungeonProgress)
            .filter(
                DungeonProgress.user_id == user_id,
                DungeonProgress.dungeon_id == dungeon_id,
            )
            .first()
        )
        if prog is None:
            prog = DungeonProgress(user_id=user_id, dungeon_id=dungeon_id, current_floor=1)
            db.add(prog)
            db.commit()
            db.refresh(prog)
        return prog

    def save(self, db: Session) -> None:
        self.updated_at = datetime.utcnow()
        db.merge(self)
        db.commit()

    def set_position(self, x: int, y: int, db: Session) -> None:
        """グリッド座標をDBに保存する（R-14 grid ダンジョン専用）"""
        self.current_x = x
        self.current_y = y
        self.save(db)
