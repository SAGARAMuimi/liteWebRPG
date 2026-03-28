"""utils/auth.py - 認証・セッション管理ヘルパー"""

from __future__ import annotations

import json
import secrets
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

import streamlit as st
from sqlalchemy.orm import Session


def _neon_auth_secrets_present() -> bool:
    """Neon Auth を使うための Secrets が設定されているかの軽い判定。

    Neon Auth の具体的なキーは運用で変わり得るため、代表的なキーのいずれかが
    入っていれば「設定あり」とみなす。
    """
    # Streamlit Cloud では secrets.toml 相当が st.secrets から提供されるため、
    # config 側の優先順位（env → secrets）で読む。
    from config import _get_setting

    truthy = {"1", "true", "yes", "on"}
    enabled = (_get_setting("NEON_AUTH_ENABLED", "") or "").strip().lower()
    if enabled in truthy:
        return True

    for key in [
        "NEON_AUTH_BASE_URL",
        "NEON_AUTH_JWKS_URL",  # JWT plugin 有効時は JWKS エンドポイントも実在する
        "NEON_AUTH_API_KEY",
    ]:
        val = _get_setting(key)
        if val is not None and str(val).strip() != "":
            return True
    return False


def _select_auth_backend() -> str:
    """認証バックエンドを選択する（local / neon）。"""
    from config import AUTH_MODE

    if AUTH_MODE in {"local"}:
        return "local"
    if AUTH_MODE in {"neon", "neon_auth"}:
        return "neon"

    # auto
    try:
        from models.database import engine

        if engine.dialect.name == "postgresql" and _neon_auth_secrets_present():
            return "neon"
    except Exception:
        # DB 初期化前などは安全側（local）へ
        pass

    return "local"


def get_auth_backend() -> str:
    """外部（UI）向けに現在のバックエンド名を返す。"""
    return _select_auth_backend()


def _neon_base_url() -> str:
    from config import _get_setting

    base = (_get_setting("NEON_AUTH_BASE_URL", "") or "").strip()
    return base.rstrip("/")


def _neon_admin_bearer_token() -> str | None:
    """必要なら管理系 Bearer トークンを付与する。

    Better Auth の参照UIでは全エンドポイントに bearerAuth が表示されることがあり、
    その場合はここで指定したトークンを Authorization ヘッダに付与する。
    """
    from config import _get_setting

    token = (_get_setting("NEON_AUTH_API_KEY") or "").strip()
    return token or None


def _http_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    timeout_sec: int = 20,
) -> tuple[int, dict[str, Any] | list[Any] | str | None]:
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)

    data: bytes | None = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")

    req = Request(url, data=data, headers=req_headers, method=method.upper())
    try:
        with urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            if not raw:
                return resp.status, None
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        if raw:
            try:
                return int(e.code), json.loads(raw)
            except json.JSONDecodeError:
                return int(e.code), raw
        return int(e.code), None
    except URLError as e:
        return 0, str(e)


def _neon_get_or_create_local_user(db: Session, neon_user: dict[str, Any]) -> tuple[int, str]:
    """Neon Auth の user をゲームDBの users に紐付ける。

    このプロジェクトのゲームデータは users.id(int) を参照するため、Neon Auth の user.id
    からローカル users を作成/取得して user_id を返す。
    """
    from models.user import User
    from utils.helpers import give_starter_items

    neon_user_id = str(neon_user.get("id") or "").strip()
    display_name = str(neon_user.get("name") or neon_user.get("email") or "").strip()
    if not neon_user_id:
        raise ValueError("Neon Auth user.id が取得できません")

    local_name = f"neon:{neon_user_id}"[:64]
    user = User.find_by_name(db, local_name)
    if user:
        return user.id, display_name or local_name

    random_password = secrets.token_urlsafe(32)
    user = User.create(db, local_name, random_password)
    give_starter_items(db, user.id)
    return user.id, display_name or local_name


def neon_get_session(session_token: str) -> dict[str, Any] | None:
    """Better Auth の `GET /get-session` でセッション情報を取得する。

    `session_token` は `/sign-in/email` 等で返る token を想定。
    """
    base = _neon_base_url()
    if not base or not session_token:
        return None

    url = urljoin(base + "/", "get-session")
    status, data = _http_json("GET", url, headers={"Authorization": f"Bearer {session_token}"}, body=None)
    if status != 200 or not isinstance(data, dict):
        return None
    return data


