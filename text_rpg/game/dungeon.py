"""
game/dungeon.py - DungeonManager クラス
"""

from __future__ import annotations
import random
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from models.dungeon import Dungeon, DungeonProgress
from models.enemy import Enemy
from config import (
    ENCOUNTER_RATE, ENCOUNTER_COUNT, ROOMS_PER_FLOOR,
    EVENT_WEIGHTS, TRAP_DAMAGE_PCT, REST_HEAL_PCT, SHRINE_HEAL_PCT,
    MERCHANT_STOCK, CHEST_GOLD_RANGE, CHEST_PATTERNS, CHEST_ITEM_IDS,
)

# ミミックのフロア別ステータス（DB 非保存・戦闘時にインメモリ生成）
_MIMIC_STATS: dict[int, dict] = {
    1: {"hp": 45,  "attack": 12, "defense": 5,  "exp_reward": 30, "gold_reward": 25},
    2: {"hp": 65,  "attack": 16, "defense": 7,  "exp_reward": 45, "gold_reward": 40},
    3: {"hp": 90,  "attack": 22, "defense": 10, "exp_reward": 60, "gold_reward": 60},
}


@dataclass
class EventResult:
    """
    イベントマスの処理結果を格納するデータクラス。

    Attributes:
        event_type    : "encounter" / "trap" / "merchant" / "shrine" / "rest" / "chest" / "nothing"
        messages      : 戦闘ログ / イベントテキスト
        enemies       : 戦闘イベントの場合の敵リスト（それ以外は空）
        need_battle   : True なら戦闘画面へ遷移が必要
        merchant_stock: 商人マスの在庫 [{"item": Item, "price": int}]
        chest_gold    : 宝箱マスで獲得するゴールド（ミミック・空は 0）
        chest_item_id : 宝箱マスで獲得するアイテムID（ない場合は 0）
    """
    event_type: str = "nothing"
    messages: list[str] = field(default_factory=list)
    enemies: list = field(default_factory=list)
    need_battle: bool = False
    merchant_stock: list[dict] = field(default_factory=list)
    chest_gold: int = 0
    chest_item_id: int = 0


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
    # エンカウント制御（後方互換 API）
    # ──────────────────────────────────────────────────────
    def check_encounter(self) -> bool:
        rate = ENCOUNTER_RATE.get(self.current_floor, 0.6)
        return random.random() < rate

    def get_random_enemies(self, hp_mult: float = 1.0, atk_mult: float = 1.0) -> list[Enemy]:
        """現在の階層からランダムに複数体の敵を返す（clone して HP を独立させる）"""
        pool = Enemy.get_by_floor(self.db, self.dungeon.id, self.current_floor, boss=False)
        if not pool:
            return []
        min_count, max_count = ENCOUNTER_COUNT.get(self.current_floor, (1, 2))
        count = random.randint(min_count, max_count)
        selected = random.choices(pool, k=count)
        enemies = [e.clone() for e in selected]
        for e in enemies:
            e.hp = max(1, int(e.hp * hp_mult))
            e.attack = max(1, int(e.attack * atk_mult))
        return enemies

    def get_boss(self, hp_mult: float = 1.0, atk_mult: float = 1.0) -> Enemy | None:
        """現在の階層のボスを返す（clone して HP を独立させる）"""
        bosses = Enemy.get_by_floor(self.db, self.dungeon.id, self.current_floor, boss=True)
        if not bosses:
            return None
        boss = bosses[0].clone()
        boss.hp = max(1, int(boss.hp * hp_mult))
        boss.attack = max(1, int(boss.attack * atk_mult))
        return boss

    # ──────────────────────────────────────────────────────
    # イベント解決（メインエントリポイント）
    # ──────────────────────────────────────────────────────
    def resolve_event(
        self,
        party: list,
        room: int,
        hp_mult: float = 1.0,
        atk_mult: float = 1.0,
    ) -> EventResult:
        """
        部屋に入ったときのイベントを解決する。

        - ボス部屋（room >= ROOMS_PER_FLOOR）は常に encounter。
        - 通常部屋は EVENT_WEIGHTS の確率テーブルで種別を決定する。

        Returns:
            EventResult オブジェクト
        """
        if self.is_boss_room(room):
            return self._event_boss(hp_mult, atk_mult)

        floor = self.current_floor
        weights_map = EVENT_WEIGHTS.get(floor, EVENT_WEIGHTS[1])
        kinds   = list(weights_map.keys())
        weights = list(weights_map.values())
        event_type = random.choices(kinds, weights=weights, k=1)[0]

        if event_type == "encounter":
            return self._event_encounter(party, hp_mult, atk_mult)
        elif event_type == "trap":
            return self._event_trap(party)
        elif event_type == "merchant":
            return self._event_merchant()
        elif event_type == "shrine":
            return self._event_shrine(party)
        elif event_type == "rest":
            return self._event_rest(party)
        elif event_type == "chest":
            return self._event_chest()
        else:
            return EventResult(event_type="nothing", messages=["静かだ…何も起きなかった。"])

    # ──────────────────────────────────────────────────────
    # 各イベント実装
    # ──────────────────────────────────────────────────────
    def _event_boss(self, hp_mult: float, atk_mult: float) -> EventResult:
        boss = self.get_boss(hp_mult=hp_mult, atk_mult=atk_mult)
        if not boss:
            return EventResult(event_type="nothing", messages=["ボスが見つかりませんでした（データ不備）。"])
        return EventResult(
            event_type="encounter",
            messages=[f"⚠️ {boss.name} が現れた！ボス戦開始！"],
            enemies=[boss],
            need_battle=True,
        )

    def _event_encounter(self, party: list, hp_mult: float, atk_mult: float) -> EventResult:
        enemies = self.get_random_enemies(hp_mult=hp_mult, atk_mult=atk_mult)
        if not enemies:
            return EventResult(event_type="nothing", messages=["静かだ…何も起きなかった。"])
        names = "、".join(e.name for e in enemies)
        return EventResult(
            event_type="encounter",
            messages=[f"⚔️ {names} が現れた！"],
            enemies=enemies,
            need_battle=True,
        )

    def _event_trap(self, party: list) -> EventResult:
        """
        罠マス: パーティ全体にダメージを与える。
        - 刃罠（75%）: 最大HPの TRAP_DAMAGE_PCT % の物理ダメージ
        - 毒ガス罠（25%）: 最大HPの半分のダメージ（ダメージは少ないが不快）
        HP が 1 を下回らないように調整する（罠では死なない）。
        """
        min_pct, max_pct = TRAP_DAMAGE_PCT
        alive = [c for c in party if c.is_alive()]
        is_poison_gas = random.random() < 0.25

        if is_poison_gas:
            pct = max(min_pct // 2, 3)
            messages = ["⚠️ 毒ガス罠を踏んだ！毒の霧が立ち込めた…"]
        else:
            pct = random.randint(min_pct, max_pct)
            messages = ["⚠️ 刃の罠を踏んだ！"]

        for c in alive:
            dmg = max(1, c.max_hp * pct // 100)
            dmg = min(dmg, c.hp - 1)  # 即死防止
            if dmg > 0:
                c.hp -= dmg
                messages.append(f"  {c.name} が {dmg} のダメージを受けた！")
            else:
                messages.append(f"  {c.name} はギリギリ耐えた！")
        messages.append(f"（最大HPの {pct}% ダメージ）")
        return EventResult(
            event_type="trap",
            messages=messages,
            enemies=[],
            need_battle=False,
        )

    def _event_rest(self, party: list) -> EventResult:
        """休憩マス: 全員の HP/MP を最大値の REST_HEAL_PCT % 回復する。"""
        pct = REST_HEAL_PCT
        messages = ["🛌 休憩できる場所を見つけた。"]
        for c in party:
            if not c.is_alive():
                continue
            hp_gain = max(1, c.max_hp * pct // 100)
            mp_gain = max(0, c.max_mp * pct // 100)
            healed_hp = c.heal(hp_gain)
            healed_mp = min(mp_gain, c.max_mp - c.mp)
            c.mp = min(c.max_mp, c.mp + mp_gain)
            messages.append(f"  {c.name}  HP +{healed_hp}  MP +{healed_mp}")
        messages.append(f"（最大HP/MPの {pct}% 回復）")
        return EventResult(event_type="rest", messages=messages)

    def _event_shrine(self, party: list) -> EventResult:
        """
        祈りの祠マス: 全員の HP/MP を最大値の SHRINE_HEAL_PCT % 回復する。
        さらに低確率（30%）でランダムな一時バフを付与する。
        """
        pct = SHRINE_HEAL_PCT
        messages = ["⛩️ 祈りの祠を発見した。"]
        for c in party:
            if not c.is_alive():
                continue
            hp_gain = max(1, c.max_hp * pct // 100)
            mp_gain = max(0, c.max_mp * pct // 100)
            healed_hp = c.heal(hp_gain)
            healed_mp = min(mp_gain, c.max_mp - c.mp)
            c.mp = min(c.max_mp, c.mp + mp_gain)
            messages.append(f"  {c.name}  HP +{healed_hp}  MP +{healed_mp}")
        messages.append(f"（最大HP/MPの {pct}% 回復）")
        return EventResult(event_type="shrine", messages=messages)

    def _event_chest(self) -> EventResult:
        """
        宝箱マス: CHEST_PATTERNS の確率テーブルで 5 パターンを決定。
          gold      : ゴールドのみ
          item      : アイテムのみ
          gold_item : ゴールド＋アイテム
          mimic     : ミミック（戦闘遷移）
          empty     : 空（ハズレ）
        """
        floor = self.current_floor
        min_gold, max_gold = CHEST_GOLD_RANGE.get(floor, (20, 60))

        patterns = [p[0] for p in CHEST_PATTERNS]
        weights  = [p[1] for p in CHEST_PATTERNS]
        pattern  = random.choices(patterns, weights=weights, k=1)[0]

        # ミミック
        if pattern == "mimic":
            stats = _MIMIC_STATS.get(floor, _MIMIC_STATS[1])
            mimic = Enemy(
                name="ミミック",
                dungeon_id=self.dungeon.id,
                floor=floor,
                is_boss=False,
                status_resistance="",
                **stats,
            )
            return EventResult(
                event_type="chest",
                messages=["📦 宝箱を発見した！", "👾 ミミックだ！！"],
                enemies=[mimic],
                need_battle=True,
            )

        gold    = 0
        item_id = 0
        messages = ["📦 宝箱を発見した！"]

        if pattern in ("gold", "gold_item"):
            gold = random.randint(min_gold, max_gold)
            messages.append(f"  💰 {gold} G を手に入れた！")

        if pattern in ("item", "gold_item"):
            item_id = random.choice(CHEST_ITEM_IDS)
            from models.item import Item
            item = Item.get_by_id(self.db, item_id)
            item_name = item.name if item else "アイテム"
            messages.append(f"  🎁 {item_name} を手に入れた！")

        if pattern == "empty":
            messages.append("  📫 空だった…")

        return EventResult(
            event_type="chest",
            messages=messages,
            chest_gold=gold,
            chest_item_id=item_id,
        )

    def _event_merchant(self) -> EventResult:
        """商人マス: 在庫リストを返す。購入処理は呼び出し側（page）で行う。"""
        from models.item import Item
        stock: list[dict] = []
        for entry in MERCHANT_STOCK:
            item = Item.get_by_id(self.db, entry["item_id"])
            if item:
                stock.append({"item": item, "price": entry["price"]})
        messages = ["🛒 商人に出会った！"]
        if not stock:
            messages.append("商品が見当たらない…")
        return EventResult(
            event_type="merchant",
            messages=messages,
            merchant_stock=stock,
        )

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

