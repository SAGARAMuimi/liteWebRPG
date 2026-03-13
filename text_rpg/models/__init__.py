# models/__init__.py
# 外部キーの解決順序を保証するため、依存元テーブルから順にインポートする
from models.user import User          # 、1位: users テーブルを最初に登録
from models.dungeon import Dungeon, DungeonProgress  # 、2位: dungeons
from models.character import Character, PartyMember  # 、3位: characters, party_members
from models.enemy import Enemy        # 、4位: enemies
from models.skill import Skill        # 、5位: skills
from models.item import Item          # 、6位: items
from models.inventory import Inventory  # 、7位: inventories（users + items に依存）
from models.equipment import Equipment, CharacterEquipment  # 、8位: equipments / character_equipments

__all__ = [
    "User",
    "Dungeon",
    "DungeonProgress",
    "Character",
    "PartyMember",
    "Enemy",
    "Skill",
    "Item",
    "Inventory",
    "Equipment",
    "CharacterEquipment",
]
