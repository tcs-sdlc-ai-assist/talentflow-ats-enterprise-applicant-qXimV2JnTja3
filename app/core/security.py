from passlib.context import CryptContext
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

from app.core.config import settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

serializer = URLSafeTimedSerializer(settings.SECRET_KEY)

_SESSION_SALT = "talentflow-session"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_session_cookie(user_id: int, username: str, role: str) -> str:
    data = {
        "user_id": user_id,
        "username": username,
        "role": role,
    }
    return serializer.dumps(data, salt=_SESSION_SALT)


def decode_session_cookie(cookie_value: str, max_age: int | None = None) -> dict | None:
    if max_age is None:
        max_age = settings.SESSION_MAX_AGE
    try:
        data = serializer.loads(cookie_value, salt=_SESSION_SALT, max_age=max_age)
        if not isinstance(data, dict):
            return None
        if "user_id" not in data or "username" not in data or "role" not in data:
            return None
        return data
    except (SignatureExpired, BadSignature, Exception):
        return None