"""Who is calling. ``accounts.auth`` and MCP pass the bearer token to ``resolve_user``.

Clients send ``Authorization: Bearer <Firebase ID token>``. In Firebase mode
the Admin SDK verifies the signature, expiration, issuer and project before
``get_or_create_by_firebase_uid`` is called. Never read a uid from the request
body, path or query.

``AUTH_MODE=dev`` explicitly accepts any bearer token and maps to one fixed
development user. Use ``AUTH_MODE=firebase`` for real account separation.
"""

import json
import logging
from threading import Lock

import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials
from firebase_admin.exceptions import FirebaseError
from google.auth.exceptions import DefaultCredentialsError, GoogleAuthError

from accounts import user_repository
from accounts.models import User
from config.app_settings import get_settings
from config.exceptions import HTTPException

logger = logging.getLogger(__name__)
_firebase_app_lock = Lock()
_firebase_app_name = "artlog-auth"


def _get_firebase_app() -> firebase_admin.App:
    """Initialize once, including when concurrent first requests arrive."""

    settings = get_settings()
    with _firebase_app_lock:
        try:
            app = firebase_admin.get_app(_firebase_app_name)
        except ValueError:
            credential = None
            if settings.firebase_service_account_json is not None:
                credential = credentials.Certificate(
                    json.loads(
                        settings.firebase_service_account_json.get_secret_value()
                    )
                )
            elif settings.google_application_credentials:
                credential = credentials.Certificate(
                    settings.google_application_credentials
                )
            app = firebase_admin.initialize_app(
                credential,
                options={"projectId": settings.firebase_project_id},
                name=_firebase_app_name,
            )
        if app.project_id != settings.firebase_project_id:
            raise ValueError("Firebase project configuration mismatch")
        return app


def _unauthorized() -> HTTPException:
    return HTTPException(401, "로그인이 필요합니다.", {"WWW-Authenticate": "Bearer"})


def resolve_user(token: str) -> User:
    settings = get_settings()
    if settings.auth_mode == "dev":
        return user_repository.get_or_create_by_firebase_uid(
            firebase_uid=settings.dev_user_uid,
            email=f"{settings.dev_user_uid}@artlog.local",
            nickname="개발용 사용자",
        )
    if settings.auth_mode != "firebase":
        raise _unauthorized()
    try:
        claims = firebase_auth.verify_id_token(token, app=_get_firebase_app())
    except DefaultCredentialsError:
        # Server misconfiguration, not a bad token: every login fails until fixed.
        logger.error("Firebase credentials are not configured")
        raise _unauthorized() from None
    except (FirebaseError, GoogleAuthError, ValueError):
        # Do not log the bearer token or include SDK/credential errors in HTTP.
        raise _unauthorized() from None

    uid, email = claims.get("uid"), claims.get("email")
    if (
        not isinstance(uid, str)
        or not uid.strip()
        or len(uid) > 128
        or not isinstance(email, str)
        or not email.strip()
        or len(email) > 255
    ):
        raise _unauthorized()
    name = claims.get("name")
    nickname = (
        name.strip()
        if isinstance(name, str) and name.strip()
        else email.split("@", 1)[0]
    )
    return user_repository.get_or_create_by_firebase_uid(
        firebase_uid=uid, email=email, nickname=nickname[:50]
    )
