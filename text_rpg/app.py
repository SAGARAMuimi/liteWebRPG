"""
app.py - トップページ（ログイン・新規登録画面）
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from models.database import init_db, SessionLocal
from utils.auth import init_session_defaults, login_user, register_user, logout_user
from utils.helpers import seed_initial_data
from config import APP_TITLE

# ─── 初期化 ────────────────────────────────────────────────
st.set_page_config(page_title=APP_TITLE, page_icon="⚔️", layout="centered")
init_db()
init_session_defaults()

with SessionLocal() as db:
    seed_initial_data(db)

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
st.divider()

# ─── タブ切り替え ──────────────────────────────────────────
tab_login, tab_register = st.tabs(["ログイン", "新規登録"])

with tab_login:
    st.subheader("ログイン")
    with st.form("login_form"):
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

with tab_register:
    st.subheader("新規登録")
    with st.form("register_form"):
        new_username = st.text_input("ユーザー名")
        new_password = st.text_input("パスワード", type="password")
        new_password2 = st.text_input("パスワード（確認）", type="password")
        reg_submitted = st.form_submit_button("登録")

    if reg_submitted:
        if not new_username or not new_password:
            st.warning("ユーザー名とパスワードを入力してください。")
        elif new_password != new_password2:
            st.warning("パスワードが一致しません。")
        else:
            with SessionLocal() as db:
                ok, msg = register_user(db, new_username, new_password)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
