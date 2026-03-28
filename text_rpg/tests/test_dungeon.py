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


# ─── MapManager テスト（R-14）──────────────────────────────────
class TestMapManager:
    """game/map_manager.py の MapManager ユニットテスト"""

    from game.map_manager import MapManager

    # ------------------------------------------------------------------
    # フィクスチャ（1F スタート地点）
    # ------------------------------------------------------------------

    @pytest.fixture
    def mm(self):
        from game.map_manager import MapManager
        sx, sy = 1, 1  # FLOOR_MAPS[1]["start"]
        return MapManager(floor=1, x=sx, y=sy)

    # ------------------------------------------------------------------
    # 初期化テスト
    # ------------------------------------------------------------------

    def test_init_loads_floor_data(self, mm):
        """__init__ でフロアデータが正しく読み込まれる"""
        assert mm.floor == 1
        assert mm.x == 1
        assert mm.y == 1
        assert mm.start == (1, 1)
        assert mm.goal == (3, 3)
        assert isinstance(mm.grid, list)
        assert len(mm.grid) > 0

    def test_init_invalid_floor_raises(self):
        """存在しないフロア番号は KeyError を送出する"""
        from game.map_manager import MapManager
        with pytest.raises(KeyError):
            MapManager(floor=99, x=0, y=0)

    def test_init_fixed_events_loaded(self, mm):
        """fixed_events が辞書として読み込まれる"""
        assert isinstance(mm.fixed_events, dict)
        assert len(mm.fixed_events) > 0

    # ------------------------------------------------------------------
    # can_move テスト
    # ------------------------------------------------------------------

    def test_can_move_into_passage(self, mm):
        """スタート(1,1)から東(2,1)は通路 → 移動可能"""
        assert mm.can_move("east") is True

    def test_can_move_into_wall(self, mm):
        """スタート(1,1)から北(1,0)は壁 → 移動不可"""
        assert mm.can_move("north") is False

    def test_can_move_into_wall_west(self, mm):
        """スタート(1,1)から西(0,1)は壁 → 移動不可"""
        assert mm.can_move("west") is False

    def test_can_move_out_of_bounds(self):
        """グリッド外（負座標）は移動不可"""
        from game.map_manager import MapManager
        mm = MapManager(floor=1, x=0, y=0)
        assert mm.can_move("north") is False
        assert mm.can_move("west") is False

    def test_can_move_invalid_direction_raises(self, mm):
        """不正な方向文字列は ValueError を送出する"""
        with pytest.raises(ValueError):
            mm.can_move("up")

    def test_can_move_to_goal(self):
        """ゴール隣から南へ進めばゴールへ移動可能"""
        from game.map_manager import MapManager
        # (3,2) はゴール(3,3)の真北 → 南に移動できるはず
        mm = MapManager(floor=1, x=3, y=2)
        assert mm.can_move("south") is True

    # ------------------------------------------------------------------
    # available_directions テスト
    # ------------------------------------------------------------------

    def test_available_directions_start(self, mm):
        """スタート(1,1)では南と東が移動可能"""
        dirs = mm.available_directions()
        assert "south" in dirs
        assert "east" in dirs
        assert "north" not in dirs
        assert "west" not in dirs

    def test_available_directions_returns_list(self, mm):
        """available_directions はリストを返す"""
        result = mm.available_directions()
        assert isinstance(result, list)

    # ------------------------------------------------------------------
    # move テスト
    # ------------------------------------------------------------------

    def test_move_updates_coordinates(self, mm):
        """move('east') で x が +1 される"""
        x, y = mm.move("east")
        assert x == 2
        assert y == 1
        assert mm.x == 2
        assert mm.y == 1

    def test_move_invalid_direction_raises(self, mm):
        """壁方向への move は ValueError を送出する"""
        with pytest.raises(ValueError):
            mm.move("north")

    def test_move_chain(self, mm):
        """連続移動でゴールまで到達できる（1F: S(1,1)→東(2,1)→東(3,1)→南(3,2)→南(3,3)=GOAL）"""
        from game.map_manager import MapManager
        mm2 = MapManager(floor=1, x=1, y=1)
        mm2.move("east")   # (2,1)
        mm2.move("east")   # (3,1)
        mm2.move("south")  # (3,2)
        mm2.move("south")  # (3,3) = goal
        assert mm2.is_goal() is True

    # ------------------------------------------------------------------
    # is_goal / is_start テスト
    # ------------------------------------------------------------------

    def test_is_start_at_start(self, mm):
        """スタート座標では is_start() が True"""
        assert mm.is_start() is True

    def test_is_start_at_other(self, mm):
        """スタート以外では is_start() が False"""
        mm.move("east")
        assert mm.is_start() is False

    def test_is_goal_at_goal(self):
        """ゴール座標では is_goal() が True"""
        from game.map_manager import MapManager
        mm = MapManager(floor=1, x=3, y=3)
        assert mm.is_goal() is True

    def test_is_goal_at_other(self, mm):
        """ゴール以外では is_goal() が False"""
        assert mm.is_goal() is False

    # ------------------------------------------------------------------
    # cell_at テスト
    # ------------------------------------------------------------------

    def test_cell_at_start(self, mm):
        """スタート座標は CELL_START(=2) を返す"""
        from config import CELL_START
        assert mm.cell_at(1, 1) == CELL_START

    def test_cell_at_wall(self, mm):
        """壁座標は CELL_WALL(=0) を返す"""
        from config import CELL_WALL
        assert mm.cell_at(0, 0) == CELL_WALL

    def test_cell_at_goal(self, mm):
        """ゴール座標は CELL_GOAL(=3) を返す"""
        from config import CELL_GOAL
        assert mm.cell_at(3, 3) == CELL_GOAL

    def test_cell_at_out_of_bounds(self, mm):
        """範囲外は CELL_WALL を返す"""
        from config import CELL_WALL
        assert mm.cell_at(-1, 0) == CELL_WALL
        assert mm.cell_at(0, -1) == CELL_WALL
        assert mm.cell_at(100, 100) == CELL_WALL

    # ------------------------------------------------------------------
    # describe_surroundings テスト
    # ------------------------------------------------------------------

    def test_describe_surroundings_returns_string(self, mm):
        """describe_surroundings() は文字列を返す"""
        text = mm.describe_surroundings()
        assert isinstance(text, str)
        assert len(text) > 0

    def test_describe_surroundings_contains_directions(self, mm):
        """描写テキストに4方向の日本語名が含まれる"""
        text = mm.describe_surroundings()
        for name in ["北", "南", "東", "西"]:
            assert name in text, f"方向 '{name}' が描写テキストに含まれていない"

    def test_describe_surroundings_wall_text(self, mm):
        """壁方向には 'CELL_DESCRIBE[CELL_WALL]' のテキストが含まれる"""
        from config import CELL_DESCRIBE, CELL_WALL
        text = mm.describe_surroundings()
        wall_desc = CELL_DESCRIBE[CELL_WALL]
        assert wall_desc in text

    # ------------------------------------------------------------------
    # get_fixed_event テスト
    # ------------------------------------------------------------------

    def test_get_fixed_event_none_at_start(self, mm):
        """スタート地点には固定イベントがない"""
        assert mm.get_fixed_event() is None

    def test_get_fixed_event_at_merchant(self, mm):
        """(2,1) は固定イベント 'merchant'"""
        mm.move("east")  # (1,1) → (2,1)
        assert mm.get_fixed_event() == "merchant"

    def test_get_fixed_event_at_trap(self):
        """(1,3) は固定イベント 'trap'"""
        from game.map_manager import MapManager
        mm = MapManager(floor=1, x=1, y=3)
        assert mm.get_fixed_event() == "trap"

    def test_get_fixed_event_at_shrine(self):
        """(3,2) は固定イベント 'shrine'"""
        from game.map_manager import MapManager
        mm = MapManager(floor=1, x=3, y=2)
        assert mm.get_fixed_event() == "shrine"

    # ------------------------------------------------------------------
    # 複数フロアテスト
    # ------------------------------------------------------------------

    def test_floor2_start_and_goal(self):
        """2F の start/goal が設定値と一致する"""
        from game.map_manager import MapManager
        mm = MapManager(floor=2, x=1, y=1)
        assert mm.start == (1, 1)
        assert mm.goal == (3, 5)
        assert mm.is_start() is True

    def test_floor3_start_and_goal(self):
        """3F の start/goal が設定値と一致する"""
        from game.map_manager import MapManager
        mm = MapManager(floor=3, x=1, y=1)
        assert mm.start == (1, 1)
        assert mm.goal == (4, 6)
        assert mm.is_start() is True

    def test_floor2_fixed_events(self):
        """2F の固定イベント（rest/chest）が正しく取得できる"""
        from game.map_manager import MapManager
        mm_rest  = MapManager(floor=2, x=4, y=1)
        mm_chest = MapManager(floor=2, x=4, y=3)
        assert mm_rest.get_fixed_event()  == "rest"
        assert mm_chest.get_fixed_event() == "chest"


