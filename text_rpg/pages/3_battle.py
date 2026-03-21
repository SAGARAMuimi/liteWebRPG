"""
pages/3_battle.py - 戦闘画面
"""

import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import models  # noqa: F401 - 全テーブルを依存順に Base.metadata に登録
import streamlit as st
from models.database import SessionLocal
from models.character import PartyMember
from models.skill import Skill
from models.item import Item
from models.inventory import Inventory
from game.battle import BattleEngine
from models.user import User
from utils.auth import check_login, get_current_user_id
from utils.helpers import hp_bar, class_display_name
from config import APP_TITLE, DIFFICULTY_PRESETS, STATUS_AILMENTS, LEVEL_UP_PLANS, CLASS_DEFAULT_LEVELUP_PLAN, ALLY_POLICIES, CLASS_DEFAULT_POLICY

st.set_page_config(page_title=f"戦闘 | {APP_TITLE}", page_icon="⚔️", layout="wide")
check_login()

# 状態異常アイコン表示ヘルパー
def _buff_tag(b: dict) -> str:
    if b.get("stat") == "status":
        kind = b.get("kind", "")
        info = STATUS_AILMENTS.get(kind, {})
        return f"{info.get('icon', '❓')}{info.get('label', kind)}({b['turns_left']}T)"
    arrow = "⬆️" if b.get("amount", 0) > 0 else "⬇️"
    stat  = "ATK" if b.get("stat") == "attack" else "DEF"
    return f"{arrow}{stat}({b['turns_left']}T)"

user_id = get_current_user_id()

# ─── パーティ・敵データ確認 ──────────────────────────────────
if not st.session_state.get("party"):
    with SessionLocal() as db:
        party = PartyMember.get_party_characters(db, user_id)
    st.session_state["party"] = party

party = st.session_state["party"]
enemies = st.session_state.get("battle_enemies", [])

if not party or not enemies:
    # battle_result が残っている場合は戦闘直後の正常遷移（switch_page の再レンダリング等）
    # 警告を出さずダンジョンへ自動遷移する
    if st.session_state.get("battle_result"):
        st.switch_page("pages/2_dungeon.py")
    st.warning("戦闘データがありません。")
    st.page_link("pages/2_dungeon.py", label="🏰 ダンジョンへ戻る")
    st.stop()

# ─── BattleEngine を session_state で管理 ───────────────────
# engine はシリアライズできないため、turn / log / defending を session_state で保持
if "battle_turn" not in st.session_state:
    st.session_state["battle_turn"] = 1
if "battle_log" not in st.session_state:
    st.session_state["battle_log"] = []
if "defending_chars" not in st.session_state:
    st.session_state["defending_chars"] = set()
if "selected_attacker_idx" not in st.session_state:
    st.session_state["selected_attacker_idx"] = 0
if "selected_enemy_idx" not in st.session_state:
    st.session_state["selected_enemy_idx"] = 0
if "show_skill_panel" not in st.session_state:
    st.session_state["show_skill_panel"] = False
if "pending_skill_id" not in st.session_state:
    st.session_state["pending_skill_id"] = None
if "battle_buffs" not in st.session_state:
    st.session_state["battle_buffs"] = {}
if "battle_hate" not in st.session_state:
    st.session_state["battle_hate"] = {}
if "battle_cooldowns" not in st.session_state:
    st.session_state["battle_cooldowns"] = {}
if "battle_inventory" not in st.session_state:
    st.session_state["battle_inventory"] = []
if "show_item_panel" not in st.session_state:
    st.session_state["show_item_panel"] = False
if "pending_levelups" not in st.session_state:
    st.session_state["pending_levelups"] = []
if "battle_enemy_max_hp" not in st.session_state:
    st.session_state["battle_enemy_max_hp"] = {}
if "battle_enemy_rotation" not in st.session_state:
    st.session_state["battle_enemy_rotation"] = {}