_NEON_SESSION_REVALIDATE_INTERVAL = 300  # 5分ごとに再検証（秒）


def _neon_jwks_url() -> str:
    """NEON_AUTH_JWKS_URL を返す。未設定なら BASE_URL から自動生成する。"""
    from config import _get_setting
    url = (_get_setting("NEON_AUTH_JWKS_URL") or "").strip()
    if url:
        return url
    base = _neon_base_url()
    if base:
        return base.rstrip("/") + "/.well-known/jwks.json"
    return ""


def _neon_verify_jwt_local(token: str) -> dict[str, Any] | None:
    """PyJWT + JWKS で JWT をローカル検証する。

    成功時は payload dict、失敗時は None を返す。
    PyJWT[crypto] が未インストールの場合は None を返す（フォールバック流に任せる）。
    """
    jwks_url = _neon_jwks_url()
    if not jwks_url or not token:
        return None
    try:
        import jwt as pyjwt
        from jwt import PyJWKClient
        jwks_client = PyJWKClient(jwks_url, cache_keys=True)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = pyjwt.decode(
            token,
            signing_key.key,
            algorithms=["EdDSA", "RS256", "ES256"],
            options={"verify_aud": False},  # Better Auth は aud を含まない場合あり
        )
        return payload
    except Exception:
        return None


def _neon_validate_session_if_needed() -> bool:
    """Neon Auth バックエンド時、トークンを再検証する。

    優先順位:
      1. JWKS が利用可能ならローカル JWT 検証（HTTPコール不要、高速）
      2. JWKS がなければ GET /get-session でチェック（フォールバック）
    - neon 以外のバックエンドでは常に True
    - _NEON_SESSION_REVALIDATE_INTERVAL 秒未満ならスキップ
    - 失効の場合はセッションを全クリアして False
    """
    if st.session_state.get("auth_backend") != "neon":
        return True

    token = st.session_state.get("neon_token")
    if not token:
        return False

    last_validated: float = st.session_state.get("neon_token_validated_at", 0.0)
    if time.time() - last_validated < _NEON_SESSION_REVALIDATE_INTERVAL:
        return True  # 検証済み期間内

    # ① JWKS ローカル検証
    payload = _neon_verify_jwt_local(token)
    if payload is not None:
        st.session_state["neon_token_validated_at"] = time.time()
        return True

    # ② JWKS 検証失敗 or 未設定 → GET /get-session でフォールバック
    session_data = neon_get_session(token)
    if session_data:
        st.session_state["neon_token_validated_at"] = time.time()
        return True

    # トークン失効 → 強制ログアウト
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    return False