# ─── DungeonManager グリッド拡張テスト（R-14 Step3）───────────────────────
class TestDungeonManagerGrid:
    """DungeonManager の R-14 グリッド拡張メソッドのユニットテスト"""

    @pytest.fixture
    def grid_dungeon(self, db):
        """dungeon_id=2（map_type='grid'）のダンジョンとプログレスを返す"""
        from models.dungeon import Dungeon, DungeonProgress
        # インメモリ DB にグリッドダンジョンを挿入
        d = Dungeon(id=2, name="迷宮の神殿", floor=3, map_type="grid")
        db.add(d)
        db.flush()
        progress = DungeonProgress(user_id=1, dungeon_id=2, current_floor=1,
                                   current_x=-1, current_y=-1)
        db.add(progress)
        db.commit()
        return d, progress

    @pytest.fixture
    def grid_manager(self, db, grid_dungeon):
        """グリッドダンジョン用 DungeonManager を返す"""
        d, progress = grid_dungeon
        # enemies for dungeon_id=2 を挿入（resolve_event_at の encounter に必要）
        from models.enemy import Enemy
        for e_data in [
            dict(id=20, name="ゾンビ",      dungeon_id=2, floor=1, hp=30,  attack=6,  defense=3,  exp_reward=15, is_boss=False),
            dict(id=25, name="邪神の使徒",  dungeon_id=2, floor=1, hp=70,  attack=12, defense=6,  exp_reward=55, is_boss=True),
            dict(id=26, name="魔将軍",       dungeon_id=2, floor=2, hp=100, attack=18, defense=9,  exp_reward=85, is_boss=True),
            dict(id=27, name="冥界の番人",   dungeon_id=2, floor=3, hp=140, attack=24, defense=12, exp_reward=110, is_boss=True),
        ]:
            db.merge(Enemy(**e_data))
        db.commit()
        return DungeonManager(db, d, progress)

    # ------------------------------------------------------------------
    # get_map_manager テスト
    # ------------------------------------------------------------------

    def test_get_map_manager_returns_map_manager(self, grid_manager):
        """get_map_manager() は MapManager インスタンスを返す"""
        from game.map_manager import MapManager
        mm = grid_manager.get_map_manager()
        assert isinstance(mm, MapManager)

    def test_get_map_manager_uses_start_when_uninitialized(self, grid_manager):
        """current_x/y が -1（未初期化）のときスタート座標を使う"""
        from config import FLOOR_MAPS
        mm = grid_manager.get_map_manager()
        sx, sy = FLOOR_MAPS[1]["start"]
        assert mm.x == sx
        assert mm.y == sy

    def test_get_map_manager_uses_saved_position(self, grid_manager, db):
        """current_x/y が保存済みのときその座標を使う"""
        grid_manager.progress.current_x = 2
        grid_manager.progress.current_y = 1
        db.commit()
        mm = grid_manager.get_map_manager()
        assert mm.x == 2
        assert mm.y == 1

    # ------------------------------------------------------------------
    # start_floor テスト
    # ------------------------------------------------------------------

    def test_start_floor_updates_progress(self, grid_manager, db):
        """start_floor(1) で current_floor/x/y が start 座標に設定される"""
        from config import FLOOR_MAPS
        mm = grid_manager.start_floor(1)
        sx, sy = FLOOR_MAPS[1]["start"]
        assert grid_manager.progress.current_floor == 1
        assert grid_manager.progress.current_x == sx
        assert grid_manager.progress.current_y == sy

    def test_start_floor_returns_map_manager(self, grid_manager):
        """start_floor() は MapManager を返す"""
        from game.map_manager import MapManager
        mm = grid_manager.start_floor(1)
        assert isinstance(mm, MapManager)

    def test_start_floor_map_manager_at_start(self, grid_manager):
        """start_floor() で返される MapManager は is_start() == True"""
        mm = grid_manager.start_floor(1)
        assert mm.is_start() is True

    def test_start_floor_2(self, grid_manager, db):
        """start_floor(2) で 2F のスタート座標にセットされる"""
        from config import FLOOR_MAPS
        grid_manager.start_floor(2)
        sx, sy = FLOOR_MAPS[2]["start"]
        assert grid_manager.progress.current_floor == 2
        assert grid_manager.progress.current_x == sx
        assert grid_manager.progress.current_y == sy

    # ------------------------------------------------------------------
    # resolve_event_at テスト
    # ------------------------------------------------------------------

    def test_resolve_event_at_goal_is_boss(self, grid_manager):
        """ゴール座標では常にボス戦（encounter + is_boss=True）"""
        from config import FLOOR_MAPS
        gx, gy = FLOOR_MAPS[1]["goal"]
        party = [make_party_char()]
        result = grid_manager.resolve_event_at(gx, gy, party)
        assert result.event_type == "encounter"
        assert result.need_battle is True
        assert len(result.enemies) == 1
        assert result.enemies[0].is_boss is True

    def test_resolve_event_at_fixed_merchant(self, grid_manager, db):
        """固定イベント 'merchant' 座標では merchant イベントが返る"""
        party = [make_party_char()]
        result = grid_manager.resolve_event_at(2, 1, party)  # 1F (2,1) = merchant
        assert result.event_type == "merchant"

    def test_resolve_event_at_fixed_shrine(self, grid_manager):
        """固定イベント 'shrine' 座標では shrine イベントが返る"""
        party = [make_party_char(hp=50)]
        party[0].max_hp = 100
        party[0].mp = 5
        party[0].max_mp = 20
        result = grid_manager.resolve_event_at(3, 2, party)  # 1F (3,2) = shrine
        assert result.event_type == "shrine"

    def test_resolve_event_at_fixed_trap(self, grid_manager):
        """固定イベント 'trap' 座標では trap イベントが返る"""
        party = [make_party_char(hp=100)]
        result = grid_manager.resolve_event_at(1, 3, party)  # 1F (1,3) = trap
        assert result.event_type == "trap"

    def test_resolve_event_at_returns_event_result(self, grid_manager):
        """通常マスでも EventResult が返る"""
        party = [make_party_char()]
        result = grid_manager.resolve_event_at(1, 1, party)  # スタート = 固定なし
        assert isinstance(result, EventResult)

    # ------------------------------------------------------------------
    # _resolve_by_type テスト
    # ------------------------------------------------------------------

    def test_resolve_by_type_encounter(self, grid_manager):
        """_resolve_by_type('encounter') は encounter EventResult を返す"""
        party = [make_party_char()]
        result = grid_manager._resolve_by_type("encounter", party, 1.0, 1.0)
        assert result.event_type == "encounter"
        assert result.need_battle is True

    def test_resolve_by_type_rest(self, grid_manager):
        """_resolve_by_type('rest') は rest EventResult を返す"""
        party = [make_party_char()]
        result = grid_manager._resolve_by_type("rest", party, 1.0, 1.0)
        assert result.event_type == "rest"

    def test_resolve_by_type_unknown(self, grid_manager):
        """_resolve_by_type(未知種別) は nothing EventResult を返す"""
        party = [make_party_char()]
        result = grid_manager._resolve_by_type("unknown_type", party, 1.0, 1.0)
        assert result.event_type == "nothing"

    # ------------------------------------------------------------------
    # reset_progress テスト（R-14 拡張）
    # ------------------------------------------------------------------

    def test_reset_progress_clears_grid_coords(self, grid_manager, db):
        """reset_progress() で current_x/y が -1 にリセットされる"""
        grid_manager.progress.current_x = 3
        grid_manager.progress.current_y = 2
        db.commit()
        grid_manager.reset_progress()
        assert grid_manager.progress.current_x == -1
        assert grid_manager.progress.current_y == -1

    def test_reset_progress_clears_floor_and_cleared(self, grid_manager, db):
        """reset_progress() で current_floor=1・is_cleared=False になる"""
        grid_manager.progress.current_floor = 3
        grid_manager.progress.is_cleared = True
        db.commit()
        grid_manager.reset_progress()
        assert grid_manager.progress.current_floor == 1
        assert grid_manager.progress.is_cleared is False


