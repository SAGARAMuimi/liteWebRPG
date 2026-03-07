"""
game/battle.py - BattleEngine クラス

バフ/デバフ辞書（buffs）の構造:
  キー  : "c_{character.id}"（味方）/ "e_{enemy.id}"（敵）
  値    : list[{"stat": "attack"|"defense",
                "amount": int,          # 正=バフ 負=デバフ
                "turns_left": int,
                "source": str,          # スキル名
                "taunt": bool}]         # True=挑発中（ターゲット最優先）

ヘイト辞書（hate）の構造:
  キー  : character.id（int）
  値    : int（ヘイト値。行動ごとに増加し、敵のターゲット選択に使われる）
  初期値: 全キャラクター 10。挑発発動時に +200。攻撃/スキル使用時に実ダメージ分投加。
"""

from __future__ import annotations
import random
from models.character import Character
from models.enemy import Enemy
from models.skill import Skill

_STATUS_NAMES: dict[str, str] = {
    "poison":   "毒",
    "stun":     "スタン",
    "def_down": "防御低下",
    "silence":  "沈黙",
}


class BattleEngine:
    def __init__(
        self,
        party: list[Character],
        enemies: list[Enemy],
        heal_mult: float = 1.0,
        exp_mult: float = 1.0,
        buffs: dict | None = None,
        hate: dict | None = None,
    ) -> None:
        self.party = party
        self.enemies = enemies
        self.turn: int = 1
        self.log: list[str] = []
        self._defending: set[int] = set()
        self.heal_mult = heal_mult
        self.exp_mult = exp_mult
        # buffs/hate は session_state と同一オブジェクトを共有する
        self.buffs: dict = buffs if buffs is not None else {}
        self.hate: dict[int, int] = hate if hate is not None else {}
        # パーティ全員の初期ヘイトを設定（新規エントリのみ）
        for c in self.party:
            if c.id not in self.hate:
                self.hate[c.id] = 10

    # ──────────────────────────────────────────────────────
    # バフ/デバフ ユーティリティ
    # ──────────────────────────────────────────────────────
    @staticmethod
    def _entity_key(entity) -> str:
        return f"c_{entity.id}" if hasattr(entity, "class_type") else f"e_{entity.id}"

    def get_effective_attack(self, entity) -> int:
        key = self._entity_key(entity)
        bonus = sum(b["amount"] for b in self.buffs.get(key, []) if b["stat"] == "attack")
        return max(1, entity.attack + bonus)

    def get_effective_defense(self, entity) -> int:
        key = self._entity_key(entity)
        bonus = sum(b["amount"] for b in self.buffs.get(key, []) if b.get("stat") == "defense")
        base = max(0, entity.defense + bonus)
        if self.has_status(entity, "def_down"):
            base = base // 2  # 防御低下: 50%減
        return base

    def apply_buff(self, target, stat: str, amount: int, duration: int, source: str, taunt: bool = False) -> str:
        """バフ/デバフを付与する。同一ソース・同一ステータスは上書き。"""
        key = self._entity_key(target)
        if key not in self.buffs:
            self.buffs[key] = []
        self.buffs[key] = [
            b for b in self.buffs[key]
            if not (b["stat"] == stat and b["source"] == source)
        ]
        self.buffs[key].append({"stat": stat, "amount": amount, "turns_left": duration, "source": source, "taunt": taunt})
        direction = "上昇" if amount > 0 else "低下"
        stat_name = "攻撃力" if stat == "attack" else "防御力"
        return f"{target.name} の{stat_name}が {abs(amount)} {direction}！（{duration}ターン）"

    # ──────────────────────────────────────────────────────
    # ヘイト管理
    # ──────────────────────────────────────────────────────
    def add_hate(self, character: Character, amount: int) -> None:
        """ヘイト値を加算する（低満 10）"""
        self.hate[character.id] = max(10, self.hate.get(character.id, 10) + amount)

    def _select_target(self) -> "Character | None":
        """
        敵の攻撃対象をヘイトに基づいて選択する。
        - 挑発中（taunt フラグ）のキャラがいれば最優先。
        - それ以外はヘイト値を重みにした確率選択。
        """
        alive = [c for c in self.party if c.is_alive()]
        if not alive:
            return None
        # 挑発中のキャラを優先選択
        taunting = [
            c for c in alive
            if any(b.get("taunt") for b in self.buffs.get(self._entity_key(c), []))
        ]
        if taunting:
            return max(taunting, key=lambda c: self.hate.get(c.id, 10))
        # 通常: ヘイト比率の重み付き確率選択
        weights = [max(1, self.hate.get(c.id, 10)) for c in alive]
        return random.choices(alive, weights=weights, k=1)[0]

    # ──────────────────────────────────────────────────────
    # 状態異常管理
    # ──────────────────────────────────────────────────────
    def _get_entity_by_key(self, key: str):
        """buffs のキーからエンティティオブジェクトを返す"""
        if key.startswith("c_"):
            cid = int(key[2:])
            return next((c for c in self.party if c.id == cid), None)
        elif key.startswith("e_"):
            eid = int(key[2:])
            return next((e for e in self.enemies if e.id == eid), None)
        return None

    def has_status(self, entity, kind: str) -> bool:
        """指定の状態異常を保持中か判定"""
        key = self._entity_key(entity)
        return any(
            b.get("stat") == "status" and b.get("kind") == kind
            for b in self.buffs.get(key, [])
        )

    def apply_status(
        self, target, kind: str, duration: int, source: str
    ) -> str:
        """状態異常を付与する。耐性を持つ敵は無効化する。"""
        resistance = getattr(target, "status_resistance", "") or ""
        name = _STATUS_NAMES.get(kind, kind)
        if kind in resistance:
            return f"{target.name} は {name} を無効化した！"
        key = self._entity_key(target)
        if key not in self.buffs:
            self.buffs[key] = []
        # 同一状態異常は上書き
        self.buffs[key] = [
            b for b in self.buffs[key]
            if not (b.get("stat") == "status" and b.get("kind") == kind)
        ]
        base_hp = getattr(target, "max_hp", target.hp)
        self.buffs[key].append({
            "stat": "status",
            "kind": kind,
            "turns_left": duration,
            "source": source,
            "taunt": False,
            "base_hp": base_hp,
        })
        return f"{target.name} は {name} 状態になった！（{duration}ターン）"

    def tick_buffs(self) -> list[str]:
        """ターン終了時にカウントダウン。期限切れを削除してメッセージを返す。"""
        messages: list[str] = []
        for key in list(self.buffs.keys()):
            entity = self._get_entity_by_key(key)
            new_list = []
            for b in self.buffs[key]:
                b["turns_left"] -= 1
                if b.get("stat") == "status":
                    kind = b.get("kind", "")
                    name = _STATUS_NAMES.get(kind, kind)
                    if b["turns_left"] <= 0:
                        messages.append(f"  「{name}」の効果が切れた。")
                    else:
                        if kind == "poison" and entity and entity.is_alive():
                            base_hp = b.get("base_hp", max(entity.hp, 1))
                            dmg = max(1, base_hp * 5 // 100)
                            entity.take_damage(dmg)
                            messages.append(f"  {entity.name} は毒で {dmg} のダメージを受けた！")
                        new_list.append(b)
                else:
                    if b["turns_left"] <= 0:
                        stat_name = "攻撃力" if b["stat"] == "attack" else "防御力"
                        messages.append(f"  {stat_name}「{b['source']}」の効果が切れた。")
                    else:
                        new_list.append(b)
            self.buffs[key] = new_list
            if not new_list:
                del self.buffs[key]
        return messages

    # ──────────────────────────────────────────────────────
    # ダメージ計算
    # ──────────────────────────────────────────────────────
    def calc_damage(self, attacker_atk: int, defender_def: int) -> int:
        base = max(1, attacker_atk - defender_def)
        return max(1, base + random.randint(-2, 2))

    def calc_skill_damage(self, attacker_atk: int, skill_power: int, defender_def: int) -> int:
        return max(1, attacker_atk + skill_power - defender_def)

    # ──────────────────────────────────────────────────────
    # プレイヤーターン
    # ──────────────────────────────────────────────────────
    def player_action(
        self,
        character: Character,
        action: str,
        target: Enemy | Character | None = None,
        skill: Skill | None = None,
    ) -> str:
        if not character.is_alive():
            return f"{character.name} は戦闘不能のため行動できない！"

        # スタンチェック（全行動ブロック）
        if self.has_status(character, "stun"):
            return f"{character.name} はスタン状態で行動できない！"

        # 沈黙チェック（スキルのみ）
        if action == "skill" and self.has_status(character, "silence"):
            return f"{character.name} は沈黙状態でスキルが使えない！"

        if action == "attack":
            if target is None or hasattr(target, "class_type"):
                return "攻撃対象が指定されていません。"
            atk = self.get_effective_attack(character)
            def_ = self.get_effective_defense(target)
            dmg = self.calc_damage(atk, def_)
            actual = target.take_damage(dmg)
            self.add_hate(character, actual)
            msg = f"{character.name} の攻撃！ {target.name} に {actual} のダメージ！"
            if not target.is_alive():
                msg += f" {target.name} を倒した！"
            return msg

        elif action == "skill":
            if skill is None:
                return "スキルが指定されていません。"
            if character.mp < skill.mp_cost:
                return f"{character.name} の MP が足りない！"
            character.mp -= skill.mp_cost

            etype = skill.effect_type

            if etype == "attack":
                if target is None or hasattr(target, "class_type"):
                    return "攻撃対象が指定されていません。"
                atk = self.get_effective_attack(character)
                def_ = self.get_effective_defense(target)
                dmg = self.calc_skill_damage(atk, skill.power, def_)
                actual = target.take_damage(dmg)
                self.add_hate(character, actual)
                msg = f"{character.name} の {skill.name}！ {target.name} に {actual} のダメージ！"
                if not target.is_alive():
                    msg += f" {target.name} を倒した！"
                return msg

            elif etype == "heal":
                heal_target = target if (target is not None and hasattr(target, "class_type")) else character
                heal_amount = max(1, int((character.attack + skill.power) * self.heal_mult))
                healed = heal_target.heal(heal_amount)
                self.add_hate(character, max(1, healed // 2))
                return f"{character.name} の {skill.name}！ {heal_target.name} の HP が {healed} 回復！"

            elif etype in ("buff_atk", "buff_def", "debuff_atk", "debuff_def"):
                stat = "attack" if "atk" in etype else "defense"
                amount = skill.power if etype.startswith("buff") else -skill.power
                duration = getattr(skill, "duration", 3) or 3
                target_type = getattr(skill, "target_type", "self") or "self"
                is_taunt = (skill.name == "挑発")

                if target_type == "all_allies":
                    msgs = [
                        self.apply_buff(ally, stat, amount, duration, skill.name)
                        for ally in self.party if ally.is_alive()
                    ]
                    self.add_hate(character, 15)
                    return f"{character.name} の {skill.name}！ " + " / ".join(msgs)
                elif target_type == "all_enemies":
                    msgs = [
                        self.apply_buff(e, stat, amount, duration, skill.name)
                        for e in self.enemies if e.is_alive()
                    ]
                    self.add_hate(character, 20)
                    return f"{character.name} の {skill.name}！ " + " / ".join(msgs)
                else:
                    buff_target = (
                        character if target_type == "self"
                        else (target if target is not None else character)
                    )
                    msg = self.apply_buff(buff_target, stat, amount, duration, skill.name, taunt=is_taunt)
                    if is_taunt:
                        self.add_hate(character, 200)  # 挑発: 大幅なヘイトブースト
                        return f"{character.name} の {skill.name}！ {msg} 敵の注目を集めた！"
                    self.add_hate(character, 10)
                    return f"{character.name} の {skill.name}！ {msg}"

            # 後方互換: 旧 buff effect_type（永続バフを置き換え）
            elif etype == "buff":
                duration = getattr(skill, "duration", 3) or 3
                msg = self.apply_buff(character, "attack", max(1, skill.power // 5), duration, skill.name)
                self.add_hate(character, 10)
                return f"{character.name} の {skill.name}！ {msg}"
            # 状態異常付与
            elif etype in ("poison", "stun", "silence", "def_down"):
                duration = getattr(skill, "duration", 3) or 3
                target_type = getattr(skill, "target_type", "enemy") or "enemy"
                if target_type == "all_enemies":
                    msgs = [
                        self.apply_status(e, etype, duration, skill.name)
                        for e in self.enemies if e.is_alive()
                    ]
                    self.add_hate(character, 20)
                    return f"{character.name} の {skill.name}！ " + " / ".join(msgs)
                else:
                    if target is None or hasattr(target, "class_type"):
                        return "攻撃対象が指定されていません。"
                    msg = self.apply_status(target, etype, duration, skill.name)
                    self.add_hate(character, 15)
                    return f"{character.name} の {skill.name}！ {msg}"

            # 状態異常治療
            elif etype == "cure":
                cure_target = (
                    target if (target is not None and hasattr(target, "class_type"))
                    else character
                )
                c_key = self._entity_key(cure_target)
                removed = [
                    _STATUS_NAMES.get(b.get("kind", ""), b.get("kind", ""))
                    for b in self.buffs.get(c_key, []) if b.get("stat") == "status"
                ]
                if c_key in self.buffs:
                    self.buffs[c_key] = [b for b in self.buffs[c_key] if b.get("stat") != "status"]
                    if not self.buffs[c_key]:
                        del self.buffs[c_key]
                self.add_hate(character, 10)
                if removed:
                    return f"{character.name} の {skill.name}！ {cure_target.name} の {'/' .join(set(removed))} が回復した！"
                return f"{character.name} の {skill.name}！ {cure_target.name} は正常状態だった。"
            return f"{character.name} の {skill.name}！（効果なし）"

        elif action == "defend":
            self._defending.add(character.id)
            self.add_hate(character, 5)
            return f"{character.name} は防御態勢をとった！"

        return "不明なアクション。"

    # ──────────────────────────────────────────────────────
    # 敵ターン
    # ──────────────────────────────────────────────────────
    def enemy_action(self) -> list[str]:
        """全生存敵がヘイトに基づいてパーティメンバーを攻撃する"""
        messages: list[str] = []
        if not any(c.is_alive() for c in self.party):
            return messages

        for enemy in self.enemies:
            if not enemy.is_alive():
                continue
            if self.has_status(enemy, "stun"):
                messages.append(f"{enemy.name} はスタン状態で行動できない！")
                continue
            target = self._select_target()
            if target is None:
                continue
            atk = self.get_effective_attack(enemy)
            effective_def = self.get_effective_defense(target)
            if target.id in self._defending:
                effective_def *= 2
            dmg = self.calc_damage(atk, effective_def)
            actual = target.take_damage(dmg)
            msg = f"{enemy.name} の攻撃！ {target.name} に {actual} のダメージ！"
            if not target.is_alive():
                msg += f" {target.name} は倒れた…"
            messages.append(msg)

        self._defending.clear()
        self.turn += 1
        return messages

    # ──────────────────────────────────────────────────────
    # 勝敗判定
    # ──────────────────────────────────────────────────────
    def is_party_wiped(self) -> bool:
        return all(not c.is_alive() for c in self.party)

    def is_all_enemies_dead(self) -> bool:
        return all(not e.is_alive() for e in self.enemies)

    def get_total_exp(self) -> int:
        base = sum(e.exp_reward for e in self.enemies if not e.is_alive())
        return max(1, int(base * self.exp_mult))