if "auto_battle_enabled" not in st.session_state:
    st.session_state["auto_battle_enabled"] = False
if "ally_policies" not in st.session_state:
    st.session_state["ally_policies"] = {}
if "auto_turn_wait" not in st.session_state:
    st.session_state["auto_turn_wait"] = 5

# 戦闘開始時にインベントリを DB からロード（battle_enemies が初層に設定されたタイミング）
if not st.session_state["battle_inventory"] and st.session_state.get("battle_enemies"):
    with SessionLocal() as db:
        inv_rows = Inventory.get_by_user(db, user_id)
        _all_items = {item.id: item for item in Item.get_all(db)}
    st.session_state["battle_inventory"] = [
        {"item": _all_items[row.item_id], "quantity": row.quantity}
        for row in inv_rows
        if row.item_id in _all_items
    ]

_diff_cfg = DIFFICULTY_PRESETS[st.session_state.get("difficulty", "normal")]
# 戦闘開始時に敵最大HP / ローテーションを初期化（戦闘中は引き継ぐ）
if enemies and not st.session_state["battle_enemy_max_hp"]:
    st.session_state["battle_enemy_max_hp"] = {e.id: e.hp for e in enemies}
if enemies and not st.session_state["battle_enemy_rotation"]:
    st.session_state["battle_enemy_rotation"] = {e.id: 0 for e in enemies}
engine = BattleEngine(
    party, enemies,
    heal_mult=_diff_cfg["heal_mult"],
    exp_mult=_diff_cfg["exp_mult"],
    buffs=st.session_state["battle_buffs"],
    hate=st.session_state["battle_hate"],
    cooldowns=st.session_state["battle_cooldowns"],
    enemy_max_hp=st.session_state["battle_enemy_max_hp"],
    enemy_rotation_idx=st.session_state["battle_enemy_rotation"],
)
engine.turn = st.session_state["battle_turn"]
engine._defending = st.session_state["defending_chars"]

# ─── タイトル ───────────────────────────────────────────────
st.title("⚔️ 戦闘")
st.caption(f"ターン {st.session_state['battle_turn']}")
st.divider()

