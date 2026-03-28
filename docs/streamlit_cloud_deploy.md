# Streamlit Community Cloud 公開手順（Neon PostgreSQL + pg8000）

この文書は、liteWebRPG を **Streamlit Community Cloud** にデプロイし、DB を **Neon（PostgreSQL）** で運用するための手順メモです。

- アプリ本体: Streamlit（`text_rpg/app.py`）
- ORM: SQLAlchemy
- PostgreSQL ドライバ: **pg8000**
- DB 接続設定: `DATABASE_URL`

本プロジェクトは PostgreSQL 接続時に以下を自動処理します。

- `postgres://...` を `postgresql://...` に正規化
- `postgresql://...` を `postgresql+pg8000://...` に正規化（psycopg 不要）
- Neon が発行する URL に付くことがある `sslmode=require` / `channel_binding=require` などの **libpq/psycopg 向けクエリ**を取り除き、pg8000 用の TLS 設定に置き換え

---

## 1. 前提

- GitHub にリポジトリが push 済み
- `text_rpg/requirements.txt` がコミット済み
- ローカルで `streamlit run text_rpg/app.py` が起動できる

---

## 2. Neon 側の準備

1. Neon でプロジェクト（DB）を作成
2. 接続文字列（Connection string / URI）を取得
   - Neon の URI は `?sslmode=require` や `&channel_binding=require` が付く場合があります。
   - 本プロジェクトは pg8000 前提のため、**URI はそのまま貼り付けてOK**（アプリ側で吸収）です。

推奨（任意）:
- アプリ用ユーザーを作って権限を絞る
- 本番はパスワード/接続文字列を定期ローテーションする

---

## 3. Streamlit Community Cloud にデプロイ

1. Streamlit Community Cloud にログイン
2. `New app` を選択
3. GitHub リポジトリ・ブランチを選択
4. `Main file path` に以下を指定
   - `text_rpg/app.py`
5. デプロイ（Deploy）

---

## 4. Secrets（環境変数）の設定

Streamlit Community Cloud では `.env` をコミットせず、**Secrets に `DATABASE_URL` を入れる**運用を推奨します。

1. 対象アプリの `Settings` → `Secrets` を開く
2. 例のように設定（値は Neon のものに置き換え）

```toml
DATABASE_URL = "postgresql://USER:PASSWORD@HOST/DB?sslmode=require&channel_binding=require"

# 認証バックエンド（任意）
# - auto : DB が postgresql かつ Neon Auth Secrets がある場合のみ neon を選択。なければ local。
# - local: 常にローカル（このプロジェクト既存の users + bcrypt）
# - neon : 常に Neon Auth（※現時点では未実装）
AUTH_MODE = "auto"

# Neon Auth Secrets（例）
# NEON_AUTH_ENABLED = "1"
# Better Auth の基本設定（Auth URL）
# NEON_AUTH_BASE_URL = "https://ep-xxx.neonauth.<region>.aws.neon.tech/neondb/auth"
# NEON_AUTH_JWKS_URL = "..."
# NEON_AUTH_PUBLIC_KEY = "..."
# NEON_AUTH_PROJECT_ID = "..."
# NEON_AUTH_API_KEY = "..."

# 任意（表示名・連絡先など）
OPERATOR_NAME = "運営者"
OPERATOR_CONTACT = ""
OPERATOR_CONTACT_EMAIL = ""
OPERATOR_CONTACT_X = ""
OPERATOR_CONTACT_DISCORD = ""
FEEDBACK_RETENTION_DAYS = "365"
```

注意:
- Secrets のキーは **必ず `DATABASE_URL`**（大文字/小文字一致）
- 末尾のクエリ（`sslmode` 等）は Neon が付けている場合そのままでOK
- `AUTH_MODE=auto` の場合、Neon Auth Secrets が未設定なら自動で local 認証にフォールバック

---

## 5. 初回起動時の DB 初期化

このプロジェクトは起動時に以下を行います。

- テーブル作成（SQLAlchemy `create_all`）
- 初期データ投入（ダンジョン/敵/スキル/装備/アイテム等）

そのため、多くの場合は **「Secrets を設定して起動するだけ」**で動きます。

補足:
- SQLite 専用のマイグレーション処理は PostgreSQL では実行されないため安全です。

---

## 6. 公開前チェックリスト

- Cloud のログで例外が出ていない
- 新規登録 → ログイン → ダンジョン → 戦闘 が一通り動く
- 再起動後もユーザー/進行が残る（＝SQLiteではなく Neon に接続できている）

---

## 7. よくある詰まりどころ（対処）

### 7.1 SQLite のまま動いてしまう

- Cloud では `.env` は使わず Secrets に `DATABASE_URL` を設定する
- ローカルでは `text_rpg/.env` を読むようにしてあるが、OS の環境変数 `DATABASE_URL` が設定されていると、そちらが優先される場合があります

### 7.2 `TypeError: connect() got an unexpected keyword argument 'sslmode'`

- Neon の URI に付く `sslmode` / `channel_binding` 等が原因です
- 本プロジェクトはこれを吸収する実装にしてあるため、原則は最新版をデプロイして再起動すれば解消します

### 7.3 接続数制限・接続が不安定

- Neon の **pooler**（`-pooler` のホスト）を使う構成は相性が良いです
- それでも厳しい場合は、将来的に SQLAlchemy の接続プール設定を調整します（アクセス増加時に検討）

---

## 8. ローカル開発で Neon に繋ぐ

ローカルでも Neon に接続できます。

- `text_rpg/.env` に `DATABASE_URL=...` を設定
- `streamlit run text_rpg/app.py` で起動

注意:
- 接続文字列の取り扱い（コミットしない、ログに出さない）に注意

---

## 付録: どこで DB を読むか

- `DATABASE_URL` 読み込み: `text_rpg/config.py`
- URL 正規化/サニタイズ・エンジン生成: `text_rpg/models/database.py`
