"""
models/equipment.py - 装備マスタ / キャラクター装備スロット管理

スロット種別:
  weapon    : 武器（ATK ボーナス中心）
  armor     : 防具（DEF + HP ボーナス中心）
  accessory : アクセサリ（HP / MP / ATK 各種ボーナス）

ボーナスはキャラクターの基礎ステータスに直接加算・減算して管理する。
（Character.equip() / unequip() で DB 保存まで行う）
"""

from __future__ import annotations
from sqlalchemy import String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, Session
from models.database import Base


class Equipment(Base):
    __tablename__ = "equipments"

    id             : Mapped[int]  = mapped_column(primary_key=True, autoincrement=True)
    name           : Mapped[str]  = mapped_column(String(64),  nullable=False)
    description    : Mapped[str]  = mapped_column(String(256), nullable=False, server_default="")
    slot           : Mapped[str]  = mapped_column(String(16),  nullable=False)  # weapon / armor / accessory
    atk_bonus      : Mapped[int]  = mapped_column(nullable=False, default=0, server_default="0")
    def_bonus      : Mapped[int]  = mapped_column(nullable=False, default=0, server_default="0")
    hp_bonus       : Mapped[int]  = mapped_column(nullable=False, default=0, server_default="0")
    mp_bonus       : Mapped[int]  = mapped_column(nullable=False, default=0, server_default="0")
    price          : Mapped[int]  = mapped_column(nullable=False, default=0,  server_default="0")
    required_class : Mapped[str]  = mapped_column(String(128), nullable=False, server_default="")
    disposable     : Mapped[bool] = mapped_column(nullable=False, default=False, server_default="0")
    # required_class: カンマ区切りの class_type。空 = 全クラス装備可
    # disposable: True = 外すと消える消耗品装備 / False = 外すとキャラインベントリに戻る

    # ──────────────────────────────────────────────────────
    @staticmethod
    def get_all(db: Session) -> list["Equipment"]:
        """全装備をスロット順・ID 順で返す"""
        return db.query(Equipment).order_by(Equipment.slot, Equipment.id).all()

    @staticmethod
    def get_by_id(db: Session, equip_id: int) -> "Equipment | None":
        return db.query(Equipment).filter(Equipment.id == equip_id).first()

    def can_equip(self, class_type: str) -> bool:
        """指定クラスが装備できるか判定（required_class 空 = 全クラス可）"""
        if not self.required_class:
            return True
        return class_type in self.required_class.split(",")

    def bonus_summary(self) -> str:
        """ボーナスを "ATK+3 / HP+10" 形式の文字列で返す"""
        parts = []
        if self.atk_bonus: parts.append(f"ATK+{self.atk_bonus}")
        if self.def_bonus: parts.append(f"DEF+{self.def_bonus}")
        if self.hp_bonus:  parts.append(f"HP+{self.hp_bonus}")
        if self.mp_bonus:  parts.append(f"MP+{self.mp_bonus}")
        summary = " / ".join(parts) if parts else "—"
        if self.disposable:
            summary += "  🔥消耗品"
        return summary


class CharacterEquipment(Base):
    __tablename__ = "character_equipments"

    id           : Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    character_id : Mapped[int] = mapped_column(ForeignKey("characters.id"), nullable=False)
    equipment_id : Mapped[int] = mapped_column(ForeignKey("equipments.id"), nullable=False)
    slot         : Mapped[str] = mapped_column(String(16), nullable=False)

    __table_args__ = (UniqueConstraint("character_id", "slot"),)

    # ──────────────────────────────────────────────────────
    @staticmethod
    def get_for_character(db: Session, character_id: int) -> list["CharacterEquipment"]:
        """キャラクターの全装備スロット一覧を返す"""
        return (
            db.query(CharacterEquipment)
            .filter(CharacterEquipment.character_id == character_id)
            .all()
        )

    @staticmethod
    def get_by_slot(db: Session, character_id: int, slot: str) -> "CharacterEquipment | None":
        return (
            db.query(CharacterEquipment)
            .filter(
                CharacterEquipment.character_id == character_id,
                CharacterEquipment.slot == slot,
            )
            .first()
        )


class CharacterInventory(Base):
    """
    キャラクターの装備インベントリ。
    装備を外した（disposable=False）際の戻り先テーブル。
    同一キャラ・同一装備IDで quantity を積み上げる。
    """
    __tablename__ = "character_inventories"

    id           : Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    character_id : Mapped[int] = mapped_column(ForeignKey("characters.id"), nullable=False)
    equipment_id : Mapped[int] = mapped_column(ForeignKey("equipments.id"), nullable=False)
    quantity     : Mapped[int] = mapped_column(nullable=False, default=1, server_default="1")

    __table_args__ = (UniqueConstraint("character_id", "equipment_id"),)

    # ──────────────────────────────────────────────────────
    @staticmethod
    def get_for_character(db: Session, character_id: int) -> list["CharacterInventory"]:
        """キャラクターのインベントリ一覧を数量降順で返す"""
        return (
            db.query(CharacterInventory)
            .filter(CharacterInventory.character_id == character_id)
            .order_by(CharacterInventory.equipment_id)
            .all()
        )

    @staticmethod
    def add(db: Session, character_id: int, equipment_id: int, qty: int = 1) -> None:
        """インベントリに装備を追加（既存なら quantity を加算）"""
        row = (
            db.query(CharacterInventory)
            .filter(
                CharacterInventory.character_id == character_id,
                CharacterInventory.equipment_id == equipment_id,
            )
            .first()
        )
        if row:
            row.quantity += qty
        else:
            db.add(CharacterInventory(
                character_id=character_id,
                equipment_id=equipment_id,
                quantity=qty,
            ))
        db.commit()

    @staticmethod
    def consume(db: Session, character_id: int, equipment_id: int, qty: int = 1) -> bool:
        """
        インベントリから装備を1個消費する。
        quantity が 0 以下になればレコードを削除。
        Returns: 成功したか
        """
        row = (
            db.query(CharacterInventory)
            .filter(
                CharacterInventory.character_id == character_id,
                CharacterInventory.equipment_id == equipment_id,
            )
            .first()
        )
        if not row or row.quantity < qty:
            return False
        row.quantity -= qty
        if row.quantity <= 0:
            db.delete(row)
        db.commit()
        return True