# ─── 勝敗チェック ────────────────────────────────────────────
if engine.is_all_enemies_dead():
    # EXP/GOLD付与は初回レンダリング時のみ（ボタンクリックによる再レンダリングで二重付与しない）
    if st.session_state.get("battle_result") != "win":
        total_exp = engine.get_total_exp()
        diff_cfg = DIFFICULTY_PRESETS.get(st.session_state.get("difficulty", "normal"), DIFFICULTY_PRESETS["normal"])
        total_gold = int(sum(e.gold_reward for e in enemies) * diff_cfg["gold_mult"])
        pending_lv: list[dict] = []
        with SessionLocal() as db:
            for chara in party:
                if engine.is_party_wiped():
                    break
                if chara.is_alive():
                    levels_gained = chara.gain_exp(db, total_exp)
                    if levels_gained > 0:
                        pending_lv.append({
                            "char_id":    chara.id,
                            "char_name":  chara.name,
                            "class_type": chara.class_type,
                            "levels":     levels_gained,
                            "new_level":  chara.level,
                        })
            User.add_gold(db, user_id, total_gold)
        st.session_state["battle_result"] = "win"
        st.session_state["battle_exp"]    = total_exp
        st.session_state["battle_gold"]   = total_gold
        st.session_state["pending_levelups"] = pending_lv
    st.success(
        f"🎉 勝利！  獲得 EXP: {st.session_state['battle_exp']}  "
        f"💰 獲得 GOLD: {st.session_state.get('battle_gold', 0)} G"
    )
    # ─── レベルアップ成長プラン選択 UI ───────────────────────────────
    _pending = st.session_state.get("pending_levelups", [])
    if _pending:
        _cur = _pending[0]
        _default_plan = CLASS_DEFAULT_LEVELUP_PLAN.get(_cur["class_type"], "balanced")
        st.subheader(f"🌟 {_cur['char_name']} が Lv {_cur['new_level']} になった！")
        if _cur["levels"] > 1:
            st.caption(f"（{_cur['levels']} レベルアップ）")
        st.write("🌱 **成長方針を選んでください**")
        _plan_cols = st.columns(len(LEVEL_UP_PLANS))
        for _pi, (_pkey, _pdata) in enumerate(LEVEL_UP_PLANS.items()):
            with _plan_cols[_pi]:
                _is_default = (_pkey == _default_plan)
                _btn_label = f"{_pdata['label']}{' ★おすすめ' if _is_default else ''}"
                g = _pdata["growth"]
                _help = (
                    f"{_pdata['desc']}\n"
                    f"HP +{g['max_hp'][0]}〜{g['max_hp'][1]}  "
                    f"MP +{g['max_mp'][0]}〜{g['max_mp'][1]}  "
                    f"ATK +{g['attack'][0]}〜{g['attack'][1]}  "
                    f"DEF +{g['defense'][0]}〜{g['defense'][1]}"
                )
                if st.button(
                    _btn_label,
                    key=f"lvup_{_cur['char_id']}_{_pkey}",
                    help=_help,
                    use_container_width=True,
                ):
                    _chara = next((c for c in party if c.id == _cur["char_id"]), None)
                    if _chara:
                        with SessionLocal() as db:
                            _chara.apply_growth(db, _pkey, _cur["levels"])
                    st.session_state["pending_levelups"] = _pending[1:]
                    st.rerun()
        st.stop()
    # battle_enemies のクリアはボタン内で行う（先にクリアすると再レンダリング時に警告が出る）
    if st.button("ダンジョンへ戻る"):
        st.session_state["battle_enemies"] = []
        st.session_state["battle_turn"] = 1
        st.session_state["defending_chars"] = set()
        st.session_state["show_skill_panel"] = False
        st.session_state["show_item_panel"] = False
        st.session_state["battle_inventory"] = []
        st.session_state["battle_exp"]  = 0
        st.session_state["battle_gold"] = 0
        st.session_state["pending_levelups"] = []
        st.session_state["battle_buffs"] = {}
        st.session_state["battle_hate"] = {}
        st.session_state["battle_cooldowns"] = {}
        st.session_state["battle_enemy_max_hp"] = {}
        st.session_state["battle_enemy_rotation"] = {}
        st.switch_page("pages/2_dungeon.py")
    st.stop()

if engine.is_party_wiped():
    st.error("💀 全滅…  ゲームオーバー")
    # HP回復・セッションクリアは初回のみ
    if st.session_state.get("battle_result") != "lose":
        with SessionLocal() as db:
            for chara in party:
                chara.hp = 1
                chara.save(db)
        st.session_state["battle_result"] = "lose"
    if st.button("キャラクター管理へ戻る"):
        st.session_state["battle_enemies"] = []
        st.session_state["battle_turn"] = 1
        st.session_state["defending_chars"] = set()
        st.session_state["show_skill_panel"] = False
        st.session_state["show_item_panel"] = False
        st.session_state["battle_inventory"] = []
        st.session_state["pending_levelups"] = []
        st.session_state["battle_buffs"] = {}
        st.session_state["battle_hate"] = {}
        st.session_state["battle_cooldowns"] = {}
        st.session_state["battle_enemy_max_hp"] = {}
        st.session_state["battle_enemy_rotation"] = {}
        st.switch_page("pages/1_character.py")
    st.stop()

