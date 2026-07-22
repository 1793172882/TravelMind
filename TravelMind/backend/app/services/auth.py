"""Local account authentication using only Python cryptographic primitives."""

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.infrastructure.models.user import User

PBKDF2_ITERATIONS = 310_000


class AuthenticationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class UserIdentity:
    id: int | None
    username: str

    @property
    def user_id(self) -> str:
        return f"web:{self.id}" if self.id is not None else "anonymous"

    def thread_id(self, value: str) -> str:
        return f"{self.user_id}:{value}"


ANONYMOUS_USER = UserIdentity(id=None, username="anonymous")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), int(iterations)
        )
        return hmac.compare_digest(actual.hex(), expected)
    except (TypeError, ValueError):
        return False


def _secret() -> bytes:
    if settings.auth_secret is None:
        raise RuntimeError("请先配置 AUTH_SECRET 后再使用账号登录")
    return settings.auth_secret.get_secret_value().encode()


def issue_token(user: User) -> str:
    payload = json.dumps(
        {
            "sub": user.id,
            "username": user.username,
            "exp": int((datetime.now(UTC) + timedelta(hours=settings.auth_token_hours)).timestamp()),
        },
        separators=(",", ":"),
    ).encode()
    encoded = base64.urlsafe_b64encode(payload).rstrip(b"=")
    signature = hmac.new(_secret(), encoded, hashlib.sha256).digest()
    return f"{encoded.decode()}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def parse_token(token: str) -> UserIdentity:
    try:
        encoded, supplied = token.split(".", 1)
        expected = hmac.new(_secret(), encoded.encode(), hashlib.sha256).digest()
        signature = base64.urlsafe_b64decode(supplied + "=" * (-len(supplied) % 4))
        if not hmac.compare_digest(signature, expected):
            raise AuthenticationError("登录令牌无效")
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        )
        if int(payload["exp"]) <= int(datetime.now(UTC).timestamp()):
            raise AuthenticationError("登录已过期")
        return UserIdentity(id=int(payload["sub"]), username=str(payload["username"]))
    except AuthenticationError:
        raise
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise AuthenticationError("登录令牌无效") from error


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def register(self, username: str, password: str) -> tuple[User, str]:
        user = User(username=username, password_hash=hash_password(password))
        self.session.add(user)
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise AuthenticationError("用户名已经存在") from error
        self.session.refresh(user)
        return user, issue_token(user)

    def login(self, username: str, password: str) -> tuple[User, str]:
        user = self.session.scalar(select(User).where(User.username == username))
        if user is None or not verify_password(password, user.password_hash):
            raise AuthenticationError("用户名或密码错误")
        return user, issue_token(user)
