"""
utils/helpers.py - 汎用ユーティリティ関数
"""

from config import CLASS_NAMES


def class_display_name(class_type: str) -> str:
    """class_type -> 日本語表示名"""
    return CLASS_NAMES.get(class_type, class_type)


def hp_bar(current: int, maximum: int, width: int = 20) -> str:
    """テキストベースの HP バーを生成する"""
    if maximum <= 0:
        return "[" + "░" * width + "]"
    ratio = max(0.0, min(1.0, current / maximum))
    filled = int(ratio * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {current}/{maximum}"


def seed_initial_data(db) -> None:
    """
    data/seed/*.csv を読み込み、マスタデータを DB に UPSERT する。
    merge() を使うため既存 DB でも新規追加分が反映される（冪等）。
    投入順: dungeons → flush → enemies / skills / items → equipments
    """
    import csv
    from pathlib import Path

    from models.dungeon import Dungeon
    from models.enemy import Enemy
    from models.item import Item
    from models.skill import Skill
    from models.equipment import Equipment

    seed_dir = Path(__file__).parent.parent / "data" / "seed"

    # ── dungeons.csv ──────────────────────────────────────
    with open(seed_dir / "dungeons.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            db.merge(Dungeon(
                id=int(row["id"]),
                name=row["name"],
                floor=int(row["floor"]),
                map_type=row.get("map_type") or "linear",
            ))
    # FK 制約のため Dungeon を先に確定させる
    db.flush()

    # ── enemies.csv ───────────────────────────────────────
    with open(seed_dir / "enemies.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            db.merge(Enemy(
                id=int(row["id"]),
                name=row["name"],
                dungeon_id=int(row["dungeon_id"]),
                floor=int(row["floor"]),
                hp=int(row["hp"]),
                attack=int(row["attack"]),
                defense=int(row["defense"]),
                exp_reward=int(row["exp_reward"]),
                gold_reward=int(row["gold_reward"]),
                is_boss=bool(int(row["is_boss"])),
                status_resistance=row.get("status_resistance") or "",
                intelligence=int(row["intelligence"]),
            ))

    # ── skills.csv ────────────────────────────────────────
    with open(seed_dir / "skills.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            db.merge(Skill(
                id=int(row["id"]),
                name=row["name"],
                class_type=row["class_type"],
                mp_cost=int(row["mp_cost"]),
                power=int(row["power"]),
                effect_type=row["effect_type"],
                target_type=row.get("target_type") or "self",
                duration=int(row.get("duration") or 0),
                cooldown=int(row.get("cooldown") or 0),
            ))

    # ── items.csv ─────────────────────────────────────────
    with open(seed_dir / "items.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            db.merge(Item(
                id=int(row["id"]),
                name=row["name"],
                description=row["description"],
                effect_type=row["effect_type"],
                power=int(row["power"]),
                target_type=row.get("target_type") or "ally",
                duration=int(row.get("duration") or 0),
                price=int(row.get("price") or 0),
            ))

    # ── equipments.csv ────────────────────────────────────
    with open(seed_dir / "equipments.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            db.merge(Equipment(
                id=int(row["id"]),
                name=row["name"],
                description=row["description"],
                slot=row["slot"],
                atk_bonus=int(row["atk_bonus"]),
                def_bonus=int(row["def_bonus"]),
                hp_bonus=int(row["hp_bonus"]),
                mp_bonus=int(row["mp_bonus"]),
                price=int(row["price"]),
                required_class=row.get("required_class") or "",
                disposable=bool(int(row.get("disposable") or 0)),
            ))

    db.commit()


def give_starter_items(db, user_id: int) -> None:
    """
    新規ユーザーにポーション×3を付与する。
    既にインベントリが存在する場合は付与しない（重複防止）。
    """
    from models.inventory import Inventory
    existing = db.query(Inventory).filter(Inventory.user_id == user_id).first()
    if existing:
        return  # 既に付与済み
    Inventory.add_item(db, user_id, item_id=1, quantity=3)  # ポーション×3