# ─── 敵ステータス ────────────────────────────────────────────
st.subheader("👾 敵")
_buffs = st.session_state.get("battle_buffs", {})
ecols = st.columns(len(enemies))
for i, enemy in enumerate(enemies):
    with ecols[i]:
        alive_mark = "" if enemy.is_alive() else " 💀"
        st.markdown(f"**{enemy.name}{alive_mark}**")
        if enemy.is_boss:
            st.caption("⭐ BOSS")
        st.text(hp_bar(enemy.hp, enemy.hp + 30))  # 表示用（元HPがないため近似）
        st.text(f"ATK {enemy.attack}  DEF {enemy.defense}")
        _ekey = f"e_{enemy.id}"
        _ebuffs = _buffs.get(_ekey, [])
        if _ebuffs:
            st.caption("  ".join(_buff_tag(b) for b in _ebuffs))

st.divider()

# ─── パーティステータス ──────────────────────────────────────
st.subheader("🧑‍🤝‍🧑 パーティ")
# 挑発中 / ヘイト最大のターゲットIDを特定
_hate = st.session_state.get("battle_hate", {})
_alive_p = [c for c in party if c.is_alive()]
_taunting = [c for c in _alive_p if any(b.get("taunt") for b in _buffs.get(f"c_{c.id}", []))]
if _taunting:
    _hate_target_id = max(_taunting, key=lambda c: _hate.get(c.id, 0)).id
elif _alive_p:
    _hate_target_id = max(_alive_p, key=lambda c: _hate.get(c.id, 0)).id
else:
    _hate_target_id = None
pcols = st.columns(len(party))
for i, chara in enumerate(party):
    with pcols[i]:
        alive_mark = "" if chara.is_alive() else " 💀"
        defending_mark = " 🛡️" if chara.id in st.session_state["defending_chars"] else ""
        hate_mark = " 🎯" if chara.is_alive() and chara.id == _hate_target_id else ""
        _ckey = f"c_{chara.id}"
        _cbuffs = _buffs.get(_ckey, [])
        stun_mark = " 💫" if any(b.get("kind") == "stun" for b in _cbuffs if b.get("stat") == "status") else ""
        st.markdown(f"**{chara.name}{alive_mark}{defending_mark}{hate_mark}{stun_mark}**")
        st.caption(class_display_name(chara.class_type))
        st.text(hp_bar(chara.hp, chara.max_hp))
        st.text(f"MP {chara.mp}/{chara.max_mp}")
        if _cbuffs:
            st.caption("  ".join(_buff_tag(b) for b in _cbuffs))

st.divider()

# ─── 行動選択 ────────────────────────────────────────────────
st.subheader("🎮 行動選択")

alive_party = [c for c in party if c.is_alive()]
alive_enemies = [e for e in enemies if e.is_alive()]

if not alive_party:
    st.stop()


def do_enemy_turn():
    msgs = engine.enemy_action()
    st.session_state["battle_log"].extend(msgs)
    # バフ/デバフのカウントダウン
    tick_msgs = engine.tick_buffs()
    if tick_msgs:
        st.session_state["battle_log"].extend(tick_msgs)
    # クールダウンのカウントダウン
    engine.tick_cooldowns()
    st.session_state["battle_turn"] = engine.turn
    st.session_state["defending_chars"] = engine._defending
    # HP を DB に保存
    with SessionLocal() as db:
        for chara in party:
            chara.save(db)
