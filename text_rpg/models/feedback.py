"""
models/feedback.py - 不具合報告・改善要望モデル
"""
from __future__ import annotations
from datetime import datetime, timedelta
from sqlalchemy import String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from models.database import Base


class Feedback(Base):
    """フィードバック（不具合報告・改善要望）テーブル"""
    __tablename__ = "feedbacks"

    id          : Mapped[int]       = mapped_column(primary_key=True, autoincrement=True)
    user_id     : Mapped[int | None] = mapped_column(nullable=True)
    category    : Mapped[str]       = mapped_column(String(16),  nullable=False)
    title       : Mapped[str]       = mapped_column(String(128), nullable=False)
    body        : Mapped[str]       = mapped_column(Text,        nullable=False)
    page_context: Mapped[str]       = mapped_column(String(64),  nullable=False, server_default="''")
    severity    : Mapped[str]       = mapped_column(String(16),  nullable=False, server_default="'normal'")
    status      : Mapped[str]       = mapped_column(String(16),  nullable=False, server_default="'open'")
    admin_note  : Mapped[str]       = mapped_column(Text,        nullable=False, server_default="''")
    created_at  : Mapped[datetime]  = mapped_column(DateTime,    nullable=False)
    updated_at  : Mapped[datetime]  = mapped_column(DateTime,    nullable=False)

    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def create(
        db,
        category: str,
        title: str,
        body: str,
        *,
        user_id: int | None = None,
        page_context: str = "",
        severity: str = "normal",
    ) -> "Feedback":
        """フィードバックを作成して返す。body が上限超えの場合 ValueError を送出する。"""
        from config import FEEDBACK_MAX_BODY_LENGTH
        if len(body) > FEEDBACK_MAX_BODY_LENGTH:
            raise ValueError(f"body は {FEEDBACK_MAX_BODY_LENGTH} 文字以内にしてください")
        now = datetime.utcnow()
        fb = Feedback(
            user_id=user_id,
            category=category,
            title=title.strip(),
            body=body.strip(),
            page_context=page_context,
            severity=severity if category == "bug" else "normal",
            status="open",
            admin_note="",
            created_at=now,
            updated_at=now,
        )
        db.add(fb)
        db.commit()
        db.refresh(fb)
        return fb

    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def get_all(
        db,
        *,
        category: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list["Feedback"]:
        """条件でフィルタしたフィードバック一覧を返す（新着順）。"""
        q = db.query(Feedback)
        if category:   q = q.filter(Feedback.category  == category)
        if status:     q = q.filter(Feedback.status     == status)
        if severity:   q = q.filter(Feedback.severity   == severity)
        if date_from:  q = q.filter(Feedback.created_at >= date_from)
        if date_to:    q = q.filter(Feedback.created_at <= date_to)
        return q.order_by(Feedback.created_at.desc()).limit(limit).offset(offset).all()

    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def count_all(db, *, category: str | None = None, status: str | None = None) -> int:
        """条件でフィルタした件数を返す。"""
        q = db.query(Feedback)
        if category: q = q.filter(Feedback.category == category)
        if status:   q = q.filter(Feedback.status   == status)
        return q.count()

    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def get_by_id(db, feedback_id: int) -> "Feedback | None":
        """IDでフィードバックを取得する。存在しない場合は None を返す。"""
        return db.query(Feedback).filter(Feedback.id == feedback_id).first()

    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def update_status(db, feedback_id: int, status: str, admin_note: str = "") -> bool:
        """ステータスと管理者メモを更新する。成功時 True、対象なし False を返す。"""
        fb = db.query(Feedback).filter(Feedback.id == feedback_id).first()
        if not fb:
            return False
        fb.status = status
        if admin_note:
            fb.admin_note = admin_note
        fb.updated_at = datetime.utcnow()
        db.commit()
        return True

    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def count_recent_by_user(
        db, user_id: int, minutes: int = 5, title: str | None = None
    ) -> int:
        """指定分以内に同ユーザーが投稿した件数を返す（重複チェック用）。"""
        threshold = datetime.utcnow() - timedelta(minutes=minutes)
        q = db.query(Feedback).filter(
            Feedback.user_id == user_id,
            Feedback.created_at >= threshold,
        )
        if title:
            q = q.filter(Feedback.title == title.strip())
        return q.count()

    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def count_today_by_user(db, user_id: int) -> int:
        """今日（UTC）にユーザーが投稿した件数を返す（1日上限チェック用）。"""
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return (
            db.query(Feedback)
            .filter(Feedback.user_id == user_id, Feedback.created_at >= today)
            .count()
        )
