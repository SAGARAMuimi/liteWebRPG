"""
pages/99_admin_feedback.py - フィードバック管理画面（管理者専用）
"""
import streamlit as st
from models.database import SessionLocal
from models.feedback import Feedback
from utils.auth import check_admin
from config import (
    FEEDBACK_CATEGORIES,
    FEEDBACK_SEVERITIES,
    FEEDBACK_STATUSES,
    FEEDBACK_PAGE_LABELS,
)

st.set_page_config(page_title="フィードバック管理 [Admin]", page_icon="🛠️")
check_admin()

st.title("🛠️ フィードバック管理")

# ── サマリー指標 ─────────────────────────────────────────────────────────
with SessionLocal() as db:
    cnt_open     = Feedback.count_all(db, status="open")
    cnt_progress = Feedback.count_all(db, status="in_progress")
    cnt_resolved = Feedback.count_all(db, status="resolved")
    cnt_total    = Feedback.count_all(db)

col1, col2, col3, col4 = st.columns(4)
col1.metric("🔴 未対応",  cnt_open)
col2.metric("🟡 対応中",  cnt_progress)
col3.metric("🟢 解決済",  cnt_resolved)
col4.metric("📊 合計",    cnt_total)

st.divider()

# ── フィルタ ──────────────────────────────────────────────────────────────
st.subheader("🔎 フィルタ")
filter_col1, filter_col2 = st.columns(2)

with filter_col1:
    cat_opts = ["（すべて）"] + list(FEEDBACK_CATEGORIES.keys())
    cat_sel  = st.selectbox(
        "カテゴリ",
        range(len(cat_opts)),
        format_func=lambda i: cat_opts[i] if i == 0
            else FEEDBACK_CATEGORIES[cat_opts[i]]["label"],
    )
    filter_cat = None if cat_sel == 0 else cat_opts[cat_sel]

with filter_col2:
    st_opts = ["（すべて）"] + list(FEEDBACK_STATUSES.keys())
    st_sel  = st.selectbox(
        "ステータス",
        range(len(st_opts)),
        format_func=lambda i: st_opts[i] if i == 0 else FEEDBACK_STATUSES[st_opts[i]],
    )
    filter_status = None if st_sel == 0 else st_opts[st_sel]

PAGE_SIZE   = 20
page_number = st.number_input("ページ番号", min_value=1, value=1, step=1)
offset      = (page_number - 1) * PAGE_SIZE

# ── フィードバック一覧 ────────────────────────────────────────────────────
st.subheader("📋 一覧")

with SessionLocal() as db:
    feedbacks = Feedback.get_all(
        db,
        category=filter_cat,
        status=filter_status,
        limit=PAGE_SIZE,
        offset=offset,
    )

if not feedbacks:
    st.info("該当するフィードバックがありません。")
else:
    for fb in feedbacks:
        cat_label    = FEEDBACK_CATEGORIES.get(fb.category, {}).get("label", fb.category)
        status_label = FEEDBACK_STATUSES.get(fb.status, fb.status)
        sev_label    = FEEDBACK_SEVERITIES.get(fb.severity, fb.severity)
        page_label   = FEEDBACK_PAGE_LABELS.get(fb.page_context, fb.page_context)
        is_anon = bool(getattr(fb, "is_anonymous", 0)) or (fb.user_id is None)
        user_text = "匿名" if is_anon else (f"UID:{fb.user_id}" if fb.user_id else "—")

        with st.expander(
            f"#{fb.id} | {cat_label} | {fb.title}  [{status_label}]",
            expanded=False,
        ):
            info_col1, info_col2, info_col3 = st.columns(3)
            info_col1.caption(f"👤 投稿者: {user_text}")
            info_col2.caption(f"📍 ページ: {page_label}")
            info_col3.caption(f"⚠️ 深刻度: {sev_label}")

            if bool(getattr(fb, "needs_reply", 0)):
                st.caption("✉️ 返信希望: はい")

            if is_anon:
                st.caption("🕶️ 匿名送信: はい（ユーザーID未保存）")

            if getattr(fb, "contact_email", None):
                st.caption(f"📧 連絡先メール: {fb.contact_email}")

            st.write(fb.body)
            st.caption(
                f"作成: {fb.created_at.strftime('%Y-%m-%d %H:%M')} UTC  "
                f"/ 更新: {fb.updated_at.strftime('%Y-%m-%d %H:%M')} UTC"
            )

            # ── ステータス変更フォーム ─────────────────────────────────────
            st.markdown("---")
            with st.form(key=f"update_form_{fb.id}"):
                form_col1, form_col2 = st.columns([2, 3])

                with form_col1:
                    new_st_opts    = list(FEEDBACK_STATUSES.keys())
                    new_st_labels  = [FEEDBACK_STATUSES[k] for k in new_st_opts]
                    current_index  = new_st_opts.index(fb.status) if fb.status in new_st_opts else 0
                    new_st_sel     = st.selectbox(
                        "ステータス変更",
                        range(len(new_st_opts)),
                        index=current_index,
                        format_func=lambda i: new_st_labels[i],
                        key=f"status_sel_{fb.id}",
                    )
                    new_status = new_st_opts[new_st_sel]

                with form_col2:
                    new_note = st.text_area(
                        "管理者メモ（任意）",
                        value=fb.admin_note or "",
                        height=80,
                        key=f"note_{fb.id}",
                    )

                submitted = st.form_submit_button("💾 更新")
                if submitted:
                    with SessionLocal() as db2:
                        ok = Feedback.update_status(db2, fb.id, new_status, new_note)
                    if ok:
                        st.success("✅ 更新しました。")
                        st.rerun()
                    else:
                        st.error("更新に失敗しました。")
