"""
models/user.py - User モデル
"""

from __future__ import annotations
import json
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
    # ── R-15 メタ進行 ──────────────────────────────────────────
    meta_gold: Mapped[int] = mapped_column(default=0, nullable=False, server_default="0")
    meta_titles: Mapped[str] = mapped_column(
        String(512), default="", nullable=False, server_default="''"
    )
    meta_upgrade_ranks: Mapped[str] = mapped_column(
        String(512), default="{}", nullable=False, server_default="'{}'"
    )
    # ── FEEDBACK 不具合報告・改善要望 ──────────────────────
    is_admin: Mapped[int] = mapped_column(
        default=0, nullable=False, server_default="0"
    )
    # ── R-28 バトルスピード設定 ──────────────────────────────
    battle_speed: Mapped[str] = mapped_column(
        String(8), default="normal", nullable=False, server_default="'normal'"
    )

    # ──────────────────────────────────────────────────────
    def get_titles_list(self) -> list[str]:
        """獲得済み称号キーのリストを返す"""
        if not self.meta_titles:
            return []
        return [t for t in self.meta_titles.split(",") if t]

    def get_upgrade_ranks(self) -> dict[str, int]:
        """メタアップグレードのランク辞書を返す"""
        try:
            return json.loads(self.meta_upgrade_ranks or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}

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

    # ── R-15 メタ進行 ──────────────────────────────────────────
    @staticmethod
    def add_meta_gold(db: Session, user_id: int, amount: int) -> int:
        """メタGOLDを加算して新しいメタGOLD残高を返す"""
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.meta_gold = max(0, user.meta_gold + amount)
            db.commit()
        return user.meta_gold if user else 0

    @staticmethod
    def add_meta_title(db: Session, user_id: int, title_key: str) -> bool:
        """称号を追加する。初めて取得した場合 True を返す"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        titles = user.get_titles_list()
        if title_key in titles:
            return False
        titles.append(title_key)
        user.meta_titles = ",".join(titles)
        db.commit()
        return True

    @staticmethod
    def upgrade_meta(db: Session, user_id: int, upgrade_key: str) -> bool:
        """
        メタアップグレードを1ランク上げる（メタGOLDを消費）。
        成功したら True を返す。
        """
        from config import META_UPGRADES
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        upgrade_def = META_UPGRADES.get(upgrade_key)
        if not upgrade_def:
            return False
        ranks = user.get_upgrade_ranks()
        current_rank = ranks.get(upgrade_key, 0)
        max_rank = len(upgrade_def["costs"])
        if current_rank >= max_rank:
            return False  # 上限
        cost = upgrade_def["costs"][current_rank]
        if user.meta_gold < cost:
            return False  # メタGOLD不足
        user.meta_gold -= cost
        ranks[upgrade_key] = current_rank + 1
        user.meta_upgrade_ranks = json.dumps(ranks)
        db.commit()
        return True

    @staticmethod
    def get_meta_bonus(db: Session, user_id: int, upgrade_key: str) -> int:
        """現在のメタアップグレードのボーナス値を返す（未取得は 0）"""
        from config import META_UPGRADES
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return 0
        upgrade_def = META_UPGRADES.get(upgrade_key)
        if not upgrade_def:
            return 0
        rank = user.get_upgrade_ranks().get(upgrade_key, 0)
        if rank == 0:
            return 0
        return upgrade_def["bonuses"][rank - 1]

    # ── R-28 バトルスピード ──────────────────────────────────
    @staticmethod
    def get_battle_speed(db: Session, user_id: int) -> str:
        """ユーザーのバトルスピード設定を返す（未設定時は 'normal'）"""
        user = db.query(User).filter(User.id == user_id).first()
        return (user.battle_speed or "normal") if user else "normal"

    @staticmethod
    def set_battle_speed(db: Session, user_id: int, speed: str) -> None:
        """バトルスピード設定を保存する"""
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.battle_speed = speed
            db.commit()

    # ──────────────────────────────────────────────────────
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
