"""
pages/3_battle.py - 戦闘画面
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import models  # noqa: F401 - 全テーブルを依存順に Base.metadata に登録
import streamlit as st
from models.database import SessionLocal
from models.character import PartyMember
from models.skill import Skill
from game.battle import BattleEngine
from utils.auth import check_login, get_current_user_id
from utils.helpers import hp_bar, class_display_name
from config import APP_TITLE

st.set_page_config(page_title=f"戦闘 | {APP_TITLE}", page_icon="⚔️", layout="wide")
check_login()

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

engine = BattleEngine(party, enemies)
engine.turn = st.session_state["battle_turn"]
engine._defending = st.session_state["defending_chars"]

# ─── タイトル ───────────────────────────────────────────────
st.title("⚔️ 戦闘")
st.caption(f"ターン {st.session_state['battle_turn']}")
st.divider()

# ─── 勝敗チェック ────────────────────────────────────────────
if engine.is_all_enemies_dead():
    # EXP付与は初回レンダリング時のみ（ボタンクリックによる再レンダリングで二重付与しない）
    if st.session_state.get("battle_result") != "win":
        total_exp = engine.get_total_exp()
        leveled: list[str] = []
        with SessionLocal() as db:
            for chara in party:
                if engine.is_party_wiped():
                    break
                if chara.is_alive():
                    up = chara.gain_exp(db, total_exp)
                    if up:
                        leveled.append(chara.name)
        st.session_state["battle_result"] = "win"
        st.session_state["battle_exp"] = total_exp
        st.session_state["battle_leveled"] = leveled
    st.success(f"🎉 勝利！  獲得 EXP: {st.session_state['battle_exp']}")
    if st.session_state.get("battle_leveled"):
        st.info(f"レベルアップ！: {', '.join(st.session_state['battle_leveled'])}")
    # battle_enemies のクリアはボタン内で行う（先にクリアすると再レンダリング時に警告が出る）
    if st.button("ダンジョンへ戻る"):
        st.session_state["battle_enemies"] = []
        st.session_state["battle_turn"] = 1
        st.session_state["defending_chars"] = set()
        st.session_state["show_skill_panel"] = False
        st.session_state["battle_exp"] = 0
        st.session_state["battle_leveled"] = []
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
        st.switch_page("pages/1_character.py")
    st.stop()

# ─── 敵ステータス ────────────────────────────────────────────
st.subheader("👾 敵")
ecols = st.columns(len(enemies))
for i, enemy in enumerate(enemies):
    with ecols[i]:
        alive_mark = "" if enemy.is_alive() else " 💀"
        st.markdown(f"**{enemy.name}{alive_mark}**")
        if enemy.is_boss:
            st.caption("⭐ BOSS")
        st.text(hp_bar(enemy.hp, enemy.hp + 30))  # 表示用（元HPがないため近似）
        st.text(f"ATK {enemy.attack}  DEF {enemy.defense}")

st.divider()

# ─── パーティステータス ──────────────────────────────────────
st.subheader("🧑‍🤝‍🧑 パーティ")
pcols = st.columns(len(party))
for i, chara in enumerate(party):
    with pcols[i]:
        alive_mark = "" if chara.is_alive() else " 💀"
        defending_mark = " 🛡️" if chara.id in st.session_state["defending_chars"] else ""
        st.markdown(f"**{chara.name}{alive_mark}{defending_mark}**")
        st.caption(class_display_name(chara.class_type))
        st.text(hp_bar(chara.hp, chara.max_hp))
        st.text(f"MP {chara.mp}/{chara.max_mp}")

st.divider()

# ─── 行動選択 ────────────────────────────────────────────────
st.subheader("🎮 行動選択")

alive_party = [c for c in party if c.is_alive()]
alive_enemies = [e for e in enemies if e.is_alive()]

if not alive_party:
    st.stop()

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

# ─── 行動ボタン ───────────────────────────────────────────────
btn_col1, btn_col2, btn_col3 = st.columns(3)

def do_enemy_turn():
    msgs = engine.enemy_action()
    st.session_state["battle_log"].extend(msgs)
    st.session_state["battle_turn"] = engine.turn
    st.session_state["defending_chars"] = engine._defending
    # HP を DB に保存
    with SessionLocal() as db:
        for chara in party:
            chara.save(db)

with btn_col1:
    if st.button("⚔️ 攻撃", use_container_width=True):
        msg = engine.player_action(attacker, "attack", target=target_enemy)
        st.session_state["battle_log"].append(msg)
        if not engine.is_all_enemies_dead():
            do_enemy_turn()
        st.rerun()

with btn_col2:
    if st.button("✨ スキル", use_container_width=True):
        st.session_state["show_skill_panel"] = not st.session_state["show_skill_panel"]
        st.rerun()

with btn_col3:
    if st.button("🛡️ 防御", use_container_width=True):
        msg = engine.player_action(attacker, "defend")
        st.session_state["battle_log"].append(msg)
        st.session_state["defending_chars"] = engine._defending
        do_enemy_turn()
        st.rerun()

# ─── スキルパネル ─────────────────────────────────────────────
if st.session_state.get("show_skill_panel"):
    st.subheader("✨ スキル選択")
    with SessionLocal() as db:
        skills = Skill.get_for_class(db, attacker.class_type)

    if not skills:
        st.info("使えるスキルがありません。")
    else:
        st.caption("⬆️ 「対象を選ぶ」で回復先・攻撃先を選択してからスキルを押してください")
        skill_cols = st.columns(len(skills))
        for i, skill in enumerate(skills):
            with skill_cols[i]:
                can_use = attacker.mp >= skill.mp_cost
                effect_icon = {"attack": "⚔️", "heal": "💚", "buff": "⬆️"}.get(skill.effect_type, "")
                label = f"{effect_icon} {skill.name}\nMP:{skill.mp_cost} PWR:{skill.power}"
                if st.button(label, key=f"skill_{skill.id}", disabled=not can_use, use_container_width=True):
                    if skill.effect_type == "heal":
                        # 💚 味方が選択されていれば使用、敵選択時は術者自身を回復
                        msg = engine.player_action(attacker, "skill", target=target_heal, skill=skill)
                    else:
                        # 👾 敵が選択されていれば使用、味方選択時は先頭の生存敵を攻撃
                        msg = engine.player_action(attacker, "skill", target=target_enemy, skill=skill)
                    st.session_state["battle_log"].append(msg)
                    st.session_state["show_skill_panel"] = False
                    st.session_state["pending_skill_id"] = None
                    if not engine.is_all_enemies_dead():
                        do_enemy_turn()
                    st.rerun()

st.divider()

# ─── 戦闘ログ ────────────────────────────────────────────────
st.subheader("📜 戦闘ログ")
log_lines = st.session_state["battle_log"][-30:]
for line in reversed(log_lines):
    st.text(line)