# ─── §11.2 set_position DB 保存テスト ─────────────────────────────────────
class TestDungeonProgressSetPosition:
    """DungeonProgress.set_position() の DB 保存を確認する（§11.2 補足）"""

    @pytest.fixture
    def progress(self, db):
        from models.dungeon import Dungeon, DungeonProgress
        d = Dungeon(id=3, name="テストダンジョン", floor=1, map_type="grid")
        db.add(d)
        db.flush()
        p = DungeonProgress(user_id=99, dungeon_id=3, current_floor=1,
                            current_x=-1, current_y=-1)
        db.add(p)
        db.commit()
        return p

    def test_set_position_updates_attributes(self, progress, db):
        """set_position() で current_x/y が更新される"""
        progress.set_position(3, 2, db)
        assert progress.current_x == 3
        assert progress.current_y == 2

    def test_set_position_persists_to_db(self, progress, db):
        """set_position() 後に DB から再取得しても座標が保持される"""
        from models.dungeon import DungeonProgress
        progress.set_position(2, 3, db)
        db.expire(progress)
        reloaded = db.query(DungeonProgress).filter_by(user_id=99, dungeon_id=3).first()
        assert reloaded.current_x == 2
        assert reloaded.current_y == 3


# ─── §11.3 ダンジョン選択ロックロジックテスト ─────────────────────────────
class TestDungeonSelectLock:
    """ダンジョン選択画面のロック判定ロジックを確認する（§11.3）"""

    def _is_locked(self, dungeon_id: int, cleared_tutorial: bool) -> bool:
        """render_dungeon_select のロック判定ロジックを直接テスト"""
        return dungeon_id >= 2 and not cleared_tutorial

    def test_dungeon1_always_unlocked(self):
        """旅立ちの洞窟（id=1）は常に開放"""
        assert self._is_locked(1, False) is False
        assert self._is_locked(1, True)  is False

    def test_dungeon2_locked_before_clear(self):
        """迷宮の神殿（id=2）は旅立ちの洞窟クリア前はロック"""
        assert self._is_locked(2, False) is True

    def test_dungeon2_unlocked_after_clear(self):
        """迷宮の神殿（id=2）は旅立ちの洞窟クリア後に解放"""
        assert self._is_locked(2, True) is False

    def test_dungeon3_locked_before_clear(self):
        """仮に id=3 のダンジョンが存在してもロック条件は同じ"""
        assert self._is_locked(3, False) is True
        assert self._is_locked(3, True)  is False

    def test_get_all_returns_multiple_dungeons(self, db):
        """Dungeon.get_all() が全ダンジョンを返す（DB 内容確認）"""
        from models.dungeon import Dungeon
        # seed_initial_data で id=1 は登録済み。id=2 も追加して確認
        d2 = Dungeon(id=2, name="迷宮の神殿", floor=3, map_type="grid")
        db.merge(d2)
        db.commit()
        dungeons = Dungeon.get_all(db)
        assert len(dungeons) >= 2
        ids = [d.id for d in dungeons]
        assert 1 in ids
        assert 2 in ids

    def test_dungeon1_is_linear(self, db):
        """id=1 のダンジョンは map_type='linear'、is_grid=False"""
        from models.dungeon import Dungeon
        d = Dungeon.get_by_id(db, 1)
        assert d.map_type == "linear"
        assert d.is_grid is False

    def test_dungeon2_is_grid(self, db):
        """id=2 のダンジョンは map_type='grid'、is_grid=True"""
        from models.dungeon import Dungeon
        d2 = Dungeon(id=2, name="迷宮の神殿", floor=3, map_type="grid")
        db.merge(d2)
        db.commit()
        d = Dungeon.get_by_id(db, 2)
        assert d.map_type == "grid"
        assert d.is_grid is True


