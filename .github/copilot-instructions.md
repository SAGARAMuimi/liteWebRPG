# liteWebRPG — AI コーディングエージェント向けガイド

## プロジェクト概要

Python + Streamlit 製のブラウザ完結型テキスト RPG。  
SQLAlchemy ORM で SQLite（開発）/ MySQL / PostgreSQL（本番）を切り替えられる。

## ディレクトリ構成と責務

```
text_rpg/
├── app.py              # エントリーポイント。init_db() / migrate_db() / seed_initial_data() を呼び出す
├── config.py           # 全定数の唯一の管理場所（ゲームパラメータ・DB URL・AUTH_MODE など）
├── models/             # SQLAlchemy モデル。__init__.py で外部キー依存順に import する
├── game/               # UI に依存しない純粋なゲームロジック（BattleEngine / DungeonManager）
├── pages/              # Streamlit マルチページ（ファイル名の番号がサイドバーの順序になる）
├── utils/auth.py       # check_login() / check_admin() / get_current_user_id()
├── utils/helpers.py    # seed_initial_data() / hp_bar() など汎用ユーティリティ
└── tests/              # pytest ユニットテスト（DB・Streamlit 非依存で動く）
```

## 開発コマンド

```bash
# アプリ起動（text_rpg/ 直下の .env が自動で読まれる）
streamlit run text_rpg/app.py

# テスト実行（text_rpg/ ルートで行うこと）
cd text_rpg
pytest tests/ -v
```

## 重要な設計パターン

### 1. 設定値は config.py に集約
ゲームパラメータ（`CLASS_INITIAL_STATS`, `ENCOUNTER_RATE`, `FLOOR_MAPS` など）は
すべて [text_rpg/config.py](../text_rpg/config.py) に定義する。ページやモデルにハードコードしない。

環境変数の取得には `_get_setting(key, default)` を使う（env → `st.secrets` → default の優先順位）。

### 2. モデルの import 順序
`models/__init__.py` で外部キー依存の昇順に import する。  
新モデルを追加したら `__init__.py` の末尾に追加し、`migrate_db()` に CREATE TABLE / ALTER TABLE を追記する。

### 3. ページの認証ガード
各ページの先頭で必ず `check_login()` を呼ぶ。管理者専用ページは `check_admin()` を呼ぶ。  
Streamlit はルートレベルの保護ができないため、ページ内チェックで代替する。

```python
# pages/各ページの冒頭パターン
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import models  # noqa: F401  ← 全テーブルを Base.metadata に登録するために必須
from utils.auth import check_login
check_login()
```

### 4. セッション状態の管理
Streamlit の再描画でリセットされるため、ゲーム進行データは都度 DB に永続化する。  
`st.session_state["party"]`, `["user_id"]`, `["username"]` がページ間を橋渡しする主要キー。  
ミュータブルなデフォルト値はファクトリ関数（`_fresh_defaults()`）で生成する。

### 5. DB セッションは `with SessionLocal() as db:` で使い捨て
コンテキストマネージャを使い、例外でも確実に close する。  
`game/` 層のクラス（`BattleEngine`, `DungeonManager`）は `db: Session` を引数で受け取る。

### 6. PostgreSQL 接続の自動正規化
`models/database.py` が `postgresql://` → `postgresql+pg8000://` に変換し、  
`sslmode` など pg8000 非対応クエリパラメータを自動除去する。接続文字列を手動修正する必要はない。

**Neon のアイドル切断対策:** `create_engine()` に `pool_pre_ping=True` を設定済み。  
Neon 無料プランは約5分アイドルで接続を切断するため、これがないと再利用時に  
`pg8000.exceptions.InterfaceError: network error` が発生する。

### 7. テストの書き方
DB・Streamlit に依存しないよう、モデルオブジェクトを素の `ClassName()` で生成し属性を手動セット（`make_character()` / `make_enemy()` パターン）。

### 8. AUTH_MODE と認証バックエンド
`config.py` の `AUTH_MODE` で認証バックエンドを切り替える（env / Streamlit Secrets で設定）。

