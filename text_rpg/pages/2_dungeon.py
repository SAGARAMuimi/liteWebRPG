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
from models.item import Item
from models.inventory import Inventory
from models.user import User
from game.dungeon import DungeonManager
from utils.auth import check_login, get_current_user_id
from utils.helpers import hp_bar, class_display_name
from config import APP_TITLE, ROOMS_PER_FLOOR, DIFFICULTY_PRESETS

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
# 商人マスの在庫を session_state に保持（再レンダリングで消えないよう）
if "merchant_stock" not in st.session_state:
    st.session_state["merchant_stock"] = []
if "show_merchant" not in st.session_state:
    st.session_state["show_merchant"] = False

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
with SessionLocal() as db:
    current_gold = User.get_gold(db, user_id)
st.title("🏰 ダンジョン探索")
col_title, col_gold = st.columns([5, 1])
with col_title:
    st.subheader(f"📍 {dungeon_name}  {current_floor}F / {dungeon_max_floor}F")
with col_gold:
    st.metric("💰 GOLD", f"{current_gold} G")

# ─── 難易度選択 ──────────────────────────────────────────────
diff_keys   = list(DIFFICULTY_PRESETS.keys())
diff_labels = [DIFFICULTY_PRESETS[k]["label"] for k in diff_keys]
current_diff = st.session_state.get("difficulty", "normal")
current_diff_idx = diff_keys.index(current_diff) if current_diff in diff_keys else 1

in_dungeon = st.session_state.get("current_room", 0) > 0
if in_dungeon:
    st.caption(f"難易度: {DIFFICULTY_PRESETS[current_diff]['label']}  （探索中は変更不可）")
else:
    selected_label = st.selectbox(
        "難易度",
        diff_labels,
        index=current_diff_idx,
        key="difficulty_select",
    )
    new_diff = diff_keys[diff_labels.index(selected_label)]
    if new_diff != current_diff:
        st.session_state["difficulty"] = new_diff
        st.rerun()

diff_cfg = DIFFICULTY_PRESETS[st.session_state.get("difficulty", "normal")]

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
        st.session_state["merchant_stock"] = []
        st.session_state["show_merchant"] = False
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
        st.session_state["show_merchant"] = False
        st.session_state["merchant_stock"] = []
        st.session_state["dungeon_log"].append(f"🚪 {current_floor}F - 部屋{room} に入った。")

        with SessionLocal() as db:
            _dungeon  = Dungeon.get_by_id(db, dungeon_id)
            _progress = DungeonProgress.get_or_create(db, user_id, dungeon_id)
            mgr = DungeonManager(db, _dungeon, _progress)

            result = mgr.resolve_event(
                party,
                room,
                hp_mult=diff_cfg["enemy_hp_mult"],
                atk_mult=diff_cfg["enemy_atk_mult"],
            )

            for msg in result.messages:
                st.session_state["dungeon_log"].append(msg)

            if result.need_battle:
                # 戦闘画面へ遷移
                st.session_state["battle_enemies"] = result.enemies
                st.session_state["battle_log"]     = []
                st.session_state["battle_result"]  = None
                st.session_state["battle_inventory"] = []
                st.switch_page("pages/3_battle.py")

            elif result.event_type in ("trap", "rest", "shrine"):
                # HP/MP が変化しているので DB に保存
                for chara in party:
                    chara.save(db)

            elif result.event_type == "merchant":
                st.session_state["merchant_stock"] = result.merchant_stock
                st.session_state["show_merchant"]  = True

        st.rerun()

with col2:
    if st.button("🏃 撤退する", use_container_width=True):
        st.session_state["current_room"] = 0
        st.session_state["dungeon_log"] = []
        st.session_state["show_merchant"] = False
        st.session_state["merchant_stock"] = []
        st.switch_page("pages/1_character.py")