# 自動行動モード トグル
auto_mode = st.toggle(
    "⚙️ 自動行動モード",
    value=st.session_state["auto_battle_enabled"],
    key="auto_toggle",
)
st.session_state["auto_battle_enabled"] = auto_mode
# ─── 自動行動パネル（auto_mode ON 時のみ表示） ─────────────────────
if auto_mode:
    with st.container(border=True):
        st.caption("⚙️ 行動方針設定")
        policy_cols = st.columns(len(alive_party))
        for _pi, _pc in enumerate(alive_party):
            with policy_cols[_pi]:
                _default_pol = CLASS_DEFAULT_POLICY.get(_pc.class_type, "attack")
                _cur_pol = st.session_state["ally_policies"].get(_pc.id, _default_pol)
                _pol_keys = list(ALLY_POLICIES.keys())
                _pol_idx = _pol_keys.index(_cur_pol) if _cur_pol in _pol_keys else 0
                _chosen = st.selectbox(
                    _pc.name,
                    _pol_keys,
                    index=_pol_idx,
                    format_func=lambda k: ALLY_POLICIES[k],
                    key=f"policy_{_pc.id}",
                )
                st.session_state["ally_policies"][_pc.id] = _chosen
        # 待機秒数スライダー
        st.session_state["auto_turn_wait"] = st.slider(
            "⏱️ 待機秒数（行動ごと）",
            min_value=1, max_value=10,
            value=st.session_state["auto_turn_wait"],
            step=1,
            key="wait_slider",
        )

    if st.button("▶ 全員行動", use_container_width=True, type="primary"):
        _wait = st.session_state["auto_turn_wait"]
        _live = st.empty()  # ライブ表示プレースホルダー
        # ── 味方1人行動 → 敵全員行動 を人数分繰り返す ──
        for _ac in alive_party:
            if not _ac.is_alive():
                continue
            # 味方1人が行動
            _pol = st.session_state["ally_policies"].get(
                _ac.id, CLASS_DEFAULT_POLICY.get(_ac.class_type, "attack")
            )
            with SessionLocal() as db:
                _skills = Skill.get_for_class(db, _ac.class_type)
            _msg = engine.ally_auto_action(_ac, _pol, _skills)
            st.session_state["battle_log"].append(_msg)
            _live.info(f"🗡️ {_msg}")
            time.sleep(_wait)
            # 敵が全滅したら終了
            if engine.is_all_enemies_dead():
                break
            # 敵全員が行動
            _enemy_msgs = engine.enemy_action()
            st.session_state["battle_log"].extend(_enemy_msgs)
            _tick_msgs = engine.tick_buffs()
            if _tick_msgs:
                st.session_state["battle_log"].extend(_tick_msgs)
            engine.tick_cooldowns()
            st.session_state["battle_turn"] = engine.turn
            st.session_state["defending_chars"] = engine._defending
            with SessionLocal() as db:
                for chara in party:
                    chara.save(db)
            with _live.container():
                for _em in _enemy_msgs:
                    st.warning(f"👾 {_em}")
            time.sleep(_wait)
            # パーティ全滅したら終了
            if engine.is_party_wiped():
                break
        st.rerun()

    st.stop()

# 手動行動 UI（auto_mode OFF 時）
# キャラクター・敵選択 — 同名が並んでも区別できるよう一意なラベルを生成する
def _unique_labels(objs) -> list[str]:
    # キャラクターは「名前（クラス）」、敵は「名前」をベースラベルにする
    seen: dict[str, int] = {}
    bases = []
    for o in objs:
        if hasattr(o, "class_type"):
            base = f"{o.name}（{class_display_name(o.class_type)}）"
        else:
            base = o.name
        seen[base] = seen.get(base, 0) + 1
        bases.append(base)
    # 重複ラベルには連番を付ける
    count: dict[str, int] = {}
    result = []
    for base in bases:
        count[base] = count.get(base, 0) + 1
        if seen[base] > 1:
            result.append(f"{base}#{count[base]}")
        else:
            result.append(base)
    return result

attacker_labels = _unique_labels(alive_party)
selected_attacker_idx = st.selectbox(
    "行動するキャラクター",
    range(len(attacker_labels)),
    format_func=lambda i: attacker_labels[i],
    key="attacker_select",
)
attacker = alive_party[selected_attacker_idx]

# ─── 統合対象選択プルダウン（👾 敵 / 💚 味方） ────────────────────
# alive_enemies → alive_party の順で並べた 1 本のセレクトボックス
alive_targets = alive_enemies + alive_party
_num_enemies  = len(alive_enemies)

