"""
pages/1_character.py - キャラクター管理・パーティ編成画面
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import models  # noqa: F401 - 全テーブルを依存順に Base.metadata に登録
import streamlit as st
from models.database import SessionLocal
from models.character import Character, PartyMember
from utils.auth import check_login, get_current_user_id
from utils.helpers import class_display_name, hp_bar
from config import CLASS_INITIAL_STATS, PARTY_SIZE, APP_TITLE

st.set_page_config(page_title=f"キャラクター管理 | {APP_TITLE}", page_icon="👤", layout="wide")
check_login()

user_id = get_current_user_id()

st.title("👤 キャラクター管理")
st.caption(f"ログイン中: {st.session_state['username']}")
st.divider()

# ─── キャラクター一覧 ────────────────────────────────────────
with SessionLocal() as db:
    characters = Character.get_by_user(db, user_id)

st.subheader("登録済みキャラクター")
if not characters:
    st.info("キャラクターがまだいません。下のフォームで作成してください。")
else:
    cols = st.columns(len(characters) if len(characters) <= 4 else 4)
    for i, chara in enumerate(characters):
        with cols[i % 4]:
            st.markdown(f"**{chara.name}** ({class_display_name(chara.class_type)})")
            st.text(f"Lv {chara.level}  EXP {chara.exp}/{chara.level * 50}")
            st.text(hp_bar(chara.hp, chara.max_hp))
            st.text(f"MP: {chara.mp}/{chara.max_mp}")
            st.text(f"ATK {chara.attack}  DEF {chara.defense}")

st.divider()

# ─── キャラクター作成 ────────────────────────────────────────
st.subheader("キャラクター作成")

# 作成成功メッセージを rerun 後に表示（session_state 経由）
if st.session_state.get("char_created_name"):
    st.success(f"「{st.session_state.pop('char_created_name')}」を作成しました！")

# フォームのキーをカウンターで変化させることで、作成後に入力欄をクリアする
if "char_form_counter" not in st.session_state:
    st.session_state["char_form_counter"] = 0

with st.form(f"create_char_form_{st.session_state['char_form_counter']}"):
    char_name = st.text_input("キャラクター名")
    class_options = {class_display_name(k): k for k in CLASS_INITIAL_STATS.keys()}
    class_label = st.selectbox("クラス", list(class_options.keys()))
    create_btn = st.form_submit_button("作成")

if create_btn:
    if not char_name.strip():
        st.warning("キャラクター名を入力してください。")
    elif len(characters) >= 8:
        st.warning("キャラクターは最大8名まで登録できます。")
    else:
        class_type = class_options[class_label]
        with SessionLocal() as db:
            from sqlalchemy.exc import IntegrityError
            try:
                Character.create(db, user_id, char_name.strip(), class_type)
                st.session_state["char_created_name"] = char_name.strip()
                st.session_state["char_form_counter"] += 1  # フォームをリセット
                st.rerun()
            except Exception as e:
                st.error(f"作成に失敗しました: {e}")

st.divider()

# ─── パーティ編成 ────────────────────────────────────────────
st.subheader(f"パーティ編成（{PARTY_SIZE}名を選択）")

if not characters:
    st.info("まずキャラクターを作成してください。")
else:
    # 同名キャラクターに対応するため「名前（クラス）」形式の表示名を生成
    char_display_map: dict[str, int] = {}
    seen_labels: dict[str, int] = {}
    for c in characters:
        base = f"{c.name}（{class_display_name(c.class_type)}）"
        if base in seen_labels:
            seen_labels[base] += 1
            label = f"{base}#{seen_labels[base]}"
        else:
            seen_labels[base] = 1
            label = base
        char_display_map[label] = c.id

    # ID から表示名への逆引きマップ
    id_to_display: dict[int, str] = {v: k for k, v in char_display_map.items()}
    char_options = ["（未選択）"] + list(char_display_map.keys())

    # 現在のパーティ情報を取得
    with SessionLocal() as db:
        current_party = PartyMember.get_party_characters(db, user_id)
    current_ids = [c.id for c in current_party]

    slot_selections: dict[int, int | None] = {}
    cols = st.columns(PARTY_SIZE)
    for slot in range(1, PARTY_SIZE + 1):
        with cols[slot - 1]:
            default_display = ""
            if len(current_ids) >= slot:
                default_display = id_to_display.get(current_ids[slot - 1], "")
            default_idx = char_options.index(default_display) if default_display in char_options else 0
            selected = st.selectbox(f"スロット {slot}", char_options, index=default_idx, key=f"slot_{slot}")
            slot_selections[slot] = char_display_map.get(selected)

    if st.button("パーティを確定する"):
        chosen = [v for v in slot_selections.values() if v is not None]
        if len(chosen) < PARTY_SIZE:
            st.warning(f"{PARTY_SIZE}名全員を選択してください。")
        elif len(set(chosen)) < PARTY_SIZE:
            st.warning("同じキャラクターを複数スロットに設定できません。")
        else:
            slot_char_map = {k: v for k, v in slot_selections.items() if v is not None}
            with SessionLocal() as db:
                PartyMember.set_party(db, user_id, slot_char_map)
                party_chars = PartyMember.get_party_characters(db, user_id)
            st.session_state["party"] = party_chars
            st.success("パーティを確定しました！")
            st.rerun()

# ─── ダンジョン探索開始ボタン ────────────────────────────────
st.divider()
party_ready = len(st.session_state.get("party", [])) == PARTY_SIZE
st.page_link(
    "pages/2_dungeon.py",
    label="🏰 ダンジョン探索へ進む",
    disabled=not party_ready,
)
if not party_ready:
    st.caption("パーティを4名確定してから探索できます。")
