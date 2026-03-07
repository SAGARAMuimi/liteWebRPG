# 戦闘システム詳細仕様書

対象要件: **R-02 バフ/デバフ** / **R-03 ヘイト・ターゲット制御** / **R-04 状態異常**

---

## 目次

1. [R-02 バフ/デバフ](#r-02-バフデバフ)
2. [R-03 ヘイト・ターゲット制御](#r-03-ヘイトターゲット制御)
3. [R-04 状態異常](#r-04-状態異常)
4. [内部データ構造](#内部データ構造)
5. [ターン進行フロー](#ターン進行フロー)

---

## R-02 バフ/デバフ

### ゲームプレイ画面

#### 表示

| 場所 | 表示内容 |
|---|---|
| 敵ステータス欄 | バフ/デバフ中の敵の下に `⬆️ATK(2T)` / `⬇️DEF(1T)` 形式のタグを表示 |
| パーティ欄 | 各キャラクターの HP/MP バーの下に同形式のタグを表示 |
| スキルパネル | スキルボタンに `⬆️ATK` / `⬆️DEF` などの効果アイコンと `MP:コスト` を表示 |

バフタグの読み方：

```
⬆️ATK(3T)
│   │   └── 残りターン数
│   └──── 対象ステータス（ATK=攻撃力 / DEF=防御力）
└──────── 上昇(⬆️) or 低下(⬇️)
```

#### バフ/デバフを持つスキル一覧

| スキル名 | クラス | MP | 効果 | 対象 | 持続 |
|---|---|---|---|---|---|
| 挑発 | 騎士 | 4 | DEF+5 / ヘイト+200 | 自分 | 3T |
| 気合い | 武道家 | 0 | ATK+4 | 自分 | 3T |
| 鼓舞の歌 | 吟遊詩人 | 8 | ATK+3 | 味方全員 | 3T |

#### 挙動

- バフ/デバフは**同一ソース・同一ステータスの重ね掛けは上書き**（リキャストで延長可能）
- 効果は **ターン終了時にカウントダウン**され、0 になると自動消滅
- 消滅時に戦闘ログへ `攻撃力「鼓舞の歌」の効果が切れた。` と表示

### 実装

#### 主要ファイル

| ファイル | 役割 |
|---|---|
| `game/battle.py` | バフ付与・有効ステータス計算・カウントダウンのコアロジック |
| `pages/3_battle.py` | バフタグの描画（`_buff_tag()`）|
| `utils/auth.py` | `battle_buffs: {}` をセッション初期値として保持 |
| `models/skill.py` | `effect_type`, `target_type`, `duration` カラム |

#### 核心メソッド（`game/battle.py`）

```python
def apply_buff(target, stat, amount, duration, source, taunt=False) -> str
```
- `stat`: `"attack"` or `"defense"`
- `amount`: 正数=バフ / 負数=デバフ
- 同一 `(stat, source)` のエントリを事前削除してから追加（上書き動作）

```python
def get_effective_attack(entity) -> int
def get_effective_defense(entity) -> int
```
- `buffs` dict から対応エンティティのエントリを走査し合算
- `def_down` 状態異常がある場合は `get_effective_defense` がさらに 50% 減算（R-04 と連動）

```python
def tick_buffs() -> list[str]
```
- 全 `buffs` エントリの `turns_left` を `-1` する
- `turns_left <= 0` になったエントリを削除し、消滅メッセージを返す

#### `session_state` との連携

```
st.session_state["battle_buffs"]  ←→  engine.buffs（同一オブジェクト参照）
```
`BattleEngine.__init__` に `buffs=st.session_state["battle_buffs"]` を渡すことで、
ページの再レンダリングをまたいでバフ状態を保持する。

---

## R-03 ヘイト・ターゲット制御

### ゲームプレイ画面

#### 表示

| マーカー | 意味 |
|---|---|
| 🎯（名前の後ろ） | 現在の敵のターゲット（ヘイト最大またはタント中のキャラ）|
| 🛡️（名前の後ろ） | 防御行動中のキャラ |
| 💫（名前の後ろ） | スタン中のキャラ（R-04 と連動）|

#### ヘイトが増加する行動

| 行動 | ヘイト増加量 |
|---|---|
| 通常攻撃 | 実ダメージ量と同値 |
| 攻撃スキル | 実ダメージ量と同値 |
| 回復スキル | 回復量の 50%（切り捨て） |
| バフ（単体） | +10 |
| バフ（全体） | +15 |
| デバフ（全体） | +20 |
| 防御 | +5 |
| **挑発スキル** | **+200（大幅ブースト）** |

#### 挑発（タント）の効果

騎士の「挑発」スキルを使用すると：
1. 自身に DEF+5 の防御バフが付く（3 ターン）
2. ヘイトが +200 される
3. 挑発フラグが立ち、**挑発が有効な間は自分が必ず敵のターゲットになる**
4. 挑発が切れると通常のヘイト比率選択に戻る

### 実装

#### 主要ファイル

| ファイル | 役割 |
|---|---|
| `game/battle.py` | ヘイト辞書管理・ターゲット選択ロジック |
| `pages/3_battle.py` | 🎯 マーカー描画 |
| `utils/auth.py` | `battle_hate: {}` をセッション初期値として保持 |

#### 核心メソッド（`game/battle.py`）

```python
def add_hate(character, amount) -> None
```
- `hate[character.id]` に `amount` を加算（下限 10）

```python
def _select_target() -> Character | None
```
ターゲット選択の優先順位：

```
1. 挑発中（taunt=True のバフを持つ）のキャラ
   → 複数いる場合はその中でヘイト最大のキャラ
2. 挑発なし
   → hate 値を重みにした random.choices() による確率選択
```

#### ヘイトの初期値と管理

```python
# 初期化: パーティ全員に 10 を設定（BattleEngine.__init__）
for c in self.party:
    if c.id not in self.hate:
        self.hate[c.id] = 10
```

`hate` dict は `session_state["battle_hate"]` と同一オブジェクト参照で共有し、
ページ再レンダリングをまたいで維持される。

#### 画面上のターゲット表示ロジック（`pages/3_battle.py`）

```python
# 挑発中キャラ → その中でヘイト最大
_taunting = [c for c in _alive_p if any(b.get("taunt") for b in _buffs.get(...))]
if _taunting:
    _hate_target_id = max(_taunting, key=lambda c: _hate.get(c.id, 0)).id
else:
    _hate_target_id = max(_alive_p, key=lambda c: _hate.get(c.id, 0)).id
```

---

## R-04 状態異常

### ゲームプレイ画面

#### 状態異常の種類

| アイコン | 名前 | 効果 | 付与スキル（クラス） |
|---|---|---|---|
| ☠️ | 毒 | ターン終了時に最大HP×5%のダメージ | 毒矢（弓使い）/ 毒霧（魔法使い・全体） |
| 💫 | スタン | そのターンの全行動をスキップ | ― |
| 🔓 | 防御低下 | 有効防御力を 50% 減 | 鎧裂き（戦士） |
| 🤐 | 沈黙 | スキルが使用不能（通常攻撃は可能） | 目眩まし（盗賊） |

#### 回復スキル

| スキル名 | クラス | MP | 効果 |
|---|---|---|---|
| 浄化 | 僧侶 | 5 | 対象の全状態異常を除去 |

#### 状態異常タグの読み方

```
☠️毒(2T)
│  │  └── 残りターン数
│  └───── 状態異常の種類
└──────── 状態異常アイコン
```

#### 表示場所

- **敵ステータス欄**: 敵が状態異常の場合はタグを表示
- **パーティ欄**: 各キャラクターの HP/MP バーの下にタグを表示（スタン中は名前の後に 💫 も追加）
- **スキルパネル**: 状態異常系スキルボタンに効果アイコンを表示

#### ボス耐性

すべてのボス（ゴブリンキング / オークチーフ / ダークロード）はスタン耐性を持つ。
スタン付与を試みると戦闘ログに `〇〇 は スタン を無効化した！` と表示される。

### 実装

#### 主要ファイル

| ファイル | 変更内容 |
|---|---|
| `config.py` | `STATUS_AILMENTS` dict（アイコン・ラベル定義） |
| `models/enemy.py` | `status_resistance: Mapped[str]` カラム追加 |
| `models/database.py` | `migrate_db()` でカラム追加 + ボスへの耐性付与 |
| `game/battle.py` | 状態異常付与・判定・毒ダメージ・スタン/沈黙チェック |
| `utils/helpers.py` | 状態異常スキル5種をシードデータに追加 |
| `data/db_init.sql` | 同スキル5種の INSERT 文 |
| `pages/3_battle.py` | 状態異常タグ表示・cure/status スキルのルーティング |

#### 核心メソッド（`game/battle.py`）

```python
def has_status(entity, kind: str) -> bool
```
- `buffs[key]` の中で `stat=="status"` かつ `kind==kind` のエントリを探して返す

```python
def apply_status(target, kind, duration, source) -> str
```
1. `target.status_resistance` に `kind` が含まれていれば無効化メッセージを返す
2. 同一 `kind` の既存エントリを削除してから新エントリを追加
3. 毒ダメージ計算用に `base_hp`（付与時の `max_hp`）を一緒に保存

```python
def tick_buffs() -> list[str]
```
- `stat=="status"` のエントリを識別し、種別ごとに処理：
  - `kind=="poison"`: `max_hp × 5%` のターンダメージを与えてログに追加
  - `turns_left <= 0`: エントリを削除して消滅メッセージを追加
  - その他: `turns_left` を -1 して継続

#### プレイヤーターンのブロックチェック（`player_action`）

```python
# 全行動ブロック（スタン）
if self.has_status(character, "stun"):
    return f"{character.name} はスタン状態で行動できない！"

# スキルのみブロック（沈黙）
if action == "skill" and self.has_status(character, "silence"):
    return f"{character.name} は沈黙状態でスキルが使えない！"
```

#### 敵ターンのスタンチェック（`enemy_action`）

```python
if self.has_status(enemy, "stun"):
    messages.append(f"{enemy.name} はスタン状態で行動できない！")
    continue
```

#### `status_resistance` の仕様

- `Enemy` モデルの `String(64)` カラム
- 値はカンマ区切り文字列（例: `"stun"` / `"stun,silence"`）
- 空文字 `""` = 耐性なし
- `migrate_db()` で既存 DB への自動追加と、ボスへの初期値設定を実施

---

## 内部データ構造

### `buffs` dict の構造

```
buffs = {
    "c_{character.id}": [   # 味方エンティティ
        # バフ/デバフエントリ
        {
            "stat":       "attack" | "defense",
            "amount":     int,        # 正=バフ / 負=デバフ
            "turns_left": int,
            "source":     str,        # スキル名
            "taunt":      bool,       # True=挑発中（R-03）
        },
        # 状態異常エントリ（R-04）
        {
            "stat":       "status",
            "kind":       "poison" | "stun" | "def_down" | "silence",
            "turns_left": int,
            "source":     str,        # スキル名
            "taunt":      False,      # 常に False
            "base_hp":    int,        # 毒ダメージ計算用（付与時の max_hp）
        },
    ],
    "e_{enemy.id}": [ ... ],        # 敵エンティティ（同構造）
}
```

### `hate` dict の構造

```
hate = {
    character.id (int): hate_value (int),  # 初期値 10 / 下限 10
    ...
}
```

### `session_state` キー一覧（戦闘関連）

| キー | 型 | 用途 |
|---|---|---|
| `battle_buffs` | `dict` | `engine.buffs` と同一参照。バフ/デバフ/状態異常を保持 |
| `battle_hate` | `dict` | `engine.hate` と同一参照。ヘイト値を保持 |
| `battle_enemies` | `list[Enemy]` | 現在の戦闘で出現している敵 |
| `battle_turn` | `int` | 現在のターン数 |
| `battle_log` | `list[str]` | 戦闘ログ（直近 30 件を表示）|
| `defending_chars` | `set[int]` | 防御中のキャラクター ID セット |

---

## ターン進行フロー

```
[プレイヤーが行動選択]
       │
       ├─ ⚔️ 攻撃 ──→ player_action(attack)
       ├─ ✨ スキル ─→ player_action(skill)
       └─ 🛡️ 防御 ──→ player_action(defend)
              │
              │  ※ スタン中は player_action が "行動不能" を返して終了
              │  ※ 沈黙中はスキルのみ "行動不能" を返して終了
              │
       [敵が全滅していなければ]
              │
              ↓
       enemy_action()
       ├─ 各敵: has_status(stun) → 行動スキップ
       └─ _select_target() でターゲット決定（ヘイト/挑発考慮）
              │
              ↓
       tick_buffs()
       ├─ バフ/デバフ: turns_left-- / 0 になれば削除
       └─ 状態異常:
           ├─ poison: max_hp×5% ダメージ付与
           └─ turns_left <= 0: エントリ削除・消滅メッセージ
              │
              ↓
       [画面再描画（st.rerun()）]
```
