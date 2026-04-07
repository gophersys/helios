import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from config import env_config

ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24


def create_token(
    user_id: str,
    email: str,
    name: str,
    permission_set_id: str | None,
    role: str = "DEVELOPER",
) -> str:
    """Create a signed JWT token with user claims."""
    payload = {
        "sub": user_id,
        "email": email,
        "name": name,
        "role": role,
        "permissionSetId": permission_set_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, env_config.JWT_SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> Tuple[Optional[dict], Optional[str]]:
    """Verify and decode a JWT token, returning (payload, error)."""
    try:
        payload = jwt.decode(token, env_config.JWT_SECRET_KEY, algorithms=[ALGORITHM])
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, "Token expired"
    except jwt.InvalidTokenError as e:
        return None, f"Invalid token: {e}"
