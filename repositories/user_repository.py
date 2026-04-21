"""
repositories/user_repository.py
---------------------------------
SQLAlchemy-backed data access layer for User objects.
"""

from typing import Optional
from models.user import User
from patterns.user_factory import UserFactory
from database.db import db_session
from database.models import UserModel


class UserRepository:

    @staticmethod
    def _to_domain(orm: UserModel) -> User:
        user = UserFactory.create(
            user_id=orm.user_id,
            username=orm.username,
            email=orm.email,
            password_hash=orm.password_hash,
            role=orm.role,
        )
        user._is_active = orm.is_active
        user._created_at = orm.created_at
        return user

    def add(self, user: User) -> None:
        with db_session() as session:
            existing = session.query(UserModel).filter_by(username=user.get_username()).first()
            if existing:
                raise ValueError(f"Username {user.get_username()!r} is already registered.")
            orm = UserModel(
                username=user.get_username(),
                email=user.get_email(),
                password_hash=user._password_hash,
                role=user.get_role(),
                is_active=user.is_active(),
            )
            session.add(orm)

    def get_by_id(self, user_id: int) -> Optional[User]:
        with db_session() as session:
            orm = session.query(UserModel).filter_by(user_id=user_id).first()
            return self._to_domain(orm) if orm else None

    def get_by_username(self, username: str) -> Optional[User]:
        with db_session() as session:
            orm = session.query(UserModel).filter_by(username=username).first()
            return self._to_domain(orm) if orm else None

    def get_password_hash(self, username: str) -> Optional[str]:
        """Return raw bcrypt hash for login verification."""
        with db_session() as session:
            orm = session.query(UserModel).filter_by(username=username).first()
            return orm.password_hash if orm else None

    def get_all(self) -> list[User]:
        with db_session() as session:
            rows = session.query(UserModel).all()
            return [self._to_domain(r) for r in rows]

    def find_by_role(self, role: str) -> list[User]:
        with db_session() as session:
            rows = session.query(UserModel).filter_by(role=role).all()
            return [self._to_domain(r) for r in rows]

    def update(self, user: User) -> None:
        with db_session() as session:
            orm = session.query(UserModel).filter_by(user_id=user.get_user_id()).first()
            if orm is None:
                raise KeyError(f"User {user.get_user_id()} not found.")
            orm.email     = user.get_email()
            orm.is_active = user.is_active()
            orm.role      = user.get_role()

    def count(self) -> int:
        with db_session() as session:
            return session.query(UserModel).count()

    def __repr__(self) -> str:
        return f"<UserRepository users={self.count()}>"
