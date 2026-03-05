"""
game/battle.py - BattleEngine クラス
"""

from __future__ import annotations
import random
from models.character import Character
from models.enemy import Enemy
from models.skill import Skill


class BattleEngine:
    def __init__(self, party: list[Character], enemies: list[Enemy]) -> None:
        self.party = party
        self.enemies = enemies
        self.turn: int = 1
        self.log: list[str] = []
        self._defending: set[int] = set()  # 防御中キャラクターの id 集合

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
        """
        action: "attack" | "skill" | "defend"
        戦闘ログメッセージを返す。
        """
        if not character.is_alive():
            return f"{character.name} は戦闘不能のため行動できない！"

        if action == "attack":
            if target is None or hasattr(target, "class_type"):  # Character は class_type を持つ、Enemy は持たない
                return "攻撃対象が指定されていません。"
            dmg = self.calc_damage(character.attack, target.defense)
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

            if skill.effect_type == "attack":
                if target is None or hasattr(target, "class_type"):  # Character は class_type を持つ、Enemy は持たない
                    return "攻撃対象が指定されていません。"
                dmg = self.calc_skill_damage(character.attack, skill.power, target.defense)
                actual = target.take_damage(dmg)
                msg = f"{character.name} の {skill.name}！ {target.name} に {actual} のダメージ！"
                if not target.is_alive():
                    msg += f" {target.name} を倒した！"
                return msg

            elif skill.effect_type == "heal":
                # 回復量 = 術者の攻撃力（魔力に相当）+ スキル威力
                # Character は class_type を持つ、Enemy は持たない
                heal_target = target if (target is not None and hasattr(target, "class_type")) else character
                heal_amount = character.attack + skill.power
                healed = heal_target.heal(heal_amount)
                return f"{character.name} の {skill.name}！ {heal_target.name} の HP が {healed} 回復！（{character.attack}+{skill.power}）"

            elif skill.effect_type == "buff":
                # 簡易バフ: attack 一時強化（本実装では永続強化として扱う）
                character.attack += skill.power // 5
                return f"{character.name} の {skill.name}！ 攻撃力が上がった！"

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
            # 防御中は防御力 2倍 で被ダメ軽減
            effective_def = target.defense * 2 if target.id in self._defending else target.defense
            dmg = self.calc_damage(enemy.attack, effective_def)
            actual = target.take_damage(dmg)
            msg = f"{enemy.name} の攻撃！ {target.name} に {actual} のダメージ！"
            if not target.is_alive():
                msg += f" {target.name} は倒れた…"
            messages.append(msg)

        # 防御フラグをリセット
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
        return sum(e.exp_reward for e in self.enemies if not e.is_alive())