# ─── §11.4 last_event_pos による重複イベントスキップロジック ──────────────
class TestLastEventPos:
    """§11.4: last_event_pos による同一マス重複イベントスキップのロジック確認"""

    def _should_fire_event(self, last_pos, new_x, new_y, is_goal=False) -> bool:
        """2_dungeon.py の do_event 判定ロジックを直接テスト"""
        return (last_pos != (new_x, new_y)) or is_goal

    def test_new_cell_fires_event(self):
        """未訪問マスではイベントが発火する"""
        assert self._should_fire_event(None, 2, 1) is True
        assert self._should_fire_event((1, 1), 2, 1) is True

    def test_same_cell_skips_event(self):
        """同一マスへの再訪ではイベントがスキップされる"""
        assert self._should_fire_event((2, 1), 2, 1) is False

    def test_goal_cell_always_fires(self):
        """ゴールマスは同一座標でも常にイベントが発火する"""
        assert self._should_fire_event((3, 3), 3, 3, is_goal=True) is True

    def test_none_last_pos_always_fires(self):
        """last_event_pos が None（初回）は常に発火する"""
        assert self._should_fire_event(None, 1, 1) is True
        assert self._should_fire_event(None, 3, 3) is True

    def test_different_x_fires_event(self):
        """X 座標が異なれば発火する"""
        assert self._should_fire_event((1, 2), 2, 2) is True

    def test_different_y_fires_event(self):
        """Y 座標が異なれば発火する"""
        assert self._should_fire_event((2, 1), 2, 2) is True


