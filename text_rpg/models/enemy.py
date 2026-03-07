"""
models/enemy.py - Enemy モデル
"""

from __future__ import annotations
from sqlalchemy import String, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, Session
from models.database import Base


class Enemy(Base):
    __tablename__ = "enemies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    dungeon_id: Mapped[int] = mapped_column(ForeignKey("dungeons.id"), nullable=False)
    floor: Mapped[int] = mapped_column(nullable=False)
    hp: Mapped[int] = mapped_column(nullable=False)
    attack: Mapped[int] = mapped_column(nullable=False)
    defense: Mapped[int] = mapped_column(nullable=False)
    exp_reward: Mapped[int] = mapped_column(nullable=False)
    is_boss: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # スタンなど状態異常耐性（カンマ区切り。例: "stun" / "stun,silence"）
    status_resistance: Mapped[str] = mapped_column(String(64), nullable=False, server_default="")

    # ──────────────────────────────────────────────────────
    @staticmethod
    def get_by_floor(db: Session, dungeon_id: int, floor: int, boss: bool = False) -> list["Enemy"]:
        return (
            db.query(Enemy)
            .filter(
                Enemy.dungeon_id == dungeon_id,
                Enemy.floor == floor,
                Enemy.is_boss == boss,
            )
            .all()
        )

    def is_alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, amount: int) -> int:
        actual = max(1, amount)
        self.hp = max(0, self.hp - actual)
        return actual

    def clone(self) -> "Enemy":
        """戦闘用に現在のインスタンスをコピー（DB 非依存）"""
        e = Enemy(
            id=self.id,
            name=self.name,
            dungeon_id=self.dungeon_id,
            floor=self.floor,
            hp=self.hp,
            attack=self.attack,
            defense=self.defense,
            exp_reward=self.exp_reward,
            is_boss=self.is_boss,
            status_resistance=self.status_resistance or "",
        )
        return e
