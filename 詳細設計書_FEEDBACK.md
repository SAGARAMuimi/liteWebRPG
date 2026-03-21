# 詳細設計書：FEEDBACK 不具合報告・改善要望フォーム

作成日: 2026-03-21  
対象ブランチ: main（169テスト通過済み）

---

## 目次

1. [前提・スコープ](#1-前提スコープ)
2. [設計方針](#2-設計方針)
3. [実装詳細](#3-実装詳細)
   - 3.1 config.py の変更
   - 3.2 models/feedback.py の新規作成
   - 3.3 models/__init__.py の変更
   - 3.4 models/database.py の変更
   - 3.5 pages/5_feedback.py の新規作成
   - 3.6 pages/99_admin_feedback.py の新規作成
   - 3.7 utils/auth.py の変更（管理者チェック追加）
4. [UI設計](#4-ui設計)
5. [テスト観点](#5-テスト観点)
6. [実装ロードマップ](#6-実装ロードマップ)

---

## 1. 前提・スコープ

### 現在の状態

```
pages/
  1_character.py   # キャラクター管理
  2_dungeon.py     # ダンジョン探索
  3_battle.py      # 戦闘
  4_town.py        # 町

models/
  user.py          # ユーザー（管理者フラグなし）
  ...              # フィードバック関連モデルなし
```

プレイヤーが不具合を発見しても報告する手段がなく、改善要望を届ける経路もない。

### 課題

| 課題 | 対応方針 |
|---|---|
| 報告手段がない | ゲーム内から直接送信できる独立ページを追加 |
| 匹名報告だと再現確認が困難 | ログイン中はユーザー情報を自動付与（匹名送信は将来拡張時に導入） |
| 投稿の追跡・管理ができない | DB に蓄積し管理者ページで対応状況を管理 |

### スコープ

- **追加するファイル**: `models/feedback.py`, `pages/5_feedback.py`, `pages/99_admin_feedback.py`
- **変更するファイル**: `config.py`, `models/__init__.py`, `models/database.py`, `utils/auth.py`
- 既存のゲームロジック（`game/battle.py` 等）への変更はなし
- 匿名送信（`user_id = NULL`）は本設計のスコープ外とする（将来拡張参照）
- メール通知・画像添付は本設計のスコープ外とする

---

## 2. 設計方針

### 主な設計上の決定

| 検討事項 | 採用案 | 理由 |
|---|---|---|
| DB格納場所 | 既存の `text_rpg.db`（SQLite）に `feedbacks` テーブルを追加 | 新規 DB 接続不要・`migrate_db()` パターンで冪等追加できる |
| 管理者識別 | `users.is_admin` カラム（0/1 整数）を追加 | 最小変更で実現。将来ロールテーブルへの移行も容易 |
| スパム防止 | DB クエリによる件数チェック（外部ライブラリ不使用） | 依存ライブラリを増やさない。`requirements.txt` 無変更 |
| 管理者ページの隠蔽 | ファイル名を `99_admin_feedback.py`（先頭 `99`）とし、Streamlit サイドバーに表示されるが管理者以外はアクセス時にブロック | Streamlit のマルチページ構造では完全なルート保護ができないため、ページ内で権限チェックする |

### ファイル間の依存関係

```
config.py
  └─ FEEDBACK_CATEGORIES, FEEDBACK_SEVERITIES, FEEDBACK_STATUSES,
     FEEDBACK_PAGE_LABELS, FEEDBACK_MAX_BODY_LENGTH,
     FEEDBACK_DAILY_LIMIT, FEEDBACK_SESSION_LIMIT, FEEDBACK_DUPLICATE_MINUTES

models/feedback.py
  └─ Base (models/database.py)
  └─ FEEDBACK_* 定数 (config.py)  ← 遅延 import

models/__init__.py
  └─ Feedback を登録（依存順序: users の後、独立テーブルのため後方でOK）

models/database.py
  └─ migrate_db() に users.is_admin カラム追加 + feedbacks テーブル作成を追記

pages/5_feedback.py
  └─ Feedback (models/feedback.py)
  └─ check_login, get_current_user_id (utils/auth.py)
  └─ FEEDBACK_* 定数 (config.py)

pages/99_admin_feedback.py
  └─ Feedback (models/feedback.py)
  └─ check_admin (utils/auth.py ← 新規追加)
  └─ FEEDBACK_* 定数 (config.py)

utils/auth.py
  └─ check_admin() 追加（users.is_admin を参照）
```

---

## 3. 実装詳細

### 3.1 config.py の変更

ファイル末尾の `META_TITLES` ブロックの後に追記する。

```python
# ─── フィードバック設定 ────────────────────────────────────────────────────

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

FEEDBACK_MAX_BODY_LENGTH: int     = 2000
FEEDBACK_DAILY_LIMIT: int         = 10   # ログイン済みユーザーの 1 日上限
FEEDBACK_DUPLICATE_MINUTES: int   = 5    # 同件名の重複送信をブロックする時間（分）
# FEEDBACK_SESSION_LIMIT は匹名送信解禁（将来拡張）時に追加する
```

---

### 3.2 models/feedback.py の新規作成

`models/item.py` の構造パターンに準拠し、静的メソッドでクエリを提供する。

```python
"""
models/feedback.py - 不具合報告・改善要望モデル
"""

from __future__ import annotations
from datetime import datetime, timedelta
from sqlalchemy import String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, Session
from models.database import Base


class Feedback(Base):
    __tablename__ = "feedbacks"

    id          : Mapped[int]       = mapped_column(primary_key=True, autoincrement=True)
    user_id     : Mapped[int|None]  = mapped_column(nullable=True)                  # 将来の匹名送信解禁までは常に SET
    category    : Mapped[str]       = mapped_column(String(16),  nullable=False)
    title       : Mapped[str]       = mapped_column(String(128), nullable=False)
    body        : Mapped[str]       = mapped_column(Text,        nullable=False)
    page_context: Mapped[str]       = mapped_column(String(64),  nullable=False, server_default="''")
    severity    : Mapped[str]       = mapped_column(String(16),  nullable=False, server_default="'normal'")
    status      : Mapped[str]       = mapped_column(String(16),  nullable=False, server_default="'open'")
    admin_note  : Mapped[str]       = mapped_column(Text,        nullable=False, server_default="''")
    created_at  : Mapped[datetime]  = mapped_column(DateTime, nullable=False)
    updated_at  : Mapped[datetime]  = mapped_column(DateTime, nullable=False)

    # ──────────────────────────────────────────────────────────
    @staticmethod
    def create(
        db: Session,
        category: str,
        title: str,
        body: str,
        *,
        user_id: int | None = None,
        page_context: str = "",
        severity: str = "normal",
    ) -> "Feedback":
        """フィードバックを作成して返す。body が上限超えの場合 ValueError を送出する。"""
        from config import FEEDBACK_MAX_BODY_LENGTH
        if len(body) > FEEDBACK_MAX_BODY_LENGTH:
            raise ValueError(
                f"body は {FEEDBACK_MAX_BODY_LENGTH} 文字以内にしてください（{len(body)} 文字）"
            )
        now = datetime.utcnow()
        fb = Feedback(
            user_id=user_id,
            category=category,
            title=title.strip(),
            body=body.strip(),
            page_context=page_context,
            severity=severity if category == "bug" else "normal",
            status="open",
            admin_note="",
            created_at=now,
            updated_at=now,
        )
        db.add(fb)
        db.commit()
        db.refresh(fb)
        return fb

    @staticmethod
    def get_all(
        db: Session,
        *,
        category: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list["Feedback"]:
        """フィルタ条件に合致するフィードバック一覧を新着順で返す。"""
        q = db.query(Feedback)
        if category:
            q = q.filter(Feedback.category == category)
        if status:
            q = q.filter(Feedback.status == status)
        if severity:
            q = q.filter(Feedback.severity == severity)
        if date_from:
            q = q.filter(Feedback.created_at >= date_from)
        if date_to:
            q = q.filter(Feedback.created_at <= date_to)
        return (
            q.order_by(Feedback.created_at.desc())
             .limit(limit)
             .offset(offset)
             .all()
        )

    @staticmethod
    def count_all(
        db: Session,
        *,
        category: str | None = None,
        status: str | None = None,
    ) -> int:
        """総件数を返す（ページネーション用）。"""
        q = db.query(Feedback)
        if category:
            q = q.filter(Feedback.category == category)
        if status:
            q = q.filter(Feedback.status == status)
        return q.count()

    @staticmethod
    def get_by_id(db: Session, feedback_id: int) -> "Feedback | None":
        return db.query(Feedback).filter(Feedback.id == feedback_id).first()

    @staticmethod
    def update_status(
        db: Session,
        feedback_id: int,
        status: str,
        admin_note: str = "",
    ) -> bool:
        """ステータスと管理者メモを更新する。対象が見つからない場合は False を返す。"""
        fb = db.query(Feedback).filter(Feedback.id == feedback_id).first()
        if not fb:
            return False
        fb.status = status
        if admin_note:
            fb.admin_note = admin_note
        fb.updated_at = datetime.utcnow()
        db.commit()
        return True

    @staticmethod
    def count_recent_by_user(
        db: Session,
        user_id: int,
        minutes: int = 5,
        title: str | None = None,
    ) -> int:
        """
        指定分以内の同ユーザーの送信件数を返す。
        title を指定した場合は同件名に限定する（重複送信チェック用）。
        """
        threshold = datetime.utcnow() - timedelta(minutes=minutes)
        q = db.query(Feedback).filter(
            Feedback.user_id == user_id,
            Feedback.created_at >= threshold,
        )
        if title:
            q = q.filter(Feedback.title == title.strip())
        return q.count()

    @staticmethod
    def count_today_by_user(db: Session, user_id: int) -> int:
        """当日（UTC 0:00 以降）のユーザー送信件数を返す。"""
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return (
            db.query(Feedback)
            .filter(Feedback.user_id == user_id, Feedback.created_at >= today)
            .count()
        )
```

---

### 3.3 models/__init__.py の変更

`CharacterInventory` の import 直後に `Feedback` を追加する。

```python
# models/__init__.py （変更後）
from models.user import User
from models.dungeon import Dungeon, DungeonProgress
from models.character import Character, PartyMember
from models.enemy import Enemy
from models.skill import Skill
from models.item import Item
from models.inventory import Inventory
from models.equipment import Equipment, CharacterEquipment, CharacterInventory
from models.feedback import Feedback          # ← 追加

__all__ = [
    "User",
    "Dungeon", "DungeonProgress",
    "Character", "PartyMember",
    "Enemy",
    "Skill",
    "Item",
    "Inventory",
    "Equipment", "CharacterEquipment", "CharacterInventory",
    "Feedback",                               # ← 追加
]
```

---

### 3.4 models/database.py の変更

`migrate_db()` の末尾（R-15 メタ進行ブロックの後）に追記する。

```python
        # ── FEEDBACK 不具合報告・改善要望 ─────────────────────────────────────

        # users テーブルに is_admin カラム追加（既存 DB 対応）
        try:
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0"
            ))
            conn.commit()
        except Exception:
            conn.rollback()

        # feedbacks テーブル作成（存在しない場合）
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS feedbacks (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER REFERENCES users(id),  -- 将来の匹名送信解禁までは常に NOT NULL 相当
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

### 3.5 utils/auth.py の変更

`check_login()` の直後に `check_admin()` を追加する。

```python
def check_admin() -> None:
    """
    未ログイン、または is_admin=False のユーザーをブロックしてページを停止する。
    管理者ページの冒頭で呼び出すこと。
    """
    check_login()
    user_id = st.session_state.get("user_id")
    from models.database import SessionLocal
    from models.user import User
    with SessionLocal() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not getattr(user, "is_admin", 0):
            st.error("🚫 このページは管理者専用です。")
            st.stop()
```

合わせて `models/user.py` の `User` クラスにカラムを追加する：

```python
# models/user.py  User クラスの既存列定義の直後に追加
is_admin: Mapped[int] = mapped_column(default=0, nullable=False, server_default="0")
```

---

### 3.6 pages/5_feedback.py の新規作成

```python
"""
pages/5_feedback.py - 不具合報告・改善要望フォーム
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import models  # noqa: F401
import streamlit as st
from models.database import SessionLocal
from models.feedback import Feedback
from utils.auth import check_login, get_current_user_id
from config import (
    APP_TITLE,
    FEEDBACK_CATEGORIES,
    FEEDBACK_SEVERITIES,
    FEEDBACK_PAGE_LABELS,
    FEEDBACK_MAX_BODY_LENGTH,
    FEEDBACK_DAILY_LIMIT,
    FEEDBACK_DUPLICATE_MINUTES,
)

st.set_page_config(page_title=f"報告フォーム | {APP_TITLE}", page_icon="📢", layout="centered")
check_login()

user_id = get_current_user_id()

st.title("📢 不具合報告・改善要望")
st.caption(f"ログイン中: {st.session_state['username']}")
st.divider()


# ─── カテゴリ選択 ─────────────────────────────────────────────
cat_labels = {k: v["label"] for k, v in FEEDBACK_CATEGORIES.items()}
selected_cat_label = st.radio(
    "カテゴリ",
    list(cat_labels.values()),
    horizontal=True,
)
selected_cat = next(k for k, v in cat_labels.items() if v == selected_cat_label)
has_severity = FEEDBACK_CATEGORIES[selected_cat]["has_severity"]

# ─── 入力フォーム ─────────────────────────────────────────────
title = st.text_input("件名", max_chars=128, placeholder="例: 戦闘中にエラーが発生した")

body  = st.text_area(
    "詳細内容",
    height=200,
    max_chars=FEEDBACK_MAX_BODY_LENGTH,
    placeholder="再現手順・期待される動作・実際の動作などをできるだけ詳しく記載してください。",
)
st.caption(f"残り {FEEDBACK_MAX_BODY_LENGTH - len(body)} 文字")

page_keys    = list(FEEDBACK_PAGE_LABELS.keys())
page_labels  = list(FEEDBACK_PAGE_LABELS.values())
selected_page_label = st.selectbox("発生ページ（任意）", page_labels)
selected_page = page_keys[page_labels.index(selected_page_label)]

severity = "normal"
if has_severity:
    sev_labels = list(FEEDBACK_SEVERITIES.values())
    sev_keys   = list(FEEDBACK_SEVERITIES.keys())
    sev_label  = st.select_slider("重要度", options=sev_labels, value="普通")
    severity   = sev_keys[sev_labels.index(sev_label)]

st.divider()
if st.button("📤 送信する", type="primary", use_container_width=True):
    # ─── バリデーション ───────────────────────────────────────
    errors = []
    if not title.strip():
        errors.append("件名を入力してください。")
    if len(body.strip()) < 10:
        errors.append("詳細内容は 10 文字以上入力してください。")
    if errors:
        for e in errors:
            st.warning(e)
        st.stop()

    # ─── 送信制限チェック ─────────────────────────────────────
    with SessionLocal() as db:
        # ログイン済みユーザー: 1日上限 & 重複チェック
        dup_count   = Feedback.count_recent_by_user(
            db, user_id, minutes=FEEDBACK_DUPLICATE_MINUTES, title=title
        )
        today_count = Feedback.count_today_by_user(db, user_id)

    if dup_count > 0:
        st.warning(
            f"同じ件名のご報告を {FEEDBACK_DUPLICATE_MINUTES} 分以内に送信済みです。"
            "しばらくしてから再送信してください。"
        )
        st.stop()
    if not anonymous and today_count >= FEEDBACK_DAILY_LIMIT:
        st.warning(f"本日の送信上限（{FEEDBACK_DAILY_LIMIT}件）に達しています。")
        st.stop()
    if anonymous and st.session_state["feedback_session_count"] >= FEEDBACK_SESSION_LIMIT:
        st.warning(f"このセッション内での送信上限（{FEEDBACK_SESSION_LIMIT}件）に達しています。")
        st.stop()

    # ─── 保存 ─────────────────────────────────────────────────
    submit_user_id = None if anonymous else user_id
    with SessionLocal() as db:
        fb = Feedback.create(
            db,
            category=selected_cat,
            title=title.strip(),
            body=body.strip(),
            user_id=submit_user_id,
            page_context=selected_page if selected_page != "other" else "",
            severity=severity,
        )
    st.session_state["feedback_session_count"] += 1
    st.success(f"✅ ご報告ありがとうございます！  受付番号: **#{fb.id}**")
    # フォームリセット（rerun でウィジェットを初期化）
    st.rerun()
```

---

### 3.7 pages/99_admin_feedback.py の新規作成

```python
"""
pages/99_admin_feedback.py - 管理者向け フィードバック一覧・対応ページ
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import models  # noqa: F401
import streamlit as st
from models.database import SessionLocal
from models.feedback import Feedback
from utils.auth import check_admin           # 管理者専用チェック
from config import (
    APP_TITLE,
    FEEDBACK_CATEGORIES,
    FEEDBACK_SEVERITIES,
    FEEDBACK_STATUSES,
    FEEDBACK_PAGE_LABELS,
)

st.set_page_config(page_title=f"[管理] フィードバック | {APP_TITLE}", page_icon="🛠️", layout="wide")
check_admin()   # 非管理者は st.stop() でブロック

PAGE_SIZE = 20

st.title("🛠️ フィードバック管理")
st.divider()

# ─── 統計サマリー ─────────────────────────────────────────────
with SessionLocal() as db:
    open_count  = Feedback.count_all(db, status="open")
    wip_count   = Feedback.count_all(db, status="in_progress")
    done_count  = Feedback.count_all(db, status="resolved")
    total_count = Feedback.count_all(db)

col1, col2, col3, col4 = st.columns(4)
col1.metric("🔴 未対応",   open_count)
col2.metric("🟡 対応中",   wip_count)
col3.metric("🟢 解決済",   done_count)
col4.metric("📋 合計",     total_count)
st.divider()

# ─── フィルタ ─────────────────────────────────────────────────
fcols = st.columns(3)
with fcols[0]:
    f_cat = st.selectbox(
        "カテゴリ",
        ["（すべて）"] + [v["label"] for v in FEEDBACK_CATEGORIES.values()],
    )
    filter_cat = next(
        (k for k, v in FEEDBACK_CATEGORIES.items() if v["label"] == f_cat), None
    )
with fcols[1]:
    f_status = st.selectbox("ステータス", ["（すべて）"] + list(FEEDBACK_STATUSES.values()))
    filter_status = next(
        (k for k, v in FEEDBACK_STATUSES.items() if v == f_status), None
    )
with fcols[2]:
    page_num = st.number_input("ページ", min_value=1, value=1, step=1)

offset = (page_num - 1) * PAGE_SIZE

# ─── 一覧取得 ─────────────────────────────────────────────────
with SessionLocal() as db:
    items = Feedback.get_all(
        db,
        category=filter_cat,
        status=filter_status,
        limit=PAGE_SIZE,
        offset=offset,
    )
    filtered_total = Feedback.count_all(db, category=filter_cat, status=filter_status)

st.caption(f"{filtered_total} 件中 {offset + 1}〜{min(offset + PAGE_SIZE, filtered_total)} 件を表示")

# ─── 一覧表示 ─────────────────────────────────────────────────
for fb in items:
    cat_label  = FEEDBACK_CATEGORIES.get(fb.category, {}).get("label", fb.category)
    stat_label = FEEDBACK_STATUSES.get(fb.status, fb.status)
    sev_label  = FEEDBACK_SEVERITIES.get(fb.severity, "")
    sev_text   = f"  重要度: {sev_label}" if fb.category == "bug" else ""
    page_text  = FEEDBACK_PAGE_LABELS.get(fb.page_context, "") if fb.page_context else ""
    user_text  = f"UID:{fb.user_id}" if fb.user_id else "匿名"

    with st.expander(
        f"{stat_label}  {cat_label}  **#{fb.id} {fb.title}**  "
        f"({user_text}  {fb.created_at.strftime('%Y-%m-%d %H:%M')})"
    ):
        st.text_area("本文", fb.body, disabled=True, height=120, key=f"body_{fb.id}")
        if page_text:
            st.caption(f"発生ページ: {page_text}{sev_text}")

        # ─── 対応フォーム ──────────────────────────────────────
        new_status_label = st.selectbox(
            "ステータス変更",
            list(FEEDBACK_STATUSES.values()),
            index=list(FEEDBACK_STATUSES.keys()).index(fb.status),
            key=f"status_{fb.id}",
        )
        new_status = next(k for k, v in FEEDBACK_STATUSES.items() if v == new_status_label)
        new_note   = st.text_area(
            "管理者メモ（プレイヤーには非表示）",
            value=fb.admin_note,
            height=80,
            key=f"note_{fb.id}",
        )
        if st.button("💾 保存", key=f"save_{fb.id}"):
            with SessionLocal() as db:
                Feedback.update_status(db, fb.id, new_status, new_note)
            st.rerun()
```

---

## 4. UI設計

### 4.1 フォームページ（`5_feedback.py`）

```
📢 不具合報告・改善要望
ログイン中: testuser

[🐛 不具合 ●] [💡 改善要望 ○] [📝 その他 ○]

件名: [___________________________________]

詳細内容:
┌────────────────────────────────────────────────┐
│                                                │
│  （ここに詳しく書いてください）                  │
│                                                │
└────────────────────────────────────────────────┘
残り 2000 文字

発生ページ: [▼ 戦闘]      重要度: [低 ─── 普通 ─●─ 高 ─── 致命的]

────────────────────────────────────────────────
[📤 送信する                                    ]
```

#### バリデーションエラー表示位置

「送信する」ボタン押下後、ボタン直上に `st.warning()` で表示。

#### 送信成功メッセージ

```
✅ ご報告ありがとうございます！  受付番号: #42
```

---

### 4.2 管理者ページ（`99_admin_feedback.py`）

```
🛠️ フィードバック管理

[🔴 未対応: 3] [🟡 対応中: 1] [🟢 解決済: 12] [📋 合計: 16]

──────────────────────────────────────────────────────────────
カテゴリ [（すべて）▼]  ステータス [（すべて）▼]  ページ [1▲]
16件中 1〜16件を表示

▼ 🔴 未対応  🐛 不具合  #42 戦闘中にエラーが発生した  (UID:3  2026-03-20 18:42)
  ┌────────────────────────────────────────────────┐
  │ 敵を選択してスキルを使うとエラーが出て...         │
  └────────────────────────────────────────────────┘
  発生ページ: 戦闘  重要度: 高
  ステータス変更 [🟡 対応中 ▼]
  管理者メモ: [___________________________________]
  [💾 保存]

▼ 🔴 未対応  💡 改善要望  #41 回復スキルの説明をわかりやすくしてほしい  (UID:2  2026-03-20 12:10)
  ...
```

---

## 5. テスト観点

新規ファイル `tests/test_feedback.py` を作成する。  
既存の `@pytest.fixture def db():` パターンを利用する。

```python
# tests/test_feedback.py に追加するテストクラス

class TestFeedbackModel:

    def test_create_feedback_logged_in(self, db):
        """user_id を指定すると保存されること"""
        user = User.create(db, "fb_user", "pass")
        fb = Feedback.create(db, "bug", "テストタイトル", "詳細内容テスト", user_id=user.id)
        assert fb.id is not None
        assert fb.user_id == user.id
        assert fb.status == "open"

    def test_create_feedback_body_max_length_validation(self, db):
        """2001 文字の body は ValueError を送出すること"""
        import pytest
        with pytest.raises(ValueError):
            Feedback.create(db, "other", "件名", "a" * 2001)

    def test_get_all_filter_by_category(self, db):
        """category フィルタが機能すること"""
        Feedback.create(db, "bug",     "バグ報告",  "内容テスト詳細1")
        Feedback.create(db, "request", "要望報告",  "内容テスト詳細2")
        results = Feedback.get_all(db, category="bug")
        assert all(fb.category == "bug" for fb in results)

    def test_get_all_filter_by_status(self, db):
        """status フィルタが機能すること"""
        fb = Feedback.create(db, "bug", "ステータステスト", "内容詳細テスト1")
        Feedback.update_status(db, fb.id, "resolved")
        open_list     = Feedback.get_all(db, status="open")
        resolved_list = Feedback.get_all(db, status="resolved")
        assert all(f.status == "open"     for f in open_list)
        assert all(f.status == "resolved" for f in resolved_list)

    def test_update_status_and_admin_note(self, db):
        """ステータス変更と admin_note が保存されること"""
        fb = Feedback.create(db, "bug", "更新テスト", "詳細更新テスト内容1")
        ok = Feedback.update_status(db, fb.id, "in_progress", admin_note="調査中")
        assert ok is True
        fresh = Feedback.get_by_id(db, fb.id)
        assert fresh.status == "in_progress"
        assert fresh.admin_note == "調査中"

    def test_count_recent_blocks_duplicate(self, db):
        """5分以内の同件名を検出すること"""
        user = User.create(db, "fb_dup", "pass")
        Feedback.create(db, "bug", "同じ件名", "重複テスト詳細内容1", user_id=user.id)
        count = Feedback.count_recent_by_user(db, user.id, minutes=5, title="同じ件名")
        assert count == 1

    def test_count_today_by_user(self, db):
        """当日件数のカウントが正確なこと"""
        user = User.create(db, "fb_today", "pass")
        Feedback.create(db, "other", "今日の投稿1", "今日の詳細テスト内容1", user_id=user.id)
        Feedback.create(db, "other", "今日の投稿2", "今日の詳細テスト内容2", user_id=user.id)
        assert Feedback.count_today_by_user(db, user.id) == 2
```

### 追加テスト数と期待通過数

| 追加テスト | 件数 |
|---|---|
| `TestFeedbackModel` | 8件 |
| **期待通過数** | **169 + 8 = 177件** |

---

## 6. 実装ロードマップ

### 実装順序

```
Step 1: config.py
  └─ FEEDBACK_* 定数を末尾に追加

Step 2: models/user.py
  └─ is_admin カラムを追加

Step 3: models/feedback.py
  └─ Feedback クラスを新規作成（7 メソッド）

Step 4: models/__init__.py
  └─ Feedback を import リストに追加

Step 5: models/database.py
  └─ migrate_db() に is_admin ALTER + feedbacks CREATE TABLE を追記

Step 6: utils/auth.py
  └─ check_admin() を追加

Step 7: tests/test_feedback.py
  └─ TestFeedbackModel（8テスト）を作成
  └─ pytest でモデル層の全テスト通過を確認（177件目標）

Step 8: pages/5_feedback.py
  └─ プレイヤー向けフォームページを新規作成

Step 9: pages/99_admin_feedback.py
  └─ 管理者向け一覧ページを新規作成

Step 10: 動作確認
  └─ streamlit run app.py でフォーム入力〜DB保存〜管理画面確認
```

### 工数見積もり

| ステップ | 難易度 | 目安工数 |
|---|---|---|
| config.py 定数追加 | 低 | 10分 |
| user.py is_admin 追加 | 低 | 5分 |
| models/feedback.py 新規作成 | 中 | 30分 |
| models/__init__.py / database.py 変更 | 低 | 10分 |
| utils/auth.py check_admin() 追加 | 低 | 10分 |
| tests/test_feedback.py 作成 | 中 | 30分 |
| pages/5_feedback.py 新規作成 | 中 | 1時間 |
| pages/99_admin_feedback.py 新規作成 | 中 | 1時間 |
| 動作確認 | 低 | 30分 |
| **合計** | | **約3.5〜4時間** |

### 依存関係

- 他の要件（R-15 等）との依存関係なし。独立して実装可能。
- `models/user.py` への `is_admin` 追加は Step 2 で行い、`check_admin()` の実装（Step 6）より先に完了させること。
- `pages/` の作成（Step 8〜9）は Step 7（テスト通過）の後に行うこと。

---
## 7. 将来拡張（スコープ外）

- **匹名送信**: 将来「外部公開」「未ログイン投稿解禁」が必要になった時点で再導入する。  
  実装時は `feedbacks.user_id` の NULL 許容化、`FEEDBACK_SESSION_LIMIT` 定数追加、  
  `Feedback.count_session_anonymous()` メソッド、フォームへの匿名送信チェックボックスの追加を行う。  
  `test_create_feedback_anonymous` テストはその隟に有効化する。
- **メール通知**: 重要度「致命的」の投稿時に管理者へメール送信（smtplib / SendGrid）
- **添付画像**: スクリーンショットのアップロード（`st.file_uploader` + クラウドストレージ連携）
- **公開 FAQ**: 解決済み投稿を FAQ として公開する機能
- **評価ボタン**: 他ユーザーが「同じ問題が起きた」ボタンで投票し、優先度に反映

---
*本設計書は実装着手前に変更する場合があります。受け入れ基準の最終確定は実装前に行ってください。*
