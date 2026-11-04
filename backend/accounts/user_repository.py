"""Reads and writes for users."""

from django.db import IntegrityError

from accounts.models import User


def get_or_create_by_firebase_uid(
    *, firebase_uid: str, email: str, nickname: str
) -> User:
    """Return the user for ``firebase_uid``, creating it on first sight.

    Two first requests can race; the UNIQUE key makes the loser re-read.
    """

    users = User.objects.filter(firebase_uid=firebase_uid)
    user = users.first()
    if user is not None:
        return user
    try:
        return User.objects.create(
            firebase_uid=firebase_uid, email=email, nickname=nickname
        )
    except IntegrityError:
        return users.first()
