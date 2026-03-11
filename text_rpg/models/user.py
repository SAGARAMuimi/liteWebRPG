"""
models/user.py - User モデル
"""

from __future__ import annotations
from datetime import datetime
import bcrypt
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, Session
from models.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(128), nullable=False)
    gold: Mapped[int] = mapped_column(default=0, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # ──────────────────────────────────────────────────────
    @staticmethod
    def get_gold(db: Session, user_id: int) -> int:
        """現在の所持金を返す"""
        user = db.query(User).filter(User.id == user_id).first()
        return user.gold if user else 0

    @staticmethod
    def add_gold(db: Session, user_id: int, amount: int) -> int:
        """所持金を加算して新しい所持金を返す"""
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.gold = max(0, user.gold + amount)
            db.commit()
        return user.gold if user else 0

    @staticmethod
    def spend_gold(db: Session, user_id: int, amount: int) -> bool:
        """所持金を消費する。不足している場合は False を返す"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user or user.gold < amount:
            return False
        user.gold -= amount
        db.commit()
        return True

    @staticmethod
    def create(db: Session, name: str, password: str) -> "User":
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user = User(name=name, password=hashed)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def find_by_name(db: Session, name: str) -> "User | None":
        return db.query(User).filter(User.name == name).first()

    def verify_password(self, raw_password: str) -> bool:
        return bcrypt.checkpw(raw_password.encode(), self.password.encode())
