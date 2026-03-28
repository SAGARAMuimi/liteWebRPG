"""
models/item.py - アイテムマスタモデル
"""

from __future__ import annotations
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from models.database import Base


class Item(Base):
    __tablename__ = "items"

    id          : Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name        : Mapped[str] = mapped_column(String(64),  nullable=False)
    description : Mapped[str] = mapped_column(String(256), nullable=False, server_default="''")
    effect_type : Mapped[str] = mapped_column(String(16),  nullable=False)
    power       : Mapped[int] = mapped_column(nullable=False, default=0)
    target_type : Mapped[str] = mapped_column(String(16),  nullable=False, server_default="ally")
    duration    : Mapped[int] = mapped_column(nullable=False, server_default="0")
    price       : Mapped[int] = mapped_column(nullable=False, server_default="0")

    # ──────────────────────────────────────────────────────
    # クエリヘルパー
    # ──────────────────────────────────────────────────────
    @staticmethod
    def get_all(db) -> list["Item"]:
        """全アイテムを id 順で返す"""
        return db.query(Item).order_by(Item.id).all()

    @staticmethod
    def get_by_id(db, item_id: int) -> "Item | None":
        return db.query(Item).filter(Item.id == item_id).first()
