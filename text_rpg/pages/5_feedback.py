"""
pages/5_feedback.py - 不具合報告・改善要望フォーム（プレイヤー向け）
"""
import streamlit as st
from models.database import SessionLocal
from models.feedback import Feedback
from utils.auth import check_login
from config import (
    FEEDBACK_CATEGORIES,
    FEEDBACK_SEVERITIES,
    FEEDBACK_PAGE_LABELS,
    FEEDBACK_MAX_BODY_LENGTH,
    FEEDBACK_DAILY_LIMIT,
    FEEDBACK_DUPLICATE_MINUTES,
)

st.set_page_config(page_title="フィードバック", page_icon="📬")
check_login()

st.title("📬 不具合報告・改善要望")
st.caption("ゲームに関するご意見・不具合をお知らせください。")

user_id: int = st.session_state["user_id"]

# ── カテゴリ選択 ──────────────────────────────────────────────────────────
cat_options = list(FEEDBACK_CATEGORIES.keys())
cat_labels  = [FEEDBACK_CATEGORIES[k]["label"] for k in cat_options]
cat_index   = st.selectbox("カテゴリ", range(len(cat_options)), format_func=lambda i: cat_labels[i])
category    = cat_options[cat_index]
has_severity = FEEDBACK_CATEGORIES[category]["has_severity"]

# ── 発生ページ ────────────────────────────────────────────────────────────
page_options = list(FEEDBACK_PAGE_LABELS.keys())
page_labels  = [FEEDBACK_PAGE_LABELS[k] for k in page_options]
page_index   = st.selectbox(
    "発生したページ", range(len(page_options)), format_func=lambda i: page_labels[i]
)
page_context = page_options[page_index]

# ── 深刻度（不具合のみ表示） ──────────────────────────────────────────────
severity = "normal"
if has_severity:
    sev_options = list(FEEDBACK_SEVERITIES.keys())
    sev_labels  = [FEEDBACK_SEVERITIES[k] for k in sev_options]
    sev_index   = sev_options.index("normal")
    sev_sel     = st.selectbox(
        "深刻度", range(len(sev_options)), index=sev_index,
        format_func=lambda i: sev_labels[i]
    )
    severity = sev_options[sev_sel]

# ── タイトル・本文 ────────────────────────────────────────────────────────
title = st.text_input(
    "タイトル（必須）",
    max_chars=128,
    placeholder="例：〇〇画面でエラーが発生する",
)
body = st.text_area(
    f"詳細（必須・{FEEDBACK_MAX_BODY_LENGTH}字以内）",
    max_chars=FEEDBACK_MAX_BODY_LENGTH,
    height=200,
    placeholder="再現手順や状況を具体的に教えてください。",
)
body_len = len(body)
st.caption(f"{body_len} / {FEEDBACK_MAX_BODY_LENGTH} 文字")

# ── 送信ボタン ────────────────────────────────────────────────────────────
if st.button("📨 送信する", type="primary"):
    # ── バリデーション ────────────────────────────────────────────────────
    errors: list[str] = []
    if not title.strip():
        errors.append("タイトルを入力してください。")
    if not body.strip():
        errors.append("詳細を入力してください。")
    if body_len > FEEDBACK_MAX_BODY_LENGTH:
        errors.append(f"詳細は {FEEDBACK_MAX_BODY_LENGTH} 文字以内にしてください。")

    if errors:
        for msg in errors:
            st.error(msg)
    else:
        with SessionLocal() as db:
            # 重複チェック（同一タイトル・FEEDBACK_DUPLICATE_MINUTES 分以内）
            dup_count = Feedback.count_recent_by_user(
                db, user_id, minutes=FEEDBACK_DUPLICATE_MINUTES, title=title
            )
            if dup_count > 0:
                st.warning(
                    f"⚠️ 直近 {FEEDBACK_DUPLICATE_MINUTES} 分以内に同じタイトルのフィードバックを送信済みです。"
                    "重複送信はご遠慮ください。"
                )
            else:
                # 1日の上限チェック
                today_count = Feedback.count_today_by_user(db, user_id)
                if today_count >= FEEDBACK_DAILY_LIMIT:
                    st.warning(
                        f"⚠️ 本日の送信上限（{FEEDBACK_DAILY_LIMIT} 件）に達しました。"
                        "明日以降にご送信ください。"
                    )
                else:
                    try:
                        Feedback.create(
                            db,
                            category=category,
                            title=title,
                            body=body,
                            user_id=user_id,
                            page_context=page_context,
                            severity=severity,
                        )
                        st.success("✅ フィードバックを送信しました。ありがとうございます！")
                        st.info(f"本日の送信数: {today_count + 1} / {FEEDBACK_DAILY_LIMIT}")
                    except ValueError as e:
                        st.error(str(e))

# ── 過去の自分の投稿を表示 ────────────────────────────────────────────────
st.divider()
st.subheader("📋 自分の送信履歴")

with SessionLocal() as db:
    my_feedbacks = Feedback.get_all(db, limit=20, offset=0)
    # user_id でフィルタ
    my_feedbacks = [f for f in my_feedbacks if f.user_id == user_id]

if not my_feedbacks:
    st.info("まだフィードバックを送信していません。")
else:
    for fb in my_feedbacks:
        cat_label  = FEEDBACK_CATEGORIES.get(fb.category, {}).get("label", fb.category)
        status_label = {
            "open":        "🔴 未対応",
            "in_progress": "🟡 対応中",
            "resolved":    "🟢 解決済",
            "closed":      "⚫ クローズ",
        }.get(fb.status, fb.status)
        with st.expander(f"{cat_label} | {fb.title}  [{status_label}]"):
            st.write(fb.body)
            if fb.admin_note:
                st.info(f"📝 管理者より: {fb.admin_note}")
            st.caption(f"送信日時: {fb.created_at.strftime('%Y-%m-%d %H:%M')} UTC")