# ─── 商人ショップ ─────────────────────────────────────────────
if st.session_state.get("show_merchant"):
    st.subheader("🛒 商人のショップ")
    with SessionLocal() as db:
        _player_gold = User.get_gold(db, user_id)
    st.caption(f"💰 現在の所持金: **{_player_gold} G**")
    stock = st.session_state.get("merchant_stock", [])
    if not stock:
        st.info("商品が見当たらない…")
    else:
        _effect_icons = {
            "heal_hp":   "💊",
            "heal_mp":   "🔵",
            "revive":    "🪶",
            "cure":      "✨",
            "buff_atk":  "⬆️ATK",
            "buff_def":  "⬆️DEF",
        }
        shop_cols = st.columns(min(len(stock), 3))
        for i, entry in enumerate(stock):
            item  = entry["item"]
            price = entry["price"]
            can_afford = _player_gold >= price
            with shop_cols[i % 3]:
                icon = _effect_icons.get(item.effect_type, "🎁")
                st.markdown(f"**{icon} {item.name}**")
                st.caption(item.description)
                st.text(f"価格: {price} G")
                if not can_afford:
                    st.warning(f"所持金不足（不足分: {price - _player_gold} G）")
                    st.button(
                        f"購入 ({price} G)",
                        key=f"shop_{item.id}",
                        disabled=True,
                        use_container_width=True,
                    )
                else:
                    if st.button(f"購入 ({price} G)", key=f"shop_{item.id}", use_container_width=True):
                        with SessionLocal() as db:
                            ok = User.spend_gold(db, user_id, price)
                            if ok:
                                Inventory.add_item(db, user_id, item.id, quantity=1)
                                st.session_state["dungeon_log"].append(
                                    f"🛒 {item.name} を {price} G で購入した！"
                                )
                                st.success(f"{item.name} を入手した！（-{price} G）")
                                st.rerun()
                            else:
                                st.error("所持金が不足しています。")
    if st.button("ショップを閉じる"):
        st.session_state["show_merchant"] = False
        st.session_state["merchant_stock"] = []
        st.rerun()

# ─── 探索中アイテム使用 ──────────────────────────────────────
with st.expander("🎒 アイテムを使う（探索中）"):
    alive_party_dungeon = [c for c in party if c.is_alive()]
    if not alive_party_dungeon:
        st.info("生存キャラクターがいません。")
    else:
        with SessionLocal() as db:
            _inv_rows = Inventory.get_by_user(db, user_id)
            _all_items_map = {item.id: item for item in Item.get_all(db)}
        _dungeon_inv = [
            {"item": _all_items_map[row.item_id], "quantity": row.quantity}
            for row in _inv_rows
            if row.item_id in _all_items_map and row.quantity > 0
        ]
        # 探索中に使えるアイテムのみ表示（heal_hp / heal_hp_pct / heal_mp / cure）
        _usable_types = {"heal_hp", "heal_hp_pct", "heal_mp", "cure"}
        _dungeon_inv_usable = [e for e in _dungeon_inv if e["item"].effect_type in _usable_types]

        if not _dungeon_inv_usable:
            st.info("使えるアイテムがありません。（revive / バフ系は戦闘中のみ使用可能）")
        else:
            _dungeon_target_labels = [
                f"{c.name}（{class_display_name(c.class_type)}）" for c in alive_party_dungeon
            ]
            _dungeon_item_labels = [
                f"{e['item'].name}  残{e['quantity']}個" for e in _dungeon_inv_usable
            ]
            _dcol1, _dcol2, _dcol3 = st.columns([2, 2, 1])
            with _dcol1:
                _d_target_idx = st.selectbox(
                    "対象",
                    range(len(_dungeon_target_labels)),
                    format_func=lambda i: _dungeon_target_labels[i],
                    key="dungeon_item_target",
                )
            with _dcol2:
                _d_item_idx = st.selectbox(
                    "アイテム",
                    range(len(_dungeon_item_labels)),
                    format_func=lambda i: _dungeon_item_labels[i],
                    key="dungeon_item_select",
                )
            with _dcol3:
                st.text("")  # 縦位置調整
                st.text("")
                if st.button("使用する", use_container_width=True):
                    _d_target = alive_party_dungeon[_d_target_idx]
                    _d_entry  = _dungeon_inv_usable[_d_item_idx]
                    _d_item   = _d_entry["item"]
                    with SessionLocal() as db:
                        _ok = Inventory.use_item(db, user_id, _d_item.id)
                        if _ok:
                            etype = _d_item.effect_type
                            if etype == "heal_hp":
                                healed = _d_target.heal(_d_item.power)
                                st.success(f"{_d_target.name} の HP が {healed} 回復！")
                            elif etype == "heal_hp_pct":
                                amount = max(1, _d_target.max_hp * _d_item.power // 100)
                                healed = _d_target.heal(amount)
                                st.success(f"{_d_target.name} の HP が {healed} 回復！")
                            elif etype == "heal_mp":
                                restored = min(_d_item.power, _d_target.max_mp - _d_target.mp)
                                _d_target.mp = min(_d_target.max_mp, _d_target.mp + _d_item.power)
                                st.success(f"{_d_target.name} の MP が {restored} 回復！")
                            elif etype == "cure":
                                st.success(f"{_d_target.name} の状態異常が回復！")
                            _d_target.save(db)
                        else:
                            st.warning("在庫がありません。")
                    st.rerun()

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
