"""
repositories/user_repository.py
---------------------------------
Data access layer for User objects.

Relationship:
  - UserRepository aggregates User objects.
  - Used by the authentication service to look up users by username or ID.

Design note (Stage 5):
  The Singleton pattern will be applied here alongside SampleRepository
  to ensure a single shared user store at runtime.
"""

from models.user import User
from typing import Optional


class UserRepository:
    """
    Provides CRUD operations and lookup for User records.

    Uses an in-memory store for Stage 3. Will be backed by SQLAlchemy in Stage 7.

    Attributes
    ----------
    _by_id       : dict[int, User]  — primary lookup by user_id
    _by_username : dict[str, User]  — secondary index by username
    """

    def __init__(self):
        self._by_id: dict[int, User] = {}
        self._by_username: dict[str, User] = {}
        self._counter: int = 0

    # ── Create ─────────────────────────────────────────────────────────────
    def add(self, user: User) -> None:
        """
        Persist a new user record.

        Raises
        ------
        ValueError — if the username is already taken
        """
        uname = user.get_username()
        if uname in self._by_username:
            raise ValueError(f"Username {uname!r} is already registered.")
        uid = user.get_user_id()
        self._by_id[uid] = user
        self._by_username[uname] = user

    # ── Read ───────────────────────────────────────────────────────────────
    def get_by_id(self, user_id: int) -> Optional[User]:
        """Return the User with the given ID, or None."""
        return self._by_id.get(user_id)

    def get_by_username(self, username: str) -> Optional[User]:
        """Return the User with the given username, or None."""
        return self._by_username.get(username)

    def get_all(self) -> list[User]:
        """Return all registered users."""
        return list(self._by_id.values())

    def find_by_role(self, role: str) -> list[User]:
        """Return all users with the given role string."""
        return [u for u in self._by_id.values() if u.get_role() == role]

    # ── Update ─────────────────────────────────────────────────────────────
    def update(self, user: User) -> None:
        """Persist changes to an existing user (e.g., email update, deactivation)."""
        uid = user.get_user_id()
        if uid not in self._by_id:
            raise KeyError(f"User {uid} not found. Cannot update.")
        self._by_id[uid] = user
        self._by_username[user.get_username()] = user

    def count(self) -> int:
        return len(self._by_id)

    def __repr__(self) -> str:
        return f"<UserRepository users={self.count()}>"
