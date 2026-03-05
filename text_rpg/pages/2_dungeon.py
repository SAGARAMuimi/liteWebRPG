"""
pages/2_dungeon.py - ダンジョン探索画面
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import models  # noqa: F401 - 全テーブルを依存順に Base.metadata に登録
import streamlit as st
from models.database import SessionLocal
from models.dungeon import Dungeon, DungeonProgress
from models.character import PartyMember
from game.dungeon import DungeonManager
from utils.auth import check_login, get_current_user_id
from utils.helpers import hp_bar, class_display_name
from config import APP_TITLE, ROOMS_PER_FLOOR

st.set_page_config(page_title=f"ダンジョン探索 | {APP_TITLE}", page_icon="🏰", layout="wide")
check_login()

user_id = get_current_user_id()

# ─── パーティ確認 ────────────────────────────────────────────
if not st.session_state.get("party"):
    with SessionLocal() as db:
        party = PartyMember.get_party_characters(db, user_id)
    if not party:
        st.warning("パーティが未設定です。")
        st.page_link("pages/1_character.py", label="👤 キャラクター管理へ戻る")
        st.stop()
    st.session_state["party"] = party

party = st.session_state["party"]

# ─── session_state の初期化 ────────────────────────────────
if "current_room" not in st.session_state:
    st.session_state["current_room"] = 0
if "dungeon_log" not in st.session_state:
    st.session_state["dungeon_log"] = []
if "floor_cleared" not in st.session_state:
    st.session_state["floor_cleared"] = False
if "dungeon_cleared" not in st.session_state:
    st.session_state["dungeon_cleared"] = False

# ─── DB からダンジョン・進行状況を取得 ───────────────────────
dungeon_id = st.session_state.get("current_dungeon_id", 1)
with SessionLocal() as db:
    _d = Dungeon.get_by_id(db, dungeon_id)
    _p = DungeonProgress.get_or_create(db, user_id, dungeon_id)
    # セッションが閉じた後も使えるようスカラーで取り出す
    dungeon_name = _d.name
    dungeon_max_floor = _d.floor
    current_floor = _p.current_floor
    is_cleared = _p.is_cleared

# ─── タイトル ───────────────────────────────────────────────
st.title("🏰 ダンジョン探索")
st.subheader(f"📍 {dungeon_name}  {current_floor}F / {dungeon_max_floor}F")
st.divider()

# ─── 全クリア表示 ────────────────────────────────────────────
if is_cleared or st.session_state.get("dungeon_cleared"):
    st.balloons()
    st.success("🎉 ダンジョンをクリアしました！")
    if st.button("再挑戦する"):
        with SessionLocal() as db:
            _dungeon = Dungeon.get_by_id(db, dungeon_id)
            _progress = DungeonProgress.get_or_create(db, user_id, dungeon_id)
            mgr = DungeonManager(db, _dungeon, _progress)
            mgr.reset_progress()
        st.session_state["current_room"] = 0
        st.session_state["dungeon_log"] = []
        st.session_state["floor_cleared"] = False
        st.session_state["dungeon_cleared"] = False
        st.rerun()
    st.page_link("pages/1_character.py", label="👤 キャラクター管理へ戻る")
    st.stop()

# ─── パーティステータス ──────────────────────────────────────
st.subheader("🧑‍🤝‍🧑 パーティ")
cols = st.columns(len(party))
for i, chara in enumerate(party):
    with cols[i]:
        alive = chara.is_alive()
        status = "" if alive else " 💀"
        st.markdown(f"**{chara.name}{status}**")
        st.caption(class_display_name(chara.class_type))
        st.text(hp_bar(chara.hp, chara.max_hp))
        st.text(f"MP {chara.mp}/{chara.max_mp}  Lv{chara.level}")

st.divider()

# ─── 探索ログ ────────────────────────────────────────────────
room = st.session_state["current_room"]
st.subheader(f"🚪 現在の部屋: {room}/{ROOMS_PER_FLOOR}")

log_area = st.container()
with log_area:
    for line in st.session_state["dungeon_log"][-20:]:
        st.text(line)

st.divider()

# ─── アクションボタン ────────────────────────────────────────
all_dead = all(not c.is_alive() for c in party)
if all_dead:
    st.error("パーティが全滅しました…")
    if st.button("キャラクター管理へ戻る"):
        st.session_state["current_room"] = 0
        st.session_state["dungeon_log"] = []
        st.switch_page("pages/1_character.py")
    st.stop()

col1, col2 = st.columns(2)

with col1:
    if st.button("▶ 先に進む", use_container_width=True):
        room += 1
        st.session_state["current_room"] = room
        is_boss_room = room >= ROOMS_PER_FLOOR

        with SessionLocal() as db:
            _dungeon = Dungeon.get_by_id(db, dungeon_id)
            _progress = DungeonProgress.get_or_create(db, user_id, dungeon_id)
            mgr = DungeonManager(db, _dungeon, _progress)

            if is_boss_room:
                # ボス戦
                boss = mgr.get_boss()
                if boss:
                    st.session_state["battle_enemies"] = [boss]
                    st.session_state["battle_log"] = []
                    st.session_state["battle_result"] = None
                    st.session_state["dungeon_log"].append(f"⚠️ {boss.name} が現れた！ボス戦開始！")
                    st.switch_page("pages/3_battle.py")
                else:
                    st.session_state["dungeon_log"].append("ボスが見つかりませんでした（データ不備）")
            else:
                # 通常部屋
                st.session_state["dungeon_log"].append(f"🚪 {current_floor}F - 部屋{room} に入った。")
                if mgr.check_encounter():
                    enemies = mgr.get_random_enemies()
                    if enemies:
                        st.session_state["battle_enemies"] = enemies
                        st.session_state["battle_log"] = []
                        st.session_state["battle_result"] = None
                        names = "、".join(e.name for e in enemies)
                        st.session_state["dungeon_log"].append(f"⚔️ {names} が現れた！")
                        st.switch_page("pages/3_battle.py")
                    else:
                        st.session_state["dungeon_log"].append("何も起きなかった。")
                else:
                    st.session_state["dungeon_log"].append("静かだ…何も起きなかった。")

        st.rerun()

with col2:
    if st.button("🏃 撤退する", use_container_width=True):
        st.session_state["current_room"] = 0
        st.session_state["dungeon_log"] = []
        st.switch_page("pages/1_character.py")

# ─── 戦闘結果の反映 ─────────────────────────────────────────
result = st.session_state.get("battle_result")
if result == "win":
    st.session_state["battle_result"] = None
    # ボス部屋クリア後に次の階層へ
    if st.session_state["current_room"] >= ROOMS_PER_FLOOR:
        with SessionLocal() as db:
            _dungeon = Dungeon.get_by_id(db, dungeon_id)
            _progress = DungeonProgress.get_or_create(db, user_id, dungeon_id)
            mgr = DungeonManager(db, _dungeon, _progress)
            all_clear = mgr.advance_to_next_floor()
        st.session_state["current_room"] = 0
        if all_clear:
            st.session_state["dungeon_cleared"] = True
        else:
            new_floor = _progress.current_floor
            st.session_state["dungeon_log"].append(f"✨ {new_floor - 1}F をクリア！ {new_floor}F へ進む。")
        st.rerun()

elif result == "lose":
    st.session_state["battle_result"] = None
    st.error("全滅してしまいました…")
    st.session_state["current_room"] = 0
    st.session_state["dungeon_log"] = []
