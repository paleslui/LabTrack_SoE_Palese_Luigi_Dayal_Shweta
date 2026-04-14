"""
patterns/user_factory.py
========================
DESIGN PATTERN: Factory  (Creational)
--------------------------------------
PROBLEM
-------
The application needs to reconstruct User objects from database rows.
Each row stores a 'role' string ('researcher', 'technician', 'admin',
'viewer'). Without a factory, every query site would need a long
if/elif chain to decide which concrete subclass to instantiate —
coupling database-layer code to every User subclass and forcing
updates in many places whenever a new role is introduced.

SOLUTION
--------
UserFactory centralises the role → subclass mapping in one place.
Callers request a user object via UserFactory.create(); they receive
the correct subclass without knowing its name. Adding a new role
requires changing only this file.

LINKS TO REQUIREMENTS
---------------------
FR-02 (RBAC with four roles) and FR-04 (administrator manages users)
both require dynamic creation of the correct User subclass at runtime
based on data retrieved from the database.
"""

from models.user import User, Researcher, LabTechnician, Administrator, Viewer


class UserFactory:
    """
    Factory for instantiating the correct User subclass from a role label.

    Usage
    -----
    user = UserFactory.create(
        user_id=1,
        username="alice",
        email="alice@lab.ch",
        password_hash="$2b$...",
        role="researcher"
    )
    # Returns a Researcher instance — caller needs no knowledge of subclasses.
    """

    # Central role registry: add new roles here without touching any other file
    _ROLE_MAP: dict[str, type[User]] = {
        "researcher": Researcher,
        "technician":  LabTechnician,
        "admin":       Administrator,
        "viewer":      Viewer,
    }

    @staticmethod
    def create(
        user_id: int,
        username: str,
        email: str,
        password_hash: str,
        role: str,
    ) -> User:
        """
        Instantiate the User subclass that corresponds to *role*.

        Parameters
        ----------
        user_id       : int  — unique database identifier
        username      : str  — login username
        email         : str  — contact email
        password_hash : str  — bcrypt hash of the password
        role          : str  — one of 'researcher', 'technician',
                               'admin', 'viewer'

        Returns
        -------
        User — the concrete subclass instance

        Raises
        ------
        ValueError — if *role* is not registered in the factory
        """
        role_key = role.strip().lower()
        cls = UserFactory._ROLE_MAP.get(role_key)

        if cls is None:
            valid = ", ".join(sorted(UserFactory._ROLE_MAP.keys()))
            raise ValueError(
                f"Unknown role {role!r}. "
                f"Valid roles are: {valid}"
            )

        return cls(user_id, username, email, password_hash)

    @staticmethod
    def register(role: str, cls: type[User]) -> None:
        """
        Register a new role → subclass mapping at runtime.

        This extension point means UserFactory satisfies the
        Open/Closed Principle: new roles can be added without
        modifying existing factory code.

        Parameters
        ----------
        role : str         — the role label (e.g. 'lab_manager')
        cls  : type[User]  — the concrete User subclass to instantiate
        """
        if not issubclass(cls, User):
            raise TypeError(f"{cls.__name__} must be a subclass of User.")
        UserFactory._ROLE_MAP[role.strip().lower()] = cls

    @staticmethod
    def supported_roles() -> list[str]:
        """Return the list of currently registered role labels."""
        return sorted(UserFactory._ROLE_MAP.keys())
