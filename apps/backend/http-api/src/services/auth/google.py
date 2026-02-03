from typing import Optional, Tuple

from google.oauth2 import id_token
from google.auth.transport import requests

from config import env_config


def verify_google_token(credential: str) -> Tuple[Optional[dict], Optional[str]]:
    try:
        idinfo = id_token.verify_oauth2_token(
            credential,
            requests.Request(),
            env_config.GOOGLE_CLIENT_ID,
        )
        return {
            "sub": idinfo["sub"],
            "email": idinfo["email"],
            "name": idinfo.get("name", ""),
            "picture": idinfo.get("picture", ""),
        }, None
    except ValueError as e:
        return None, f"Invalid Google token: {e}"
