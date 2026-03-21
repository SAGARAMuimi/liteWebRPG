"""
pages/6_privacy.py - プライバシー/取扱い（個人運用向け）

フィードバックフォームでメールアドレス等を任意で受領する前提の、最低限の説明ページ。
"""

import streamlit as st

from config import (
    APP_TITLE,
    OPERATOR_NAME,
    OPERATOR_CONTACT,
    OPERATOR_CONTACT_DISCORD,
    OPERATOR_CONTACT_EMAIL,
    OPERATOR_CONTACT_X,
    FEEDBACK_RETENTION_DAYS,
)


st.set_page_config(page_title="プライバシー / 取扱い", page_icon="🔒")

st.title("🔒 プライバシー / 取扱い")
st.caption(f"{APP_TITLE}（個人運用）")

st.markdown(
    """
このページは、本サービス（個人運用）における、フィードバック送信時の情報の取扱いを説明するものです。
"""
)

st.subheader("1. 取得する可能性のある情報")
st.markdown(
    """
- フィードバック本文・タイトル、カテゴリ、発生ページ等
- （任意入力）メールアドレス
- 利用環境により、アクセスログ（IPアドレス、ブラウザ情報、アクセス日時等）がサーバ/ホスティング側で記録される場合があります
"""
)

st.subheader("2. 利用目的")
st.markdown(
    """
取得した情報は、主に以下の目的で利用します。

- 不具合の再現、原因調査、修正
- 改善要望の検討、機能改善
- 必要と判断した場合の連絡（任意入力のメールアドレスがある場合）
- 不正利用・スパム等の抑止、運営上の安全確保
"""
)

st.subheader("3. 個人情報等の入力に関するお願い")
st.markdown(
    """
- 本文には、氏名・住所・電話番号・パスワード等の個人情報、第三者の個人情報、機密情報を記載しないでください。
- 本文にSNSアカウント等の連絡先を記載されても、個別連絡の希望に必ずしもお応えできません。
- 送信内容に不適切な情報（個人情報を含む）が含まれると判断した場合、運営者の裁量で削除・非表示等の対応を行うことがあります。
"""
)

st.subheader("4. 第三者提供")
st.markdown(
    """
法令に基づく場合等を除き、取得した情報を第三者へ提供しません。
"""
)

st.subheader("5. 保存期間")
st.markdown(
    f"""
フィードバックや問い合わせに関する情報は、原則として **{FEEDBACK_RETENTION_DAYS} 日** を目安に保管し、
不要となった場合は削除するよう努めます。

※法令対応・不正対策等の必要がある場合、合理的な範囲で保存期間が延長されることがあります。
"""
)

st.subheader("6. 問い合わせ・削除等の依頼")
email = OPERATOR_CONTACT_EMAIL.strip()
x_id = OPERATOR_CONTACT_X.strip()
discord = OPERATOR_CONTACT_DISCORD.strip()
legacy = OPERATOR_CONTACT.strip()

contact_lines: list[str] = []
if email:
    contact_lines.append(f"- メール: {email}")
if x_id:
    x_norm = x_id[1:] if x_id.startswith("@") else x_id
    contact_lines.append(f"- X: @{x_norm}（https://x.com/{x_norm}）")
if discord:
    contact_lines.append(f"- Discord: {discord}")
if legacy:
    contact_lines.append(f"- その他: {legacy}")

if contact_lines:
    st.markdown(
        "運営者への連絡先:\n\n" + "\n".join(contact_lines)
        + "\n\n削除等の依頼を行う場合、本人確認のため追加情報の提示をお願いすることがあります。"
    )
else:
    st.markdown(
        """
削除等の依頼や問い合わせは、フィードバックフォームからご連絡ください。
（返信が必要な場合は、フォームのメールアドレス欄に入力してください。）

※本人確認ができない場合、対応できないことがあります。
"""
    )

st.subheader("7. 改定")
st.markdown(
    """
本内容は、必要に応じて予告なく改定されることがあります。
"""
)

st.divider()
st.caption(f"運営者: {OPERATOR_NAME}")
