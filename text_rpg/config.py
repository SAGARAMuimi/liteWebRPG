"""config.py - 定数・設定値の一元管理"""

import os
from pathlib import Path

from dotenv import load_dotenv


def _get_setting(key: str, default: str | None = None) -> str | None:
    """環境変数 → Streamlit secrets → default の順で設定値を取得する。"""
    env_val = os.getenv(key)
    if env_val is not None and env_val != "":
        return env_val

    # Streamlit Community Cloud の Secrets は st.secrets で提供される
    try:
        import streamlit as st  # 遅延 import（通常のテスト/CLI 実行でも落ちないように）

        if key in st.secrets:
            val = st.secrets.get(key)
            if val is None:
                return default
            return str(val)
    except Exception:
        pass

    return default


# Streamlit からの起動位置に依存せず、text_rpg/.env を確実に読む
_local_env_path = Path(__file__).with_name(".env")
load_dotenv(dotenv_path=_local_env_path)
# 併用運用のため、カレントディレクトリの .env も読めるようにしておく
load_dotenv()

# ─── 実行プロファイル/認証設定 ─────────────────────────────
# AUTH_MODE:
# - auto : DB が postgresql かつ Neon Auth Secrets がある場合のみ neon を選ぶ。なければ local。
# - local: 常にローカル（このプロジェクト既存の users + bcrypt）
# - neon : 常に Neon Auth（※未実装のため現時点ではエラーになる）
AUTH_MODE: str = (_get_setting("AUTH_MODE", "auto") or "auto").strip().lower()

# ─── データベース ───────────────────────────────────────────
DATABASE_URL: str = _get_setting("DATABASE_URL", "sqlite:///./text_rpg.db") or "sqlite:///./text_rpg.db"

# ─── クラス定義 ────────────────────────────────────────────
CLASS_NAMES: dict[str, str] = {
    "warrior": "戦士",
    "mage":    "魔法使い",
    "thief":   "盗賊",
    "priest":  "僧侶",
    "knight":  "騎士",
    "archer":  "弓使い",
    "monk":    "武道家",
    "bard":    "吟遊詩人",
}

# クラス別初期ステータス
CLASS_INITIAL_STATS: dict[str, dict] = {
    "warrior": {"max_hp": 120, "max_mp": 20,  "attack": 18, "defense": 12},
    "mage":    {"max_hp": 70,  "max_mp": 80,  "attack": 10, "defense": 5},
    "thief":   {"max_hp": 90,  "max_mp": 40,  "attack": 16, "defense": 8},
    "priest":  {"max_hp": 100, "max_mp": 60,  "attack": 12, "defense": 10},
    "knight":  {"max_hp": 140, "max_mp": 15,  "attack": 15, "defense": 16},
    "archer":  {"max_hp": 85,  "max_mp": 35,  "attack": 17, "defense": 7},
    "monk":    {"max_hp": 130, "max_mp": 10,  "attack": 20, "defense": 10},
    "bard":    {"max_hp": 80,  "max_mp": 70,  "attack": 8,  "defense": 8},
}

# クラス別説明文
CLASS_DESCRIPTIONS: dict[str, str] = {
    "warrior": "高い攻撃力と防御力を誇る前衛の要。バランス型の万能戦士。",
    "mage":    "強力な魔法で敵を殲滅する。HPは低いが魔法の威力は随一。",
    "thief":   "素早い連携攻撃と変幻自在の技を持つ。MP消費も控えめ。",
    "priest":  "味方を癒す回復の要。直接攻撃は苦手だが後衛として不可欠。",
    "knight":  "最高の防御力を誇る守護者。仲間への攻撃を引きつける挑発が得意。",
    "archer":  "遠距離から精確な攻撃を放つ弓の達人。攻撃力は高いが防御は低い。",
    "monk":    "武器を持たない格闘技の求道者。MP不要の技が多く継戦能力が高い。",
    "bard":    "歌と演奏でパーティを鼓舞する支援の専門家。MPが豊富で補助が得意。",
}

