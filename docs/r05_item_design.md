# R-05 アイテム（消耗品）詳細設計書

**対象要件**: R-05  
**依存**: なし（独立実装可）/ R-08（商人マス）・R-10（通貨）への布石

---

## 目次

1. [概要](#概要)
2. [データモデル](#データモデル)
3. [初期アイテムデータ](#初期アイテムデータ)
4. [BattleEngine への組み込み](#battleengine-への組み込み)
5. [画面仕様](#画面仕様)
6. [session_state 追加キー](#session_state-追加キー)
7. [実装ファイル一覧](#実装ファイル一覧)
8. [実装手順](#実装手順)

---

## 概要

戦闘中およびダンジョン探索中にパーティが消耗品を使用できる機能を追加する。

**スコープ（R-05）**
- アイテムのマスタ定義（`items` テーブル）
- ユーザーごとの所持数管理（`inventories` テーブル）
- 戦闘中のアイテム使用（HP/MP回復・蘇生・状態異常回復）
- ダンジョン探索中のアイテム使用（HP/MP回復のみ）
- 初期配布アイテム（新規ユーザー登録時にポーション×3を付与）

**スコープ外（後続要件）**
- アイテム購入・売却 → R-10（通貨・町機能）
- 商人マスでの入手 → R-08（イベントマス）
- 装備品 → R-11（装備システム）

---

## データモデル

### `items` テーブル（新規）

```python
# models/item.py
class Item(Base):
    __tablename__ = "items"

    id          : Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name        : Mapped[str] = mapped_column(String(64),  nullable=False)
    description : Mapped[str] = mapped_column(String(256), nullable=False, server_default="")
    effect_type : Mapped[str] = mapped_column(String(16),  nullable=False)
    power       : Mapped[int] = mapped_column(nullable=False, default=0)
    target_type : Mapped[str] = mapped_column(String(16),  nullable=False, server_default="ally")
    duration    : Mapped[int] = mapped_column(nullable=False, server_default="0")
    price       : Mapped[int] = mapped_column(nullable=False, server_default="0")
    # price は R-10 で使用。R-05 では 0 のまま。
```

#### `effect_type` 一覧

| 値 | 効果 | `power` の意味 |
|---|---|---|
| `heal_hp` | HP を固定値回復 | 回復量（例: 30）|
| `heal_hp_pct` | HP を最大HP×%回復 | %値（例: 50 → 最大HP×50%）|
| `heal_mp` | MP を固定値回復 | 回復量（例: 20）|
| `revive` | 戦闘不能キャラを蘇生 | 蘇生後のHP%（例: 30 → 最大HP×30%）|
| `cure` | 全状態異常を除去 | 未使用（0）|
| `buff_atk` | ATK一時バフ | バフ量（`duration` ターン持続）|
| `buff_def` | DEF一時バフ | バフ量（`duration` ターン持続）|

#### `target_type` 一覧

| 値 | 対象 |
|---|---|
| `ally` | 選択した味方1人（戦闘不能キャラも対象。`revive` 用）|
| `all_allies` | 生存している味方全員 |
| `self` | 使用者のみ |

---

### `inventories` テーブル（新規）

```python
# models/inventory.py
class Inventory(Base):
    __tablename__ = "inventories"

    id       : Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id  : Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    item_id  : Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    quantity : Mapped[int] = mapped_column(nullable=False, default=0)

    __table_args__ = (UniqueConstraint("user_id", "item_id"),)
```

#### 主要メソッド

```python
@staticmethod
def get_by_user(db, user_id) -> list["Inventory"]:
    """user_id のインベントリ（quantity > 0 のみ）を item と JOIN して返す"""

@staticmethod
def add_item(db, user_id, item_id, quantity=1) -> None:
    """アイテムを付与（既存なら quantity 加算、なければ INSERT）"""

@staticmethod
def use_item(db, user_id, item_id) -> bool:
    """アイテムを1個消費。quantity > 0 なら -1 して True を返す。なければ False。"""
```

---

## 初期アイテムデータ

`helpers.py` の `seed_initial_data()` および `data/db_init.sql` に追加。

| id | name | description | effect_type | power | target_type | duration | price |
|---|---|---|---|---|---|---|---|
| 1 | ポーション | HPを30回復する | heal_hp | 30 | ally | 0 | 50 |
| 2 | ハイポーション | HPを80回復する | heal_hp | 80 | ally | 0 | 150 |
| 3 | エーテル | MPを20回復する | heal_mp | 20 | ally | 0 | 80 |
| 4 | 万能薬 | 状態異常を全て回復する | cure | 0 | ally | 0 | 100 |
| 5 | フェニックスの羽 | 戦闘不能を蘇生（HP30%）| revive | 30 | ally | 0 | 200 |
| 6 | 活力の薬 | ATKを3上昇（3ターン）| buff_atk | 3 | self | 3 | 120 |

### 新規ユーザーへの初期配布

`User.create()` 呼び出し後、または `seed_initial_data()` 完了後に  
ポーション（id=1）×3 を付与する。  
実装場所: `utils/helpers.py` または `app.py` のユーザー登録フロー。

---

## BattleEngine への組み込み

### `use_item()` メソッドを追加

```python
# game/battle.py
def use_item(
    self,
    character: "Character",
    item: "Item",
    target: "Character | None" = None,
) -> str:
    """
    アイテムを使用する。
    - target が None の場合は character 自身に適用。
    - revive は target が戦闘不能でなければ失敗メッセージを返す。
    - ヘイトは固定で +5 加算（行動として認識させる）。
    """
    etype = item.effect_type
    actual_target = target if target is not None else character

    if etype == "heal_hp":
        healed = actual_target.heal(item.power)
        self.add_hate(character, 5)
        return f"{character.name} は {item.name} を使った！ {actual_target.name} の HP が {healed} 回復！"

    elif etype == "heal_hp_pct":
        amount = max(1, actual_target.max_hp * item.power // 100)
        healed = actual_target.heal(amount)
        self.add_hate(character, 5)
        return f"{character.name} は {item.name} を使った！ {actual_target.name} の HP が {healed} 回復！"

    elif etype == "heal_mp":
        restored = min(item.power, actual_target.max_mp - actual_target.mp)
        actual_target.mp = min(actual_target.max_mp, actual_target.mp + item.power)
        self.add_hate(character, 5)
        return f"{character.name} は {item.name} を使った！ {actual_target.name} の MP が {restored} 回復！"

    elif etype == "revive":
        if actual_target.is_alive():
            return f"{actual_target.name} は戦闘不能ではない！"
        hp = max(1, actual_target.max_hp * item.power // 100)
        actual_target.hp = hp
        self.add_hate(character, 5)
        return f"{character.name} は {item.name} を使った！ {actual_target.name} が蘇生！（HP {hp}）"

    elif etype == "cure":
        c_key = self._entity_key(actual_target)
        if c_key in self.buffs:
            self.buffs[c_key] = [b for b in self.buffs[c_key] if b.get("stat") != "status"]
            if not self.buffs[c_key]:
                del self.buffs[c_key]
        self.add_hate(character, 5)
        return f"{character.name} は {item.name} を使った！ {actual_target.name} の状態異常が回復！"

    elif etype in ("buff_atk", "buff_def"):
        stat = "attack" if etype == "buff_atk" else "defense"
        duration = item.duration or 3
        msg = self.apply_buff(actual_target, stat, item.power, duration, item.name)
        self.add_hate(character, 5)
        return f"{character.name} は {item.name} を使った！ {msg}"

    return f"{item.name}（効果なし）"
```

### スタン中のアイテム使用

スタン中でもアイテム使用は**可能**とする（スキルのみブロック、アイテムは行動扱いにしない）。  
`player_action()` のスタンチェックは `action == "skill"` の場合のみに適用済みのため変更不要。

---

## 画面仕様

### 戦闘画面（`pages/3_battle.py`）

#### 行動ボタン列に「🎒 アイテム」を追加

```
[ ⚔️ 攻撃 ]  [ ✨ スキル ]  [ 🛡️ 防御 ]  [ 🎒 アイテム ]
```

4列レイアウトに変更（現在3列）。

#### アイテムパネル

スキルパネルと同じ開閉トグル方式。  
`show_item_panel` フラグで表示制御。

```
🎒 アイテム選択
┌──────────────────────────────────────────┐
│  💊 ポーション          🔵 エーテル       │
│  HP+30  残3個          MP+20  残1個       │
│  [ 使用 ]               [ 使用 ]          │
│                                           │
│  🪶 フェニックスの羽                      │
│  蘇生(HP30%)  残0個                      │
│  [ 使用 - 在庫なし（グレー）]             │
└──────────────────────────────────────────┘
```

- 在庫が 0 のアイテムはボタンを `disabled=True`
- `target_type == "ally"` のアイテムは「対象を選ぶ」プルダウンで選択した味方を対象に
- `target_type == "self"` のアイテムは使用者に自動適用
- `revive` は戦闘不能キャラも「対象を選ぶ」に含める（通常は生存者のみ）

#### 対象プルダウンの変更

`revive` アイテムを使うとき、**戦闘不能キャラも選択肢に含める**必要がある。  
現在は `alive_party` のみを表示しているため、アイテムパネル開示中は  
`全パーティメンバー`（`party`）を対象リストに切り替える。

```python
# アイテムパネルが開いているとき: 全パーティを対象に
item_target_pool = party if st.session_state.get("show_item_panel") else alive_party
```

#### インベントリの読み込みタイミング

- 戦闘開始時（`battle_enemies` が設定されたタイミング）に DB からロードして  
  `session_state["battle_inventory"]` に保存
- アイテム使用時に `Inventory.use_item(db, user_id, item_id)` で DB を更新し、  
  `session_state["battle_inventory"]` の数量も -1 する

---

### ダンジョン探索画面（`pages/2_dungeon.py`）

移動・探索ボタンの下にサイドバーまたは折りたたみセクションとして配置。

```
▼ 🎒 アイテムを使う（探索中）
  対象: [プルダウン - 生存キャラ]
  アイテム: [プルダウン - 所持アイテム]
  [ 使用する ]
```

- 探索中は `BattleEngine` なしで直接 `character.heal()` / `character.mp +=` を呼ぶ
- 使用後 DB 保存（`character.save(db)` + `Inventory.use_item(db, ...)`）
- 使用できる効果: `heal_hp` / `heal_hp_pct` / `heal_mp` / `cure`（`revive` / バフ系は戦闘中のみ）

---

## session_state 追加キー

| キー | 型 | 用途 |
|---|---|---|
| `battle_inventory` | `list[dict]` | 戦闘中のアイテム所持状況。`{"item": Item, "quantity": int}` のリスト。DB と同期。 |
| `show_item_panel` | `bool` | アイテムパネルの開閉状態 |

`init_session_defaults()`（`utils/auth.py`）に追加：

```python
"battle_inventory": [],
"show_item_panel":  False,
```

---

## 実装ファイル一覧

| ファイル | 変更種別 | 変更内容 |
|---|---|---|
| `models/item.py` | **新規** | `Item` モデル定義 |
| `models/inventory.py` | **新規** | `Inventory` モデル + `add_item` / `use_item` / `get_by_user` |
| `models/__init__.py` | **更新** | `Item`, `Inventory` を import・`__all__` に追加 |
| `models/database.py` | **更新** | `migrate_db()` に items / inventories テーブル作成と初期データ INSERT を追加 |
| `game/battle.py` | **更新** | `use_item()` メソッドを追加 |
| `utils/auth.py` | **更新** | `init_session_defaults()` に `battle_inventory` / `show_item_panel` を追加 |
| `utils/helpers.py` | **更新** | `seed_initial_data()` にアイテム6種を追加。新規ユーザーへポーション×3を付与する `give_starter_items()` を追加 |
| `data/db_init.sql` | **更新** | `items` / `inventories` テーブルの DDL と初期データ INSERT を追加 |
| `pages/3_battle.py` | **更新** | アイテムボタン・アイテムパネル・`battle_inventory` ロード処理を追加 |
| `pages/2_dungeon.py` | **更新** | 探索中アイテム使用 UI を追加 |
| `tests/test_battle.py` | **更新** | `TestItemUse` クラスを追加（7テスト程度）|

---

## 実装手順

```
Step 1: models/item.py + models/inventory.py を新規作成
Step 2: models/__init__.py を更新
Step 3: models/database.py の migrate_db() を更新
        → items / inventories テーブル作成 + アイテム初期データ INSERT OR IGNORE
Step 4: game/battle.py に use_item() を追加
Step 5: utils/auth.py に session_state キーを追加
Step 6: utils/helpers.py に seed_initial_data() のアイテムデータと give_starter_items() を追加
Step 7: data/db_init.sql に DDL とデータを追加
Step 8: pages/3_battle.py を更新（アイテムパネル実装）
Step 9: pages/2_dungeon.py を更新（探索中使用 UI 実装）
Step 10: tests/test_battle.py に TestItemUse クラスを追加
Step 11: pytest で全テスト通過確認
```

---

## テストケース（`TestItemUse`）

| テスト名 | 確認内容 |
|---|---|
| `test_heal_hp_item` | HP回復アイテムを使うと HP が増加する |
| `test_heal_hp_not_exceed_max` | HP回復が最大HPを超えない |
| `test_heal_mp_item` | MP回復アイテムを使うと MP が増加する |
| `test_revive_dead_character` | 蘇生アイテムで HP=0 のキャラが復活する |
| `test_revive_alive_fails` | 生存キャラに蘇生を使うと失敗メッセージ |
| `test_cure_item_removes_status` | 万能薬で毒が除去される |
| `test_buff_atk_item` | 活力の薬で ATK バフが付与される |
