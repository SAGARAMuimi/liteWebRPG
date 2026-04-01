# 詳細設計書

**プロジェクト名**: liteWebRPG  
**バージョン**: 1.0.0  
**作成日**: 2026-03-05  

---

## 目次
1. [システム構成](#1-システム構成)
2. [画面設計](#2-画面設計)
3. [クラス・モジュール設計](#3-クラスモジュール設計)
4. [データベース詳細設計](#4-データベース詳細設計)
5. [ゲームパラメータ定義](#5-ゲームパラメータ定義)
6. [処理フロー設計](#6-処理フロー設計)
7. [セッション状態管理](#7-セッション状態管理)
8. [エラーハンドリング](#8-エラーハンドリング)

---

## 1. システム構成

### 1.1 アーキテクチャ概要

```
ブラウザ (ユーザー)
    ↕ HTTP
Streamlit アプリ (app.py / pages/)
    ↕ SQLAlchemy ORM
SQLite / MySQL (DB)
```

### 1.2 ファイル構成・役割詳細

```
text_rpg/
│── app.py                  # トップページ（ログイン画面）
│── config.py               # 定数・設定値の一元管理
│── requirements.txt        # 依存ライブラリ
│── .env                    # 環境変数（DB接続URL等）
│── pages/
│   ├── 1_character.py      # キャラクター作成・パーティ編成画面
│   ├── 2_dungeon.py        # ダンジョン探索画面
│   └── 3_battle.py         # 戦闘画面
│── models/
│   ├── database.py         # DB接続・セッション管理
│   ├── character.py        # Character / PartyMember モデル
│   ├── dungeon.py          # Dungeon / DungeonProgress モデル
│   ├── enemy.py            # Enemy モデル
│   ├── skill.py            # Skill モデル
│   └── user.py             # User モデル
│── game/
│   ├── battle.py           # 戦闘ロジック（BattleEngine クラス）
│   └── dungeon.py          # ダンジョン探索ロジック（DungeonManager クラス）
│── static/
│   └── images/             # キャラクター・敵の画像（任意）
│── utils/
│   ├── auth.py             # 認証ヘルパー関数
│   └── helpers.py          # 汎用ユーティリティ関数
│── data/
│   └── db_init.sql         # 初期データ投入スクリプト
└── tests/
    ├── test_battle.py      # 戦闘ロジックのユニットテスト
    ├── test_dungeon.py     # ダンジョンロジックのユニットテスト
    └── test_models.py      # モデルのユニットテスト
```

---

## 2. 画面設計

### 2.1 画面一覧

| 画面ID | ファイル           | 画面名               | 遷移元             |
|--------|-------------------|---------------------|--------------------|
| SCR-01 | app.py            | ログイン・登録画面   | （起点）           |
| SCR-02 | 1_character.py    | キャラクター管理画面 | SCR-01（ログイン後）|
| SCR-03 | 2_dungeon.py      | ダンジョン探索画面   | SCR-02（パーティ確定後）|
| SCR-04 | 3_battle.py       | 戦闘画面             | SCR-03（エンカウント時）|

### 2.2 各画面の詳細

#### SCR-01: ログイン・登録画面（app.py）

**表示要素**
- タイトルロゴ / ゲームタイトルテキスト
- ユーザー名入力フォーム
- パスワード入力フォーム
- ログインボタン
- 新規登録ボタン

**処理**
1. `streamlit-authenticator` を使用してログイン状態を確認
2. 認証成功 → `st.session_state["user_id"]` にユーザーIDをセット → SCR-02 へリダイレクト
3. 新規登録 → `users` テーブルに INSERT → 自動ログイン → SCR-02 へ

---

#### SCR-02: キャラクター管理画面（1_character.py）

**表示要素**
- 登録済みキャラクター一覧（最大4名）
- キャラクター作成フォーム
  - キャラクター名（テキスト入力）
  - クラス選択（セレクトボックス）
- パーティ編成エリア（スロット1～4にキャラクターをアサイン）
- ダンジョン探索開始ボタン（パーティが4名揃った場合に有効化）

**処理**
1. ログイン済み確認（未ログインなら SCR-01 に戻す）
2. `characters` テーブルから `user_id` でキャラクター一覧を取得・表示
3. キャラクター作成時、クラスに応じた初期パラメータを設定して INSERT
4. パーティ編成を `party_members` テーブルに UPSERT
5. パーティ4名確定後、`st.session_state["party"]` に格納

---

#### SCR-03: ダンジョン探索画面（2_dungeon.py）

**表示要素**
- パーティステータス表示（HP/MP/レベル）
- 現在の階層表示
- 探索進行ログ（テキストエリア）
- 「先に進む」ボタン
- 「撤退する」ボタン

**処理**
1. `DungeonManager.advance_floor()` を呼び出し
2. ランダムエンカウント判定（確率は各階層で設定）
3. エンカウント発生 → `st.session_state["battle_enemies"]` に敵データをセット → SCR-04 に遷移
4. ボス部屋到達 → 必ずボス戦発生
5. 階層クリア → `dungeon_progress` を更新 → 次の階層へ

---

#### SCR-04: 戦闘画面（3_battle.py）

**表示要素**
- 敵の情報（名前・HP バー）
- パーティの情報（名前・HP バー・MP）
- 行動選択ボタン（攻撃 / スキル / 防御）
- スキル選択モーダル（スキルボタン押下時に表示）
- 戦闘ログ（テキストエリア）
- リザルト画面（勝利 / 敗北）

**処理フロー**
1. プレイヤーターン：ボタン押下で行動選択
2. `BattleEngine.player_action()` を呼び出して結果を計算
3. 敵ターン：`BattleEngine.enemy_action()` を自動実行
4. HP が 0 になったキャラクター・敵を戦闘不能状態にする
5. 全敵撃破 → 勝利 → 経験値付与 → レベルアップ判定 → SCR-03 に戻る
6. パーティ全滅 → 敗北 → ゲームオーバー画面 → SCR-02 に戻る

---

## 3. クラス・モジュール設計

### 3.1 models/user.py

```python
class User(Base):
    __tablename__ = "users"
    id: int          # PK, AUTO INCREMENT
    name: str        # ユーザー名 (UNIQUE)
    password: str    # ハッシュ化パスワード
    created_at: datetime

    # メソッド
    @staticmethod
    def create(name: str, password: str) -> "User"
    @staticmethod
    def find_by_name(name: str) -> "User | None"
```

### 3.2 models/character.py

```python
class Character(Base):
    __tablename__ = "characters"
    id: int
    user_id: int     # FK -> users.id
    name: str
    class_type: str  # "warrior" | "mage" | "thief" | "priest"
    level: int       # デフォルト: 1
    exp: int         # デフォルト: 0
    hp: int
    max_hp: int
    mp: int
    max_mp: int
    attack: int
    defense: int
    intelligence: int  # 味方AI判断・回復スキル計算用の知性値

    # メソッド
    def is_alive(self) -> bool
    def take_damage(self, amount: int) -> int   # 実ダメージ量を返す
    def heal(self, amount: int) -> int          # 実回復量を返す
    def gain_exp(self, amount: int) -> bool     # レベルアップした場合 True
    def level_up(self) -> None                  # パラメータを成長させる

class PartyMember(Base):
    __tablename__ = "party_members"
    id: int
    user_id: int     # FK -> users.id
    character_id: int # FK -> characters.id
    slot: int        # 1〜4
```

### 3.3 models/enemy.py

```python
class Enemy(Base):
    __tablename__ = "enemies"
    id: int
    name: str
    dungeon_id: int  # FK -> dungeons.id
    floor: int
    hp: int
    attack: int
    defense: int
    exp_reward: int
    intelligence: int  # 敵AI判断用の知性値
    is_boss: bool

    # メソッド
    def is_alive(self) -> bool
    def take_damage(self, amount: int) -> int
```

### 3.4 models/skill.py

```python
class Skill(Base):
    __tablename__ = "skills"
    id: int
    name: str
    class_type: str       # 使用可能クラス（"mage" など、"all" で全クラス）
    mp_cost: int
    power: int
    effect_type: str      # "attack" | "heal" | "buff" | "cure" など
```

### 3.5 models/dungeon.py

```python
class Dungeon(Base):
    __tablename__ = "dungeons"
    id: int
    name: str
    floor: int  # 最大階層数

class DungeonProgress(Base):
    __tablename__ = "dungeon_progress"
    id: int
    user_id: int      # FK -> users.id
    dungeon_id: int   # FK -> dungeons.id
    current_floor: int
    is_cleared: bool
    updated_at: datetime
```

### 3.6 game/battle.py（BattleEngine クラス）

```python
class BattleEngine:
    def __init__(
        self,
        party: list[Character],
        enemies: list[Enemy],
        heal_mult: float = 1.0,
        exp_mult: float = 1.0,
    ):
        self.party = party
        self.enemies = enemies
        self.turn = 1
        self.log: list[str] = []

    def player_action(
        self,
        character: Character,
        action: str,
        target: Enemy | Character | None = None,
        skill: Skill | None = None,
    ) -> str:
        """
        action: "attack" | "skill" | "defend"
        戦闘ログメッセージを返す
        """

    def enemy_action(self) -> list[str]:
        """
        全生存敵がAIに基づいて行動する
        戦闘ログメッセージのリストを返す
        """

    def use_item(self, character: Character, item, target: Character | None = None) -> str:
        """戦闘中にアイテムを使用する"""

    def calc_damage(self, attacker_atk: int, defender_def: int) -> int:
        """
        ダメージ計算式: max(1, attacker_atk - defender_def) + random(-2, 2)
        """

    def calc_skill_damage(self, attacker_atk: int, skill_power: int, defender_def: int) -> int:
        """スキル攻撃ダメージ計算式: max(1, attack + skill.power - defense)"""

    def calc_heal_amount(self, skill_power: int, intelligence: int, heal_mult: float) -> int:
        """
        回復計算式: (skill.power + offset + intelligence * scale) * heal_mult
        offset / scale は config.py の定数で調整する
        """

    def ally_auto_action(self, character: Character, policy: str, skills: list, intelligence: int = 5) -> str:
        """味方AIの自動行動を実行する"""

    def is_party_wiped(self) -> bool:
    def is_all_enemies_dead(self) -> bool:
    def get_total_exp(self) -> int:
        """撃破した敵の合計経験値を返す"""
```

### 3.7 game/dungeon.py（DungeonManager クラス）

```python
class DungeonManager:
    ENCOUNTER_RATE = {1: 0.6, 2: 0.7, 3: 0.8}  # 階層別エンカウント確率

    def __init__(self, dungeon: Dungeon, progress: DungeonProgress):
        self.dungeon = dungeon
        self.progress = progress

    def advance_floor(self) -> str
        """
        次の部屋へ進む。ログメッセージを返す。
        """

    def check_encounter(self) -> bool
        """現在の階層のエンカウント率でランダム判定"""

    def get_random_enemies(self) -> list[Enemy]
        """現在の階層からランダムに1〜3体の敵を選択して返す"""

    def get_boss(self) -> Enemy
        """現在の階層のボスを返す"""

    def is_boss_floor(self) -> bool
        """3部屋目（各階層の最終部屋）かどうかを判定"""

    def advance_to_next_floor(self) -> bool
        """次の階層に進む。全階層クリアなら True を返す"""
```

### 3.8 utils/auth.py

```python
def init_authenticator() -> Authenticator
    """streamlit-authenticator の初期化"""

def check_login() -> bool
    """ログイン状態確認。未ログインなら st.stop() で画面を停止"""

def get_current_user_id() -> int
    """st.session_state["user_id"] からユーザーIDを取得"""
```

---

## 4. データベース詳細設計

### 4.1 ER 図（テキスト表現）

```
users ──< characters
users ──< party_members >── characters
users ──< dungeon_progress >── dungeons
dungeons ──< enemies
skills（クラス属性による論理関連）
```

### 4.2 インデックス定義

| テーブル          | カラム             | 種別    | 目的                   |
|------------------|--------------------|---------|------------------------|
| users            | name               | UNIQUE  | ユーザー名重複防止      |
| characters       | user_id            | INDEX   | ユーザー別検索高速化    |
| party_members    | user_id, slot      | UNIQUE  | スロット重複防止        |
| enemies          | dungeon_id, floor  | INDEX   | 階層別敵検索高速化      |
| dungeon_progress | user_id, dungeon_id| UNIQUE  | 進行状況の一意性保証    |

### 4.3 初期データ（db_init.sql 概要）

**dungeons テーブル**

| id | name             | floor |
|----|-----------------|-------|
| 1  | 暗黒の洞窟       | 3     |

**enemies テーブル（抜粋）**

| id | name       | dungeon_id | floor | hp | attack | defense | exp_reward | is_boss |
|----|-----------|------------|-------|----|--------|---------|------------|---------|
| 1  | スライム   | 1          | 1     | 20 | 5      | 2       | 10         | FALSE   |
| 2  | コウモリ   | 1          | 1     | 15 | 7      | 1       | 12         | FALSE   |
| 3  | ゴブリン   | 1          | 2     | 35 | 10     | 4       | 20         | FALSE   |
| 4  | オーク     | 1          | 2     | 40 | 12     | 5       | 25         | FALSE   |
| 5  | ドラゴン   | 1          | 3     | 30 | 14     | 6       | 35         | FALSE   |
| 6  | ダークロード| 1          | 3     | 120| 20     | 10      | 100        | TRUE    |

**skills テーブル**

| id | name         | class_type | mp_cost | power | effect_type |
|----|-------------|-----------|---------|-------|-------------|
| 1  | ファイア     | mage      | 10      | 30    | attack      |
| 2  | ヒール       | priest    | 8       | 40    | heal        |
| 3  | バックスタブ | thief     | 6       | 25    | attack      |
| 4  | チャージ     | warrior   | 5       | 20    | attack      |
| 5  | 応急手当     | all       | 0       | 30    | heal        |

---

## 5. ゲームパラメータ定義

### 5.1 クラス別初期ステータス

| クラス     | class_type | max_hp | max_mp | attack | defense |
|-----------|-----------|--------|--------|--------|---------|
| 戦士       | warrior   | 120    | 20     | 18     | 12      |
| 魔法使い   | mage      | 70     | 80     | 10     | 5       |
| 盗賊       | thief     | 90     | 40     | 16     | 8       |
| 僧侶       | priest    | 100    | 60     | 12     | 10      |

### 5.1.1 クラス別初期知性値

| クラス     | class_type | intelligence |
|-----------|-----------|--------------|
| 戦士       | warrior   | 2            |
| 武道家     | monk      | 2            |
| 騎士       | knight    | 5            |
| 弓使い     | archer    | 5            |
| 盗賊       | thief     | 5            |
| 魔法使い   | mage      | 8            |
| 僧侶       | priest    | 8            |
| 吟遊詩人   | bard      | 8            |

### 5.2 レベルアップ設定

- 必要経験値: `level * 50`（例: Lv1→Lv2 は 50 exp）
- レベルアップ時の成長値（クラス共通）:

| パラメータ | 成長量       |
|-----------|-------------|
| max_hp    | +10〜15（乱数）|
| max_mp    | +3〜8（乱数） |
| attack    | +1〜3（乱数） |
| defense   | +1〜2（乱数） |

### 5.3 ダメージ計算式

$$
\text{damage} = \max(1,\ \text{attack} - \text{defense}) + \text{random}(-2,\ +2)
$$

スキル攻撃の場合:

$$
\text{damage} = \max(1,\ \text{attack} + \text{skill.power} - \text{defense})
$$

### 5.3.1 回復スキル計算式

回復系スキル（`effect_type = "heal"`）は INT ベースで計算する。

$$
    ext{heal} = \max\left(1,\ \left(\text{skill.power} + \text{HEAL\_SKILL\_INT\_BASE\_OFFSET} + \text{intelligence} \times \text{HEAL\_SKILL\_INT\_SCALE}\right) \times \text{heal\_mult}\right)
$$

- `HEAL_SKILL_INT_BASE_OFFSET = -4`
- `HEAL_SKILL_INT_SCALE = 2`
- 知性値が 10 を超える場合も、回復量計算にはその値をそのまま使う
- アイテム回復は固定値

### 5.4 エンカウント設定

| 階層 | エンカウント確率 | 出現数  |
|------|----------------|---------|
| 1F   | 60%            | 1〜2体  |
| 2F   | 70%            | 1〜3体  |
| 3F   | 80%            | 2〜3体  |
| ボス | 100%（固定）   | 1体     |

各階層の構成: 通常部屋 × 2 → ボス部屋 × 1（計3部屋）

---

## 6. 処理フロー設計

### 6.1 ゲーム全体フロー

```
[起動]
  └→ SCR-01: ログイン画面
        ├→ ログイン成功
        │     └→ SCR-02: キャラクター管理
        │           └→ パーティ確定
        │                 └→ SCR-03: ダンジョン探索（1F）
        │                       ├→ エンカウント
        │                       │     └→ SCR-04: 戦闘
        │                       │           ├→ 勝利 → 経験値獲得 → SCR-03 へ戻る
        │                       │           └→ 敗北 → SCR-02 へ戻る
        │                       ├→ 階層クリア → 次の階層へ
        │                       └→ 全階層クリア → エンディング → SCR-02 へ
        └→ 新規登録 → 自動ログイン → SCR-02
```

### 6.2 戦闘ターンフロー

```
[戦闘開始]
  └→ プレイヤーターン
        ├→ 行動選択: 攻撃
        │     └→ calc_damage() でダメージ計算 → 敵 HP 減少
        ├→ 行動選択: スキル
        │     ├→ スキル選択画面表示
        │     ├→ MP 消費
      │     └→ 効果適用（attack / heal / cure / buff / 状態異常）
      ├→ 行動選択: アイテム
      │     └→ use_item() で固定回復 / 状態異常回復 / 蘇生などを適用
        └→ 行動選択: 防御
              └→ 次のターン中、防御力 2倍 で被ダメ軽減

  └→ 敵ターン（全生存敵が順番に行動）
      └→ EnemyAI に基づいて単体攻撃 / 全体攻撃 / 状態異常 / バフ / 自己回復

  └→ 勝敗判定
        ├→ 全敵撃破 → 勝利
        └→ パーティ全滅 → 敗北
```

### 6.3 レベルアップ処理フロー

```
gain_exp(amount)
  └→ self.exp += amount
  └→ 必要経験値 (level * 50) を超えたか判定
        ├→ YES: level_up() 呼び出し
        │         └→ level += 1
        │         └→ 各パラメータにランダム成長値を加算
    │         └→ support プランでは intelligence が +1 成長する場合がある
        │         └→ hp / mp を max_hp / max_mp に回復
        │         └→ DB に保存
        └→ NO: DB に exp のみ保存
```

---

## 7. セッション状態管理

### 7.1 st.session_state キー一覧

| キー名                  | 型                  | 設定タイミング         | 説明                         |
|------------------------|---------------------|----------------------|------------------------------|
| `user_id`              | int                 | ログイン時            | ログイン中ユーザーID           |
| `username`             | str                 | ログイン時            | ログイン中ユーザー名           |
| `party`                | list[Character]     | パーティ確定時        | 現在のパーティメンバー（4名）  |
| `current_dungeon_id`   | int                 | ダンジョン選択時      | 探索中のダンジョンID           |
| `current_floor`        | int                 | 階層移動時            | 現在の階層（1〜3）             |
| `current_room`         | int                 | 部屋移動時            | 現在の部屋番号（1〜3）         |
| `battle_enemies`       | list[Enemy]         | エンカウント時        | 現在の戦闘の敵リスト           |
| `battle_log`           | list[str]           | 戦闘中               | 戦闘ログのテキストリスト       |
| `defending_chars`      | set[int]            | 防御選択時            | 防御中のキャラクターID集合     |
| `battle_result`        | str \| None         | 戦闘終了時            | "win" / "lose" / None        |

### 7.2 セッションの初期化

```python
# utils/auth.py
def init_session_defaults():
    defaults = {
        "user_id": None,
        "username": None,
        "party": [],
        "current_dungeon_id": 1,
        "current_floor": 1,
        "current_room": 0,
        "battle_enemies": [],
        "battle_log": [],
        "defending_chars": set(),
        "battle_result": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
```

---

## 8. エラーハンドリング

| エラー種別                   | 対処方法                                             |
|-----------------------------|------------------------------------------------------|
| DB接続失敗                   | `st.error()` でエラー表示、ページを停止              |
| 未ログインでの画面アクセス    | `check_login()` でガード → SCR-01 に `st.switch_page()` |
| パーティが4名未満での探索開始 | 開始ボタンを `disabled=True` にして操作を禁止         |
| 戦闘中の MP 不足             | スキルボタンを `disabled=True` にして選択不可         |
| キャラクター名の重複          | DB の UNIQUE 制約エラーをキャッチ → `st.warning()` 表示 |
| 全キャラクターが戦闘不能      | 敗北フローに移行、`st.session_state["battle_result"] = "lose"` |
