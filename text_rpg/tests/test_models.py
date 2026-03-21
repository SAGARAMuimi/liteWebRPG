"""
tests/test_models.py - モデルのユニットテスト
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.database import Base
from models.user import User
from models.character import Character
from models.enemy import Enemy


@pytest.fixture
def db():
    """インメモリ SQLite でテスト用 DB を作成"""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestUserModel:
    def test_create_user(self, db):
        user = User.create(db, "testuser", "password123")
        assert user.id is not None
        assert user.name == "testuser"

    def test_find_by_name(self, db):
        User.create(db, "findme", "pass")
        found = User.find_by_name(db, "findme")
        assert found is not None
        assert found.name == "findme"

    def test_verify_password(self, db):
        user = User.create(db, "authuser", "secret")
        assert user.verify_password("secret") is True
        assert user.verify_password("wrong") is False

    def test_duplicate_name_raises(self, db):
        from sqlalchemy.exc import IntegrityError
        User.create(db, "dupuser", "pass1")
        with pytest.raises(IntegrityError):
            User.create(db, "dupuser", "pass2")


class TestCharacterModel:
    def test_create_character(self, db):
        user = User.create(db, "player1", "pass")
        chara = Character.create(db, user.id, "勇者", "warrior")
        assert chara.id is not None
        assert chara.name == "勇者"
        assert chara.hp == chara.max_hp

    def test_take_damage(self, db):
        user = User.create(db, "player2", "pass")
        chara = Character.create(db, user.id, "戦士", "warrior")
        original_hp = chara.hp
        actual = chara.take_damage(10)
        assert chara.hp == original_hp - max(1, 10)
        assert actual >= 1

    def test_heal(self, db):
        user = User.create(db, "player3", "pass")
        chara = Character.create(db, user.id, "僧侶", "priest")
        chara.hp = 50
        healed = chara.heal(30)
        assert chara.hp == 80
        assert healed == 30

    def test_heal_does_not_exceed_max_hp(self, db):
        user = User.create(db, "player4", "pass")
        chara = Character.create(db, user.id, "魔法使い", "mage")
        chara.hp = chara.max_hp - 5
        chara.heal(100)
        assert chara.hp == chara.max_hp

    def test_is_alive(self, db):
        user = User.create(db, "player5", "pass")
        chara = Character.create(db, user.id, "盗賊", "thief")
        assert chara.is_alive()
        chara.hp = 0
        assert not chara.is_alive()

    def test_gain_exp_level_up(self, db):
        user = User.create(db, "player6", "pass")
        chara = Character.create(db, user.id, "英雄", "warrior")
        leveled = chara.gain_exp(db, 50)  # Lv1 必要EXP = 50
        assert leveled >= 1
        assert chara.level == 2


class TestEnemyModel:
    def test_is_alive(self):
        e = Enemy()
        e.hp = 10
        assert e.is_alive()
        e.hp = 0
        assert not e.is_alive()

    def test_take_damage(self):
        e = Enemy()
        e.hp = 20
        actual = e.take_damage(8)
        assert e.hp == 12
        assert actual == 8

    def test_take_damage_minimum_1(self):
        e = Enemy()
        e.hp = 20
        actual = e.take_damage(0)
        assert actual == 1


class TestUserGold:
    def test_initial_gold_is_zero(self, db):
        user = User.create(db, "golduser1", "pass")
        assert user.gold == 0

    def test_add_gold(self, db):
        user = User.create(db, "golduser2", "pass")
        new_total = User.add_gold(db, user.id, 100)
        assert new_total == 100
        assert User.get_gold(db, user.id) == 100

    def test_add_gold_multiple_times(self, db):
        user = User.create(db, "golduser3", "pass")
        User.add_gold(db, user.id, 50)
        User.add_gold(db, user.id, 30)
        assert User.get_gold(db, user.id) == 80

    def test_spend_gold_success(self, db):
        user = User.create(db, "golduser4", "pass")
        User.add_gold(db, user.id, 200)
        ok = User.spend_gold(db, user.id, 150)
        assert ok is True
        assert User.get_gold(db, user.id) == 50

    def test_spend_gold_insufficient(self, db):
        user = User.create(db, "golduser5", "pass")
        User.add_gold(db, user.id, 100)
        ok = User.spend_gold(db, user.id, 200)
        assert ok is False
        assert User.get_gold(db, user.id) == 100  # 変化なし

    def test_spend_gold_exact_amount(self, db):
        user = User.create(db, "golduser6", "pass")
        User.add_gold(db, user.id, 50)
        ok = User.spend_gold(db, user.id, 50)
        assert ok is True
        assert User.get_gold(db, user.id) == 0


class TestEnemyGoldReward:
    def test_gold_reward_default_zero(self):
        e = Enemy()
        e.gold_reward = 0
        assert e.gold_reward == 0

    def test_clone_preserves_gold_reward(self):
        e = Enemy(
            id=1, name="スライム", dungeon_id=1, floor=1,
            hp=20, attack=5, defense=2,
            exp_reward=10, gold_reward=8,
            is_boss=False, status_resistance="",
        )
        cloned = e.clone()
        assert cloned.gold_reward == 8


# ─── 装備システムテスト ────────────────────────────────────
class TestEquipmentModel:
    def _make_equip(self, db, eid, name="テスト剣", slot="weapon",
                    atk=5, def_=0, hp=0, mp=0, price=100, req="", disposable=False):
        from models.equipment import Equipment
        eq = Equipment(id=eid, name=name, description="", slot=slot,
                       atk_bonus=atk, def_bonus=def_,
                       hp_bonus=hp, mp_bonus=mp,
                       price=price, required_class=req,
                       disposable=disposable)
        db.add(eq)
        db.commit()
        db.refresh(eq)
        return eq

    def test_equip_weapon_raises_attack(self, db):
        user  = User.create(db, "equser1", "pass")
        chara = Character.create(db, user.id, "テスト戦士", "warrior")
        base_atk = chara.attack
        eq = self._make_equip(db, 100, atk=5)
        chara.equip(db, eq)
        assert chara.attack == base_atk + 5

    def test_equip_armor_raises_defense_and_hp(self, db):
        user  = User.create(db, "equser2", "pass")
        chara = Character.create(db, user.id, "テスト僧侶", "priest")
        base_def = chara.defense
        base_mhp = chara.max_hp
        eq = self._make_equip(db, 101, name="テスト鎧", slot="armor",
                               atk=0, def_=4, hp=20)
        chara.equip(db, eq)
        assert chara.defense == base_def + 4
        assert chara.max_hp  == base_mhp + 20

    def test_equip_replaces_same_slot(self, db):
        user  = User.create(db, "equser3", "pass")
        chara = Character.create(db, user.id, "テスト盗賊", "thief")
        base_atk = chara.attack
        eq1 = self._make_equip(db, 102, name="剣A", atk=3)
        eq2 = self._make_equip(db, 103, name="剣B", atk=7)
        chara.equip(db, eq1)
        chara.equip(db, eq2)  # 同スロットに上書き装備
        assert chara.attack == base_atk + 7  # eq2 のボーナスのみ適用

    def test_unequip_restores_stats(self, db):
        user  = User.create(db, "equser4", "pass")
        chara = Character.create(db, user.id, "テスト魔法使い", "mage")
        base_atk = chara.attack
        eq = self._make_equip(db, 104, atk=5)
        chara.equip(db, eq)
        assert chara.attack == base_atk + 5
        chara.unequip(db, "weapon")
        assert chara.attack == base_atk

    def test_hp_clamped_after_unequip(self, db):
        user  = User.create(db, "equser5", "pass")
        chara = Character.create(db, user.id, "テスト騎士", "knight")
        eq = self._make_equip(db, 105, name="テスト鎧2", slot="armor",
                               atk=0, def_=0, hp=30)
        chara.equip(db, eq)
        pre_max_hp = chara.max_hp
        chara.hp   = pre_max_hp  # 満タン状態にする
        chara.unequip(db, "armor")
        assert chara.max_hp == pre_max_hp - 30  # max_hp が戻る
        assert chara.hp <= chara.max_hp          # HP が上限を超えない

    def test_can_equip_class_filter(self):
        from models.equipment import Equipment
        eq = Equipment(id=999, name="鋼の剣", description="", slot="weapon",
                       atk_bonus=6, def_bonus=0, hp_bonus=0, mp_bonus=0,
                       price=280, required_class="warrior,knight", disposable=False)
        assert eq.can_equip("warrior") is True
        assert eq.can_equip("mage")    is False
        assert eq.can_equip("knight")  is True

    def test_can_equip_no_restriction(self):
        from models.equipment import Equipment
        eq = Equipment(id=998, name="銅の剣", description="", slot="weapon",
                       atk_bonus=3, def_bonus=0, hp_bonus=0, mp_bonus=0,
                       price=100, required_class="", disposable=False)
        for cls in ["warrior", "mage", "thief", "priest",
                    "knight", "archer", "monk", "bard"]:
            assert eq.can_equip(cls) is True

    def test_bonus_summary(self):
        from models.equipment import Equipment
        eq = Equipment(id=997, name="テスト装備", description="", slot="armor",
                       atk_bonus=0, def_bonus=3, hp_bonus=10, mp_bonus=0,
                       price=120, required_class="", disposable=False)
        summary = eq.bonus_summary()
        assert "DEF+3"  in summary
        assert "HP+10"  in summary
        assert "ATK"    not in summary  # ATK ボーナスなし

    def test_bonus_summary_disposable_label(self):
        """disposable=True の場合、bonus_summary に 🔥消耗品 が含まれること"""
        from models.equipment import Equipment
        eq = Equipment(id=996, name="消耗品剣", description="", slot="weapon",
                       atk_bonus=4, def_bonus=0, hp_bonus=0, mp_bonus=0,
                       price=80, required_class="", disposable=True)
        summary = eq.bonus_summary()
        assert "消耗品" in summary

    def test_unequip_disposable_no_inventory(self, db):
        """disposable=True の装備を外すと、インベントリに戻らない"""
        from models.equipment import Equipment as Eq, CharacterInventory as CI
        user  = User.create(db, "dispuser1", "pass")
        chara = Character.create(db, user.id, "消耗テスト1", "warrior")
        eq = Eq(id=200, name="消耗品剣", description="", slot="weapon",
                atk_bonus=5, def_bonus=0, hp_bonus=0, mp_bonus=0,
                price=80, required_class="", disposable=True)
        db.add(eq); db.commit(); db.refresh(eq)
        chara.equip(db, eq)
        chara.unequip(db, "weapon")
        rows = CI.get_for_character(db, chara.id)
        assert len(rows) == 0  # インベントリに何も残らない

    def test_unequip_permanent_returns_to_inventory(self, db):
        """disposable=False の装備を外すと、インベントリに1個戻る"""
        from models.equipment import Equipment as Eq, CharacterInventory as CI
        user  = User.create(db, "permuser1", "pass")
        chara = Character.create(db, user.id, "永続テスト1", "warrior")
        eq = Eq(id=201, name="永続剣", description="", slot="weapon",
                atk_bonus=5, def_bonus=0, hp_bonus=0, mp_bonus=0,
                price=100, required_class="", disposable=False)
        db.add(eq); db.commit(); db.refresh(eq)
        chara.equip(db, eq)
        chara.unequip(db, "weapon")
        rows = CI.get_for_character(db, chara.id)
        assert len(rows) == 1
        assert rows[0].equipment_id == eq.id
        assert rows[0].quantity == 1

    def test_unequip_permanent_stacks_in_inventory(self, db):
        """同じ永続装備を2回外すと quantity が 2 になること"""
        from models.equipment import Equipment as Eq, CharacterInventory as CI
        user  = User.create(db, "stackuser1", "pass")
        chara = Character.create(db, user.id, "スタックテスト", "warrior")
        eq = Eq(id=202, name="量産型剣", description="", slot="weapon",
                atk_bonus=3, def_bonus=0, hp_bonus=0, mp_bonus=0,
                price=100, required_class="", disposable=False)
        db.add(eq); db.commit(); db.refresh(eq)
        # 1回目：装備→外す
        chara.equip(db, eq)
        chara.unequip(db, "weapon")
        # 2回目：再装備→外す
        chara.equip(db, eq)
        chara.unequip(db, "weapon")
        rows = CI.get_for_character(db, chara.id)
        assert rows[0].quantity == 2

    def test_character_inventory_consume(self, db):
        """CharacterInventory.consume で quantity が減り、0以下になれば削除される"""
        from models.equipment import Equipment as Eq, CharacterInventory as CI
        user  = User.create(db, "conuser1", "pass")
        chara = Character.create(db, user.id, "消費テスト", "warrior")
        eq = Eq(id=203, name="消費剣", description="", slot="weapon",
                atk_bonus=3, def_bonus=0, hp_bonus=0, mp_bonus=0,
                price=100, required_class="", disposable=False)
        db.add(eq); db.commit(); db.refresh(eq)
        CI.add(db, chara.id, eq.id, qty=2)
        ok = CI.consume(db, chara.id, eq.id, qty=1)
        assert ok is True
        rows = CI.get_for_character(db, chara.id)
        assert rows[0].quantity == 1
        # もう1回消費 → レコード削除
        CI.consume(db, chara.id, eq.id, qty=1)
        rows = CI.get_for_character(db, chara.id)
        assert len(rows) == 0


class TestLevelUpPlans:
    """R-07 選択式成長プランのテスト"""

    def test_gain_exp_returns_int_level_count(self, db):
        """gain_exp はレベルアップ回数（int）を返す"""
        user  = User.create(db, "lv_cnt", "pass")
        chara = Character.create(db, user.id, "カウント者", "warrior")
        # Lv1→Lv2: 50, Lv2→Lv3: 100 → 計 150 で 2 レベル
        levels = chara.gain_exp(db, 150)
        assert levels == 2
        assert chara.level == 3

    def test_gain_exp_no_levelup_returns_zero(self, db):
        """EXP が不足なら 0 を返す"""
        user  = User.create(db, "lv_zero", "pass")
        chara = Character.create(db, user.id, "未成長", "mage")
        levels = chara.gain_exp(db, 10)
        assert levels == 0
        assert chara.level == 1

    def test_apply_growth_power_boosts_attack(self, db):
        """power プランで attack が +3 以上増加"""
        user  = User.create(db, "lv_power", "pass")
        chara = Character.create(db, user.id, "地偽い戦士", "warrior")
        old_atk = chara.attack
        chara.apply_growth(db, "power", times=1)
        assert chara.attack >= old_atk + 3  # power の attack min = 3

    def test_apply_growth_tank_boosts_hp(self, db):
        """tank プランで max_hp が +15 以上増加"""
        user  = User.create(db, "lv_tank", "pass")
        chara = Character.create(db, user.id, "強固騎士", "knight")
        old_hp = chara.max_hp
        chara.apply_growth(db, "tank", times=1)
        assert chara.max_hp >= old_hp + 15  # tank の max_hp min = 15

    def test_apply_growth_support_boosts_mp(self, db):
        """support プランで max_mp が +6 以上増加"""
        user  = User.create(db, "lv_sup", "pass")
        chara = Character.create(db, user.id, "回復僧侶", "priest")
        old_mp = chara.max_mp
        chara.apply_growth(db, "support", times=1)
        assert chara.max_mp >= old_mp + 6  # support の max_mp min = 6

    def test_apply_growth_restores_full_hp_mp(self, db):
        """apply_growth 後に HP/MP が全回復する"""
        user  = User.create(db, "lv_full", "pass")
        chara = Character.create(db, user.id, "低体力者", "warrior")
        chara.hp = 1
        chara.mp = 0
        chara.apply_growth(db, "balanced", times=1)
        assert chara.hp == chara.max_hp
        assert chara.mp == chara.max_mp

    def test_apply_growth_multiple_times_stacks(self, db):
        """times=3 指定で power min の 3倍以上 attack が増加"""
        user  = User.create(db, "lv_multi", "pass")
        chara = Character.create(db, user.id, "連続強化", "warrior")
        old_atk = chara.attack
        chara.apply_growth(db, "power", times=3)
        assert chara.attack >= old_atk + 9  # 3 per level * 3 levels

    def test_apply_growth_invalid_plan_fallback(self, db):
        """unknown プランは balanced にフォールバック"""
        user  = User.create(db, "lv_inv", "pass")
        chara = Character.create(db, user.id, "未知プラン", "warrior")
        old_hp = chara.max_hp
        chara.apply_growth(db, "unknown_plan", times=1)
        assert chara.max_hp >= old_hp + 10  # balanced の max_hp min = 10

    def test_levelup_support_grows_intelligence(self, db):
        """support プランのレベルアップで intelligence が +1 増加すること"""
        user  = User.create(db, "lv_intel", "pass")
        chara = Character.create(db, user.id, "成長僧侶", "priest")
        old_intel = chara.intelligence
        chara.apply_growth(db, "support", times=1)
        # support の intelligence growth = (1, 1) → 必ず +1
        assert chara.intelligence == old_intel + 1

    def test_levelup_support_intelligence_capped_at_10(self, db):
        """intelligence=10 で support プランを適用しても 10 を超えないこと"""
        user  = User.create(db, "lv_cap", "pass")
        chara = Character.create(db, user.id, "賢者上限", "priest")
        chara.intelligence = 10
        chara.apply_growth(db, "support", times=1)
        assert chara.intelligence == 10  # クランプ済み