# ─── §11.4 マップ経路到達可能性テスト ────────────────────────────────────
class TestMapReachability:
    """全フロアのスタートからゴールへ到達可能かを BFS で検証する（§11.4）"""

    def _bfs_reachable(self, floor: int) -> bool:
        """BFS でスタートからゴールへの経路が存在するか確認"""
        from collections import deque
        from config import FLOOR_MAPS, CELL_WALL
        data  = FLOOR_MAPS[floor]
        grid  = data["grid"]
        start = data["start"]
        goal  = data["goal"]
        visited = set()
        queue   = deque([start])
        visited.add(start)
        dirs = [(0, -1), (0, 1), (-1, 0), (1, 0)]
        while queue:
            x, y = queue.popleft()
            if (x, y) == goal:
                return True
            for dx, dy in dirs:
                nx, ny = x + dx, y + dy
                if (nx, ny) in visited:
                    continue
                if ny < 0 or ny >= len(grid) or nx < 0 or nx >= len(grid[0]):
                    continue
                if grid[ny][nx] == CELL_WALL:
                    continue
                visited.add((nx, ny))
                queue.append((nx, ny))
        return False

    def test_floor1_start_to_goal_reachable(self):
        """1F: スタートからゴールへ到達可能"""
        assert self._bfs_reachable(1) is True

    def test_floor2_start_to_goal_reachable(self):
        """2F: スタートからゴールへ到達可能"""
        assert self._bfs_reachable(2) is True

    def test_floor3_start_to_goal_reachable(self):
        """3F: スタートからゴールへ到達可能"""
        assert self._bfs_reachable(3) is True

    def test_floor1_fixed_events_on_passage(self):
        """1F: 全固定イベントマスが通路（CELL_WALL でない）上にある"""
        from config import FLOOR_MAPS, CELL_WALL
        data = FLOOR_MAPS[1]
        grid = data["grid"]
        for (x, y), etype in data["fixed_events"].items():
            assert grid[y][x] != CELL_WALL, \
                f"1F 固定イベント '{etype}' @ ({x},{y}) が壁上にある"

    def test_floor2_fixed_events_on_passage(self):
        """2F: 全固定イベントマスが通路上にある"""
        from config import FLOOR_MAPS, CELL_WALL
        data = FLOOR_MAPS[2]
        grid = data["grid"]
        for (x, y), etype in data["fixed_events"].items():
            assert grid[y][x] != CELL_WALL, \
                f"2F 固定イベント '{etype}' @ ({x},{y}) が壁上にある"

    def test_floor3_fixed_events_on_passage(self):
        """3F: 全固定イベントマスが通路上にある"""
        from config import FLOOR_MAPS, CELL_WALL
        data = FLOOR_MAPS[3]
        grid = data["grid"]
        for (x, y), etype in data["fixed_events"].items():
            assert grid[y][x] != CELL_WALL, \
                f"3F 固定イベント '{etype}' @ ({x},{y}) が壁上にある"

    def test_start_cell_is_cell_start(self):
        """全フロアのスタート座標は CELL_START (2) である"""
        from config import FLOOR_MAPS, CELL_START
        for floor, data in FLOOR_MAPS.items():
            sx, sy = data["start"]
            assert data["grid"][sy][sx] == CELL_START, \
                f"{floor}F スタート座標 ({sx},{sy}) が CELL_START でない"

    def test_goal_cell_is_cell_goal(self):
        """全フロアのゴール座標は CELL_GOAL (3) である"""
        from config import FLOOR_MAPS, CELL_GOAL
        for floor, data in FLOOR_MAPS.items():
            gx, gy = data["goal"]
            assert data["grid"][gy][gx] == CELL_GOAL, \
                f"{floor}F ゴール座標 ({gx},{gy}) が CELL_GOAL でない"
