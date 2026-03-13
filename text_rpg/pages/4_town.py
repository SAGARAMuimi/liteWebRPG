"""
pages/4_town.py - 町（ショップ / 売却 / 宿屋 / 帰還）
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import models  # noqa: F401 - 全テーブルを依存順に Base.metadata に登録
import streamlit as st
from models.database import SessionLocal
from models.character import PartyMember
from models.dungeon import DungeonProgress
from models.item import Item
from models.inventory import Inventory
from models.user import User
from utils.auth import check_login, get_current_user_id
from utils.helpers import hp_bar, class_display_name
from config import (
    APP_TITLE,
    TOWN_SELL_RATE,
    TOWN_REST_COSTS,
    TOWN_ITEM_MAX_STACK,
    EQUIPMENT_SLOT_NAMES,
)
from models.equipment import Equipment, CharacterEquipment, CharacterInventory

st.set_page_config(page_title=f"町 | {APP_TITLE}", page_icon="🏘️", layout="wide")
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

# ─── 所持金 ─────────────────────────────────────────────────
with SessionLocal() as db:
    current_gold = User.get_gold(db, user_id)

# ─── タイトル ───────────────────────────────────────────────
st.title("🏘️ 町")
col_title, col_gold = st.columns([5, 1])
with col_title:
    st.caption("ショップで装備を整え、宿屋で体力を回復しよう。")
with col_gold:
    st.metric("💰 GOLD", f"{current_gold} G")

st.divider()

# ─── パーティ状態表示 ────────────────────────────────────────
with st.expander("🧑‍🤝‍🧑 パーティ状態", expanded=False):
    pcols = st.columns(len(party))
    for i, chara in enumerate(party):
        with pcols[i]:
            alive_mark = "" if chara.is_alive() else " 💀"
            st.markdown(f"**{chara.name}{alive_mark}**")
            st.caption(class_display_name(chara.class_type))
            st.text(hp_bar(chara.hp, chara.max_hp))
            st.text(f"MP {chara.mp}/{chara.max_mp}")

st.divider()

# ─── タブ ───────────────────────────────────────────────────
tab_shop, tab_sell, tab_equip, tab_inn, tab_leave = st.tabs([
    "🛒 ショップ",
    "💰 売却",
    "⚔️ 装備",
    "🛌 宿屋",
    "🚪 帰還",
])

# ════════════════════════════════════════════════════════════
# 🛒 ショップタブ
# ════════════════════════════════════════════════════════════
with tab_shop:
    st.subheader("🛒 ショップ")
    st.caption(f"1種類につき最大 {TOWN_ITEM_MAX_STACK} 個まで購入できます。")

    with SessionLocal() as db:
        all_items = Item.get_all(db)
        inv_rows  = Inventory.get_by_user(db, user_id)

    # 現在の所持数マップ {item_id: quantity}
    owned: dict[int, int] = {row.item_id: row.quantity for row in inv_rows}

    with SessionLocal() as db:
        current_gold = User.get_gold(db, user_id)

    if not all_items:
        st.info("現在ショップに商品はありません。")
    else:
        shop_cols = st.columns(3)
        for idx, item in enumerate(all_items):
            with shop_cols[idx % 3]:
                qty_owned = owned.get(item.id, 0)
                at_max    = qty_owned >= TOWN_ITEM_MAX_STACK
                can_buy   = current_gold >= item.price and not at_max

                st.markdown(f"**{item.name}**")
                st.caption(item.description)
                st.text(f"💰 {item.price} G　所持: {qty_owned}/{TOWN_ITEM_MAX_STACK}")

                if at_max:
                    st.button("購入", key=f"buy_{item.id}", disabled=True,
                              help="所持上限に達しています", use_container_width=True)
                elif not can_buy:
                    st.button("購入", key=f"buy_{item.id}", disabled=True,
                              help="所持金が足りません", use_container_width=True)
                else:
                    if st.button("購入", key=f"buy_{item.id}", use_container_width=True):
                        with SessionLocal() as db:
                            ok = User.spend_gold(db, user_id, item.price)
                        if ok:
                            with SessionLocal() as db:
                                Inventory.add_item(db, user_id, item.id, quantity=1)
                            st.success(f"✅ {item.name} を購入しました！")
                            st.rerun()
                        else:
                            st.error("所持金が足りません。")

# ════════════════════════════════════════════════════════════
# 💰 売却タブ
# ════════════════════════════════════════════════════════════
with tab_sell:
    st.subheader("💰 売却")
    buy_rate_pct = int(TOWN_SELL_RATE * 100)
    st.caption(f"アイテムを定価の {buy_rate_pct}% で買い取ります。")

    with SessionLocal() as db:
        inv_rows  = Inventory.get_by_user(db, user_id)
        all_items_map = {item.id: item for item in Item.get_all(db)}

    sell_stock = [
        {"item": all_items_map[row.item_id], "quantity": row.quantity}
        for row in inv_rows
        if row.item_id in all_items_map and row.quantity > 0
    ]

    if not sell_stock:
        st.info("売却できるアイテムがありません。")
    else:
        sell_cols = st.columns(3)
        for idx, entry in enumerate(sell_stock):
            item = entry["item"]
            qty  = entry["quantity"]
            sell_price = max(1, int(item.price * TOWN_SELL_RATE))

            with sell_cols[idx % 3]:
                st.markdown(f"**{item.name}**")
                st.caption(item.description)
                st.text(f"売値: {sell_price} G　所持: {qty} 個")
                if st.button("売却 (1個)", key=f"sell_{item.id}", use_container_width=True):
                    with SessionLocal() as db:
                        ok = Inventory.use_item(db, user_id, item.id)
                    if ok:
                        with SessionLocal() as db:
                            User.add_gold(db, user_id, sell_price)
                        st.success(f"✅ {item.name} を {sell_price} G で売却しました！")
                        st.rerun()
                    else:
                        st.error("売却できませんでした。")

# ════════════════════════════════════════════════════════════
# ⚔️ 装備タブ
# ════════════════════════════════════════════════════════════
with tab_equip:
    st.subheader("⚔️ 装備")

    with SessionLocal() as db:
        all_equips   = Equipment.get_all(db)
        current_gold = User.get_gold(db, user_id)
        equip_obj_map: dict[int, Equipment] = {e.id: e for e in all_equips}
        # 各キャラの装備スロット {char_id: {slot: CharacterEquipment}}
        equip_map: dict[int, dict[str, CharacterEquipment]] = {}
        for chara in party:
            slots = CharacterEquipment.get_for_character(db, chara.id)
            equip_map[chara.id] = {ce.slot: ce for ce in slots}
        # 各キャラのインベントリ {char_id: list[CharacterInventory]}
        inv_map: dict[int, list] = {}
        for chara in party:
            inv_map[chara.id] = CharacterInventory.get_for_character(db, chara.id)

    # ── 現在の装備 ──────────────────────────────────────────────
    st.markdown("#### 📦 現在の装備")
    for chara in party:
        with st.expander(
            f"{chara.name}（{class_display_name(chara.class_type)}）"
            f"  ATK:{chara.attack}  DEF:{chara.defense}  HP:{chara.max_hp}  MP:{chara.max_mp}",
            expanded=True,
        ):
            slot_cols = st.columns(len(EQUIPMENT_SLOT_NAMES))
            for col_idx, (slot_key, slot_label) in enumerate(EQUIPMENT_SLOT_NAMES.items()):
                with slot_cols[col_idx]:
                    st.markdown(f"**{slot_label}**")
                    ce = equip_map.get(chara.id, {}).get(slot_key)
                    if ce and ce.equipment_id in equip_obj_map:
                        eq = equip_obj_map[ce.equipment_id]
                        st.text(eq.name)
                        st.caption(eq.bonus_summary())
                        if st.button("外す", key=f"unequip_{chara.id}_{slot_key}",
                                     use_container_width=True):
                            with SessionLocal() as db:
                                fresh = db.merge(chara)
                                msg = fresh.unequip(db, slot_key)
                                for attr in ("attack", "defense", "max_hp", "max_mp", "hp", "mp"):
                                    setattr(chara, attr, getattr(fresh, attr))
                            st.session_state["party"] = party
                            st.success(msg)
                            st.rerun()
                    else:
                        st.caption("— 装備なし —")

    st.divider()

    # ── 所持装備（インベントリ）──────────────────────────────────
    st.markdown("#### 🎒 所持している装備")
    st.caption("スロットから外した永続装備がここに保管されます。装備ボタンで再装備できます。")

    any_inv = any(inv_map.get(chara.id) for chara in party)
    if not any_inv:
        st.info("所持している装備はありません。")
    else:
        for chara in party:
            inv_rows_chara = inv_map.get(chara.id, [])
            if not inv_rows_chara:
                continue
            with st.expander(
                f"{chara.name}（{class_display_name(chara.class_type)}）の所持装備",
                expanded=True,
            ):
                inv_cols = st.columns(3)
                for idx, ci in enumerate(inv_rows_chara):
                    eq = equip_obj_map.get(ci.equipment_id)
                    if not eq:
                        continue
                    with inv_cols[idx % 3]:
                        st.text(f"{eq.name} × {ci.quantity}")
                        st.caption(eq.bonus_summary())
                        # 装備ボタン
                        if st.button("装備する", key=f"inv_equip_{chara.id}_{eq.id}",
                                     use_container_width=True):
                            with SessionLocal() as db:
                                # インベントリから1個消費
                                ok = CharacterInventory.consume(db, chara.id, eq.id, qty=1)
                            if ok:
                                with SessionLocal() as db:
                                    fresh_eq = Equipment.get_by_id(db, eq.id)
                                    fresh_ch = db.merge(chara)
                                    msg = fresh_ch.equip(db, fresh_eq)
                                    for attr in ("attack", "defense", "max_hp",
                                                 "max_mp", "hp", "mp"):
                                        setattr(chara, attr, getattr(fresh_ch, attr))
                                st.session_state["party"] = party
                                st.success(f"✅ {msg}")
                                st.rerun()
                            else:
                                st.error("装備できませんでした。")
                        # 売却ボタン（売値は定価の TOWN_SELL_RATE 倍）
                        sell_price = max(1, int(eq.price * TOWN_SELL_RATE))
                        if st.button(f"売却 ({sell_price}G)", key=f"inv_sell_{chara.id}_{eq.id}",
                                     use_container_width=True):
                            with SessionLocal() as db:
                                ok = CharacterInventory.consume(db, chara.id, eq.id, qty=1)
                            if ok:
                                with SessionLocal() as db:
                                    User.add_gold(db, user_id, sell_price)
                                st.success(f"✅ {eq.name} を {sell_price} G で売却しました！")
                                st.rerun()
                            else:
                                st.error("売却できませんでした。")

    st.divider()

    # ── 装備を購入して装備する ──────────────────────────────────────
    st.markdown("#### 🛍️ 装備を購入して装備する")
    st.caption("購入と同時に即座に装備されます。同スロットに既存の装備があれば自動で外します。")

    alive_party = [c for c in party if c.is_alive()]
    if not alive_party:
        st.info("装備できるキャラクターがいません。")
    else:
        chara_labels = [f"{c.name}（{class_display_name(c.class_type)}）" for c in alive_party]
        sel_idx   = st.selectbox("装備するキャラクター",
                                 range(len(alive_party)),
                                 format_func=lambda i: chara_labels[i],
                                 key="equip_target_chara")
        sel_chara = alive_party[sel_idx]
        st.caption(f"💰 所持金: {current_gold} G")

        for slot_key, slot_label in EQUIPMENT_SLOT_NAMES.items():
            slot_equips = [
                e for e in all_equips
                if e.slot == slot_key and e.can_equip(sel_chara.class_type)
            ]
            if not slot_equips:
                continue
            st.markdown(f"**{slot_label}**")
            e_cols = st.columns(3)
            for i, eq in enumerate(slot_equips):
                with e_cols[i % 3]:
                    st.text(eq.name)
                    st.caption(eq.description)
                    st.caption(f"{eq.bonus_summary()}  /  💰 {eq.price} G")
                    # 既に装備中か確認
                    ce = equip_map.get(sel_chara.id, {}).get(slot_key)
                    already = ce is not None and ce.equipment_id == eq.id
                    can_buy = current_gold >= eq.price
                    if already:
                        st.button("✅ 装備中", key=f"buy_eq_{sel_chara.id}_{eq.id}",
                                  disabled=True, use_container_width=True)
                    elif not can_buy:
                        st.button("購入して装備", key=f"buy_eq_{sel_chara.id}_{eq.id}",
                                  disabled=True, help="所持金が足りません",
                                  use_container_width=True)
                    else:
                        if st.button("購入して装備", key=f"buy_eq_{sel_chara.id}_{eq.id}",
                                     use_container_width=True):
                            with SessionLocal() as db:
                                ok = User.spend_gold(db, user_id, eq.price)
                            if ok:
                                with SessionLocal() as db:
                                    fresh_eq = Equipment.get_by_id(db, eq.id)
                                    fresh_ch = db.merge(sel_chara)
                                    msg = fresh_ch.equip(db, fresh_eq)
                                    for attr in ("attack", "defense", "max_hp",
                                                 "max_mp", "hp", "mp"):
                                        setattr(sel_chara, attr, getattr(fresh_ch, attr))
                                st.session_state["party"] = party
                                st.success(f"✅ {msg}")
                                st.rerun()
                            else:
                                st.error("所持金が足りません。")

# ════════════════════════════════════════════════════════════
# 🛌 宿屋タブ
# ════════════════════════════════════════════════════════════
with tab_inn:
    st.subheader("🛌 宿屋")
    st.caption("ゴールドを消費してパーティのHP・MPを回復します。")

    with SessionLocal() as db:
        current_gold = User.get_gold(db, user_id)

    # パーティ状態表示
    inn_cols = st.columns(len(party))
    for i, chara in enumerate(party):
        with inn_cols[i]:
            alive_mark = "" if chara.is_alive() else " 💀"
            st.markdown(f"**{chara.name}{alive_mark}**")
            st.caption(class_display_name(chara.class_type))
            st.text(hp_bar(chara.hp, chara.max_hp))
            st.text(f"MP {chara.mp}/{chara.max_mp}")

    st.divider()

    # 休息プラン
    for plan_key, plan in TOWN_REST_COSTS.items():
        cost    = plan["cost"]
        pct     = plan["pct"]
        label   = plan["label"]
        can_rest = current_gold >= cost

        col_info, col_btn = st.columns([4, 1])
        with col_info:
            if pct == 100:
                st.markdown(f"**{label}**  ─  HP/MP を **全回復**")
            else:
                st.markdown(f"**{label}**  ─  HP/MP を **{pct}%** 回復")
            st.caption(f"費用: {cost} G　（現在: {current_gold} G）")
        with col_btn:
            if st.button(f"休む ({cost}G)", key=f"rest_{plan_key}",
                         disabled=not can_rest, use_container_width=True):
                with SessionLocal() as db:
                    ok = User.spend_gold(db, user_id, cost)
                if ok:
                    with SessionLocal() as db:
                        for chara in party:
                            if pct == 100:
                                chara.hp = chara.max_hp
                                chara.mp = chara.max_mp
                            else:
                                chara.hp = min(chara.max_hp, chara.hp + chara.max_hp * pct // 100)
                                chara.mp = min(chara.max_mp, chara.mp + chara.max_mp * pct // 100)
                            chara.save(db)
                    # session_state のパーティも同期
                    st.session_state["party"] = party
                    st.success(f"✅ {label}でパーティが回復しました！")
                    st.rerun()
                else:
                    st.error("所持金が足りません。")

# ════════════════════════════════════════════════════════════
# 🚪 帰還タブ
# ════════════════════════════════════════════════════════════
with tab_leave:
    st.subheader("🚪 帰還")

    dungeon_id = st.session_state.get("current_dungeon_id", 1)

    with SessionLocal() as db:
        prog = DungeonProgress.get_or_create(db, user_id, dungeon_id)
        current_floor = prog.current_floor

    st.info(
        f"現在 **{current_floor}F** を探索中です。\n\n"
        "帰還すると **ダンジョンの進行状況が 1F にリセット** されます。\n"
        "所持金・アイテム・キャラクターの成長はそのまま保持されます。"
    )

    if current_floor == 1 and st.session_state.get("current_room", 0) == 0:
        st.success("すでにダンジョン入口にいます。")
    else:
        st.warning("⚠️ 帰還するとこの階層の進行状況は失われます。")
        if st.button("🚪 ダンジョンを離れて帰還する", type="primary", use_container_width=False):
            # ダンジョン進行をリセット
            with SessionLocal() as db:
                prog = DungeonProgress.get_or_create(db, user_id, dungeon_id)
                prog.current_floor = 1
                prog.save(db)
            st.session_state["current_floor"]  = 1
            st.session_state["current_room"]   = 0
            st.session_state["floor_cleared"]  = False
            st.session_state["dungeon_cleared"] = False
            st.session_state["dungeon_log"]    = []
            st.session_state["battle_enemies"] = []
            st.session_state["battle_result"]  = None
            st.session_state["battle_buffs"]   = {}
            st.session_state["battle_hate"]    = {}
            st.success("帰還しました。ダンジョン入口に戻ります。")
            st.page_link("pages/2_dungeon.py", label="🏰 ダンジョンへ")

    st.divider()
    st.page_link("pages/2_dungeon.py", label="← ダンジョンへ戻る（進行状況を維持）")
