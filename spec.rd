# 要件定義書

## 1. 概要
本プロジェクトは、PythonとStreamlitを用いたWebアプリケーションとして、テキストベースのRPGを開発する。ユーザーは複数のクラスから4名のPC（プレイヤーキャラクター）を選択し、3階層のダンジョンを攻略する。各階層ではランダムエンカウントとボス戦が発生する。

## 2. システム要件
### 2.1 技術スタック
- 言語: Python 3.x
- Webフレームワーク: Streamlit
- データベース: SQLite（開発環境） / MySQL（本番環境・`.env` の `DATABASE_URL` を切り替えることで移行可能）
- その他ライブラリ:
  - SQLAlchemy（ORM）
  - random（エンカウント制御）
  - python-dotenv（環境変数管理）
  - PyMySQL（MySQL接続時に必要）
  - streamlit-authenticator（ログイン画面の実装）

### 2.2 フォルダ構成
```
text_rpg/
│── app.py               # Streamlitのエントリーポイント（トップページ）
│── config.py            # 設定ファイル
│── requirements.txt     # 必要ライブラリ一覧
│── .env                 # 環境変数（DB接続情報など）
│── pages/               # Streamlit マルチページ用ディレクトリ
│   ├── 1_character.py   # キャラクター作成・管理ページ
│   ├── 2_dungeon.py     # ダンジョン探索ページ
│   ├── 3_battle.py      # 戦闘ページ
│── data/
│   ├── db_init.sql      # 初期DB設定スクリプト
│── models/
│   ├── database.py      # DB接続管理
│   ├── character.py     # キャラクターモデル
│   ├── dungeon.py       # ダンジョン・階層管理
│── game/
│   ├── battle.py        # 戦闘システム
│   ├── dungeon.py       # ダンジョン探索ロジック
│── static/              # UI用の画像ファイル（st.imageで参照）
│── utils/               # ユーティリティ関数
│── tests/               # テストコード
```

> **補足**: Streamlit では `templates/`（Jinja2 HTML テンプレート）は不要。マルチページ構成は `pages/` ディレクトリと `st.session_state` で状態管理を行う。

## 3. データベース設計
### 3.1 テーブル定義
#### `users`（プレイヤー情報）
| カラム名   | 型         | 主キー | 外部キー | 説明 |
|------------|-----------|--------|---------|------|
| id         | INT       | ○      |         | ユーザーID |
| name       | VARCHAR   |        |         | ユーザー名 |
| created_at | DATETIME  |        |         | 登録日時 |

#### `characters`（プレイヤーキャラクター）
| カラム名   | 型        | 主キー | 外部キー | 説明 |
|------------|----------|--------|---------|------|
| id         | INT      | ○      |         | キャラクターID |
| user_id    | INT      |        | users(id) | 所属ユーザー |
| name       | VARCHAR  |        |         | キャラクター名 |
| class      | VARCHAR  |        |         | キャラクターのクラス |
| level      | INT      |        |         | レベル |
| exp        | INT      |        |         | 経験値 |
| hp         | INT      |        |         | 現在ヒットポイント |
| max_hp     | INT      |        |         | 最大ヒットポイント |
| mp         | INT      |        |         | 現在マジックポイント |
| max_mp     | INT      |        |         | 最大マジックポイント |
| attack     | INT      |        |         | 攻撃力 |
| defense    | INT      |        |         | 防御力 |

#### `dungeons`（ダンジョン情報）
| カラム名   | 型        | 主キー | 外部キー | 説明 |
|------------|----------|--------|---------|------|
| id         | INT      | ○      |         | ダンジョンID |
| name       | VARCHAR  |        |         | ダンジョン名 |
| floor      | INT      |        |         | 階層数 |

#### `enemies`（敵情報）
| カラム名   | 型        | 主キー | 外部キー | 説明 |
|------------|----------|--------|---------|------|
| id         | INT      | ○      |         | 敵ID |
| name       | VARCHAR  |        |         | 敵名 |
| dungeon_id | INT      |        | dungeons(id) | 出現ダンジョン |
| floor      | INT      |        |         | 出現階層 |
| hp         | INT      |        |         | ヒットポイント |
| attack     | INT      |        |         | 攻撃力 |
| defense    | INT      |        |         | 防御力 |
| exp_reward | INT      |        |         | 撃破時の獲得経験値 |
| is_boss    | BOOLEAN  |        |         | ボスフラグ（TRUE=ボス） |

#### `party_members`（パーティ構成）
| カラム名      | 型        | 主キー | 外部キー | 説明 |
|--------------|----------|--------|---------|------|
| id           | INT      | ○      |         | パーティメンバーID |
| user_id      | INT      |        | users(id) | 所属ユーザー |
| character_id | INT      |        | characters(id) | キャラクターID |
| slot         | INT      |        |         | パーティスロット番号（1～4） |

#### `skills`（スキル情報）
| カラム名      | 型        | 主キー | 外部キー | 説明 |
|--------------|----------|--------|---------|------|
| id           | INT      | ○      |         | スキルID |
| name         | VARCHAR  |        |         | スキル名 |
| class        | VARCHAR  |        |         | 使用可能クラス |
| mp_cost      | INT      |        |         | 消費MP |
| power        | INT      |        |         | 威力（攻撃系）または回復量（回復系） |
| effect_type  | VARCHAR  |        |         | 効果種別（attack / heal / buff） |

#### `dungeon_progress`（ゲーム進行状況）
| カラム名      | 型        | 主キー | 外部キー | 説明 |
|--------------|----------|--------|---------|------|
| id           | INT      | ○      |         | 進行状況ID |
| user_id      | INT      |        | users(id) | 所属ユーザー |
| dungeon_id   | INT      |        | dungeons(id) | 攻略中ダンジョン |
| current_floor| INT      |        |         | 現在の階層 |
| is_cleared   | BOOLEAN  |        |         | クリアフラグ |
| updated_at   | DATETIME |        |         | 最終更新日時 |

## 4. 機能一覧
### 4.1 ユーザー管理
- ユーザー登録
- ユーザーログイン

### 4.2 キャラクター管理
- 4名のPC作成
- クラス選択（例: 戦士, 魔法使い, 盗賊 など）

### 4.3 ダンジョン探索
- 3階層のダンジョン実装
- 各階層ごとのランダムエンカウント（2～3回）
- ボス戦の配置

### 4.4 戦闘システム
- ターン制バトル（プレイヤー vs 敵）
- 攻撃/スキル/防御の選択
- 戦闘終了時のリザルト表示

## 5. 制約と考慮事項
- 初期リリースでは最低限の機能のみ実装
- 将来的にUI強化やアイテム要素の追加を検討
- Streamlit の `st.session_state` を活用してページ間のゲーム状態（パーティ情報・戦闘状態・進行フラグ）を保持する
- Streamlit はページ再読み込みで状態がリセットされるため、重要な進行データは都度 DB に永続化すること
- ユーザー認証には `streamlit-authenticator` ライブラリを使用し、セッション管理を簡略化する

## 6. 実装スケジュール
| フェーズ | 期間 | 内容 |
|----------|------|------|
| 設計     | 1週間 | 要件定義、データベース設計 |
| 実装     | 3週間 | 各機能の開発（ユーザー管理、ダンジョン探索、戦闘） |
| テスト   | 1週間 | 動作確認とバグ修正 |
| リリース | -    | デプロイと運用開始 |

---

この要件定義書をもとに、Python + StreamlitによるテキストRPGを実装する。

