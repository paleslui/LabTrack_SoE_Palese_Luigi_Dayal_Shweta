"""
models/user.py
--------------
Defines the User base class and its role-based subclasses.

Relationships:
  - User is the abstract base (generalization)
  - Researcher, LabTechnician, Administrator, Viewer inherit from User
  - Each subclass overrides `can_edit_sample()` and `can_manage_users()`
    demonstrating polymorphism

Design note (Stage 5):
  The Factory pattern will be used to instantiate the correct subclass
  based on the role string stored in the database.
"""

from abc import ABC, abstractmethod
from datetime import datetime


class User(ABC):
    """
    Abstract base class representing any LabTrack system user.

    Attributes
    ----------
    _user_id   : int   — unique database identifier
    _username  : str   — login username (unique)
    _email     : str   — contact email address
    _password_hash : str — bcrypt-hashed password (never stored in plaintext)
    _role      : str   — role label (set by subclass)
    _is_active : bool  — whether the account is enabled
    _created_at : datetime — account creation timestamp
    """

    def __init__(self, user_id: int, username: str, email: str, password_hash: str):
        self._user_id: int = user_id
        self._username: str = username
        self._email: str = email
        self._password_hash: str = password_hash
        self._role: str = ""          # set by each subclass
        self._is_active: bool = True
        self._created_at: datetime = datetime.utcnow()

    # ── Getters ────────────────────────────────────────────────────────────
    def get_user_id(self) -> int:
        return self._user_id

    def get_username(self) -> str:
        return self._username

    def get_email(self) -> str:
        return self._email

    def get_role(self) -> str:
        return self._role

    def is_active(self) -> bool:
        return self._is_active

    def get_created_at(self) -> datetime:
        return self._created_at

    # ── Setters ────────────────────────────────────────────────────────────
    def set_email(self, email: str) -> None:
        """Update the user's email address."""
        if "@" not in email:
            raise ValueError("Invalid email address.")
        self._email = email

    def set_active(self, active: bool) -> None:
        """Enable or disable the user account."""
        self._is_active = active

    def set_password_hash(self, password_hash: str) -> None:
        """Replace the stored password hash (e.g., after a password reset)."""
        self._password_hash = password_hash

    # ── Abstract permission methods (polymorphism) ─────────────────────────
    @abstractmethod
    def can_register_sample(self) -> bool:
        """Return True if this user role may register new samples."""

    @abstractmethod
    def can_update_status(self) -> bool:
        """Return True if this user role may update sample lifecycle status."""

    @abstractmethod
    def can_manage_users(self) -> bool:
        """Return True if this user role may create or deactivate user accounts."""

    @abstractmethod
    def can_import_csv(self) -> bool:
        """Return True if this user role may bulk-import samples via CSV."""

    # ── Common utility ────────────────────────────────────────────────────
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self._user_id} username={self._username!r}>"


# ══════════════════════════════════════════════════════════════════════════════
# Concrete subclasses (Role-Based Access Control via inheritance)
# ══════════════════════════════════════════════════════════════════════════════

class Researcher(User):
    """
    A lab researcher who registers samples and monitors their status.

    Inherits from: User
    Permissions: register samples, update status, import CSV
    """

    def __init__(self, user_id: int, username: str, email: str, password_hash: str):
        super().__init__(user_id, username, email, password_hash)
        self._role = "researcher"

    def can_register_sample(self) -> bool:
        return True

    def can_update_status(self) -> bool:
        return True

    def can_manage_users(self) -> bool:
        return False

    def can_import_csv(self) -> bool:
        return True


class LabTechnician(User):
    """
    A lab technician who processes and stores samples but does not register them.

    Inherits from: User
    Permissions: update status only
    """

    def __init__(self, user_id: int, username: str, email: str, password_hash: str):
        super().__init__(user_id, username, email, password_hash)
        self._role = "technician"

    def can_register_sample(self) -> bool:
        return False

    def can_update_status(self) -> bool:
        return True

    def can_manage_users(self) -> bool:
        return False

    def can_import_csv(self) -> bool:
        return False


class Administrator(User):
    """
    A system administrator with full access to all features.

    Inherits from: User
    Permissions: all operations including user management
    """

    def __init__(self, user_id: int, username: str, email: str, password_hash: str):
        super().__init__(user_id, username, email, password_hash)
        self._role = "admin"

    def can_register_sample(self) -> bool:
        return True

    def can_update_status(self) -> bool:
        return True

    def can_manage_users(self) -> bool:
        return True

    def can_import_csv(self) -> bool:
        return True


class Viewer(User):
    """
    A read-only user (e.g., auditor or supervisor) who cannot modify data.

    Inherits from: User
    Permissions: none (read-only access enforced at API level)
    """

    def __init__(self, user_id: int, username: str, email: str, password_hash: str):
        super().__init__(user_id, username, email, password_hash)
        self._role = "viewer"

    def can_register_sample(self) -> bool:
        return False

    def can_update_status(self) -> bool:
        return False

    def can_manage_users(self) -> bool:
        return False

    def can_import_csv(self) -> bool:
        return False
