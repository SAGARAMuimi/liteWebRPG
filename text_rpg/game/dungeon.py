"""
game/dungeon.py - DungeonManager クラス
"""

from __future__ import annotations
import random
from sqlalchemy.orm import Session
from models.dungeon import Dungeon, DungeonProgress
from models.enemy import Enemy
from config import ENCOUNTER_RATE, ENCOUNTER_COUNT, ROOMS_PER_FLOOR


class DungeonManager:
    def __init__(self, db: Session, dungeon: Dungeon, progress: DungeonProgress) -> None:
        self.db = db
        self.dungeon = dungeon
        self.progress = progress

    # ──────────────────────────────────────────────────────
    # プロパティ
    # ──────────────────────────────────────────────────────
    @property
    def current_floor(self) -> int:
        return self.progress.current_floor

    @property
    def current_room(self) -> int:
        """st.session_state で管理するため、外部から渡す想定"""
        return 0

    def is_boss_room(self, room: int) -> bool:
        """最終部屋（ROOMS_PER_FLOOR 番目）がボス部屋"""
        return room >= ROOMS_PER_FLOOR

    # ──────────────────────────────────────────────────────
    # エンカウント制御
    # ──────────────────────────────────────────────────────
    def check_encounter(self) -> bool:
        rate = ENCOUNTER_RATE.get(self.current_floor, 0.6)
        return random.random() < rate

    def get_random_enemies(self) -> list[Enemy]:
        """現在の階層からランダムに複数体の敵を返す（clone して HP を独立させる）"""
        pool = Enemy.get_by_floor(self.db, self.dungeon.id, self.current_floor, boss=False)
        if not pool:
            return []
        min_count, max_count = ENCOUNTER_COUNT.get(self.current_floor, (1, 2))
        count = random.randint(min_count, max_count)
        selected = random.choices(pool, k=count)
        return [e.clone() for e in selected]

    def get_boss(self) -> Enemy | None:
        """現在の階層のボスを返す（clone して HP を独立させる）"""
        bosses = Enemy.get_by_floor(self.db, self.dungeon.id, self.current_floor, boss=True)
        if not bosses:
            return None
        return bosses[0].clone()

    # ──────────────────────────────────────────────────────
    # 進行管理
    # ──────────────────────────────────────────────────────
    def advance_to_next_floor(self) -> bool:
        """
        次の階層に進む。
        全階層クリアなら is_cleared = True にして True を返す。
        """
        if self.progress.current_floor >= self.dungeon.floor:
            self.progress.is_cleared = True
            self.progress.save(self.db)
            return True  # 全クリア
        self.progress.current_floor += 1
        self.progress.save(self.db)
        return False

    def reset_progress(self) -> None:
        """進行状況をリセット（再挑戦用）"""
        self.progress.current_floor = 1
        self.progress.is_cleared = False
        self.progress.save(self.db)
