"""
config.py - 定数・設定値の一元管理
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── データベース ───────────────────────────────────────────
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./text_rpg.db")

# ─── クラス定義 ────────────────────────────────────────────
CLASS_NAMES: dict[str, str] = {
    "warrior": "戦士",
    "mage":    "魔法使い",
    "thief":   "盗賊",
    "priest":  "僧侶",
}

# クラス別初期ステータス
CLASS_INITIAL_STATS: dict[str, dict] = {
    "warrior": {"max_hp": 120, "max_mp": 20,  "attack": 18, "defense": 12},
    "mage":    {"max_hp": 70,  "max_mp": 80,  "attack": 10, "defense": 5},
    "thief":   {"max_hp": 90,  "max_mp": 40,  "attack": 16, "defense": 8},
    "priest":  {"max_hp": 100, "max_mp": 60,  "attack": 12, "defense": 10},
}

# ─── レベルアップ設定 ─────────────────────────────────────
EXP_PER_LEVEL: int = 50  # 必要経験値 = level * EXP_PER_LEVEL

LEVEL_UP_GROWTH: dict[str, tuple[int, int]] = {
    "max_hp":  (10, 15),  # (min, max)
    "max_mp":  (3,  8),
    "attack":  (1,  3),
    "defense": (1,  2),
}

# ─── ダンジョン設定 ────────────────────────────────────────
ENCOUNTER_RATE: dict[int, float] = {1: 0.6, 2: 0.7, 3: 0.8}
ENCOUNTER_COUNT: dict[int, tuple[int, int]] = {
    1: (1, 2),  # 1F: 1〜2体
    2: (1, 3),  # 2F: 1〜3体
    3: (2, 3),  # 3F: 2〜3体
}
ROOMS_PER_FLOOR: int = 3  # 各階層の部屋数（最後の部屋がボス）
MAX_FLOOR: int = 3
PARTY_SIZE: int = 4

# ─── UI設定 ───────────────────────────────────────────────
APP_TITLE: str = "⚔️ liteWebRPG"