def _target_labels(enemies, chars) -> list[str]:
    """👾 敵 と 💚 味方 に分けてラベルを生成。同名には連番を付ける。"""
    raw_bases = [e.name for e in enemies] + [
        f"{c.name}（{class_display_name(c.class_type)}）" for c in chars
    ]
    prefixes = ["👾"] * len(enemies) + ["💚"] * len(chars)
    total: dict[str, int] = {}
    for b in raw_bases:
        total[b] = total.get(b, 0) + 1
    seen: dict[str, int] = {}
    result = []
    for prefix, base in zip(prefixes, raw_bases):
        seen[base] = seen.get(base, 0) + 1
        suffix = f"#{seen[base]}" if total[base] > 1 else ""
        result.append(f"{prefix} {base}{suffix}")
    return result

target_labels_combined = _target_labels(alive_enemies, alive_party)
selected_target_idx = st.selectbox(
    "対象を選ぶ",
    range(len(target_labels_combined)),
    format_func=lambda i: target_labels_combined[i],
    key="target_select",
)

# インデックスで敵・味方を判別して attack 用と heal 用に振り分ける
_is_enemy  = selected_target_idx < _num_enemies
target_enemy = alive_enemies[selected_target_idx] if _is_enemy else alive_enemies[0]
target_heal  = alive_party[selected_target_idx - _num_enemies] if not _is_enemy else (alive_party[0] if alive_party else attacker)

# アイテムパネルが開いているとき: 全パーティ（戦闘不能含む）を対象に
_show_item = st.session_state.get("show_item_panel", False)
_item_target_pool = party if _show_item else alive_party
_item_target_labels = _unique_labels(_item_target_pool)
if _show_item and _item_target_pool:
    _item_target_sel_idx = st.selectbox(
        "🎒 アイテム対象を選ぶ",
        range(len(_item_target_labels)),
        format_func=lambda i: _item_target_labels[i],
        key="item_target_select",
    )
    item_target = _item_target_pool[_item_target_sel_idx]
else:
    item_target = alive_party[0] if alive_party else attacker

# ─── 行動ボタン ───────────────────────────────────────────────
btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)


with btn_col1:
    if st.button("⚔️ 攻撃", use_container_width=True):
        msg = engine.player_action(attacker, "attack", target=target_enemy)
        st.session_state["battle_log"].append(msg)
        st.session_state["show_skill_panel"] = False
        st.session_state["show_item_panel"] = False
        if not engine.is_all_enemies_dead():
            do_enemy_turn()
        st.rerun()

with btn_col2:
    if st.button("✨ スキル", use_container_width=True):
        st.session_state["show_skill_panel"] = not st.session_state["show_skill_panel"]
        st.session_state["show_item_panel"] = False
        st.rerun()

with btn_col3:
    if st.button("🛡️ 防御", use_container_width=True):
        msg = engine.player_action(attacker, "defend")
        st.session_state["battle_log"].append(msg)
        st.session_state["defending_chars"] = engine._defending
        st.session_state["show_skill_panel"] = False
        st.session_state["show_item_panel"] = False
        do_enemy_turn()
        st.rerun()

with btn_col4:
    if st.button("🎒 アイテム", use_container_width=True):
        st.session_state["show_item_panel"] = not st.session_state["show_item_panel"]
        st.session_state["show_skill_panel"] = False
        st.rerun()

