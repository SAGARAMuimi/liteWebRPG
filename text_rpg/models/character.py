"""
models/character.py - Character / PartyMember モデル
"""

from __future__ import annotations
import random
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, Session
from models.database import Base
from config import CLASS_INITIAL_STATS, EXP_PER_LEVEL, LEVEL_UP_GROWTH


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    class_type: Mapped[str] = mapped_column(String(16), nullable=False)
    level: Mapped[int] = mapped_column(default=1, nullable=False)
    exp: Mapped[int] = mapped_column(default=0, nullable=False)
    hp: Mapped[int] = mapped_column(nullable=False)
    max_hp: Mapped[int] = mapped_column(nullable=False)
    mp: Mapped[int] = mapped_column(nullable=False)
    max_mp: Mapped[int] = mapped_column(nullable=False)
    attack: Mapped[int] = mapped_column(nullable=False)
    defense: Mapped[int] = mapped_column(nullable=False)

    # ──────────────────────────────────────────────────────
    @staticmethod
    def create(db: Session, user_id: int, name: str, class_type: str) -> "Character":
        stats = CLASS_INITIAL_STATS[class_type]
        chara = Character(
            user_id=user_id,
            name=name,
            class_type=class_type,
            hp=stats["max_hp"],
            max_hp=stats["max_hp"],
            mp=stats["max_mp"],
            max_mp=stats["max_mp"],
            attack=stats["attack"],
            defense=stats["defense"],
        )
        db.add(chara)
        db.commit()
        db.refresh(chara)
        return chara

    @staticmethod
    def get_by_user(db: Session, user_id: int) -> list["Character"]:
        return db.query(Character).filter(Character.user_id == user_id).all()

    def is_alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, amount: int) -> int:
        actual = max(1, amount)
        self.hp = max(0, self.hp - actual)
        return actual

    def heal(self, amount: int) -> int:
        before = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp - before

    def gain_exp(self, db: Session, amount: int) -> bool:
        """経験値を加算し、レベルアップした場合 True を返す"""
        self.exp += amount
        leveled_up = False
        while self.exp >= self.level * EXP_PER_LEVEL:
            self.exp -= self.level * EXP_PER_LEVEL
            self.level_up()
            leveled_up = True
        merged = db.merge(self)
        db.commit()
        # session_state上のオブジェクトにも変更を反映
        for attr in ("exp", "level", "hp", "max_hp", "mp", "max_mp", "attack", "defense"):
            setattr(self, attr, getattr(merged, attr))
        return leveled_up

    def level_up(self) -> None:
        self.level += 1
        for stat, (mn, mx) in LEVEL_UP_GROWTH.items():
            growth = random.randint(mn, mx)
            setattr(self, stat, getattr(self, stat) + growth)
        # レベルアップ時に HP / MP を全回復
        self.hp = self.max_hp
        self.mp = self.max_mp

    def save(self, db: Session) -> None:
        db.merge(self)
        db.commit()

    # ──────────────────────────────────────────────────────
    # R-11 装備システム
    # ──────────────────────────────────────────────────────
    def _apply_equip_bonus(self, equipment, sign: int) -> None:
        """sign=+1 でボーナス付与、sign=-1 でボーナス削除"""
        self.attack  += sign * equipment.atk_bonus
        self.defense += sign * equipment.def_bonus
        self.max_hp  += sign * equipment.hp_bonus
        self.max_mp  += sign * equipment.mp_bonus

    def equip(self, db: Session, equipment) -> str:
        """
        装備を付ける。同スロットに既存装備があれば先に外す。
        ステータスボーナスをキャラクターの基礎値に加算して DB 保存する。
        Returns: 処理メッセージ
        """
        from models.equipment import Equipment as Eq, CharacterEquipment as CE

        # 同スロットの既存装備を外す
        existing_ce = CE.get_by_slot(db, self.id, equipment.slot)
        if existing_ce:
            old_equip = Eq.get_by_id(db, existing_ce.equipment_id)
            if old_equip:
                self._apply_equip_bonus(old_equip, sign=-1)
            db.query(CE).filter(
                CE.character_id == self.id,
                CE.slot == equipment.slot,
            ).delete()
            db.flush()

        # 新装備のボーナスを加算
        self._apply_equip_bonus(equipment, sign=+1)
        # HP/MP を新 max 値でクランプ
        self.hp = min(self.hp, self.max_hp)
        self.mp = min(self.mp, self.max_mp)

        # 装備スロットを DB に登録
        db.add(CE(character_id=self.id, equipment_id=equipment.id, slot=equipment.slot))
        merged = db.merge(self)
        db.commit()
        for attr in ("attack", "defense", "max_hp", "max_mp", "hp", "mp"):
            setattr(self, attr, getattr(merged, attr))
        return f"{self.name} が {equipment.name} を装備した！"

    def unequip(self, db: Session, slot: str) -> str:
        """
        指定スロットの装備を外す。
        - disposable=True  : 装備は消滅する（消耗品）
        - disposable=False : キャラクターインベントリに戻る
        Returns: 処理メッセージ
        """
        from models.equipment import Equipment as Eq, CharacterEquipment as CE, CharacterInventory as CI
        from config import EQUIPMENT_SLOT_NAMES

        existing_ce = CE.get_by_slot(db, self.id, slot)
        if not existing_ce:
            slot_name = EQUIPMENT_SLOT_NAMES.get(slot, slot)
            return f"{slot_name} スロットに装備がありません。"

        equip = Eq.get_by_id(db, existing_ce.equipment_id)
        equip_name = equip.name if equip else "装備"
        if equip:
            self._apply_equip_bonus(equip, sign=-1)
            # max_hp/max_mp が下がった場合、HP/MP を上限でクランプ
            self.hp = min(self.hp, self.max_hp)
            self.mp = min(self.mp, self.max_mp)

        db.query(CE).filter(
            CE.character_id == self.id,
            CE.slot == slot,
        ).delete()
        merged = db.merge(self)
        db.commit()
        for attr in ("attack", "defense", "max_hp", "max_mp", "hp", "mp"):
            setattr(self, attr, getattr(merged, attr))

        # disposable=False ならインベントリに戻す
        if equip and not equip.disposable:
            CI.add(db, self.id, equip.id, qty=1)
            return f"{self.name} が {equip_name} を外した。（インベントリに戻りました）"

        return f"{self.name} が {equip_name} を外した。（消耗品のため消滅）"


class PartyMember(Base):
    __tablename__ = "party_members"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id"), nullable=False)
    slot: Mapped[int] = mapped_column(nullable=False)  # 1〜4

    @staticmethod
    def set_party(db: Session, user_id: int, slot_char_map: dict[int, int]) -> None:
        """
        slot_char_map: {slot: character_id}
        既存のパーティを削除してから再登録（UPSERT相当）
        """
        db.query(PartyMember).filter(PartyMember.user_id == user_id).delete()
        for slot, character_id in slot_char_map.items():
            db.add(PartyMember(user_id=user_id, character_id=character_id, slot=slot))
        db.commit()

    @staticmethod
    def get_party_characters(db: Session, user_id: int) -> list[Character]:
        """スロット順にキャラクターを返す"""
        members = (
            db.query(PartyMember)
            .filter(PartyMember.user_id == user_id)
            .order_by(PartyMember.slot)
            .all()
        )
        characters = []
        for m in members:
            chara = db.query(Character).filter(Character.id == m.character_id).first()
            if chara:
                characters.append(chara)
        return characters
