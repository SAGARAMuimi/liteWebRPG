"""
tests/test_battle.py - BattleEngine のユニットテスト
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import MagicMock
from game.battle import BattleEngine, EnemyAI
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
        s.cooldown = 0  # クールダウンなし（デフォルト）
        s.duration = 0
        s.target_type = "enemy"
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


# ─── ヘイト/ターゲット制御テスト ──────────────────────
class TestHateSystem:
    def setup_method(self):
        self.c1 = make_character(name="勇者", hp=100)
        self.c1.id = 1
        self.c2 = make_character(name="騎士", class_type="knight", hp=140)
        self.c2.id = 2
        self.enemy = make_enemy(attack=10, defense=0)
        self.engine = BattleEngine([self.c1, self.c2], [self.enemy])

    def test_initial_hate_is_set(self):
        """初期ヘイトが全キャラに設定される"""
        assert self.engine.hate[self.c1.id] == 10
        assert self.engine.hate[self.c2.id] == 10

    def test_add_hate_increments(self):
        """add_hate がヘイト値を加算する"""
        self.engine.add_hate(self.c1, 50)
        assert self.engine.hate[self.c1.id] == 60

    def test_attack_increases_hate(self):
        """攻撃後にヘイトが増加する"""
        before = self.engine.hate[self.c1.id]
        self.engine.player_action(self.c1, "attack", target=self.enemy)
        assert self.engine.hate[self.c1.id] > before

    def test_defend_increases_hate_slightly(self):
        """防御でヘイトが少し増える"""
        before = self.engine.hate[self.c1.id]
        self.engine.player_action(self.c1, "defend")
        assert self.engine.hate[self.c1.id] == before + 5

    def test_select_target_prefers_high_hate(self):
        """ヘイトが高いキャラが選ばれやすい"""
        # c2 のヘイトを大幅に上げる
        self.engine.hate[self.c2.id] = 1000
        self.engine.hate[self.c1.id] = 10
        # 100 回引いて c2 が媚鄧混じりの大多数を占めることを確認
        results = [self.engine._select_target().id for _ in range(100)]
        assert results.count(self.c2.id) > 70

    def test_taunt_forces_target(self):
        """挑発中のキャラが必ず選ばれる"""
        # c1 のヘイトを大幅上げても、c2 が挑発中なら c2 が選ばれる
        self.engine.hate[self.c1.id] = 9999
        self.engine.hate[self.c2.id] = 10
        key2 = self.engine._entity_key(self.c2)
        self.engine.buffs[key2] = [{"stat": "defense", "amount": 5, "turns_left": 3, "source": "挑発", "taunt": True}]
        for _ in range(20):
            assert self.engine._select_target().id == self.c2.id

    def test_taunt_expires_after_tick(self):
        """挑発有効期限が切れると通常選択に戻る"""
        key2 = self.engine._entity_key(self.c2)
        self.engine.buffs[key2] = [{"stat": "defense", "amount": 5, "turns_left": 1, "source": "挑発", "taunt": True}]
        self.engine.tick_buffs()  # ターン終了で削除
        assert key2 not in self.engine.buffs or not any(b.get("taunt") for b in self.engine.buffs.get(key2, []))

    def test_select_target_returns_none_if_all_dead(self):
        """味方全滅時に Noneを返す"""
        self.c1.hp = 0
        self.c2.hp = 0
        assert self.engine._select_target() is None


# ─── 状態異常テスト ───────────────────────────────────────
class TestStatusAilment:
    def setup_method(self):
        self.chara = make_character(name="勇者", hp=100, mp=50, attack=15, defense=8)
        self.chara.id = 1
        self.enemy = make_enemy(name="スライム", hp=100, attack=5, defense=2)
        self.enemy.id = 10
        self.enemy.status_resistance = ""
        self.engine = BattleEngine([self.chara], [self.enemy])

    def _make_status_skill(self, effect_type, mp_cost=8, target_type="enemy", duration=3):
        s = Skill()
        s.id = 99
        s.name = f"テスト{effect_type}"
        s.effect_type = effect_type
        s.mp_cost = mp_cost
        s.power = 0
        s.target_type = target_type
        s.duration = duration
        s.cooldown = 0  # クールダウンなし
        return s

    # ── apply_status / has_status ──────────────────────────────────────────────

    def test_apply_status_to_enemy(self):
        """apply_status で敵に状態異常が付与される"""
        msg = self.engine.apply_status(self.enemy, "poison", 3, "テスト")
        assert self.engine.has_status(self.enemy, "poison")
        assert "毒" in msg

    def test_has_status_returns_false_when_no_ailment(self):
        """状態異常がないときは False を返す"""
        assert not self.engine.has_status(self.chara, "stun")

    # ── スタン ────────────────────────────────────────────────────────────────

    def test_stun_blocks_player_action(self):
        """スタン中はプレイヤーの全行動がスキップされる"""
        self.engine.apply_status(self.chara, "stun", 2, "テスト")
        msg = self.engine.player_action(self.chara, "attack", target=self.enemy)
        assert "スタン" in msg

    def test_stun_blocks_enemy_action(self):
        """スタン中は敵の行動がスキップされる"""
        self.engine.apply_status(self.enemy, "stun", 2, "テスト")
        msgs = self.engine.enemy_action()
        assert any("スタン" in m for m in msgs)
        # スタン中は敵が攻撃しないのでダメージなし
        assert self.chara.hp == self.chara.max_hp

    # ── 沈黙 ─────────────────────────────────────────────────────────────────

    def test_silence_blocks_skill_only(self):
        """沈黙中はスキルが使えないが通常攻撃はできる"""
        self.engine.apply_status(self.chara, "silence", 2, "テスト")
        skill = self._make_status_skill("attack", mp_cost=5)
        msg = self.engine.player_action(self.chara, "skill", target=self.enemy, skill=skill)
        assert "沈黙" in msg

    def test_silence_does_not_block_attack(self):
        """沈黙中でも通常攻撃は実行される"""
        self.engine.apply_status(self.chara, "silence", 2, "テスト")
        before_hp = self.enemy.hp
        self.engine.player_action(self.chara, "attack", target=self.enemy)
        assert self.enemy.hp < before_hp  # ダメージあり

    # ── 毒 ───────────────────────────────────────────────────────────────────

    def test_poison_deals_damage_on_tick(self):
        """毒状態のエンティティはtick_buffsでダメージを受ける"""
        self.enemy.max_hp = 100
        self.engine.apply_status(self.enemy, "poison", 3, "テスト")
        before_hp = self.enemy.hp
        logs = self.engine.tick_buffs()
        assert self.enemy.hp < before_hp
        assert any("毒" in l for l in logs)

    def test_poison_via_skill(self):
        """poison スキルで敵に毒が付与される"""
        skill = self._make_status_skill("poison")
        self.engine.player_action(self.chara, "skill", target=self.enemy, skill=skill)
        assert self.engine.has_status(self.enemy, "poison")

    # ── 防御低下 ──────────────────────────────────────────────────────────────

    def test_def_down_halves_defense(self):
        """def_down が付与されると有効防御力が半減する"""
        base_def = self.engine.get_effective_defense(self.enemy)
        self.engine.apply_status(self.enemy, "def_down", 3, "テスト")
        halved_def = self.engine.get_effective_defense(self.enemy)
        assert halved_def <= base_def // 2 + 1

    # ── ボス耐性 ─────────────────────────────────────────────────────────────

    def test_boss_resists_stun(self):
        """status_resistance='stun' の敵にスタンが無効化される"""
        boss = make_enemy(name="ボス", hp=200)
        boss.id = 99
        boss.status_resistance = "stun"
        boss.is_boss = True
        engine = BattleEngine([self.chara], [boss])
        msg = engine.apply_status(boss, "stun", 2, "テスト")
        assert "無効化" in msg
        assert not engine.has_status(boss, "stun")

    # ── 期限切れ ─────────────────────────────────────────────────────────────

    def test_status_expires_after_duration(self):
        """duration ターン後に状態異常が消える"""
        self.engine.apply_status(self.enemy, "poison", 1, "テスト")
        self.engine.tick_buffs()  # 1ターン経過 → 期限切れ
        assert not self.engine.has_status(self.enemy, "poison")

    # ── cure スキル ──────────────────────────────────────────────────────────

    def test_cure_removes_status(self):
        """cure スキルで状態異常が除去される"""
        self.engine.apply_status(self.chara, "poison", 3, "テスト")
        assert self.engine.has_status(self.chara, "poison")
        cure = self._make_status_skill("cure", mp_cost=5, target_type="ally", duration=0)
        self.engine.player_action(self.chara, "skill", target=self.chara, skill=cure)
        assert not self.engine.has_status(self.chara, "poison")


# ─── アイテム使用テスト ────────────────────────────────────
class TestItemUse:
    """BattleEngine.use_item() のユニットテスト"""

    def setup_method(self):
        self.chara = make_character(hp=50, mp=20)
        self.chara.max_hp = 100
        self.chara.max_mp = 30
        self.ally = make_character(name="仲間", hp=40, mp=10)
        self.ally.id = 2
        self.ally.max_hp = 80
        self.ally.max_mp = 20
        self.enemy = make_enemy(hp=30)
        self.engine = BattleEngine([self.chara, self.ally], [self.enemy])

    @staticmethod
    def _make_item(name="テストアイテム", effect_type="heal_hp", power=30,
                   target_type="ally", duration=0):
        item = MagicMock()
        item.id = 99
        item.name = name
        item.effect_type = effect_type
        item.power = power
        item.target_type = target_type
        item.duration = duration
        return item

    def test_heal_hp_item(self):
        """HP回復アイテムを使うと HP が増加する"""
        item = self._make_item("ポーション", effect_type="heal_hp", power=30)
        before = self.chara.hp
        msg = self.engine.use_item(self.chara, item, target=self.chara)
        assert self.chara.hp > before
        assert "回復" in msg

    def test_heal_hp_not_exceed_max(self):
        """HP回復が最大 HP を超えない"""
        self.chara.hp = 90  # 最大 100
        item = self._make_item("ポーション", effect_type="heal_hp", power=30)
        self.engine.use_item(self.chara, item, target=self.chara)
        assert self.chara.hp <= self.chara.max_hp

    def test_heal_mp_item(self):
        """MP回復アイテムを使うと MP が増加する"""
        self.chara.mp = 5
        item = self._make_item("エーテル", effect_type="heal_mp", power=20)
        before = self.chara.mp
        msg = self.engine.use_item(self.chara, item, target=self.chara)
        assert self.chara.mp > before
        assert "回復" in msg

    def test_revive_dead_character(self):
        """蘇生アイテムで HP=0 のキャラが復活する"""
        self.ally.hp = 0
        assert not self.ally.is_alive()
        item = self._make_item("フェニックスの羽", effect_type="revive", power=30)
        msg = self.engine.use_item(self.chara, item, target=self.ally)
        assert self.ally.is_alive()
        assert "蘇生" in msg

    def test_revive_alive_fails(self):
        """生存キャラに蘇生を使うと失敗メッセージを返す"""
        assert self.ally.is_alive()
        item = self._make_item("フェニックスの羽", effect_type="revive", power=30)
        msg = self.engine.use_item(self.chara, item, target=self.ally)
        assert "戦闘不能ではない" in msg

    def test_cure_item_removes_status(self):
        """万能薬で毒が除去される"""
        self.engine.apply_status(self.chara, "poison", 3, "テスト毒")
        assert self.engine.has_status(self.chara, "poison")
        item = self._make_item("万能薬", effect_type="cure", power=0)
        self.engine.use_item(self.chara, item, target=self.chara)
        assert not self.engine.has_status(self.chara, "poison")

    def test_buff_atk_item(self):
        """活力の薬で ATK バフが付与される"""
        item = self._make_item("活力の薬", effect_type="buff_atk", power=3, duration=3)
        msg = self.engine.use_item(self.chara, item, target=self.chara)
        key = self.engine._entity_key(self.chara)
        buffs = self.engine.buffs.get(key, [])
        atk_buffs = [b for b in buffs if b["stat"] == "attack"]
        assert atk_buffs, "ATK バフが付与されていない"
        assert atk_buffs[0]["amount"] == 3
        assert "上昇" in msg


# ─── クールダウンテスト ───────────────────────────────────────
class TestCooldown:
    def setup_method(self):
        self.chara = make_character(mp=50)
        self.enemy = make_enemy(hp=100)
        self.engine = BattleEngine([self.chara], [self.enemy])

    def _make_skill(self, effect_type="attack", mp_cost=10, power=20, cooldown=2):
        s = Skill()
        s.id = 99
        s.name = "CD付きスキル"
        s.effect_type = effect_type
        s.mp_cost = mp_cost
        s.power = power
        s.cooldown = cooldown
        s.duration = 0
        s.target_type = "enemy"
        return s

    def test_no_cooldown_after_use_when_zero(self):
        """cooldown=0 のスキルは使用後にクールダウンが設定されない"""
        s = self._make_skill(cooldown=0)
        self.engine.player_action(self.chara, "skill", target=self.enemy, skill=s)
        assert self.engine.get_skill_cooldown(self.chara, s) == 0

    def test_cooldown_set_after_use(self):
        """cooldown=2 のスキルを使用すると残り2ターンのCDが設定される"""
        s = self._make_skill(cooldown=2)
        self.engine.player_action(self.chara, "skill", target=self.enemy, skill=s)
        assert self.engine.get_skill_cooldown(self.chara, s) == 2

    def test_cooldown_blocks_reuse(self):
        """CD中にスキルを使うとブロックメッセージが返りMPを消費しない"""
        s = self._make_skill(cooldown=2)
        self.engine.player_action(self.chara, "skill", target=self.enemy, skill=s)
        mp_before = self.chara.mp
        msg = self.engine.player_action(self.chara, "skill", target=self.enemy, skill=s)
        assert "使えない" in msg
        assert self.chara.mp == mp_before  # MP を消費しない

    def test_tick_cooldowns_decrements(self):
        """tick_cooldowns を1回呼ぶと残ターンが1減る"""
        s = self._make_skill(cooldown=2)
        self.engine.player_action(self.chara, "skill", target=self.enemy, skill=s)
        self.engine.tick_cooldowns()
        assert self.engine.get_skill_cooldown(self.chara, s) == 1

    def test_tick_cooldowns_clears_when_zero(self):
        """tick_cooldowns で0以下になるとCDエントリが削除される"""
        s = self._make_skill(cooldown=1)
        self.engine.player_action(self.chara, "skill", target=self.enemy, skill=s)
        self.engine.tick_cooldowns()
        assert self.engine.get_skill_cooldown(self.chara, s) == 0  # エントリ削除 → 0 返る

    def test_skill_usable_after_cooldown_expires(self):
        """CD切れ後はスキルが再度使用できる"""
        s = self._make_skill(cooldown=1)
        self.chara.mp = 50
        self.engine.player_action(self.chara, "skill", target=self.enemy, skill=s)
        self.engine.tick_cooldowns()  # CD 0 になる
        mp_before = self.chara.mp
        msg = self.engine.player_action(self.chara, "skill", target=self.enemy, skill=s)
        assert "使えない" not in msg
        assert self.chara.mp < mp_before  # MP を消費した

    def test_cooldown_is_per_character(self):
        """CDは各キャラクター独立して管理される"""
        chara2 = make_character(name="魔法使い", class_type="mage", mp=50)
        chara2.id = 2
        engine2 = BattleEngine([self.chara, chara2], [self.enemy])
        s = self._make_skill(cooldown=2)
        engine2.player_action(self.chara, "skill", target=self.enemy, skill=s)
        # chara1 はCD中だが chara2 はCDなし
        assert engine2.get_skill_cooldown(self.chara, s) == 2
        assert engine2.get_skill_cooldown(chara2, s) == 0


# ─── 敵AI テスト ────────────────────────────────────────────

class TestEnemyAI:
    """R-12 ルールベース敵AI のユニットテスト"""

    def _make_enemy(self, name="スライム", hp=100, attack=10, defense=3):
        e = make_enemy(name=name, hp=hp, attack=attack, defense=defense)
        return e

    def _make_party(self, count=2):
        party = []
        for i in range(count):
            c = make_character(name=f"勇者{i+1}", hp=100, attack=15, defense=5)
            c.id = i + 1
            party.append(c)
        return party

    # ── EnemyAI.get_phase ──────────────────────────────────
    def test_get_phase_normal(self):
        """HP > 50% なら NORMAL フェーズ"""
        e = self._make_enemy(hp=60)
        assert EnemyAI.get_phase(e, max_hp=100) == "NORMAL"

    def test_get_phase_danger_boundary(self):
        """HP = 50% ちょうどは DANGER フェーズ"""
        e = self._make_enemy(hp=50)
        assert EnemyAI.get_phase(e, max_hp=100) == "DANGER"

    def test_get_phase_danger_below(self):
        """HP < 50% は DANGER フェーズ"""
        e = self._make_enemy(hp=30)
        assert EnemyAI.get_phase(e, max_hp=100) == "DANGER"

    # ── EnemyAI.is_win_first ──────────────────────────────
    def test_is_win_first_false_when_hp_high(self):
        """全員 HP > 15% なら WIN_FIRST でない"""
        party = self._make_party()
        # 全員 HP100/max100 = 100% → WIN_FIRST 不要
        assert EnemyAI.is_win_first(party) is False

    def test_is_win_first_true_when_low_hp(self):
        """HP ≤ 15% のキャラがいれば WIN_FIRST"""
        party = self._make_party()
        party[0].hp = 10   # 10/100 = 10% ≤ 15%
        assert EnemyAI.is_win_first(party) is True

    def test_is_win_first_ignores_dead(self):
        """戦闘不能キャラは WIN_FIRST 判定に含めない"""
        party = self._make_party()
        party[0].hp = 0   # 戦闘不能（is_alive = False）
        party[1].hp = 80  # 80% → WIN_FIRST 不要
        assert EnemyAI.is_win_first(party) is False

    # ── EnemyAI.select_win_first_target ───────────────────
    def test_win_first_targets_lowest_hp_ratio(self):
        """最低HP率のキャラをターゲットに選ぶ"""
        party = self._make_party()
        party[0].hp = 30   # 30%
        party[1].hp = 60   # 60%
        target = EnemyAI.select_win_first_target(party)
        assert target.id == party[0].id

    # ── EnemyAI.choose_action ─────────────────────────────
    def test_choose_action_normal_rotation(self):
        """NORMAL フェーズはローテーション順に行動"""
        e = self._make_enemy(name="オーク", hp=100)
        # オークの normal_rotation = ["attack", "heavy_blow", "attack"]
        _, def0 = EnemyAI.choose_action(e, "NORMAL", 0)
        _, def1 = EnemyAI.choose_action(e, "NORMAL", 1)
        _, def2 = EnemyAI.choose_action(e, "NORMAL", 2)
        assert def0["type"] == "attack" and def0.get("power_rate", 1.0) == 1.0
        assert def1["type"] == "attack" and def1.get("power_rate", 1.0) == 1.5
        assert def2["type"] == "attack" and def2.get("power_rate", 1.0) == 1.0

    def test_choose_action_danger_priority(self):
        """DANGER フェーズは danger_priority に切り替わる"""
        e = self._make_enemy(name="ドラゴン", hp=30)
        # ドラゴンの danger_priority = ["breath", "attack"]
        name0, _ = EnemyAI.choose_action(e, "DANGER", 0)
        assert name0 == "breath"

    def test_choose_action_unknown_enemy_uses_default(self):
        """ENEMY_AI_ACTIONS に存在しない敵名は default ルールを使う"""
        e = self._make_enemy(name="謎の怪物", hp=100)
        name, action_def = EnemyAI.choose_action(e, "NORMAL", 0)
        assert action_def["type"] == "attack"

    def test_choose_action_rotation_wraps(self):
        """ローテーションが末尾を超えると先頭に戻る"""
        e = self._make_enemy(name="スライム", hp=100)
        # normal_rotation length = 3
        name_0, _ = EnemyAI.choose_action(e, "NORMAL", 0)
        name_3, _ = EnemyAI.choose_action(e, "NORMAL", 3)
        assert name_0 == name_3

    # ── _execute_enemy_action / enemy_action ──────────────
    def test_enemy_attack_deals_damage(self):
        """enemy_action で敵の通常攻撃がパーティに当たる"""
        party = self._make_party(1)
        enemy = self._make_enemy(name="スライム", hp=50, attack=10)
        engine = BattleEngine(party, [enemy])
        hp_before = party[0].hp
        msgs = engine.enemy_action()
        assert len(msgs) >= 1
        assert party[0].hp < hp_before

    def test_enemy_rotation_index_increments(self):
        """enemy_action を呼ぶたびに rotation_idx が増える"""
        party = self._make_party(1)
        enemy = self._make_enemy(name="オーク", hp=50)
        engine = BattleEngine(party, [enemy])
        engine.enemy_action()
        assert engine.enemy_rotation_idx[enemy.id] == 1
        engine.enemy_action()
        assert engine.enemy_rotation_idx[enemy.id] == 2

    def test_stun_blocks_enemy_action(self):
        """スタン状態の敵は行動できない（スキップされる）"""
        party = self._make_party(1)
        enemy = self._make_enemy(hp=50)
        engine = BattleEngine(party, [enemy])
        engine.apply_status(enemy, "stun", 1, "test")
        hp_before = party[0].hp
        msgs = engine.enemy_action()
        assert party[0].hp == hp_before
        assert any("スタン" in m for m in msgs)

    def test_danger_phase_switches_when_hp_drops(self):
        """敵 HP が 50% 以下になると DANGER フェーズに切り替わる"""
        enemy = self._make_enemy(name="ドラゴン", hp=40)  # 40/100 = 40%
        phase = EnemyAI.get_phase(enemy, max_hp=100)
        assert phase == "DANGER"

    def test_attack_all_hits_all_alive_party(self):
        """全体攻撃アクションで全生存パーティメンバーにダメージが入る"""
        party = self._make_party(3)
        enemy = self._make_enemy(name="ドラゴン", hp=100, attack=15)
        engine = BattleEngine(party, [enemy])
        hp_before = [c.hp for c in party]
        # ドラゴンのローテーション index=1 で "breath"（attack_all）
        engine.enemy_rotation_idx[enemy.id] = 1
        engine.enemy_action()
        # 全員ダメージを受けているはず
        for i, c in enumerate(party):
            assert c.hp < hp_before[i], f"party[{i}] がダメージを受けていない"

    def test_enemy_max_hp_preserved_in_engine(self):
        """BattleEngine が敵の初期HPを正しく記録する"""
        enemy = self._make_enemy(hp=80)
        engine = BattleEngine([make_character()], [enemy])
        assert engine.enemy_max_hp[enemy.id] == 80

    def test_enemy_max_hp_passed_from_outside(self):
        """外部から enemy_max_hp を渡すと上書きされず初期値が保たれる"""
        enemy = self._make_enemy(hp=50)   # 現在HP（ダメージ済み想定）
        engine = BattleEngine(
            [make_character()], [enemy],
            enemy_max_hp={enemy.id: 100},   # 本来の最大HP
        )
        assert engine.enemy_max_hp[enemy.id] == 100


# ─── R-13 味方自動行動AI テスト ──────────────────────────────
class TestAllyAutoAction:
    """BattleEngine.ally_auto_action() の動作確認"""

    def _make_char(self, name="勇者", class_type="warrior", hp=100, mp=30,
                   attack=15, defense=8, char_id=1) -> Character:
        c = Character()
        c.id = char_id
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

    def _make_enemy(self, name="スライム", hp=30, attack=5, defense=2) -> Enemy:
        e = Enemy()
        e.id = 1
        e.name = name
        e.hp = hp
        e.attack = attack
        e.defense = defense
        e.exp_reward = 10
        e.is_boss = False
        return e

    def _make_skill(self, name="攻撃スキル", effect_type="attack",
                    mp_cost=10, power=20, duration=0, target_type="enemy",
                    skill_id=1) -> Skill:
        s = Skill()
        s.id = skill_id
        s.name = name
        s.effect_type = effect_type
        s.mp_cost = mp_cost
        s.power = power
        s.cooldown = 0
        s.duration = duration
        s.target_type = target_type
        return s

    def _make_engine(self, party, enemies):
        return BattleEngine(party, enemies)

    # ── attack ポリシー ──────────────────────────────────────
    def test_auto_attack_uses_skill(self):
        """attack ポリシーで攻撃スキルが使用されること"""
        chara  = self._make_char(mp=30)
        enemy  = self._make_enemy(hp=50)
        engine = self._make_engine([chara], [enemy])
        skills = [self._make_skill("斬撃", "attack", mp_cost=10, power=20)]
        msg = engine.ally_auto_action(chara, "attack", skills)
        assert "斬撃" in msg
        assert chara.mp == 20  # MP 消費

    def test_auto_attack_fallback_to_normal(self):
        """MP ゼロで攻撃スキルが使えない場合に通常攻撃にフォールバックすること"""
        chara  = self._make_char(mp=0)
        enemy  = self._make_enemy(hp=50)
        engine = self._make_engine([chara], [enemy])
        skills = [self._make_skill("斬撃", "attack", mp_cost=10)]
        msg = engine.ally_auto_action(chara, "attack", skills)
        assert "攻撃" in msg
        assert "斬撃" not in msg

    # ── heal ポリシー ────────────────────────────────────────
    def test_auto_heal_cures_critical(self):
        """HP ≤ 30% のキャラがいるとき heal ポリシーで回復スキルが使われること"""
        healer  = self._make_char(name="僧侶", class_type="priest", mp=50, char_id=1)
        wounded = self._make_char(name="戦士", hp=25, char_id=2)  # max_hp=25, HP=25=100% (満タン)
        # max_hp=100 なのに hp=25 にするためにセット
        wounded.hp     = 25
        wounded.max_hp = 100  # 25%
        enemy  = self._make_enemy()
        engine = self._make_engine([healer, wounded], [enemy])
        heal_sk = self._make_skill("ヒール", "heal", mp_cost=10, power=30)
        msg = engine.ally_auto_action(healer, "heal", [heal_sk])
        assert "ヒール" in msg

    def test_auto_heal_attacks_when_full(self):
        """全員 HP ≥ 70% のとき heal ポリシーで攻撃にフォールバックすること"""
        healer = self._make_char(name="僧侶", class_type="priest", mp=50)
        enemy  = self._make_enemy(hp=50)
        engine = self._make_engine([healer], [enemy])
        # 回復スキルのみ
        heal_sk   = self._make_skill("ヒール", "heal", mp_cost=10, power=30, skill_id=1)
        attack_sk = self._make_skill("攻撃", "attack", mp_cost=5, power=10, skill_id=2)
        msg = engine.ally_auto_action(healer, "heal", [heal_sk, attack_sk])
        # 全員満タン → 攻撃スキルにフォールバック
        assert "攻撃" in msg

    def test_auto_heal_cures_status(self):
        """状態異常保持キャラがいるとき heal ポリシーで cure スキルを優先すること"""
        healer  = self._make_char(name="僧侶", class_type="priest", mp=50, char_id=1)
        ill     = self._make_char(name="戦士", char_id=2)
        enemy   = self._make_enemy()
        engine  = self._make_engine([healer, ill], [enemy])
        # ill キャラに毒を付与
        engine.apply_status(ill, "poison", 3, "test")
        cure_sk = self._make_skill("キュア", "cure", mp_cost=8, power=0, skill_id=1)
        heal_sk = self._make_skill("ヒール", "heal", mp_cost=10, power=30, skill_id=2)
        msg = engine.ally_auto_action(healer, "heal", [cure_sk, heal_sk])
        assert "キュア" in msg

    # ── defend ポリシー ──────────────────────────────────────
    def test_auto_defend_uses_taunt(self):
        """挑発スキルを持つ騎士が defend ポリシーで挑発を使うこと"""
        knight = self._make_char(name="騎士", class_type="knight", mp=20)
        enemy  = self._make_enemy()
        engine = self._make_engine([knight], [enemy])
        taunt_sk = self._make_skill("挑発", "buff_def", mp_cost=8, power=5,
                                    duration=3, target_type="self")
        msg = engine.ally_auto_action(knight, "defend", [taunt_sk])
        assert "挑発" in msg

    def test_auto_defend_finishes_enemy(self):
        """止めを刺せる敵がいるとき defend ポリシーで攻撃すること"""
        chara  = self._make_char(attack=20, mp=30)
        enemy  = self._make_enemy(hp=1, defense=0)  # あと1撃で倒せる
        engine = self._make_engine([chara], [enemy])
        atk_sk = self._make_skill("斬撃", "attack", mp_cost=5, power=10)
        msg = engine.ally_auto_action(chara, "defend", [atk_sk])
        # 防御でなく攻撃が選択されるはず
        assert "防御" not in msg

    # ── 状態異常への対応 ────────────────────────────────────
    def test_auto_stun_skip(self):
        """スタン中のキャラが行動スキップされること"""
        chara  = self._make_char()
        enemy  = self._make_enemy()
        engine = self._make_engine([chara], [enemy])
        engine.apply_status(chara, "stun", 1, "test")
        msg = engine.ally_auto_action(chara, "attack", [])
        assert "スタン" in msg

    def test_auto_silence_no_skill(self):
        """沈黙中のキャラがスキルを使わず通常攻撃にフォールバックすること"""
        chara  = self._make_char(mp=30)
        enemy  = self._make_enemy(hp=50)
        engine = self._make_engine([chara], [enemy])
        engine.apply_status(chara, "silence", 2, "test")
        atk_sk = self._make_skill("斬撃", "attack", mp_cost=5, power=10)
        msg = engine.ally_auto_action(chara, "attack", [atk_sk])
        # スキルを使わず通常攻撃のはず
        assert "斬撃" not in msg
        assert "攻撃" in msg


# ─── 敵AI 知性値拡張テスト ────────────────────────────────────────────
class TestEnemyAIIntelligence:
    """R-12 敵AI 知性値パラメータによる行動変化テスト"""

    def _make_enemy(self, name="オーク", hp=100, attack=10, defense=3):
        e = make_enemy(name=name, hp=hp, attack=attack, defense=defense)
        return e

    def _make_party(self, count=2):
        party = []
        for i in range(count):
            c = make_character(name=f"勇者{i+1}", hp=100, attack=15, defense=5)
            c.id = i + 1
            party.append(c)
        return party

    # ── DANGER フェーズ移行しきい値の変化 ─────────────────────────
    def test_intel1_danger_threshold(self):
        """知性値1 の敵は HP 40% でも NORMAL フェーズになること（しきい値 35%）"""
        e = self._make_enemy(hp=40)  # 40/100 = 40%
        # intel=1: DANGER しきい値=35%. 40% > 35% → NORMAL
        assert EnemyAI.get_phase(e, max_hp=100, intelligence=1) == "NORMAL"

    def test_intel3_danger_threshold(self):
        """知性値3 の敵は HP 60% で DANGER フェーズになること（しきい値 65%）"""
        e = self._make_enemy(hp=60)  # 60/100 = 60%
        # intel=3: DANGER しきい値=65%. 60% <= 65% → DANGER
        assert EnemyAI.get_phase(e, max_hp=100, intelligence=3) == "DANGER"

    # ── WIN_FIRST しきい値の変化 ────────────────────────────────
    def test_intel3_win_first_wider(self):
        """知性値3 は HP 20% のキャラも WIN_FIRST 対象になるが、知性値2 では対象外"""
        party = self._make_party()
        party[0].hp = 20   # 20/100 = 20%

        # intel=2: しきい値=15%. 20% > 15% → WIN_FIRST でない
        assert EnemyAI.is_win_first(party, intelligence=2) is False
        # intel=3: しきい値=25%. 20% <= 25% → WIN_FIRST
        assert EnemyAI.is_win_first(party, intelligence=3) is True

    # ── 知性値1: ランダム行動の混入 ────────────────────────────
    def test_intel1_random_action(self):
        """知性値1 の敵で 200 回試行するとローテーション外の行動が観測されること"""
        e = self._make_enemy(name="オーク", hp=100)
        # オークの normal_rotation = ["attack", "heavy_blow", "attack"]
        # index=0 のローテーション行動は "attack"
        # intel=1: 25%確率でランダム → "heavy_blow" が出る可能性がある
        results = set()
        for _ in range(200):
            name, _ = EnemyAI.choose_action(e, "NORMAL", 0, intelligence=1)
            results.add(name)
        # 200回試行で少なくとも1回は "heavy_blow" が出るはず（確率的にほぼ確実）
        assert len(results) > 1, "知性値1 でもローテーション外行動が一度も観測されなかった"

    # ── デフォルト引数の後方互換性 ──────────────────────────────
    def test_default_intel_backward_compat(self):
        """intelligence 引数を省略しても既存テストと同等の動作をすること"""
        e = self._make_enemy(hp=50)   # 50/100 = 50%

        # 既存テストと同じ: HP=50% で DANGER（intel=2 デフォルト、しきい値 50%）
        assert EnemyAI.get_phase(e, max_hp=100) == "DANGER"

        # 既存テストと同じ: HP=10% のキャラで WIN_FIRST（intel=2 デフォルト、しきい値 15%）
        party = self._make_party()
        party[0].hp = 10   # 10% <= 15%
        assert EnemyAI.is_win_first(party) is True


# ─── 知性値拡張テスト ─────────────────────────────────────────────
class TestAllyAutoActionIntelligence:
    """ally_auto_action() の intelligence パラメータによる挙動変化テスト"""

    def _make_char(self, name="勇者", class_type="warrior", hp=100, mp=30,
                   attack=15, defense=8, char_id=1) -> Character:
        c = Character()
        c.id = char_id
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

    def _make_enemy(self, name="スライム", hp=30, attack=5, defense=0) -> Enemy:
        e = Enemy()
        e.id = 1
        e.name = name
        e.hp = hp
        e.attack = attack
        e.defense = defense
        e.exp_reward = 10
        e.is_boss = False
        return e

    def _make_skill(self, name="ヒール", effect_type="heal",
                    mp_cost=10, power=30, duration=0, target_type="ally",
                    skill_id=1) -> Skill:
        s = Skill()
        s.id = skill_id
        s.name = name
        s.effect_type = effect_type
        s.mp_cost = mp_cost
        s.power = power
        s.cooldown = 0
        s.duration = duration
        s.target_type = target_type
        return s

    # ── 知性値1: 回復しきい値が低い (critical=0.20) ───────────────────
    def test_intel1_heal_not_triggered_at_25pct(self):
        """知性値1 の heal ポリシーは HP25% でも critical 未満（20%以下）でないため回復しない"""
        healer  = self._make_char(name="僧侶", class_type="priest", mp=50, char_id=1)
        wounded = self._make_char(name="戦士", char_id=2)
        wounded.hp     = 25   # 25%
        wounded.max_hp = 100
        enemy  = self._make_enemy()
        engine = BattleEngine([healer, wounded], [enemy])
        heal_sk   = self._make_skill("ヒール", "heal", mp_cost=10, power=30, skill_id=1)
        attack_sk = self._make_skill("攻撃", "attack", mp_cost=5, power=10,
                                     target_type="enemy", skill_id=2)
        msg = engine.ally_auto_action(healer, "heal", [heal_sk, attack_sk], intelligence=1)
        # 知性1の critical しきい値は 20% → HP25% は critical でない
        # また hurt しきい値は 50% → HP25% は hurt 範囲 → 回復が走る
        # (25% < 50% なので hurt に引っかかる)
        assert "ヒール" in msg

    def test_intel1_heal_not_triggered_at_55pct(self):
        """知性値1 の heal ポリシーは HP55% では hurt しきい値（50%）以上なので攻撃にフォールバック"""
        healer  = self._make_char(name="僧侶", class_type="priest", mp=50, char_id=1)
        wounded = self._make_char(name="戦士", char_id=2)
        wounded.hp     = 55   # 55%
        wounded.max_hp = 100
        enemy  = self._make_enemy()
        engine = BattleEngine([healer, wounded], [enemy])
        heal_sk   = self._make_skill("ヒール", "heal", mp_cost=10, power=30, skill_id=1)
        attack_sk = self._make_skill("攻撃", "attack", mp_cost=5, power=10,
                                     target_type="enemy", skill_id=2)
        msg = engine.ally_auto_action(healer, "heal", [heal_sk, attack_sk], intelligence=1)
        # 知性1: hurt しきい値は 50% → HP55% は heal しない → 攻撃フォールバック
        assert "ヒール" not in msg
        assert "攻撃" in msg

    # ── 知性値3: 回復しきい値が高い (critical=0.40, hurt=0.80) ────────
    def test_intel3_heal_triggered_at_35pct(self):
        """知性値3 の heal ポリシーは HP35% で critical しきい値（40%）以下なので回復する"""
        healer  = self._make_char(name="僧侶", class_type="priest", mp=50, char_id=1)
        wounded = self._make_char(name="戦士", char_id=2)
        wounded.hp     = 35   # 35%
        wounded.max_hp = 100
        enemy  = self._make_enemy()
        engine = BattleEngine([healer, wounded], [enemy])
        heal_sk = self._make_skill("ヒール", "heal", mp_cost=10, power=30, skill_id=1)
        msg = engine.ally_auto_action(healer, "heal", [heal_sk], intelligence=3)
        # 知性3: critical しきい値 40% → 35% は critical → 回復
        assert "ヒール" in msg

    # ── 知性値1: defend で one-shot 判定しない ──────────────────────
    def test_intel1_defend_skips_oneshot(self):
        """知性値1 の defend ポリシーは止めを刺せる敵がいても防御行動を選ぶ"""
        chara  = self._make_char(attack=50, mp=0)  # MPゼロ → スキル不可
        enemy  = self._make_enemy(hp=1, defense=0)  # 通常攻撃で必ず倒せる
        engine = BattleEngine([chara], [enemy])
        msg = engine.ally_auto_action(chara, "defend", [], intelligence=1)
        # 知性1は one-shot 判定しない → 防御
        assert "防御" in msg

    # ── デフォルト引数の後方互換性 ────────────────────────────────
    def test_default_intelligence_backward_compat(self):
        """intelligence を省略した場合、既存の標準テスト（HP≤30% で回復）が成立する"""
        healer  = self._make_char(name="僧侶", class_type="priest", mp=50, char_id=1)
        wounded = self._make_char(name="戦士", char_id=2)
        wounded.hp     = 25   # 25% ≤ 30% (intel=2 の critical しきい値)
        wounded.max_hp = 100
        enemy  = self._make_enemy()
        engine = BattleEngine([healer, wounded], [enemy])
        heal_sk = self._make_skill("ヒール", "heal", mp_cost=10, power=30)
        # intelligence 引数なし → デフォルト 2 が使われる
        msg = engine.ally_auto_action(healer, "heal", [heal_sk])
        assert "ヒール" in msg