# ─── レベルアップ設定 ─────────────────────────────────────
EXP_PER_LEVEL: int = 50  # 必要経験値 = level * EXP_PER_LEVEL

LEVEL_UP_GROWTH: dict[str, tuple[int, int]] = {
    "max_hp":  (10, 15),  # (min, max)
    "max_mp":  (3,  8),
    "attack":  (1,  3),
    "defense": (1,  2),
}

# R-07 選択式成長プラン
LEVEL_UP_PLANS: dict[str, dict] = {
    "power": {
        "label": "⚔️ 火力",
        "desc": "攻撃力を重点的に強化する",
        "growth": {"max_hp": (5, 8), "max_mp": (2, 4), "attack": (3, 5), "defense": (1, 2)},
    },
    "tank": {
        "label": "🛡️ 耐久",
        "desc": "HPと防御力を重点的に強化する",
        "growth": {"max_hp": (15, 20), "max_mp": (1, 3), "attack": (1, 2), "defense": (2, 4)},
    },
    "support": {
        "label": "💫 支援",
        "desc": "MPを重点的に強化する（スキル・回復向け）",
        "growth": {"max_hp": (8, 12), "max_mp": (6, 12), "attack": (1, 2), "defense": (1, 3), "intelligence": (1, 1)},
    },
    "balanced": {
        "label": "⚖️ バランス",
        "desc": "全ステータスをバランス良く強化する",
        "growth": {"max_hp": (10, 15), "max_mp": (3, 8), "attack": (1, 3), "defense": (1, 2)},
    },
}

