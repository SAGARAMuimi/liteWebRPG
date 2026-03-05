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
        assert leveled is True
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
