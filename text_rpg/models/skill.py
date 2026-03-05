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
    effect_type: Mapped[str] = mapped_column(String(16), nullable=False)  # attack / heal / buff

    @staticmethod
    def get_for_class(db: Session, class_type: str) -> list["Skill"]:
        return (
            db.query(Skill)
            .filter((Skill.class_type == class_type) | (Skill.class_type == "all"))
            .all()
        )
