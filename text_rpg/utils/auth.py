"""
utils/auth.py - 認証・セッション管理ヘルパー
"""

import streamlit as st
from sqlalchemy.orm import Session


def init_session_defaults() -> None:
    """セッション状態のデフォルト値を初期化する"""
    defaults: dict = {
        "user_id": None,
        "username": None,
        "party": [],
        "current_dungeon_id": 1,
        "current_floor": 1,
        "current_room": 0,
        "battle_enemies": [],
        "battle_log": [],
        "defending_chars": set(),
        "battle_result": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def check_login() -> None:
    """未ログインの場合はトップページに戻してページを停止する"""
    init_session_defaults()
    if not st.session_state.get("user_id"):
        st.warning("ログインが必要です。")
        st.page_link("app.py", label="ログイン画面へ")
        st.stop()


def get_current_user_id() -> int:
    return st.session_state["user_id"]


def login_user(db: Session, username: str, password: str) -> bool:
    """ログイン処理。成功時に session_state を設定して True を返す"""
    from models.user import User
    user = User.find_by_name(db, username)
    if user and user.verify_password(password):
        st.session_state["user_id"] = user.id
        st.session_state["username"] = user.name
        return True
    return False


def register_user(db: Session, username: str, password: str) -> tuple[bool, str]:
    """新規登録処理。(成功フラグ, メッセージ) を返す"""
    from models.user import User
    from sqlalchemy.exc import IntegrityError
    try:
        user = User.create(db, username, password)
        st.session_state["user_id"] = user.id
        st.session_state["username"] = user.name
        return True, "登録しました！"
    except IntegrityError:
        db.rollback()
        return False, "そのユーザー名はすでに使われています。"


def logout_user() -> None:
    """セッションをクリアしてログアウト"""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
