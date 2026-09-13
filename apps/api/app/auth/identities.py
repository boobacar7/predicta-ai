from dataclasses import dataclass

from app.db.models import AuthSession, User


@dataclass(frozen=True, slots=True)
class AuthenticatedIdentity:
    user: User
    session: AuthSession
