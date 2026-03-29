"""
create_admin.py - 管理者ユーザー作成スクリプト

使い方:
    cd text_rpg
    python create_admin.py <ユーザー名> <パスワード>

例:
    python create_admin.py admin mypassword123

Streamlit Cloud（Neon PostgreSQL）で実行する場合:
    - このスクリプトをローカルで実行し、DATABASE_URL に Neon の接続文字列を指定する
    - 例: DATABASE_URL="postgresql://..." python create_admin.py admin mypassword123
"""

import sys
import os

# text_rpg/ 直下から実行する前提
sys.path.insert(0, os.path.dirname(__file__))

# .env を読み込む
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(dotenv_path=Path(__file__).with_name(".env"))
load_dotenv()


def main() -> None:
    if len(sys.argv) != 3:
        print("使い方: python create_admin.py <ユーザー名> <パスワード>")
        sys.exit(1)

    username = sys.argv[1].strip()
    password = sys.argv[2]

    if not username or not password:
        print("エラー: ユーザー名とパスワードは空にできません。")
        sys.exit(1)

    # DB 初期化
    import models  # noqa: F401
    from models.database import init_db, migrate_db, SessionLocal
    from models.user import User
    from utils.helpers import seed_initial_data, give_starter_items
    from sqlalchemy.exc import IntegrityError

    print(f"データベースに接続中...")
    init_db()
    migrate_db()

    with SessionLocal() as db:
        seed_initial_data(db)

        existing = User.find_by_name(db, username)
        if existing:
            # 既存ユーザーを管理者に昇格
            existing.is_admin = 1
            db.commit()
            print(f"✅ ユーザー '{username}' を管理者に設定しました（is_admin=1）。")
        else:
            # 新規作成して管理者に設定
            try:
                user = User.create(db, username, password)
                user.is_admin = 1
                db.commit()
                give_starter_items(db, user.id)
                print(f"✅ 管理者ユーザー '{username}' を作成しました（id={user.id}）。")
            except IntegrityError:
                db.rollback()
                print(f"エラー: ユーザー名 '{username}' は既に使われています。")
                sys.exit(1)


if __name__ == "__main__":
    main()
