# 不具合報告・改善要望フォーム 仕様書

**文書番号**: SPEC-FEEDBACK-01  
**作成日**: 2026-03-21  
**対象アプリ**: liteWebRPG（Python + Streamlit テキスト RPG）

---

## 1. 概要・目的

公開サイト上にプレイヤーが不具合を報告したり改善要望を送信できるフォームページを設ける。  
受け付けた内容は DB に蓄積し、管理者が Streamlit 管理ページから一覧・対応状況管理ができるようにする。

### 1.1 解決したい課題

| 課題 | 対応方針 |
|------|----------|
| プレイヤーが不具合を発見しても報告手段がない | ゲーム内から直接送信できるフォームを設置 |
| 要望がどこに寄せられているか分散している | DB 一元管理＋ステータス管理で追跡可能にする |
| 匹名報告だと再現確認が困難 | ログイン中はユーザー情報を自動付与（匹名送信は将来拡張時に導入） |

---

## 2. ページ構成

### 2.1 追加するページ

```
pages/
  5_feedback.py          # フォーム入力ページ（プレイヤー向け）
  99_admin_feedback.py   # 管理者向け一覧・対応ページ（要管理者フラグ）
```

### 2.2 ナビゲーション配置

- `app.py` のサイドバーリンクに「📢 不具合報告・改善要望」を追加
- `1_character.py` ページ末尾にもフッターリンクとして設置

---

## 3. データモデル

### 3.1 `feedbacks` テーブル

```sql
CREATE TABLE IF NOT EXISTS feedbacks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER REFERENCES users(id),   -- 将来の匿名送信解禁まで常に NOT NULL 相当で使用
    category     VARCHAR(16)  NOT NULL,           -- 'bug' | 'request' | 'other'
    title        VARCHAR(128) NOT NULL,
    body         TEXT         NOT NULL,
    page_context VARCHAR(64)  NOT NULL DEFAULT '', -- 発生ページ（任意）
    severity     VARCHAR(16)  NOT NULL DEFAULT 'normal', -- 'low'|'normal'|'high'|'critical'
    status       VARCHAR(16)  NOT NULL DEFAULT 'open',   -- 'open'|'in_progress'|'resolved'|'closed'
    admin_note   TEXT         NOT NULL DEFAULT '',
    created_at   DATETIME     NOT NULL,
    updated_at   DATETIME     NOT NULL
);
```

### 3.2 フィールド詳細

| カラム | 型 | 必須 | 説明 |
|--------|----|------|------|
| `id` | INTEGER | ✓ | 自動採番 |
| `user_id` | INTEGER | ✓ | ログイン中ユーザーの ID（現時点はログイン必須のため常にセット） |
| `category` | VARCHAR(16) | ✓ | `bug`（不具合）/ `request`（改善要望）/ `other`（その他） |
| `title` | VARCHAR(128) | ✓ | 件名（最大 128 文字） |
| `body` | TEXT | ✓ | 詳細内容（最大 2000 文字） |
| `page_context` | VARCHAR(64) | — | 発生したページ（例: `3_battle`）。フォーム遷移元 URL から自動設定可 |
| `severity` | VARCHAR(16) | ✓ | 重要度（不具合カテゴリのみ使用） |
| `status` | VARCHAR(16) | ✓ | 対応ステータス（初期値: `open`） |
| `admin_note` | TEXT | — | 管理者メモ（プレイヤーには非表示） |
| `created_at` | DATETIME | ✓ | 作成日時（UTC） |
| `updated_at` | DATETIME | ✓ | 更新日時（UTC） |

---

## 4. 機能要件

### 4.1 フォーム入力ページ（`5_feedback.py`）

#### 4.1.1 入力項目

| 項目 | UI コンポーネント | バリデーション |
|------|-----------------|----------------|
| カテゴリ | `st.radio`（不具合 / 改善要望 / その他） | 必須 |
| 件名 | `st.text_input` | 必須、1〜128 文字 |
| 詳細内容 | `st.text_area`（高さ 200px） | 必須、10〜2000 文字 |
| 発生ページ | `st.selectbox`（ページ一覧＋「その他・不明」） | 任意 |
| 重要度 | `st.select_slider`（低 / 普通 / 高 / 致命的）※不具合カテゴリのみ表示 | カテゴリが「不具合」の場合は必須 |

#### 4.1.2 自動付与情報

- ログイン中ユーザーの `user_id` を自動セット（ログイン必須のため常に付与）
- `page_context` → `st.session_state` の直前ページ情報から自動設定（不明時は空文字）

#### 4.1.3 送信後の動作

1. DB に保存（`Feedback.create()`）
2. `st.success("ご報告ありがとうございます！受付番号: #XXX")` を表示
3. フォームをリセット（`st.rerun()`）
4. 重複送信防止: 同一ユーザーが同一件名で 5 分以内に再送信しようとした場合はブロックし警告表示