| 値 | 動作 |
|---|---|
| `auto`（デフォルト） | DB が PostgreSQL かつ Neon Auth Secrets があれば `neon`、なければ `local` |
| `local` | 自前 `users` テーブル + bcrypt |
| `neon` | Neon Auth（Better Auth 経由）※現時点では実験的実装 |

Neon Auth の有効判定に使われる Secrets キー: `NEON_AUTH_ENABLED`, `NEON_AUTH_BASE_URL`, `NEON_AUTH_API_KEY`。  
いずれか 1 つでも設定されていれば `neon` 扱いになる。

## 管理者機能
- `users.is_admin = 1` で管理者になる（DB を直接更新）
- 管理ページは `pages/99_admin_feedback.py`（`99_` プレフィックスでサイドバー末尾に表示）

## game/ 層の設計

### BattleEngine（game/battle.py）
UI から独立したバトルロジック。`party: list[Character]` と `enemies: list[Enemy]` を受け取り初期化する。  
難易度倍率は `heal_mult` / `exp_mult` を引数で渡す。

**バフ/デバフ辞書（`buffs`）の構造:**
```python
# キー: "c_{character.id}"（味方）/ "e_{enemy.id}"（敵）
# 値:  list of dict
{"stat": "attack"|"defense", "amount": int, "turns_left": int, "source": str, "taunt": bool}
# amount 正=バフ、負=デバフ。taunt=True は挑発状態（ターゲット最優先）
```

**ヘイト辞書（`hate`）の構造:**
```python
# キー: character.id (int)、値: int（ヘイト値）
# 初期値 10。挑発発動で +200、攻撃/スキル使用時に実ダメージ分加算。
```

**敵 AI（`EnemyAI` クラス）の判定フロー:**
1. `get_phase()` で HP 比とクラス知性値からフェーズ（`NORMAL` / `DANGER`）を決定
2. `choose_action()` でローテーション or `danger_priority` から行動を選択
3. `ENEMY_AI_ACTIONS["default"]` にフォールバックするため未登録の敵名は通常攻撃のみになる

**味方 AI の回復しきい値** は `calc_heal_threshold(intelligence, "critical"|"hurt")` で線形補間して取得。  
知性値（1〜10）は `CLASS_INTELLIGENCE` で定義され、`support` プランのレベルアップで +1 成長する。

### DungeonManager（game/dungeon.py）
`db: Session`, `dungeon: Dungeon`, `progress: DungeonProgress` を受け取る。  
マス移動後のイベント結果は `EventResult` dataclass で返す（`need_battle=True` の場合は戦闘画面へ遷移）。

## マップ定義（R-14 グリッドダンジョン）
`config.py` の `FLOOR_MAPS[floor_no]` に `grid`（2D リスト）・`start`・`goal`・`fixed_events` を定義する。  
セル値: `0`=壁, `1`=通路, `2`=スタート, `3`=ゴール。

## 本番デプロイ

### Streamlit Community Cloud + Neon PostgreSQL（推奨）
- `Main file path`: `text_rpg/app.py`
- `.env` はコミットせず、Streamlit の `Settings → Secrets` に以下を設定:
  ```toml
  DATABASE_URL = "postgresql://USER:PASSWORD@HOST/DB?sslmode=require"
  AUTH_MODE = "auto"
  OPERATOR_NAME = "運営者"
  ```
- Neon が発行する URI の `sslmode=require` / `channel_binding=require` はそのまま貼り付けてよい（アプリ側で自動除去）。
- 初回起動時に `migrate_db()` と `seed_initial_data()` が自動実行されるため手動マイグレーション不要。
- 詳細手順は [docs/streamlit_cloud_deploy.md](../docs/streamlit_cloud_deploy.md) を参照。

### さくら共用レンタルサーバ
Streamlit は常駐プロセス + WebSocket が前提のため共用環境では**動作保証外**。  
VPS/クラウドへの変更か Flask/Django への移植を検討すること（判定フローは [docs/sakura_shared_hosting_checklist.md](../docs/sakura_shared_hosting_checklist.md) を参照）。
