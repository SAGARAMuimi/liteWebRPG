"""
tests/test_dungeon.py - DungeonManager のユニットテスト
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.database import Base
from models.dungeon import Dungeon, DungeonProgress
from models.enemy import Enemy
from models.skill import Skill
from game.dungeon import DungeonManager
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