#### 4.1.4 スパム・悪用対策

- ログインあり: 24 時間以内に同一ユーザーから 10 件以上の場合はブロック
- `body` に含まれる URL は 3 個以上の場合は送信を拒否

### 4.2 管理者ページ（`99_admin_feedback.py`）

#### 4.2.1 アクセス制御

- `st.session_state["is_admin"]` が `True` のユーザーのみ表示
- `users` テーブルに `is_admin INTEGER NOT NULL DEFAULT 0` カラムを追加（マイグレーション対応）

#### 4.2.2 一覧表示

- フィルタ: カテゴリ・重要度・ステータス・日付範囲でフィルタリング可能
- ソート: 作成日（新順/古順）・重要度（高順）で切り替え可能
- `st.dataframe` で表示（ページネーション: 20 件/ページ）
- 各行をクリックすると詳細モーダルを表示（`st.expander` または `st.dialog`）

#### 4.2.3 対応管理

| 操作 | 説明 |
|------|------|
| ステータス変更 | `open` → `in_progress` → `resolved` / `closed` |
| 管理者メモ記入 | テキストエリアで編集・保存 |
| 削除 | 論理削除（`status = 'closed'` へ変更） |

#### 4.2.4 統計ダッシュボード（任意実装）

- カテゴリ別件数の棒グラフ（`st.bar_chart`）
- 直近 30 日の投稿数推移（`st.line_chart`）
- 対応中件数サマリー（`st.metric`）

---

## 5. モデル実装（`models/feedback.py`）

```python
class Feedback(Base):
    __tablename__ = "feedbacks"

    id:           Mapped[int]      = mapped_column(primary_key=True, autoincrement=True)
    user_id:      Mapped[int|None] = mapped_column(nullable=True)
    category:     Mapped[str]      = mapped_column(String(16),  nullable=False)
    title:        Mapped[str]      = mapped_column(String(128), nullable=False)
    body:         Mapped[str]      = mapped_column(Text,        nullable=False)
    page_context: Mapped[str]      = mapped_column(String(64),  nullable=False, server_default="''")
    severity:     Mapped[str]      = mapped_column(String(16),  nullable=False, server_default="'normal'")
    status:       Mapped[str]      = mapped_column(String(16),  nullable=False, server_default="'open'")
    admin_note:   Mapped[str]      = mapped_column(Text,        nullable=False, server_default="''")
    created_at:   Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at:   Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # ── 静的メソッド ──────────────────────────────────────
    @staticmethod
    def create(db, user_id, category, title, body, page_context="", severity="normal") -> "Feedback": ...

    @staticmethod
    def get_all(db, *, category=None, status=None, severity=None,
                date_from=None, date_to=None, limit=20, offset=0) -> list["Feedback"]: ...

    @staticmethod
    def get_by_id(db, feedback_id) -> "Feedback | None": ...

    @staticmethod
    def update_status(db, feedback_id, status, admin_note="") -> bool: ...

    @staticmethod
    def count_recent_by_user(db, user_id, minutes=5, title=None) -> int: ...
    # 重複送信チェック用

    @staticmethod
    def count_today_by_user(db, user_id) -> int: ...
    # 1日の送信上限チェック用
```

---

## 6. UI / UX 詳細

### 6.1 フォームページ レイアウト

```
📢 不具合報告・改善要望

ログイン中: {username}  ← ログイン済みの場合のみ表示

[不具合  ●] [改善要望  ○] [その他  ○]   ← カテゴリ選択 (radio)

件名: [________________________]

詳細内容:
┌─────────────────────────────────┐
│                                 │
│  （ここに詳しく書いてください）    │
│                                 │
└─────────────────────────────────┘
残り {N} 文字

発生ページ: [▼ 戦闘画面]     重要度: [低 ─●─ 普通 ─ 高 ─ 致命的]

[  送信する  ]
```

### 6.2 カテゴリ別アイコン

| カテゴリ | アイコン | 重要度表示 |
|----------|---------|------------|
| 不具合   | 🐛 | あり |
| 改善要望 | 💡 | なし（非表示） |
| その他   | 📝 | なし（非表示） |

### 6.3 ステータスバッジ（管理ページ）

| ステータス | 表示色 | ラベル |
|-----------|--------|--------|
| `open`        | 🔴 赤 | 未対応 |
| `in_progress` | 🟡 黄 | 対応中 |
| `resolved`    | 🟢 緑 | 解決済 |
| `closed`      | ⚫ 灰 | クローズ |

---

## 7. `database.py` マイグレーション追加

`migrate_db()` に以下を追記（冪等）:

```python
# ── フィードバック機能 ──────────────────────────────────────────────────

# users テーブルに is_admin カラム追加
try:
    conn.execute(text("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0"))
    conn.commit()
except Exception:
    conn.rollback()

# feedbacks テーブル作成（存在しない場合）
conn.execute(text("""
    CREATE TABLE IF NOT EXISTS feedbacks (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id      INTEGER REFERENCES users(id),
        category     VARCHAR(16)  NOT NULL,
        title        VARCHAR(128) NOT NULL,
        body         TEXT         NOT NULL,
        page_context VARCHAR(64)  NOT NULL DEFAULT '',
        severity     VARCHAR(16)  NOT NULL DEFAULT 'normal',
        status       VARCHAR(16)  NOT NULL DEFAULT 'open',
        admin_note   TEXT         NOT NULL DEFAULT '',
        created_at   DATETIME     NOT NULL,
        updated_at   DATETIME     NOT NULL
    )
"""))
conn.commit()
```

---

## 8. `models/__init__.py` への登録

`Feedback` モデルを `models/__init__.py` の import リストに追加し、  
`Base.metadata.create_all()` の対象に含める。

---

## 9. `config.py` への追加定数

```python
# ─── フィードバック設定 ───────────────────────────────────────
FEEDBACK_CATEGORIES: dict[str, dict] = {
    "bug":     {"label": "🐛 不具合",    "has_severity": True},
    "request": {"label": "💡 改善要望",  "has_severity": False},
    "other":   {"label": "📝 その他",    "has_severity": False},
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

FEEDBACK_MAX_BODY_LENGTH: int = 2000
FEEDBACK_DAILY_LIMIT: int     = 10   # ログイン済みユーザーの 1 日上限
FEEDBACK_DUPLICATE_MINUTES: int = 5  # 同件名の重複送信をブロックする時間（分）
# FEEDBACK_SESSION_LIMIT は匿名送信解禁（将来拡張）時に追加する
```

---

## 10. テスト計画

### 10.1 `tests/test_feedback.py` に追加するテストクラス

```
TestFeedbackModel
  test_create_feedback_logged_in     -- user_id が正しく保存されること
  test_create_feedback_anonymous     -- user_id=None で保存できること
  test_get_all_filter_by_category    -- category フィルタが機能すること
  test_get_all_filter_by_status      -- status フィルタが機能すること
  test_update_status                 -- ステータス変更と admin_note が保存されること
  test_count_recent_blocks_duplicate -- 5 分以内の同件名を検出すること
  test_count_today_by_user           -- 当日件数のカウントが正確なこと
  test_body_max_length_validation    -- 2001 文字の body は ValueError を送出すること
```

---

## 11. 非機能要件

| 項目 | 要件 |
|------|------|
| セキュリティ | `body` / `title` は HTMLエスケープして保存（XSS対策） |
| パフォーマンス | 一覧取得は `LIMIT/OFFSET` によるページネーションを使用（全件取得禁止） |
| 可用性 | フォーム送信は戦闘中など他の操作と干渉しない独立ページ |
| 保守性 | カテゴリ・重要度・ステータスは `config.py` の辞書で一元管理し、UI との二重定義を避ける |
| 国際化 | 現時点は日本語のみ。ラベル文字列は `config.py` に集約し後から差し替え可能な設計とする |

---

## 12. 実装順序（推奨）

1. `config.py` にフィードバック関連定数を追加  
2. `models/feedback.py` を新規作成（`Feedback` モデル）  
3. `database.py` の `migrate_db()` にマイグレーションを追加  
4. `models/__init__.py` に `Feedback` を登録  
5. `pages/5_feedback.py`（プレイヤー向けフォーム）を作成  
6. `pages/99_admin_feedback.py`（管理者向け一覧）を作成  
7. `tests/test_feedback.py` を作成してテストを通過させる  
8. `app.py` / `pages/1_character.py` にナビゲーションリンクを追加  

---

## 13. 将来拡張（スコープ外）

- **匿名送信**: 将来「外部公開」「未ログイン投稿解禁」が必要になった時点で再導入する。  
  実装時は `feedbacks.user_id` を NULL 許容のまま使い、`FEEDBACK_SESSION_LIMIT` 定数と  
  `Feedback.count_session_anonymous()` メソッドを追加してセッション上限チェックを行う。  
  フォームには「匿名で送信する（ユーザー名を伏せて報告）」チェックボックスを追加し、  
  OFF 時は `user_id` を自動セット、ON 時は NULL で保存する。
- **メール通知**: 重要度「致命的」の投稿時に管理者へメール送信（smtplib / SendGrid）
- **添付画像**: スクリーンショットのアップロード（`st.file_uploader` + クラウドストレージ連携）
- **公開 FAQ**: 解決済み投稿を FAQ として公開する機能
- **評価ボタン**: 他ユーザーが「同じ問題が起きた」ボタンで投票し、優先度に反映
