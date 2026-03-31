"""
pages/2_dungeon.py - ダンジョン探索画面
R-14: グリッドダンジョン（迷宮の神殿）対応
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
from models.equipment import Equipment, CharacterEquipment
from models.user import User
from game.dungeon import DungeonManager
from game.map_manager import MapManager
from utils.auth import check_login, get_current_user_id
from utils.helpers import hp_bar, class_display_name
from config import (
    APP_TITLE, ROOMS_PER_FLOOR, DIFFICULTY_PRESETS,
    DIRECTION_LABELS, FLOOR_MAPS, EXP_PER_LEVEL,
)

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

# ─── 装備キャッシュ（party_equipment）──────────────────────────
if "party_equipment" not in st.session_state:
    with SessionLocal() as db:
        _all_equips_map = {e.id: e for e in Equipment.get_all(db)}
        _party_equip_cache: dict = {}
        for _c in party:
            _slots: dict = {}
            for _ce in CharacterEquipment.get_for_character(db, _c.id):
                _eq = _all_equips_map.get(_ce.equipment_id)
                if _eq:
                    _slots[_ce.slot] = _eq.name
            _party_equip_cache[_c.id] = _slots
    st.session_state["party_equipment"] = _party_equip_cache

# ─── session_state の初期化（共通） ───────────────────────────
# ミュータブルな値（list など）を毎回新しいオブジェクトで返すファクトリ関数
def _fresh_defaults() -> dict:
    return {
        "current_room":    0,
        "dungeon_log":     [],
        "floor_cleared":   False,
        "dungeon_cleared": False,
        "merchant_stock":  [],
        "show_merchant":   False,
        # グリッドダンジョン用（R-14）
        "map_x":           -1,
        "map_y":           -1,
        "last_event_pos":  None,
    }

for _k, _v in _fresh_defaults().items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ──────────────────────────────────────────────────────────────
# ダンジョン選択UI
# ──────────────────────────────────────────────────────────────
def render_dungeon_select(uid: int) -> None:
    """ダンジョン一覧を表示し、選択時に current_dungeon_id をセットして rerun する。"""
    st.title("🏰 ダンジョン探索")
    st.subheader("🗺️ ダンジョンを選択してください")
    st.divider()

    with SessionLocal() as db:
        dungeons = Dungeon.get_all(db)
        prog1 = DungeonProgress.get_or_create(db, uid, 1)
        cleared_tutorial = prog1.is_cleared
        dungeon_data = []
        for d in dungeons:
            p = DungeonProgress.get_or_create(db, uid, d.id)
            dungeon_data.append({
                "id":            d.id,
                "name":          d.name,
                "floor":         d.floor,
                "map_type":      d.map_type,
                "is_cleared":    p.is_cleared,
                "current_floor": p.current_floor,
            })

    for data in dungeon_data:
        is_locked   = data["id"] >= 2 and not cleared_tutorial
        map_icon    = "🗺️" if data["map_type"] == "grid" else "📏"
        map_label   = "グリッド探索" if data["map_type"] == "grid" else "線形探索"
        state_label = "✅ クリア済み" if data["is_cleared"] else f"📍 {data['current_floor']}F 探索中"

        with st.container(border=True):
            col_info, col_btn = st.columns([4, 1])
            with col_info:
                if is_locked:
                    st.markdown(f"### 🔒 {data['name']}")
                    st.caption(f"{map_icon} {map_label}  |  {data['floor']}F 構成  |  旅立ちの洞窟クリアで解放")
                else:
                    st.markdown(f"### {data['name']}")
                    st.caption(f"{map_icon} {map_label}  |  {data['floor']}F 構成  |  {state_label}")
            with col_btn:
                st.write("")
                if is_locked:
                    st.button("🔒 未解放", key=f"sel_{data['id']}", disabled=True, use_container_width=True)
                else:
                    if st.button("挑戦する", key=f"sel_{data['id']}", use_container_width=True):
                        # 探索状態を完全リセットしてからダンジョンIDをセット
                        _d = _fresh_defaults()
                        for _k, _v in _d.items():
                            st.session_state[_k] = _v
                        st.session_state["current_dungeon_id"] = data["id"]
                        st.rerun()


# ──────────────────────────────────────────────────────────────
# 共通ヘルパー
# ──────────────────────────────────────────────────────────────
def _render_party_status(party_list: list) -> None:
    """パーティステータスを表示する。"""
    st.subheader("🧑‍🤝‍🧑 パーティ")
    cols = st.columns(len(party_list))
    for i, chara in enumerate(party_list):
        with cols[i]:
            status = "" if chara.is_alive() else " 💀"
            st.markdown(f"**{chara.name}{status}**")
            st.caption(class_display_name(chara.class_type))
            st.text(hp_bar(chara.hp, chara.max_hp))
            st.text(f"MP {chara.mp}/{chara.max_mp}  Lv{chara.level}")
            st.text(f"ATK {chara.attack}  DEF {chara.defense}")
            with st.expander("詳細 ▼"):
                _exp_to_next = chara.level * EXP_PER_LEVEL - chara.exp
                st.text(f"Lv {chara.level}  EXP {chara.exp} / {chara.level * EXP_PER_LEVEL}（残 {_exp_to_next}）")
                st.text(f"INT {chara.intelligence}")
                _equip_slots = st.session_state.get("party_equipment", {}).get(chara.id, {})
                st.text(f"⚔️  武器: {_equip_slots.get('weapon', 'なし')}")
                st.text(f"🛡️  防具: {_equip_slots.get('armor', 'なし')}")
                st.text(f"💍  アクセサリ: {_equip_slots.get('accessory', 'なし')}")


def _render_merchant_shop(uid: int, dungeon_log: list) -> None:
    """商人ショップUIを描画する（show_merchant=True のときのみ）。"""
    if not st.session_state.get("show_merchant"):
        return
    st.subheader("🛒 商人のショップ")
    with SessionLocal() as db:
        _gold = User.get_gold(db, uid)
    st.caption(f"💰 現在の所持金: **{_gold} G**")
    stock = st.session_state.get("merchant_stock", [])
    if not stock:
        st.info("商品が見当たらない…")
    else:
        _effect_icons = {
            "heal_hp":  "💊", "heal_mp": "🔵", "revive": "🪶",
            "cure":     "✨", "buff_atk": "⬆️ATK", "buff_def": "⬆️DEF",
        }
        shop_cols = st.columns(min(len(stock), 3))
        for i, entry in enumerate(stock):
            item  = entry["item"]
            price = entry["price"]
            with shop_cols[i % 3]:
                icon = _effect_icons.get(item.effect_type, "🎁")
                st.markdown(f"**{icon} {item.name}**")
                st.caption(item.description)
                st.text(f"価格: {price} G")
                if _gold < price:
                    st.warning(f"所持金不足（不足: {price - _gold} G）")
                    st.button(f"購入 ({price} G)", key=f"shop_{item.id}",
                              disabled=True, use_container_width=True)
                else:
                    if st.button(f"購入 ({price} G)", key=f"shop_{item.id}",
                                 use_container_width=True):
                        with SessionLocal() as db:
                            if User.spend_gold(db, uid, price):
                                Inventory.add_item(db, uid, item.id, quantity=1)
                                dungeon_log.append(f"🛒 {item.name} を {price} G で購入した！")
                                st.success(f"{item.name} を入手した！（-{price} G）")
                                st.rerun()
                            else:
                                st.error("所持金が不足しています。")
    if st.button("ショップを閉じる"):
        st.session_state["show_merchant"]  = False
        st.session_state["merchant_stock"] = []
        st.rerun()


def _render_item_use(uid: int, party_list: list, dungeon_log: list) -> None:
    """探索中アイテム使用UIを描画する。"""
    with st.expander("🎒 アイテムを使う（探索中）"):
        alive = [c for c in party_list if c.is_alive()]
        if not alive:
            st.info("生存キャラクターがいません。")
            return
        with SessionLocal() as db:
            _inv_rows      = Inventory.get_by_user(db, uid)
            _all_items_map = {it.id: it for it in Item.get_all(db)}
        _usable_types = {"heal_hp", "heal_hp_pct", "heal_mp", "cure"}
        _usable = [
            {"item": _all_items_map[row.item_id], "quantity": row.quantity}
            for row in _inv_rows
            if row.item_id in _all_items_map and row.quantity > 0
            and _all_items_map[row.item_id].effect_type in _usable_types
        ]
        if not _usable:
            st.info("使えるアイテムがありません。（revive / バフ系は戦闘中のみ使用可能）")
            return

        _target_labels = [f"{c.name}（{class_display_name(c.class_type)}）" for c in alive]
        _item_labels   = [f"{e['item'].name}  残{e['quantity']}個" for e in _usable]
        dc1, dc2, dc3  = st.columns([2, 2, 1])
        with dc1:
            ti = st.selectbox("対象",   range(len(_target_labels)),
                              format_func=lambda i: _target_labels[i], key="dungeon_item_target")
        with dc2:
            ii = st.selectbox("アイテム", range(len(_item_labels)),
                              format_func=lambda i: _item_labels[i],   key="dungeon_item_select")
        with dc3:
            st.text(""); st.text("")
            if st.button("使用する", use_container_width=True):
                _tgt  = alive[ti]
                _item = _usable[ii]["item"]
                with SessionLocal() as db:
                    if Inventory.use_item(db, uid, _item.id):
                        et = _item.effect_type
                        if et == "heal_hp":
                            st.success(f"{_tgt.name} の HP が {_tgt.heal(_item.power)} 回復！")
                        elif et == "heal_hp_pct":
                            amt = max(1, _tgt.max_hp * _item.power // 100)
                            st.success(f"{_tgt.name} の HP が {_tgt.heal(amt)} 回復！")
                        elif et == "heal_mp":
                            restored = min(_item.power, _tgt.max_mp - _tgt.mp)
                            _tgt.mp  = min(_tgt.max_mp, _tgt.mp + _item.power)
                            st.success(f"{_tgt.name} の MP が {restored} 回復！")
                        elif et == "cure":
                            st.success(f"{_tgt.name} の状態異常が回復！")
                        _tgt.save(db)
                    else:
                        st.warning("在庫がありません。")
                st.rerun()


def _apply_event_result(
    result,
    uid: int,
    party_list: list,
    dungeon_id: int,
    dungeon_log: list,
    diff_cfg: dict,
    current_floor: int,
) -> None:
    """
    EventResult を受け取ってセッション・DBに反映する共通処理。
    need_battle=True の場合は戦闘画面へ遷移（この関数は戻らない）。
    """
    for msg in result.messages:
        dungeon_log.append(msg)
    st.session_state["dungeon_log"] = dungeon_log

    if result.need_battle:
        st.session_state["battle_enemies"]   = result.enemies
        st.session_state["battle_log"]       = []
        st.session_state["battle_result"]    = None
        st.session_state["battle_inventory"] = []
        st.switch_page("pages/3_battle.py")

    with SessionLocal() as db:
        if result.event_type in ("trap", "rest", "shrine"):
            for chara in party_list:
                chara.save(db)
        elif result.event_type == "chest":
            if result.chest_gold > 0:
                User.add_gold(db, uid, result.chest_gold)
            if result.chest_item_id > 0:
                Inventory.add_item(db, uid, result.chest_item_id, quantity=1)
        elif result.event_type == "merchant":
            st.session_state["merchant_stock"] = result.merchant_stock
            st.session_state["show_merchant"]  = True


# ──────────────────────────────────────────────────────────────
# 線形ダンジョン
# ──────────────────────────────────────────────────────────────
def render_linear_dungeon(
    uid: int,
    dungeon_id: int,
    dungeon_name: str,
    dungeon_max_floor: int,
    current_floor: int,
    is_cleared: bool,
    party_list: list,
    diff_cfg: dict,
) -> None:
    """線形探索ダンジョンの UI 全体を描画する。"""

    # ─── タイトルバー ─────────────────────────────────────
    with SessionLocal() as db:
        current_gold = User.get_gold(db, uid)
    cb, ct, cg, ctown = st.columns([2, 4, 1, 1])
    with cb:
        if st.button("← ダンジョン選択"):
            del st.session_state["current_dungeon_id"]
            for _k, _v in _fresh_defaults().items():
                st.session_state[_k] = _v
            st.rerun()
    with ct:
        st.subheader(f"📍 {dungeon_name}  {current_floor}F / {dungeon_max_floor}F")
    with cg:
        st.metric("💰 GOLD", f"{current_gold} G")
    with ctown:
        st.page_link("pages/4_town.py", label="🏘️ 町へ")

    # ─── 全クリア ─────────────────────────────────────────
    if is_cleared or st.session_state.get("dungeon_cleared"):
        st.balloons()
        st.success("🎉 ダンジョンをクリアしました！")
        if st.button("再挑戦する", key="retry_linear"):
            with SessionLocal() as db:
                mgr = DungeonManager(db, Dungeon.get_by_id(db, dungeon_id),
                                     DungeonProgress.get_or_create(db, uid, dungeon_id))
                mgr.reset_progress()
            for _k, _v in _fresh_defaults().items():
                st.session_state[_k] = _v
            st.rerun()
        if st.button("ダンジョン選択に戻る", key="back_after_clear_linear"):
            del st.session_state["current_dungeon_id"]
            st.rerun()
        st.stop()

    # ─── パーティ・ログ ────────────────────────────────────
    _render_party_status(party_list)
    st.divider()

    room = st.session_state["current_room"]
    st.subheader(f"🚪 現在の部屋: {room}/{ROOMS_PER_FLOOR}")
    with st.container():
        for line in st.session_state["dungeon_log"][-20:]:
            st.text(line)
    st.divider()

    # ─── 全滅チェック ──────────────────────────────────────
    if all(not c.is_alive() for c in party_list):
        st.error("パーティが全滅しました…")
        if st.button("キャラクター管理へ戻る"):
            st.session_state["current_room"] = 0
            st.session_state["dungeon_log"]  = []
            st.switch_page("pages/1_character.py")
        st.stop()

    # ─── アクションボタン ──────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶ 先に進む", use_container_width=True, key="advance_linear"):
            room += 1
            st.session_state["current_room"]   = room
            st.session_state["show_merchant"]  = False
            st.session_state["merchant_stock"] = []
            log = st.session_state["dungeon_log"]
            log.append(f"🚪 {current_floor}F - 部屋{room} に入った。")
            with SessionLocal() as db:
                if room == 1:
                    bonus = User.get_meta_bonus(db, uid, "start_gold")
                    if bonus > 0:
                        User.add_gold(db, uid, bonus)
                        log.append(f"💰 開始資金ボーナス +{bonus}G！")
                _dungeon  = Dungeon.get_by_id(db, dungeon_id)
                _progress = DungeonProgress.get_or_create(db, uid, dungeon_id)
                mgr    = DungeonManager(db, _dungeon, _progress)
                result = mgr.resolve_event(
                    party_list, room,
                    hp_mult=diff_cfg["enemy_hp_mult"],
                    atk_mult=diff_cfg["enemy_atk_mult"],
                )
            _apply_event_result(result, uid, party_list, dungeon_id, log, diff_cfg, current_floor)
            st.rerun()
    with col2:
        if st.button("🏃 撤退する", use_container_width=True, key="retreat_linear"):
            st.session_state["current_room"]   = 0
            st.session_state["dungeon_log"]    = []
            st.session_state["show_merchant"]  = False
            st.session_state["merchant_stock"] = []
            st.switch_page("pages/1_character.py")

    # ─── 商人・アイテム ────────────────────────────────────
    _render_merchant_shop(uid, st.session_state["dungeon_log"])
    _render_item_use(uid, party_list, st.session_state["dungeon_log"])

    # ─── 戦闘結果の反映 ────────────────────────────────────
    battle_result = st.session_state.get("battle_result")
    if battle_result == "win":
        st.session_state["battle_result"] = None
        if st.session_state["current_room"] >= ROOMS_PER_FLOOR:
            with SessionLocal() as db:
                _dungeon  = Dungeon.get_by_id(db, dungeon_id)
                _progress = DungeonProgress.get_or_create(db, uid, dungeon_id)
                mgr       = DungeonManager(db, _dungeon, _progress)
                all_clear = mgr.advance_to_next_floor()
                if all_clear:
                    User.add_meta_title(db, uid, "dungeon_cleared")
                else:
                    _nf = _progress.current_floor
                    if _nf == 2:
                        User.add_meta_title(db, uid, "floor2")
                    elif _nf == 3:
                        User.add_meta_title(db, uid, "floor3")
            st.session_state["current_room"] = 0
            if all_clear:
                st.session_state["dungeon_cleared"] = True
            else:
                st.session_state["dungeon_log"].append(
                    f"✨ {_nf - 1}F をクリア！ {_nf}F へ進む。")
        st.rerun()
    elif battle_result == "lose":
        st.session_state["battle_result"] = None
        st.error("全滅してしまいました…")
        st.session_state["current_room"] = 0
        st.session_state["dungeon_log"]  = []


# ──────────────────────────────────────────────────────────────
# グリッドダンジョン（R-14）
# ──────────────────────────────────────────────────────────────
def _render_move_buttons(mm: MapManager) -> "str | None":
    """
    十字キーレイアウトで方向ボタンを表示する。
    クリックされた方向文字列（"north"/"south"/"west"/"east"）、なければ None を返す。
    """
    clicked: "str | None" = None

    _, cn, _ = st.columns([1, 1, 1])
    with cn:
        if st.button(DIRECTION_LABELS["north"], key="move_north",
                     disabled=not mm.can_move("north"), use_container_width=True):
            clicked = "north"

    cw, cc, ce = st.columns([1, 1, 1])
    with cw:
        if st.button(DIRECTION_LABELS["west"], key="move_west",
                     disabled=not mm.can_move("west"), use_container_width=True):
            clicked = "west"
    with cc:
        st.button("🧍", key="move_center", disabled=True, use_container_width=True)
    with ce:
        if st.button(DIRECTION_LABELS["east"], key="move_east",
                     disabled=not mm.can_move("east"), use_container_width=True):
            clicked = "east"

    _, cs, _ = st.columns([1, 1, 1])
    with cs:
        if st.button(DIRECTION_LABELS["south"], key="move_south",
                     disabled=not mm.can_move("south"), use_container_width=True):
            clicked = "south"

    return clicked


def render_grid_dungeon(
    uid: int,
    dungeon_id: int,
    dungeon_name: str,
    dungeon_max_floor: int,
    current_floor: int,
    is_cleared: bool,
    party_list: list,
    diff_cfg: dict,
) -> None:
    """グリッドマップダンジョンの UI 全体を描画する（R-14）。"""

    # ─── タイトルバー ─────────────────────────────────────
    with SessionLocal() as db:
        current_gold = User.get_gold(db, uid)
    cb, ct, cg, ctown = st.columns([2, 4, 1, 1])
    with cb:
        if st.button("← ダンジョン選択"):
            del st.session_state["current_dungeon_id"]
            for _k, _v in _fresh_defaults().items():
                st.session_state[_k] = _v
            st.rerun()
    with ct:
        _x = st.session_state.get("map_x", -1)
        _y = st.session_state.get("map_y", -1)
        _pos = f"  （座標 {_x},{_y}）" if _x >= 0 else ""
        st.subheader(f"🗺️ {dungeon_name}  {current_floor}F / {dungeon_max_floor}F{_pos}")
    with cg:
        st.metric("💰 GOLD", f"{current_gold} G")
    with ctown:
        st.page_link("pages/4_town.py", label="🏘️ 町へ")

    # ─── 全クリア ─────────────────────────────────────────
    if is_cleared or st.session_state.get("dungeon_cleared"):
        st.balloons()
        st.success("🎉 ダンジョンをクリアしました！")
        if st.button("再挑戦する", key="retry_grid"):
            with SessionLocal() as db:
                mgr = DungeonManager(db, Dungeon.get_by_id(db, dungeon_id),
                                     DungeonProgress.get_or_create(db, uid, dungeon_id))
                mgr.reset_progress()
            for _k, _v in _fresh_defaults().items():
                st.session_state[_k] = _v
            st.rerun()
        if st.button("ダンジョン選択に戻る", key="back_after_clear_grid"):
            del st.session_state["current_dungeon_id"]
            st.rerun()
        st.stop()

    # ─── グリッド座標の初期化（初回 or リセット後） ─────────
    x = st.session_state.get("map_x", -1)
    y = st.session_state.get("map_y", -1)
    if x < 0 or y < 0:
        with SessionLocal() as db:
            _dungeon  = Dungeon.get_by_id(db, dungeon_id)
            _progress = DungeonProgress.get_or_create(db, uid, dungeon_id)
            mm_init   = DungeonManager(db, _dungeon, _progress).start_floor(current_floor)
        x, y = mm_init.x, mm_init.y
        st.session_state["map_x"]          = x
        st.session_state["map_y"]          = y
        st.session_state["last_event_pos"] = None
        st.session_state["dungeon_log"].append(
            f"🗺️ {current_floor}F の探索を開始した。スタート地点: ({x},{y})")

    # ─── パーティ・ログ ────────────────────────────────────
    _render_party_status(party_list)
    st.divider()

    # ─── 全滅チェック ──────────────────────────────────────
    if all(not c.is_alive() for c in party_list):
        st.error("パーティが全滅しました…")
        if st.button("キャラクター管理へ戻る"):
            for k in ("map_x", "map_y", "last_event_pos", "dungeon_log"):
                st.session_state[k] = _ss_defaults[k]
            st.switch_page("pages/1_character.py")
        st.stop()

    mm = MapManager(current_floor, x, y)
    st.info(mm.describe_surroundings())

    with st.container():
        for line in st.session_state["dungeon_log"][-20:]:
            st.text(line)
    st.divider()

    # ─── 移動ボタン ────────────────────────────────────────
    col_map, col_act = st.columns([1, 2])
    with col_map:
        direction = _render_move_buttons(mm)
    with col_act:
        retreat = st.button("🏃 撤退する", use_container_width=True, key="retreat_grid")

    # ─── 撤退 ─────────────────────────────────────────────
    if retreat:
        for k in ("map_x", "map_y", "last_event_pos", "dungeon_log",
                  "show_merchant", "merchant_stock"):
            st.session_state[k] = _ss_defaults[k]
        st.switch_page("pages/1_character.py")

    # ─── 移動処理 ──────────────────────────────────────────
    if direction is not None:
        new_x, new_y = mm.move(direction)
        st.session_state["map_x"] = new_x
        st.session_state["map_y"] = new_y
        st.session_state["show_merchant"]  = False
        st.session_state["merchant_stock"] = []
        log = st.session_state["dungeon_log"]
        log.append(f"→ {DIRECTION_LABELS[direction]} へ進んだ。({new_x},{new_y})")

        new_mm     = MapManager(current_floor, new_x, new_y)
        last_pos   = st.session_state.get("last_event_pos")
        do_event   = (last_pos != (new_x, new_y)) or new_mm.is_goal()

        with SessionLocal() as db:
            _dungeon  = Dungeon.get_by_id(db, dungeon_id)
            _progress = DungeonProgress.get_or_create(db, uid, dungeon_id)
            _progress.set_position(new_x, new_y, db)
            if do_event:
                st.session_state["last_event_pos"] = (new_x, new_y)
                mgr    = DungeonManager(db, _dungeon, _progress)
                result = mgr.resolve_event_at(
                    new_x, new_y, party_list,
                    hp_mult=diff_cfg["enemy_hp_mult"],
                    atk_mult=diff_cfg["enemy_atk_mult"],
                )
        if do_event:
            _apply_event_result(result, uid, party_list, dungeon_id, log, diff_cfg, current_floor)
        st.rerun()

    # ─── 商人・アイテム ────────────────────────────────────
    _render_merchant_shop(uid, st.session_state["dungeon_log"])
    _render_item_use(uid, party_list, st.session_state["dungeon_log"])

    # ─── 戦闘結果の反映 ────────────────────────────────────
    battle_result = st.session_state.get("battle_result")
    if battle_result == "win":
        st.session_state["battle_result"] = None
        goal_pos = tuple(FLOOR_MAPS[current_floor]["goal"])
        if st.session_state.get("last_event_pos") == goal_pos:
            with SessionLocal() as db:
                _dungeon  = Dungeon.get_by_id(db, dungeon_id)
                _progress = DungeonProgress.get_or_create(db, uid, dungeon_id)
                mgr       = DungeonManager(db, _dungeon, _progress)
                all_clear = mgr.advance_to_next_floor()
                if all_clear:
                    User.add_meta_title(db, uid, "dungeon_cleared")
                else:
                    _nf = _progress.current_floor
                    if _nf == 2:
                        User.add_meta_title(db, uid, "floor2")
                    elif _nf == 3:
                        User.add_meta_title(db, uid, "floor3")
            st.session_state["map_x"]          = -1
            st.session_state["map_y"]          = -1
            st.session_state["last_event_pos"] = None
            if all_clear:
                st.session_state["dungeon_cleared"] = True
            else:
                st.session_state["dungeon_log"].append(
                    f"✨ {_nf - 1}F をクリア！ {_nf}F へ進む。")
        st.rerun()
    elif battle_result == "lose":
        st.session_state["battle_result"] = None
        st.error("全滅してしまいました…")
        for k in ("map_x", "map_y", "last_event_pos", "dungeon_log"):
            st.session_state[k] = _fresh_defaults()[k]


# ──────────────────────────────────────────────────────────────
# メインルーティング
# ──────────────────────────────────────────────────────────────

# ダンジョン未選択 → 選択画面（タイトルは render_dungeon_select 内で表示）
if "current_dungeon_id" not in st.session_state:
    render_dungeon_select(user_id)
    st.stop()

dungeon_id = st.session_state["current_dungeon_id"]

# ─── 難易度選択 ───────────────────────────────────────────────
diff_keys    = list(DIFFICULTY_PRESETS.keys())
diff_labels  = [DIFFICULTY_PRESETS[k]["label"] for k in diff_keys]
current_diff = st.session_state.get("difficulty", "normal")
current_diff_idx = diff_keys.index(current_diff) if current_diff in diff_keys else 1

in_dungeon = (
    st.session_state.get("current_room", 0) > 0
    or st.session_state.get("map_x", -1) >= 0
)
if in_dungeon:
    st.caption(f"難易度: {DIFFICULTY_PRESETS[current_diff]['label']}  （探索中は変更不可）")
else:
    sel_label = st.selectbox("難易度", diff_labels, index=current_diff_idx, key="difficulty_select")
    new_diff  = diff_keys[diff_labels.index(sel_label)]
    if new_diff != current_diff:
        st.session_state["difficulty"] = new_diff
        st.rerun()

diff_cfg = DIFFICULTY_PRESETS[st.session_state.get("difficulty", "normal")]

# ─── DB 取得 ──────────────────────────────────────────────────
with SessionLocal() as db:
    _d = Dungeon.get_by_id(db, dungeon_id)
    _p = DungeonProgress.get_or_create(db, user_id, dungeon_id)
    dungeon_name      = _d.name
    dungeon_max_floor = _d.floor
    dungeon_is_grid   = _d.is_grid
    current_floor     = _p.current_floor
    is_cleared        = _p.is_cleared

st.divider()

# ─── ダンジョン種別で描画先を分岐 ─────────────────────────────
if dungeon_is_grid:
    render_grid_dungeon(
        user_id, dungeon_id, dungeon_name, dungeon_max_floor,
        current_floor, is_cleared, party, diff_cfg,
    )
else:
    render_linear_dungeon(
        user_id, dungeon_id, dungeon_name, dungeon_max_floor,
        current_floor, is_cleared, party, diff_cfg,
    )
