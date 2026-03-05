"""
tests/test_battle.py - BattleEngine のユニットテスト
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import MagicMock
from game.battle import BattleEngine
from models.character import Character
from models.enemy import Enemy
from models.skill import Skill


def make_character(name="勇者", class_type="warrior", hp=100, mp=30, attack=15, defense=8) -> Character:
    c = Character()
    c.id = 1
    c.name = name
    c.class_type = class_type
    c.hp = hp
    c.max_hp = hp
    c.mp = mp
    c.max_mp = mp
    c.attack = attack
    c.defense = defense
    c.level = 1
    c.exp = 0
    return c


def make_enemy(name="スライム", hp=20, attack=5, defense=2, exp_reward=10) -> Enemy:
    e = Enemy()
    e.id = 1
    e.name = name
    e.hp = hp
    e.attack = attack
    e.defense = defense
    e.exp_reward = exp_reward
    e.is_boss = False
    return e


# ─── ダメージ計算テスト ────────────────────────────────────
class TestCalcDamage:
    def setup_method(self):
        self.engine = BattleEngine([make_character()], [make_enemy()])

    def test_damage_is_positive(self):
        for _ in range(20):
            dmg = self.engine.calc_damage(15, 5)
            assert dmg >= 1

    def test_damage_with_zero_atk(self):
        dmg = self.engine.calc_damage(0, 10)
        assert dmg >= 1


# ─── 通常攻撃テスト ────────────────────────────────────────
class TestPlayerAttack:
    def setup_method(self):
        self.chara = make_character()
        self.enemy = make_enemy(hp=50)
        self.engine = BattleEngine([self.chara], [self.enemy])

    def test_attack_reduces_enemy_hp(self):
        before_hp = self.enemy.hp
        msg = self.engine.player_action(self.chara, "attack", target=self.enemy)
        assert self.enemy.hp < before_hp
        assert self.enemy.name in msg

    def test_attack_kills_enemy(self):
        self.enemy.hp = 1
        msg = self.engine.player_action(self.chara, "attack", target=self.enemy)
        assert not self.enemy.is_alive()
        assert "倒した" in msg


# ─── スキルテスト ─────────────────────────────────────────
class TestSkillAction:
    def setup_method(self):
        self.chara = make_character(mp=30)
        self.enemy = make_enemy(hp=50)
        self.engine = BattleEngine([self.chara], [self.enemy])

    def _make_skill(self, effect_type="attack", mp_cost=10, power=20):
        s = Skill()
        s.name = "テストスキル"
        s.effect_type = effect_type
        s.mp_cost = mp_cost
        s.power = power
        return s

    def test_attack_skill_costs_mp(self):
        skill = self._make_skill("attack", mp_cost=10)
        before_mp = self.chara.mp
        self.engine.player_action(self.chara, "skill", target=self.enemy, skill=skill)
        assert self.chara.mp == before_mp - 10

    def test_heal_skill_restores_hp(self):
        self.chara.hp = 50
        skill = self._make_skill("heal", mp_cost=8, power=30)
        self.engine.player_action(self.chara, "skill", target=self.chara, skill=skill)
        assert self.chara.hp > 50

    def test_skill_fails_if_no_mp(self):
        self.chara.mp = 0
        skill = self._make_skill("attack", mp_cost=10)
        msg = self.engine.player_action(self.chara, "skill", target=self.enemy, skill=skill)
        assert "足りない" in msg


# ─── 防御テスト ───────────────────────────────────────────
class TestDefend:
    def setup_method(self):
        self.chara = make_character()
        self.enemy = make_enemy(attack=20, defense=0)
        self.engine = BattleEngine([self.chara], [self.enemy])

    def test_defend_adds_to_defending_set(self):
        self.engine.player_action(self.chara, "defend")
        assert self.chara.id in self.engine._defending

    def test_defending_reduces_damage(self):
        import random
        random.seed(42)
        self.chara.hp = 100
        self.engine.player_action(self.chara, "defend")
        msgs = self.engine.enemy_action()
        hp_with_defend = self.chara.hp

        # 防御なし
        self.chara.hp = 100
        random.seed(42)
        self.engine2 = BattleEngine([self.chara], [self.enemy])
        self.engine2.enemy_action()
        hp_without_defend = self.chara.hp

        assert hp_with_defend >= hp_without_defend


# ─── 勝敗判定テスト ──────────────────────────────────────
class TestWinLose:
    def test_all_enemies_dead(self):
        chara = make_character()
        enemy = make_enemy(hp=0)
        engine = BattleEngine([chara], [enemy])
        assert engine.is_all_enemies_dead()

    def test_party_wiped(self):
        chara = make_character(hp=0)
        enemy = make_enemy()
        engine = BattleEngine([chara], [enemy])
        assert engine.is_party_wiped()

    def test_get_total_exp(self):
        chara = make_character()
        e1 = make_enemy(hp=0, exp_reward=10)
        e2 = make_enemy(hp=0, exp_reward=20)
        engine = BattleEngine([chara], [e1, e2])
        assert engine.get_total_exp() == 30