def init_session_defaults() -> None:
    """セッション状態のデフォルト値を初期化する"""
    defaults: dict = {
        "user_id": None,
        "username": None,
        "party": [],
        # NOTE: "current_dungeon_id" はここで設定しない。
        #       2_dungeon.py の render_dungeon_select() でダンジョン選択後に設定される。
        "current_floor": 1,
        "current_room": 0,
        "battle_enemies": [],
        "battle_log": [],
        "defending_chars": set(),
        "battle_result": None,
        "difficulty": "normal",
        "battle_buffs": {},
        "battle_hate": {},
        "battle_inventory": [],
        "show_item_panel": False,
        "my_feedback_ids": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def check_login() -> None:
    """未ログインの場合はトップページに戻してページを停止する"""
    init_session_defaults()
    if not st.session_state.get("user_id"):
        st.warning("ログインが必要です。")
        st.page_link("app.py", label="ログイン画面へ")
        st.stop()
    if not _neon_validate_session_if_needed():
        st.warning("セッションが期限切れです。再ログインしてください。")
        st.page_link("app.py", label="ログイン画面へ")
        st.stop()


def check_admin() -> None:
    """管理者以外をブロックしてページを停止する"""
    check_login()
    user_id = st.session_state.get("user_id")
    from models.database import SessionLocal
    from models.user import User
    with SessionLocal() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not getattr(user, "is_admin", 0):
            st.error("🚫 このページは管理者専用です。")
            st.stop()


def get_current_user_id() -> int:
    return st.session_state["user_id"]


def login_user(db: Session, username: str, password: str) -> bool:
    """ログイン処理。成功時に session_state を設定して True を返す

    - local: username/password を users+bcrypt で検証
    - neon : username を email として Neon Auth の /sign-in/email を呼ぶ
    """
    backend = _select_auth_backend()
    if backend == "neon":
        base = _neon_base_url()
        if not base:
            st.error("NEON_AUTH_BASE_URL が未設定です（Streamlit Secrets / .env を確認してください）。")
            return False

        email = (username or "").strip()
        if not email:
            return False

        url = urljoin(base + "/", "sign-in/email")
        body: dict[str, Any] = {"email": email, "password": password}

        headers: dict[str, str] = {}
        admin_token = _neon_admin_bearer_token()
        if admin_token:
            headers["Authorization"] = f"Bearer {admin_token}"

        status, data = _http_json("POST", url, headers=headers, body=body)
        if status != 200 or not isinstance(data, dict):
            return False

        token = data.get("token")
        neon_user = data.get("user")
        if not token or not isinstance(neon_user, dict):
            return False

        try:
            local_user_id, display_name = _neon_get_or_create_local_user(db, neon_user)
        except Exception as e:
            st.error(f"Neon Auth ユーザーのローカル紐付けに失敗しました: {e}")
            return False

        st.session_state["user_id"] = local_user_id
        st.session_state["username"] = display_name
        st.session_state["auth_backend"] = "neon"
        st.session_state["neon_token"] = str(token)
        st.session_state["neon_user"] = neon_user
        return True

    from models.user import User

    user = User.find_by_name(db, username)
    if user and user.verify_password(password):
        st.session_state["user_id"] = user.id
        st.session_state["username"] = user.name
        return True
    return False


def register_user(db: Session, username: str, password: str, *, email: str | None = None) -> tuple[bool, str]:
    """新規登録処理。(成功フラグ, メッセージ) を返す

    - local: username/password を users+bcrypt で作成
    - neon : username を表示名、email をメールとして Neon Auth の /sign-up/email を呼ぶ
    """
    backend = _select_auth_backend()
    if backend == "neon":
        base = _neon_base_url()
        if not base:
            return False, "NEON_AUTH_BASE_URL が未設定です（Streamlit Secrets / .env を確認してください）。"

        display_name = (username or "").strip()
        email_addr = (email or "").strip()
        if not display_name or not email_addr or not password:
            return False, "表示名・メールアドレス・パスワードを入力してください。"

        url = urljoin(base + "/", "sign-up/email")
        body: dict[str, Any] = {"name": display_name, "email": email_addr, "password": password}

        headers: dict[str, str] = {}
        admin_token = _neon_admin_bearer_token()
        if admin_token:
            headers["Authorization"] = f"Bearer {admin_token}"

        status, data = _http_json("POST", url, headers=headers, body=body)
        if status != 200 or not isinstance(data, dict):
            if status == 422:
                return False, "そのメールアドレスは既に登録済みです。"
            return False, "登録に失敗しました。"

        neon_user = data.get("user")
        if isinstance(neon_user, dict):
            try:
                local_user_id, mapped_name = _neon_get_or_create_local_user(db, neon_user)
            except Exception:
                local_user_id, mapped_name = 0, display_name
        else:
            local_user_id, mapped_name = 0, display_name

        token = data.get("token")
        if token:
            # サーバ設定により、サインアップと同時にセッションが発行される場合
            if local_user_id:
                st.session_state["user_id"] = local_user_id
                st.session_state["username"] = mapped_name
                st.session_state["auth_backend"] = "neon"
                st.session_state["neon_token"] = str(token)
                if isinstance(neon_user, dict):
                    st.session_state["neon_user"] = neon_user
            return True, "登録しました！"

        # token が null の場合（メール検証が必要など）
        return True, "登録しました。必要に応じてメール確認後、ログインしてください。"

    from models.user import User
    from utils.helpers import give_starter_items
    from sqlalchemy.exc import IntegrityError
    try:
        user = User.create(db, username, password)
        st.session_state["user_id"] = user.id
        st.session_state["username"] = user.name
        give_starter_items(db, user.id)
        return True, "登録しました！"
    except IntegrityError:
        db.rollback()
        return False, "そのユーザー名はすでに使われています。"


def logout_user() -> None:
    """セッションをクリアしてログアウト"""
    backend = st.session_state.get("auth_backend")
    if backend == "neon":
        base = _neon_base_url()
        token = st.session_state.get("neon_token")
        if base and token:
            url = urljoin(base + "/", "sign-out")
            _http_json("POST", url, headers={"Authorization": f"Bearer {token}"}, body={})

    for key in list(st.session_state.keys()):
        del st.session_state[key]
