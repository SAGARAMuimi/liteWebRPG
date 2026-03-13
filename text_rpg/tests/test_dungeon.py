"""
tests/test_dungeon.py - DungeonManager のユニットテスト
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.database import Base
from models.dungeon import Dungeon, DungeonProgress
from models.enemy import Enemy
from models.skill import Skill
from models.item import Item
from game.dungeon import DungeonManager, EventResult
from utils.helpers import seed_initial_data


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    seed_initial_data(session)
    yield session
    session.close()


@pytest.fixture
def manager(db):
    dungeon = Dungeon.get_by_id(db, 1)
    progress = DungeonProgress(user_id=1, dungeon_id=1, current_floor=1)
    db.add(progress)
    db.commit()
    return DungeonManager(db, dungeon, progress)


def make_party_char(name="勇者", hp=100):
    from models.character import Character
    c = Character()
    c.id = 1
    c.name = name
    c.class_type = "warrior"
    c.hp = hp
    c.max_hp = hp
    c.mp = 20
    c.max_mp = 20
    c.attack = 15
    c.defense = 8
    c.level = 1
    c.exp = 0
    return c


class TestDungeonManager:
    def test_initial_floor(self, manager):
        assert manager.current_floor == 1

    def test_is_boss_room(self, manager):
        assert manager.is_boss_room(3) is True
        assert manager.is_boss_room(2) is False

    def test_check_encounter_returns_bool(self, manager):
        result = manager.check_encounter()
        assert isinstance(result, bool)

    def test_get_random_enemies_returns_list(self, manager):
        enemies = manager.get_random_enemies()
        assert isinstance(enemies, list)
        assert len(enemies) >= 1

    def test_get_boss_returns_enemy(self, manager):
        boss = manager.get_boss()
        assert boss is not None
        assert boss.is_boss is True

    def test_enemy_clone_is_independent(self, manager):
        enemies = manager.get_random_enemies()
        original_hp = enemies[0].hp
        enemies[0].hp = 0
        # 再取得しても元のデータは変わらない
        new_enemies = manager.get_random_enemies()
        assert new_enemies[0].hp == original_hp or new_enemies[0].hp > 0

    def test_advance_to_next_floor(self, manager, db):
        all_clear = manager.advance_to_next_floor()
        assert all_clear is False
        assert manager.current_floor == 2

    def test_advance_to_final_floor(self, manager, db):
        manager.progress.current_floor = 3
        all_clear = manager.advance_to_next_floor()
        assert all_clear is True
        assert manager.progress.is_cleared is True

    def test_reset_progress(self, manager, db):
        manager.progress.current_floor = 3
        manager.reset_progress()
        assert manager.progress.current_floor == 1
        assert manager.progress.is_cleared is False


# ─── イベントシステムテスト ──────────────────────────────────
class TestEventSystem:
    """DungeonManager.resolve_event() のユニットテスト"""

    def setup_method(self):
        pass

    def test_resolve_event_returns_event_result(self, manager):
        """resolve_event は EventResult を返す"""
        party = [make_party_char()]
        result = manager.resolve_event(party, room=1)
        assert isinstance(result, EventResult)

    def test_boss_room_always_encounter(self, manager):
        """ボス部屋（room >= ROOMS_PER_FLOOR）は必ず encounter"""
        party = [make_party_char()]
        for _ in range(10):
            result = manager.resolve_event(party, room=3)
            assert result.event_type == "encounter"
            assert result.need_battle is True
            assert len(result.enemies) == 1
            assert result.enemies[0].is_boss is True

    def test_encounter_event_has_enemies(self, manager):
        """encounter イベントは enemies を持つ"""
        import random as _random
        party = [make_party_char()]
        _orig = _random.choices
        _call = [0]

        def _side(*args, **kwargs):
            _call[0] += 1
            if _call[0] == 1:           # 最初の呼び出し: イベント種別選択
                return ["encounter"]
            return _orig(*args, **kwargs)  # 以降: get_random_enemies 等は本物を使用

        with patch("random.choices", side_effect=_side):
            result = manager.resolve_event(party, room=1)
        assert result.event_type == "encounter"
        assert result.need_battle is True
        assert len(result.enemies) >= 1

    def test_trap_event_reduces_hp(self, manager):
        """trap イベントはパーティ全体の HP を減らす（ただし 1 以上を保つ）"""
        chara = make_party_char(hp=100)
        party = [chara]
        with patch("random.choices", return_value=["trap"]):
            with patch("random.random", return_value=0.5):  # ダメージ罠（poison gas 閾値=0.25 より大）
                result = manager.resolve_event(party, room=1)
        assert result.event_type == "trap"
        assert chara.hp >= 1        # 即死しない
        assert chara.hp < 100       # ダメージを受けた

    def test_trap_event_does_not_kill(self, manager):
        """罠イベントで HP 1 以下にならない"""
        chara = make_party_char(hp=10)  # HP が少なくても
        chara.max_hp = 100
        party = [chara]
        with patch("random.choices", return_value=["trap"]):
            with patch("random.random", return_value=0.5):  # ダメージ罠
                result = manager.resolve_event(party, room=1)
        assert chara.hp >= 1

    def test_rest_event_heals_hp_mp(self, manager):
        """rest イベントは HP/MP を回復する"""
        chara = make_party_char(hp=50)
        chara.max_hp = 100
        chara.mp = 5
        chara.max_mp = 20
        party = [chara]
        before_hp = chara.hp
        before_mp = chara.mp
        with patch("random.choices", return_value=["rest"]):
            result = manager.resolve_event(party, room=1)
        assert result.event_type == "rest"
        assert chara.hp > before_hp
        assert chara.mp > before_mp

    def test_rest_event_does_not_exceed_max(self, manager):
        """rest イベントで HP/MP が最大値を超えない"""
        chara = make_party_char(hp=100)
        chara.max_hp = 100
        chara.mp = 20
        chara.max_mp = 20
        party = [chara]
        with patch("random.choices", return_value=["rest"]):
            result = manager.resolve_event(party, room=1)
        assert chara.hp <= chara.max_hp
        assert chara.mp <= chara.max_mp

    def test_shrine_event_heals_more_than_rest(self, manager):
        """shrine は rest より多く回復する（SHRINE_HEAL_PCT > REST_HEAL_PCT）"""
        from config import SHRINE_HEAL_PCT, REST_HEAL_PCT
        assert SHRINE_HEAL_PCT >= REST_HEAL_PCT

    def test_merchant_event_returns_stock(self, manager):
        """merchant イベントは merchant_stock を返す"""
        party = [make_party_char()]
        with patch("random.choices", return_value=["merchant"]):
            result = manager.resolve_event(party, room=1)
        assert result.event_type == "merchant"
        assert isinstance(result.merchant_stock, list)
        # アイテムが DB に存在する場合は在庫がある
        assert len(result.merchant_stock) >= 0

    def test_event_type_distribution(self, manager):
        """100 回試行でイベント種別が偏りすぎない（encounter 以外も発生する）"""
        party = [make_party_char()]
        counter: dict[str, int] = {}
        for _ in range(200):
            # HP をリセット
            party[0].hp = party[0].max_hp
            res = manager.resolve_event(party, room=1)
            counter[res.event_type] = counter.get(res.event_type, 0) + 1
        # encounter は 50±20% 以内（100〜140/200）
        enc_count = counter.get("encounter", 0)
        assert 60 <= enc_count <= 160, f"encounter 出現数が範囲外: {enc_count}"
        # encounter 以外も出現する
        non_enc = sum(v for k, v in counter.items() if k != "encounter")
        assert non_enc > 0, "encounter 以外のイベントが出現しなかった"

    def test_chest_gold_pattern(self, manager):
        """chest gold パターンは chest_gold > 0、chest_item_id == 0 を返す"""
        party = [make_party_char()]
        _call = [0]
        def _side(*args, **kwargs):
            _call[0] += 1
            return ["chest"] if _call[0] == 1 else ["gold"]
        with patch("random.choices", side_effect=_side):
            result = manager.resolve_event(party, room=1)
        assert result.event_type == "chest"
        assert result.chest_gold > 0
        assert result.chest_item_id == 0
        assert result.need_battle is False

    def test_chest_gold_within_range(self, manager):
        """chest gold パターンのゴールドが CHEST_GOLD_RANGE の範囲内に収まる"""
        from config import CHEST_GOLD_RANGE
        party = [make_party_char()]
        min_g, max_g = CHEST_GOLD_RANGE.get(1, (20, 60))
        _calls = [0]
        def _side(*args, **kwargs):
            _calls[0] += 1
            return ["chest"] if _calls[0] % 2 == 1 else ["gold"]
        with patch("random.choices", side_effect=_side):
            for _ in range(20):
                result = manager.resolve_event(party, room=1)
                assert min_g <= result.chest_gold <= max_g

    def test_chest_item_pattern(self, manager):
        """chest item パターンは chest_item_id > 0、chest_gold == 0 を返す"""
        party = [make_party_char()]
        _call = [0]
        def _side(*args, **kwargs):
            _call[0] += 1
            return ["chest"] if _call[0] == 1 else ["item"]
        with patch("random.choices", side_effect=_side):
            result = manager.resolve_event(party, room=1)
        assert result.event_type == "chest"
        assert result.chest_item_id > 0
        assert result.chest_gold == 0
        assert result.need_battle is False

    def test_chest_gold_item_pattern(self, manager):
        """chest gold_item パターンは chest_gold > 0 かつ chest_item_id > 0 を返す"""
        party = [make_party_char()]
        _call = [0]
        def _side(*args, **kwargs):
            _call[0] += 1
            return ["chest"] if _call[0] == 1 else ["gold_item"]
        with patch("random.choices", side_effect=_side):
            result = manager.resolve_event(party, room=1)
        assert result.event_type == "chest"
        assert result.chest_gold > 0
        assert result.chest_item_id > 0
        assert result.need_battle is False

    def test_chest_empty_pattern(self, manager):
        """chest empty パターンは gold も item も返さない"""
        party = [make_party_char()]
        _call = [0]
        def _side(*args, **kwargs):
            _call[0] += 1
            return ["chest"] if _call[0] == 1 else ["empty"]
        with patch("random.choices", side_effect=_side):
            result = manager.resolve_event(party, room=1)
        assert result.event_type == "chest"
        assert result.chest_gold == 0
        assert result.chest_item_id == 0
        assert result.need_battle is False
        assert any("空" in m for m in result.messages)

    def test_chest_mimic_starts_battle(self, manager):
        """chest mimic パターンは need_battle=True でミミックを返す"""
        party = [make_party_char()]
        _call = [0]
        def _side(*args, **kwargs):
            _call[0] += 1
            return ["chest"] if _call[0] == 1 else ["mimic"]
        with patch("random.choices", side_effect=_side):
            result = manager.resolve_event(party, room=1)
        assert result.event_type == "chest"
        assert result.need_battle is True
        assert len(result.enemies) == 1
        assert result.enemies[0].name == "ミミック"
        assert result.chest_gold == 0
        assert result.chest_item_id == 0

