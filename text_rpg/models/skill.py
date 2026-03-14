"""
models/skill.py - Skill モデル
"""

from __future__ import annotations
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, Session
from models.database import Base


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    class_type: Mapped[str] = mapped_column(String(16), nullable=False)  # "all" で全クラス
    mp_cost: Mapped[int] = mapped_column(nullable=False)
    power: Mapped[int] = mapped_column(nullable=False)
    effect_type: Mapped[str] = mapped_column(String(16), nullable=False)
    # effect_type: attack / heal / buff_atk / buff_def / debuff_atk / debuff_def
    target_type: Mapped[str] = mapped_column(String(16), nullable=False, server_default="self")
    # target_type: self / ally / all_allies / enemy / all_enemies
    duration: Mapped[int] = mapped_column(nullable=False, server_default="0")
    # duration: バフ/デバフの持続ターン数（0 = 持続なし）
    cooldown: Mapped[int] = mapped_column(nullable=False, server_default="0")
    # cooldown: スキル使用後に再使用できるまでのターン数（0 = クールダウンなし）

    @staticmethod
    def get_for_class(db: Session, class_type: str) -> list["Skill"]:
        return (
            db.query(Skill)
            .filter((Skill.class_type == class_type) | (Skill.class_type == "all"))
            .all()
        )
