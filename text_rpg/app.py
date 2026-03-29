"""
app.py - トップページ（ログイン・新規登録画面）
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from models.database import init_db, migrate_db, SessionLocal
from utils.auth import init_session_defaults, login_user, register_user, logout_user, get_auth_backend
from utils.helpers import seed_initial_data
from config import APP_TITLE, NOTICE_TEXT, NOTICE_LEVEL

# ─── 初期化 ──────────────────────────────────────────────
st.set_page_config(page_title=APP_TITLE, page_icon="⚔️", layout="centered")
init_db()
migrate_db()  # 既存 DB へのカラム追加・データ修正（山筊幹）
init_session_defaults()
auth_backend = get_auth_backend()

with SessionLocal() as db:
    seed_initial_data(db)

# ─── お知らせ（R-16） ────────────────────────────────────
# NOTICE_TEXT が設定されている場合のみ表示（ログイン前後どちらでも表示）
if NOTICE_TEXT:
    _notice_fn = {"warning": st.warning, "error": st.error}.get(NOTICE_LEVEL, st.info)
    _notice_fn(f"📢 {NOTICE_TEXT}")

# ─── ログイン済みの場合はキャラクター画面へ ─────────────────
if st.session_state.get("user_id"):
    st.success(f"ようこそ、{st.session_state['username']} さん！")
    st.page_link("pages/1_character.py", label="⚔️ キャラクター管理へ進む")
    if st.button("ログアウト"):
        logout_user()
        st.rerun()
    st.stop()

# ─── タイトル ───────────────────────────────────────────────
st.title(APP_TITLE)
st.caption("Python + Streamlit で作ったテキストRPG")
st.page_link("pages/6_privacy.py", label="🔒 プライバシー / 取扱い")
st.divider()

# ─── タブ切り替え ──────────────────────────────────────────
tab_login, tab_register = st.tabs(["ログイン", "新規登録"])

with tab_login:
    st.subheader("ログイン")
    with st.form("login_form"):
        if auth_backend == "neon":
            username = st.text_input("メールアドレス")
        else:
            username = st.text_input("ユーザー名")
        password = st.text_input("パスワード", type="password")
        submitted = st.form_submit_button("ログイン")

    if submitted:
        if not username or not password:
            st.warning("ユーザー名とパスワードを入力してください。")
        else:
            with SessionLocal() as db:
                ok = login_user(db, username, password)
            if ok:
                st.success("ログインしました！")
                st.rerun()
            else:
                st.error("ユーザー名またはパスワードが違います。")
                # Neon Auth バックエンドのエラー詳細（デバッグ用）
                _neon_err = st.session_state.pop("_neon_login_error", None)
                if _neon_err:
                    st.caption(f"🔍 詳細: {_neon_err}")

with tab_register:
    st.subheader("新規登録")
    with st.form("register_form"):
        if auth_backend == "neon":
            new_display_name = st.text_input("表示名")
            new_email = st.text_input("メールアドレス")
            new_username = new_display_name
        else:
            new_email = None
            new_username = st.text_input("ユーザー名")
        new_password = st.text_input("パスワード", type="password")
        new_password2 = st.text_input("パスワード（確認）", type="password")
        reg_submitted = st.form_submit_button("登録")

    if reg_submitted:
        if auth_backend == "neon":
            missing = not new_username or not new_email or not new_password
            missing_msg = "表示名・メールアドレス・パスワードを入力してください。"
        else:
            missing = not new_username or not new_password
            missing_msg = "ユーザー名とパスワードを入力してください。"

        if missing:
            st.warning(missing_msg)
        elif new_password != new_password2:
            st.warning("パスワードが一致しません。")
        else:
            with SessionLocal() as db:
                ok, msg = register_user(db, new_username, new_password, email=new_email)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