# クラスごとのデフォルト成長プラン（レベルアップ選択画面でハイライトされる推奨プラン）
CLASS_DEFAULT_LEVELUP_PLAN: dict[str, str] = {
    "warrior": "power",
    "mage":    "support",
    "thief":   "power",
    "priest":  "support",
    "knight":  "tank",
    "archer":  "power",
    "monk":    "tank",
    "bard":    "support",
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

# ─── お知らせ（R-16） ─────────────────────────────────────────
# NOTICE_TEXT: 表示するお知らせ文。空文字 / 未設定の場合は非表示。
# NOTICE_LEVEL: "info"（青）/ "warning"（黄）/ "error"（赤）のいずれか。デフォルト "info"。
# Streamlit Cloud の Secrets または環境変数で設定する。
# 例: NOTICE_TEXT = "2025-04-01 にメンテナンスのためログアウトが発生する場合があります。"
NOTICE_TEXT: str = _get_setting("NOTICE_TEXT", "") or ""
NOTICE_LEVEL: str = (_get_setting("NOTICE_LEVEL", "info") or "info").strip().lower()

# ─── 運営者・プライバシー（個人運用向け） ─────────────────────────────
# 表示名（例: "運営者" やハンドルネーム）
OPERATOR_NAME: str = os.getenv("OPERATOR_NAME", "運営者")

# 問い合わせ方法（例: "you@example.com" / "X: @your_handle" / 空文字で非表示）
OPERATOR_CONTACT: str = os.getenv("OPERATOR_CONTACT", "")

# 問い合わせ先（個別設定）: 値があるものだけ画面に表示される
OPERATOR_CONTACT_EMAIL: str = os.getenv("OPERATOR_CONTACT_EMAIL", "")
OPERATOR_CONTACT_X: str = os.getenv("OPERATOR_CONTACT_X", "")  # 例: "your_id" または "@your_id"
OPERATOR_CONTACT_DISCORD: str = os.getenv("OPERATOR_CONTACT_DISCORD", "")

# フィードバック/問い合わせ情報の保存期間（日）
FEEDBACK_RETENTION_DAYS: int = int(os.getenv("FEEDBACK_RETENTION_DAYS", "365"))

# ─── 難易度設定 ────────────────────────────────────────────
# 各倍率の意味:
#   enemy_hp_mult  : 敵の最大HPへの倍率
#   enemy_atk_mult : 敵の攻撃力への倍率
#   exp_mult       : 獲得経験値への倍率
#   heal_mult      : スキルによる回復量への倍率
DIFFICULTY_PRESETS: dict[str, dict] = {
    "easy":   {"label": "🟢 やさしい",   "enemy_hp_mult": 0.7, "enemy_atk_mult": 0.8, "exp_mult": 1.5, "heal_mult": 1.3, "gold_mult": 1.5},
    "normal": {"label": "🟡 ふつう",    "enemy_hp_mult": 1.0, "enemy_atk_mult": 1.0, "exp_mult": 1.0, "heal_mult": 1.0, "gold_mult": 1.0},
    "hard":   {"label": "🔴 むずかしい", "enemy_hp_mult": 1.5, "enemy_atk_mult": 1.2, "exp_mult": 0.8, "heal_mult": 0.8, "gold_mult": 0.8},
}

# 回復系スキルの INT ベース計算式（案B）
# 実回復量 = (skill.power + HEAL_SKILL_INT_BASE_OFFSET + intelligence * HEAL_SKILL_INT_SCALE) * heal_mult
HEAL_SKILL_INT_BASE_OFFSET: int = -4
HEAL_SKILL_INT_SCALE: int = 2

# ─── 状態異常定義 ────────────────────────────────────────────
STATUS_AILMENTS: dict[str, dict] = {
    "poison":   {"icon": "☠️",  "label": "毒"},
    "stun":     {"icon": "💫",  "label": "スタン"},
    "def_down": {"icon": "🔓",  "label": "防御低下"},
    "silence":  {"icon": "🤐",  "label": "沈黙"},
}

# ─── イベントマス設定 ─────────────────────────────────────────
# 通常部屋のイベント種別の重みテーブル（encounter / trap / merchant / shrine / rest）
# ボス部屋は対象外（常に encounter）
EVENT_WEIGHTS: dict[int, dict[str, float]] = {
    # 1F: 遭遇多め・休憩もある程度
    1: {"encounter": 0.42, "trap": 0.10, "merchant": 0.10, "shrine": 0.15, "rest": 0.15, "chest": 0.08},
    # 2F: 罠と遭遇増加
    2: {"encounter": 0.47, "trap": 0.15, "merchant": 0.10, "shrine": 0.10, "rest": 0.10, "chest": 0.08},
    # 3F: 遭遇最大・罠増加（休憩/祠が減る代わりに宝箱多め）
    3: {"encounter": 0.52, "trap": 0.20, "merchant": 0.05, "shrine": 0.05, "rest": 0.08, "chest": 0.10},
}

# 宝箱ゴールド報酬範囲（フロア別 min, max）
CHEST_GOLD_RANGE: dict[int, tuple[int, int]] = {
    1: (20,  60),
    2: (40, 100),
    3: (60, 150),
}

# 宝箱パターン（パターン名, 重み）
CHEST_PATTERNS: list[tuple[str, float]] = [
    ("gold",      0.35),  # ゴールドのみ
    ("item",      0.25),  # アイテムのみ
    ("gold_item", 0.20),  # ゴールド＋アイテム
    ("mimic",     0.10),  # ミミック（戦闘）
    ("empty",     0.10),  # 空（ハズレ）
]

# 宝箱から出るアイテムID（フェニックスの羽=5 は除く）
CHEST_ITEM_IDS: list[int] = [1, 2, 3, 4, 6]

# 罠ダメージ: パーティ全体に最大HPの(min%, max%)のダメージ
TRAP_DAMAGE_PCT: tuple[int, int] = (5, 15)

# 休憩回復量: HP/MP を最大値の %回復
REST_HEAL_PCT: int = 20

# 祈りの祠 回復量: HP/MP を最大値の %回復（休憩より多め）
SHRINE_HEAL_PCT: int = 30

# ─── 町設定 ───────────────────────────────────────────────────
# 売却買取率（定価の何割で買い取るか）
TOWN_SELL_RATE: float = 0.5

# 宿屋の休息プラン（key → label, cost[G], pct[%]）
TOWN_REST_COSTS: dict[str, dict] = {
    "partial": {"label": "仮眠",         "cost": 30, "pct": 50},   # HP/MP 50%回復
    "full":    {"label": "ゆっくり休む", "cost": 80, "pct": 100},  # HP/MP 全回復
}

# アイテム1種類あたりの最大所持数（ショップ購入上限）
TOWN_ITEM_MAX_STACK: int = 6

# ─── 装備システム ─────────────────────────────────────────────
# スロット表示名
EQUIPMENT_SLOT_NAMES: dict[str, str] = {
    "weapon":    "⚔️ 武器",
    "armor":     "🛡️ 防具",
    "accessory": "💍 アクセサリ",
}

# 商人の在庫（アイテムID とその定価）
# id は items テーブルの初期データと対応
MERCHANT_STOCK: list[dict] = [
    {"item_id": 1, "price": 50},   # ポーション
    {"item_id": 2, "price": 150},  # ハイポーション
    {"item_id": 3, "price": 80},   # エーテル
    {"item_id": 4, "price": 100},  # 万能薬
    {"item_id": 5, "price": 200},  # フェニックスの羽
    {"item_id": 6, "price": 120},  # 活力の薬
]

# ─── R-12 敵AI（疑似AI）────────────────────────────────────────
# 敵名をキーとするルールベースAI行動定義
# actions.type 一覧:
#   attack      : 単体攻撃（power_rate で威力倍率）
#   attack_all  : 全体攻撃（power_rate で威力倍率、省略時 0.7）
#   status      : 状態異常付与・単体（kind, duration）
#   status_all  : 状態異常付与・全体（kind, duration）
#   buff        : 自身へのバフ/デバフ（stat, amount, duration）
#   heal_self   : 自己回復（max_hp × power_rate）
ENEMY_AI_ACTIONS: dict[str, dict] = {
    "default": {
        "normal_rotation": ["attack", "attack", "attack"],
        "danger_priority": ["attack"],
        "actions": {
            "attack": {"type": "attack"},
        },
    },
    "スライム": {
        "normal_rotation": ["attack", "attack", "split_atk"],
        "danger_priority":  ["attack"],
        "actions": {
            "attack":    {"type": "attack"},
            "split_atk": {"type": "attack_all", "power_rate": 0.6},
        },
    },
    "コウモリ": {
        "normal_rotation": ["attack", "stun_bite", "attack"],
        "danger_priority":  ["attack"],
        "actions": {
            "attack":    {"type": "attack"},
            "stun_bite": {"type": "status", "kind": "stun", "duration": 1},
        },
    },
    "ゴブリン": {
        "normal_rotation": ["attack", "attack", "def_down_slash"],
        "danger_priority":  ["attack"],
        "actions": {
            "attack":         {"type": "attack"},
            "def_down_slash": {"type": "status", "kind": "def_down", "duration": 2},
        },
    },
    "オーク": {
        "normal_rotation": ["attack", "heavy_blow", "attack"],
        "danger_priority":  ["attack"],
        "actions": {
            "attack":     {"type": "attack"},
            "heavy_blow": {"type": "attack", "power_rate": 1.5},
        },
    },
    "ドラゴン": {
        "normal_rotation": ["attack", "breath", "attack", "attack"],
        "danger_priority":  ["breath", "attack"],
        "actions": {
            "attack": {"type": "attack"},
            "breath": {"type": "attack_all", "power_rate": 0.8},
        },
    },
    "ゴブリンキング": {
        "normal_rotation": ["attack", "buff_def_self", "attack", "call_minion_atk"],
        "danger_priority":  ["poison_all", "attack"],
        "actions": {
            "attack":          {"type": "attack"},
            "buff_def_self":   {"type": "buff", "stat": "defense", "amount": 8,  "duration": 3},
            "call_minion_atk": {"type": "attack_all", "power_rate": 0.5},
            "poison_all":      {"type": "status_all", "kind": "poison", "duration": 3},
        },
    },
    "オークチーフ": {
        "normal_rotation": ["attack", "attack", "def_down_slash", "heavy_blow"],
        "danger_priority":  ["rage", "heavy_blow"],
        "actions": {
            "attack":         {"type": "attack"},
            "heavy_blow":     {"type": "attack",  "power_rate": 1.6},
            "def_down_slash": {"type": "status",  "kind": "def_down", "duration": 3},
            "rage":           {"type": "buff",    "stat": "attack",   "amount": 10, "duration": 3},
        },
    },
    "ダークロード": {
        "normal_rotation": ["attack", "dark_blast", "silence_all", "attack", "buff_atk_self"],
        "danger_priority":  ["heal_self", "dark_blast", "attack"],
        "actions": {
            "attack":        {"type": "attack"},
            "dark_blast":    {"type": "attack_all",  "power_rate": 0.9},
            "silence_all":   {"type": "status_all",  "kind": "silence", "duration": 2},
            "buff_atk_self": {"type": "buff",         "stat": "attack",  "amount": 12, "duration": 3},
            "heal_self":     {"type": "heal_self",    "power_rate": 0.3},
        },
    },
    "ミミック": {
        "normal_rotation": ["attack", "spit_coin", "attack"],
        "danger_priority":  ["bite_hard", "attack"],
        "actions": {
            "attack":    {"type": "attack"},
            "spit_coin": {"type": "attack", "power_rate": 0.7},
            "bite_hard": {"type": "attack", "power_rate": 1.8},
        },
    },
}

# ─── R-13 味方自動行動AI ────────────────────────────────────────
# ポリシーキー → 表示名
ALLY_POLICIES: dict[str, str] = {
    "attack": "⚔️ 攻撃重視",
    "heal":   "💚 回復優先",
    "defend": "🛡️ 防御重視",
}

# クラスごとのデフォルトポリシー（キャラクター作成時の初期値）
CLASS_DEFAULT_POLICY: dict[str, str] = {
    "warrior": "attack",
    "mage":    "attack",
    "priest":  "heal",
    "thief":   "attack",
    "knight":  "defend",
    "archer":  "attack",
    "monk":    "attack",
    "bard":    "heal",
}

# ─── 知性値（味方 AI の判断精度）─────────────────────────────────
# 1〜10 スケール: 2=低（単純）  5=標準  8=高（戦況読解）
# 上限は 10（support プランで毎レベル +1 成長）
CLASS_INTELLIGENCE: dict[str, int] = {
    "warrior": 2,   # 旧: 1（低）
    "monk":    2,   # 旧: 1（低）
    "knight":  5,   # 旧: 2（中）
    "archer":  5,   # 旧: 2（中）
    "thief":   5,   # 旧: 2（中）
    "mage":    8,   # 旧: 3（高）
    "priest":  8,   # 旧: 3（高）
    "bard":    8,   # 旧: 3（高）
}

# 回復しきい値は game/battle.py の calc_heal_threshold() で線形補間して取得する
# （旧 ALLY_HEAL_THRESHOLDS は Section 8 で線形補間方式に移行済み）

# ─── R-12 敵AI 知性値拡張 ─────────────────────────────────────────
# 知性値別の DANGER フェーズ移行しきい値（HP比）
INTELLIGENCE_THRESHOLDS: dict[int, float] = {
    1: 0.35,   # 鈍感：HP35%以下でDANGER（気づくのが遅い）
    2: 0.50,   # 標準：HP50%以下でDANGER
    3: 0.65,   # 鋭敏：HP65%以下で早めに危機対応
}

# 知性値別の WIN_FIRST 判定しきい値（HP比）
WIN_FIRST_THRESHOLDS: dict[int, float] = {
    1: 0.10,   # 鈍感：HP10%以下のキャラのみ止めを狙う
    2: 0.15,   # 標準：HP15%以下
    3: 0.25,   # 鋭敏：HP25%以下のキャラも積極的に狙う
}
# ─── R-15 メタ進行（恒久解放）──────────────────────────────────────────────
# 全滅時に通常ゴールドの何割をメタGOLDに変換するか
META_GOLD_KEEP_RATE: float = 0.30

# メタアップグレード定義
# costs[rank-1]  = ランクを上げるために必要なメタGOLD
# bonuses[rank-1] = そのランクで得られるボーナス値
META_UPGRADES: dict[str, dict] = {
    "start_gold": {
        "label":   "💰 開始資金",
        "desc":    "ダンジョン突入時の所持金 +{bonus}G",
        "costs":   [30,  60, 100, 150, 200],
        "bonuses": [50, 100, 160, 230, 300],
    },
    "exp_bonus": {
        "label":   "⭐ EXP強化",
        "desc":    "獲得EXP +{bonus}%",
        "costs":   [50, 100, 180],
        "bonuses": [10,  20,  35],
    },
    "heal_bonus": {
        "label":   "💊 回復強化",
        "desc":    "回復スキル効果 +{bonus}%",
        "costs":   [60, 120, 200],
        "bonuses": [10,  20,  35],
    },
}

# 称号（実績）定義
META_TITLES: dict[str, dict] = {
    "first_clear":     {"label": "⚔️ 初陣の勝者",    "desc": "初めて戦闘に勝利した"},
    "floor2":          {"label": "🗺️ 探検家",        "desc": "2Fに到達した"},
    "floor3":          {"label": "🏔️ 深淵の挑戦者",  "desc": "3Fに到達した"},
    "dungeon_cleared": {"label": "👑 ダンジョン征服者", "desc": "ダンジョンをクリアした"},
    "perseverance":    {"label": "💪 不屈の意志",     "desc": "全滅を経験した"},
    "meta_shopper":    {"label": "🛒 強化の探求者",   "desc": "メタショップで初めて強化した"},
}

# ─── R-14 マップ移動（直角構成）──────────────────────────────────────────────

# セル種別
CELL_WALL    = 0  # 壁（移動不可）
CELL_PASSAGE = 1  # 通路（移動可能）
CELL_START   = 2  # スタート地点（各フロアの入場地点）
CELL_GOAL    = 3  # ボス部屋 / 次フロアへの扉

# 方向定義（name → (dx, dy)）
# 北 = Y 減少、南 = Y 増加（左上原点）
DIRECTIONS: dict[str, tuple[int, int]] = {
    "north": ( 0, -1),
    "south": ( 0,  1),
    "west":  (-1,  0),
    "east":  ( 1,  0),
}

DIRECTION_LABELS: dict[str, str] = {
    "north": "🔼 北",
    "south": "🔽 南",
    "west":  "◀️ 西",
    "east":  "▶️ 東",
}

DIRECTION_NAMES_JA: dict[str, str] = {
    "north": "北",
    "south": "南",
    "west":  "西",
    "east":  "東",
}

# セル種別 → 周辺描写テキスト
CELL_DESCRIBE: dict[int, str] = {
    CELL_WALL:    "壁が立ちはだかっている。",
    CELL_PASSAGE: "暗い通路が続いている。",
    CELL_GOAL:    "重厚な扉が見える…何かが待ち構えているようだ。",
    CELL_START:   "来た道が見える。",
}

# フロアマップ定義（dungeon_id=2「迷宮の神殿」専用）
# grid: [y][x] の二次元リスト（0=壁, 1=通路, 2=スタート, 3=ゴール）
# start: (x, y) スタート座標
# goal:  (x, y) ゴール座標
# fixed_events: {(x, y): event_type}  指定マスのイベント種別を固定する
FLOOR_MAPS: dict[int, dict] = {
    1: {
        "grid": [
            #  0  1  2  3  4
            [  0, 0, 0, 0, 0],  # y=0
            [  0, 2, 1, 1, 0],  # y=1  S─┬─
            [  0, 1, 0, 1, 0],  # y=2  │   │
            [  0, 1, 1, 3, 0],  # y=3  └─┴─G
            [  0, 0, 0, 0, 0],  # y=4
        ],
        "start": (1, 1),
        "goal":  (3, 3),
        "fixed_events": {
            (2, 1): "merchant",  # スタートから東に1マス
            (3, 2): "shrine",    # ゴールの1マス北
            (1, 3): "trap",      # ゴールへの南回り
        },
    },
    2: {
        "grid": [
            #  0  1  2  3  4  5
            [  0, 0, 0, 0, 0, 0],  # y=0
            [  0, 2, 1, 0, 1, 0],  # y=1  S─  ─
            [  0, 0, 1, 0, 1, 0],  # y=2    │   │
            [  0, 0, 1, 1, 1, 0],  # y=3    └─┬─┘
            [  0, 0, 0, 1, 0, 0],  # y=4      │
            [  0, 0, 0, 3, 0, 0],  # y=5      G
        ],
        "start": (1, 1),
        "goal":  (3, 5),
        "fixed_events": {
            (4, 1): "rest",    # 東の行き止まり（休憩）
            (4, 3): "chest",   # 合流地点の東（宝箱）
        },
    },
    3: {
        "grid": [
            #  0  1  2  3  4  5  6
            [  0, 0, 0, 0, 0, 0, 0],  # y=0
            [  0, 2, 1, 1, 0, 0, 0],  # y=1  S──
            [  0, 0, 0, 1, 0, 0, 0],  # y=2     │
            [  0, 0, 1, 1, 1, 1, 0],  # y=3  ───┼──
            [  0, 0, 1, 0, 0, 1, 0],  # y=4  │     │
            [  0, 0, 1, 1, 1, 1, 0],  # y=5  └───┬─┘
            [  0, 0, 0, 0, 3, 0, 0],  # y=6      G
        ],
        "start": (1, 1),
        "goal":  (4, 6),
        "fixed_events": {
            (2, 3): "shrine",    # 西ルートの分岐点
            (5, 3): "merchant",  # 東ルートの分岐点
            (2, 5): "rest",      # 南西の行き止まり
        },
    },
}

# ── FEEDBACK 不具合報告・改善要望 ─────────────────────────────────────
FEEDBACK_CATEGORIES: dict[str, dict] = {
    "bug":     {"label": "🐛 不具合",   "has_severity": True},
    "request": {"label": "💡 改善要望", "has_severity": False},
    "other":   {"label": "📝 その他",   "has_severity": False},
}
FEEDBACK_SEVERITIES: dict[str, str] = {
    "low":      "低",
    "normal":   "普通",
    "high":     "高",
    "critical": "致命的",
}
FEEDBACK_STATUSES: dict[str, str] = {
    "open":        "🔴 未対応",
    "in_progress": "🟡 対応中",
    "resolved":    "🟢 解決済",
    "closed":      "⚫ クローズ",
}
FEEDBACK_PAGE_LABELS: dict[str, str] = {
    "1_character": "キャラクター管理",
    "2_dungeon":   "ダンジョン探索",
    "3_battle":    "戦闘",
    "4_town":      "町",
    "other":       "その他・不明",
}
FEEDBACK_MAX_BODY_LENGTH: int   = 2000
FEEDBACK_DAILY_LIMIT: int       = 10
FEEDBACK_DUPLICATE_MINUTES: int = 5
# FEEDBACK_SESSION_LIMIT は匿名送信解禁時に追加予定