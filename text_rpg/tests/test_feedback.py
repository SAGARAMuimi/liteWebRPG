"""
tests/test_feedback.py - Feedback モデルの単体テスト
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.database import Base
from models.feedback import Feedback


# ── テスト用インメモリ DB セットアップ ────────────────────────────────
@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


# ─────────────────────────────────────────────────────────────────────────────
class TestFeedbackModel:
    """Feedback モデルの単体テスト"""

    def test_create_feedback_logged_in(self, db):
        """ログイン済みユーザーが送信した場合、user_id が正しく保存される"""
        fb = Feedback.create(
            db,
            category="bug",
            title="テスト不具合",
            body="再現手順: 〇〇すると落ちる",
            user_id=42,
            page_context="3_battle",
            severity="high",
        )
        assert fb.id is not None
        assert fb.user_id == 42
        assert fb.category == "bug"
        assert fb.severity == "high"
        assert fb.status == "open"
        assert fb.page_context == "3_battle"

    def test_create_feedback_body_max_length_validation(self, db):
        """body が FEEDBACK_MAX_BODY_LENGTH（2000）を超えた場合 ValueError が送出される"""
        from config import FEEDBACK_MAX_BODY_LENGTH
        long_body = "あ" * (FEEDBACK_MAX_BODY_LENGTH + 1)
        with pytest.raises(ValueError):
            Feedback.create(
                db,
                category="request",
                title="長文テスト",
                body=long_body,
                user_id=1,
            )

    def test_get_all_filter_by_category(self, db):
        """category フィルタが正しく動作する"""
        Feedback.create(db, category="bug",     title="バグ1",  body="内容1", user_id=1)
        Feedback.create(db, category="request", title="要望1",  body="内容2", user_id=2)
        Feedback.create(db, category="bug",     title="バグ2",  body="内容3", user_id=1)

        bugs = Feedback.get_all(db, category="bug")
        requests = Feedback.get_all(db, category="request")

        assert len(bugs) == 2
        assert all(f.category == "bug" for f in bugs)
        assert len(requests) == 1
        assert requests[0].category == "request"

    def test_get_all_filter_by_status(self, db):
        """status フィルタが正しく動作する"""
        fb1 = Feedback.create(db, category="bug", title="B1", body="x", user_id=1)
        fb2 = Feedback.create(db, category="bug", title="B2", body="y", user_id=2)
        Feedback.update_status(db, fb1.id, "resolved")

        open_list     = Feedback.get_all(db, status="open")
        resolved_list = Feedback.get_all(db, status="resolved")

        assert len(open_list) == 1
        assert open_list[0].id == fb2.id
        assert len(resolved_list) == 1
        assert resolved_list[0].id == fb1.id

    def test_update_status_and_admin_note(self, db):
        """update_status でステータスと admin_note が保存される"""
        fb = Feedback.create(db, category="bug", title="テスト", body="内容", user_id=5)
        result = Feedback.update_status(db, fb.id, "in_progress", admin_note="確認中です")

        assert result is True
        updated = Feedback.get_by_id(db, fb.id)
        assert updated.status == "in_progress"
        assert updated.admin_note == "確認中です"

    def test_count_recent_blocks_duplicate(self, db):
        """FEEDBACK_DUPLICATE_MINUTES 以内に同一タイトルで投稿済みの場合、カウント > 0 となる"""
        from config import FEEDBACK_DUPLICATE_MINUTES
        title = "同じタイトル"
        Feedback.create(db, category="other", title=title, body="内容", user_id=10)

        count = Feedback.count_recent_by_user(
            db, user_id=10, minutes=FEEDBACK_DUPLICATE_MINUTES, title=title
        )
        assert count > 0

    def test_count_today_by_user(self, db):
        """当日の投稿件数が正しくカウントされる"""
        Feedback.create(db, category="request", title="要望A", body="内容A", user_id=7)
        Feedback.create(db, category="request", title="要望B", body="内容B", user_id=7)
        Feedback.create(db, category="request", title="要望C", body="内容C", user_id=99)  # 別ユーザー

        count_7  = Feedback.count_today_by_user(db, user_id=7)
        count_99 = Feedback.count_today_by_user(db, user_id=99)

        assert count_7  == 2
        assert count_99 == 1
