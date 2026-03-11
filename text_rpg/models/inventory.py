"""
models/inventory.py - ユーザーごとのアイテム所持管理
"""

from __future__ import annotations
from sqlalchemy import UniqueConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from models.database import Base


class Inventory(Base):
    __tablename__ = "inventories"

    id       : Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id  : Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    item_id  : Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    quantity : Mapped[int] = mapped_column(nullable=False, default=0)

    __table_args__ = (UniqueConstraint("user_id", "item_id"),)

    # ──────────────────────────────────────────────────────
    # クエリヘルパー
    # ──────────────────────────────────────────────────────
    @staticmethod
    def get_by_user(db, user_id: int) -> list["Inventory"]:
        """user_id のインベントリ（全件）を item_id 昇順で返す"""
        return (
            db.query(Inventory)
            .filter(Inventory.user_id == user_id)
            .order_by(Inventory.item_id)
            .all()
        )

    @staticmethod
    def add_item(db, user_id: int, item_id: int, quantity: int = 1) -> None:
        """アイテムを付与（既存なら quantity 加算、なければ INSERT）"""
        row = (
            db.query(Inventory)
            .filter(Inventory.user_id == user_id, Inventory.item_id == item_id)
            .first()
        )
        if row:
            row.quantity += quantity
        else:
            db.add(Inventory(user_id=user_id, item_id=item_id, quantity=quantity))
        db.commit()

    @staticmethod
    def use_item(db, user_id: int, item_id: int) -> bool:
        """
        アイテムを1個消費する。
        quantity > 0 なら -1 して True を返す。
        在庫なし・レコードなしの場合は False を返す。
        """
        row = (
            db.query(Inventory)
            .filter(Inventory.user_id == user_id, Inventory.item_id == item_id)
            .first()
        )
        if row and row.quantity > 0:
            row.quantity -= 1
            db.commit()
            return True
        return False