# ─── スキルパネル ─────────────────────────────────────────────
if st.session_state.get("show_skill_panel"):
    st.subheader("✨ スキル選択")
    with SessionLocal() as db:
        skills = Skill.get_for_class(db, attacker.class_type)

    if not skills:
        st.info("使えるスキルがありません。")
    else:
        st.caption("⬆️ バフ系は自動で対象を判定。回復・攻撃は「対象を選ぶ」で選択してください")
        skill_cols = st.columns(len(skills))
        for i, skill in enumerate(skills):
            with skill_cols[i]:
                cd = engine.get_skill_cooldown(attacker, skill)
                can_use = attacker.mp >= skill.mp_cost and cd == 0
                effect_icon = {
                    "attack":    "⚔️",
                    "heal":      "💚",
                    "buff":      "⬆️",
                    "buff_atk":  "⬆️ATK",
                    "buff_def":  "⬆️DEF",
                    "debuff_atk": "⬇️ATK",
                    "debuff_def": "⬇️DEF",
                    "poison":   "☠️",
                    "stun":     "💫",
                    "silence":  "🤐",
                    "def_down": "🔓",
                    "cure":     "✨",
                }.get(skill.effect_type, "")
                if cd > 0:
                    label = f"⏳ {skill.name}\nあと{cd}T"
                    help_text = f"CD: あと {cd} ターン"
                else:
                    label = f"{effect_icon} {skill.name}\nMP:{skill.mp_cost}"
                    help_text = None
                if st.button(label, key=f"skill_{skill.id}",
                             disabled=not can_use,
                             help=help_text,
                             use_container_width=True):
                    etype = skill.effect_type
                    if etype == "heal":
                        msg = engine.player_action(attacker, "skill", target=target_heal, skill=skill)
                    elif etype == "cure":
                        msg = engine.player_action(attacker, "skill", target=target_heal, skill=skill)
                    elif etype in ("buff_atk", "buff_def", "buff"):
                        msg = engine.player_action(attacker, "skill", target=attacker, skill=skill)
                    elif etype in ("debuff_atk", "debuff_def", "poison", "stun", "silence", "def_down"):
                        msg = engine.player_action(attacker, "skill", target=target_enemy, skill=skill)
                    else:
                        msg = engine.player_action(attacker, "skill", target=target_enemy, skill=skill)
                    st.session_state["battle_log"].append(msg)
                    st.session_state["show_skill_panel"] = False
                    st.session_state["pending_skill_id"] = None
                    if not engine.is_all_enemies_dead():
                        do_enemy_turn()
                    st.rerun()

# ─── アイテムパネル ───────────────────────────────────────────
if st.session_state.get("show_item_panel"):
    st.subheader("🎒 アイテム選択")
    inv = st.session_state.get("battle_inventory", [])
    if not inv:
        st.info("アイテムを所持していません。")
    else:
        _effect_icons = {
            "heal_hp":    "💊",
            "heal_hp_pct": "💊",
            "heal_mp":    "🔵",
            "revive":     "🪶",
            "cure":       "✨",
            "buff_atk":   "⬆️ATK",
            "buff_def":   "⬆️DEF",
        }
        item_cols = st.columns(min(len(inv), 4))
        for i, entry in enumerate(inv):
            item = entry["item"]
            qty  = entry["quantity"]
            with item_cols[i % len(item_cols)]:
                icon = _effect_icons.get(item.effect_type, "🎁")
                st.markdown(f"**{icon} {item.name}**")
                st.caption(item.description)
                st.text(f"残 {qty} 個")
                if st.button("使用", key=f"item_{item.id}", disabled=(qty <= 0), use_container_width=True):
                    # DB を更新
                    with SessionLocal() as db:
                        ok = Inventory.use_item(db, user_id, item.id)
                    if ok:
                        # session_state のキャッシュも -1
                        entry["quantity"] -= 1
                        msg = engine.use_item(attacker, item, target=item_target)
                        st.session_state["battle_log"].append(msg)
                        st.session_state["show_item_panel"] = False
                        if not engine.is_all_enemies_dead():
                            do_enemy_turn()
                        # DB に HP/MP を保存
                        with SessionLocal() as db:
                            for chara in party:
                                chara.save(db)
                        st.rerun()
                    else:
                        st.warning("アイテムの消費に失敗しました。")



# ─── 戦闘ログ ────────────────────────────────────────────────
st.subheader("📜 戦闘ログ")
log_lines = st.session_state["battle_log"][-30:]
for line in reversed(log_lines):
    st.text(line)
