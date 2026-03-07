"""
game/battle.py - BattleEngine クラス

バフ/デバフ辞書（buffs）の構造:
  キー  : "c_{character.id}"（味方）/ "e_{enemy.id}"（敵）
  値    : list[{"stat": "attack"|"defense",
                "amount": int,          # 正=バフ 負=デバフ
                "turns_left": int,
                "source": str}]         # スキル名
"""

from __future__ import annotations
import random
from models.character import Character
from models.enemy import Enemy
from models.skill import Skill


class BattleEngine:
    def __init__(
        self,
        party: list[Character],
        enemies: list[Enemy],
        heal_mult: float = 1.0,
        exp_mult: float = 1.0,
        buffs: dict | None = None,
    ) -> None:
        self.party = party
        self.enemies = enemies
        self.turn: int = 1
        self.log: list[str] = []
        self._defending: set[int] = set()
        self.heal_mult = heal_mult
        self.exp_mult = exp_mult
        # buffs は session_state["battle_buffs"] と同一オブジェクトを共有する
        self.buffs: dict = buffs if buffs is not None else {}

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
        bonus = sum(b["amount"] for b in self.buffs.get(key, []) if b["stat"] == "defense")
        return max(0, entity.defense + bonus)

    def apply_buff(self, target, stat: str, amount: int, duration: int, source: str) -> str:
        """バフ/デバフを付与する。同一ソース・同一ステータスは上書き。"""
        key = self._entity_key(target)
        if key not in self.buffs:
            self.buffs[key] = []
        self.buffs[key] = [
            b for b in self.buffs[key]
            if not (b["stat"] == stat and b["source"] == source)
        ]
        self.buffs[key].append({"stat": stat, "amount": amount, "turns_left": duration, "source": source})
        direction = "上昇" if amount > 0 else "低下"
        stat_name = "攻撃力" if stat == "attack" else "防御力"
        return f"{target.name} の{stat_name}が {abs(amount)} {direction}！（{duration}ターン）"

    def tick_buffs(self) -> list[str]:
        """ターン終了時にカウントダウン。期限切れを削除してメッセージを返す。"""
        messages: list[str] = []
        for key in list(self.buffs.keys()):
            new_list = []
            for b in self.buffs[key]:
                b["turns_left"] -= 1
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

        if action == "attack":
            if target is None or hasattr(target, "class_type"):
                return "攻撃対象が指定されていません。"
            atk = self.get_effective_attack(character)
            def_ = self.get_effective_defense(target)
            dmg = self.calc_damage(atk, def_)
            actual = target.take_damage(dmg)
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
                msg = f"{character.name} の {skill.name}！ {target.name} に {actual} のダメージ！"
                if not target.is_alive():
                    msg += f" {target.name} を倒した！"
                return msg

            elif etype == "heal":
                heal_target = target if (target is not None and hasattr(target, "class_type")) else character
                heal_amount = max(1, int((character.attack + skill.power) * self.heal_mult))
                healed = heal_target.heal(heal_amount)
                return f"{character.name} の {skill.name}！ {heal_target.name} の HP が {healed} 回復！"

            elif etype in ("buff_atk", "buff_def", "debuff_atk", "debuff_def"):
                stat = "attack" if "atk" in etype else "defense"
                amount = skill.power if etype.startswith("buff") else -skill.power
                duration = getattr(skill, "duration", 3) or 3
                target_type = getattr(skill, "target_type", "self") or "self"

                if target_type == "all_allies":
                    msgs = [
                        self.apply_buff(ally, stat, amount, duration, skill.name)
                        for ally in self.party if ally.is_alive()
                    ]
                    return f"{character.name} の {skill.name}！ " + " / ".join(msgs)
                elif target_type == "all_enemies":
                    msgs = [
                        self.apply_buff(e, stat, amount, duration, skill.name)
                        for e in self.enemies if e.is_alive()
                    ]
                    return f"{character.name} の {skill.name}！ " + " / ".join(msgs)
                else:
                    buff_target = (
                        character if target_type == "self"
                        else (target if target is not None else character)
                    )
                    msg = self.apply_buff(buff_target, stat, amount, duration, skill.name)
                    return f"{character.name} の {skill.name}！ {msg}"

            # 後方互換: 旧 buff effect_type（永続バフを置き換え）
            elif etype == "buff":
                duration = getattr(skill, "duration", 3) or 3
                msg = self.apply_buff(character, "attack", max(1, skill.power // 5), duration, skill.name)
                return f"{character.name} の {skill.name}！ {msg}"

            return f"{character.name} の {skill.name}！（効果なし）"

        elif action == "defend":
            self._defending.add(character.id)
            return f"{character.name} は防御態勢をとった！"

        return "不明なアクション。"

    # ──────────────────────────────────────────────────────
    # 敵ターン
    # ──────────────────────────────────────────────────────
    def enemy_action(self) -> list[str]:
        """全生存敵がランダムなパーティメンバーに攻撃する"""
        messages: list[str] = []
        alive_party = [c for c in self.party if c.is_alive()]
        if not alive_party:
            return messages

        for enemy in self.enemies:
            if not enemy.is_alive():
                continue
            target = random.choice(alive_party)
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
