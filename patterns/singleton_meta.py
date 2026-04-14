"""
patterns/singleton_meta.py
===========================
DESIGN PATTERN: Singleton  (Creational)
----------------------------------------
PROBLEM
-------
SampleRepository and UserRepository each manage a shared in-memory
store (and later a database connection pool). If multiple instances
were created at runtime, each would hold a separate, inconsistent
copy of the data. Any write to one instance would be invisible to
the others, causing silent data loss and broken invariants.

SOLUTION
--------
A Python metaclass (SingletonMeta) overrides __call__ so that the
first instantiation of a class stores the instance in a class-level
dict. Every subsequent call returns the same object. Applying this
metaclass to both repository classes enforces the singleton guarantee
without modifying the repository logic itself.

WHY METACLASS INSTEAD OF __new__?
----------------------------------
Using a separate metaclass keeps the Singleton mechanism reusable
across any class (not just repositories) and avoids cluttering
business-logic classes with infrastructure concerns — a clean
separation of responsibilities.

LINKS TO REQUIREMENTS
---------------------
NFR-07 (atomic database writes, no inconsistency) and the three-tier
architecture decision both require a single, shared data-access point.
The course slides explicitly list "database connection pools" as the
canonical use case for Singleton.
"""

import threading


class SingletonMeta(type):
    """
    Thread-safe Singleton metaclass.

    Apply as:
        class MyClass(metaclass=SingletonMeta):
            ...

    The lock ensures that two threads racing to create the first
    instance do not each construct a separate object.
    """

    _instances: dict[type, object] = {}
    _lock: threading.Lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        # Double-checked locking: fast path avoids acquiring the lock
        # on every call once the instance exists.
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    instance = super().__call__(*args, **kwargs)
                    cls._instances[cls] = instance
        return cls._instances[cls]

    @classmethod
    def reset(mcs, cls: type) -> None:
        """
        Remove the cached instance for *cls*.

        Should only be used in unit tests to restore a clean state
        between test runs. Never call this in production code.
        """
        with mcs._lock:
            mcs._instances.pop(cls, None)


# ---------------------------------------------------------------------------
# Updated repository classes — Singleton applied via metaclass
# ---------------------------------------------------------------------------

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.sample import Sample, SampleStatus
from models.user import User
from typing import Optional
from datetime import datetime


class SampleRepository(metaclass=SingletonMeta):
    """
    Singleton repository for Sample objects.

    Only one instance exists across the entire application lifetime.
    All components that inject or call SampleRepository() receive the
    same object, guaranteeing a consistent view of the sample store.

    Design pattern applied: Singleton (via SingletonMeta metaclass)
    """

    def __init__(self):
        # __init__ runs only once because __call__ returns the cached
        # instance on subsequent invocations.
        self._store: dict[str, Sample] = {}
        self._counter: int = 0

    def _generate_id(self) -> str:
        self._counter += 1
        year = datetime.utcnow().year
        return f"LT-{year}-{self._counter:04d}"

    def add(self, sample: Sample) -> None:
        sid = sample.get_sample_id()
        if sid in self._store:
            raise ValueError(f"Sample {sid!r} already exists.")
        self._store[sid] = sample

    def create(self, sample_type: str, source_organism: str,
               collection_date: datetime, storage_location: str,
               created_by_id: int, notes: str = "") -> Sample:
        new_id = self._generate_id()
        sample = Sample(new_id, sample_type, source_organism,
                        collection_date, storage_location,
                        created_by_id, notes)
        self.add(sample)
        return sample

    def get_by_id(self, sample_id: str) -> Optional[Sample]:
        return self._store.get(sample_id)

    def get_all(self) -> list[Sample]:
        return list(self._store.values())

    def update(self, sample: Sample) -> None:
        if sample.get_sample_id() not in self._store:
            raise KeyError(f"Sample {sample.get_sample_id()!r} not found.")
        self._store[sample.get_sample_id()] = sample

    def count(self) -> int:
        return len(self._store)

    def __repr__(self) -> str:
        return f"<SampleRepository [Singleton] samples={self.count()}>"


class UserRepository(metaclass=SingletonMeta):
    """
    Singleton repository for User objects.

    Design pattern applied: Singleton (via SingletonMeta metaclass)
    """

    def __init__(self):
        self._by_id:       dict[int, User] = {}
        self._by_username: dict[str, User] = {}

    def add(self, user: User) -> None:
        uname = user.get_username()
        if uname in self._by_username:
            raise ValueError(f"Username {uname!r} already registered.")
        self._by_id[user.get_user_id()] = user
        self._by_username[uname] = user

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self._by_id.get(user_id)

    def get_by_username(self, username: str) -> Optional[User]:
        return self._by_username.get(username)

    def get_all(self) -> list[User]:
        return list(self._by_id.values())

    def update(self, user: User) -> None:
        if user.get_user_id() not in self._by_id:
            raise KeyError(f"User {user.get_user_id()} not found.")
        self._by_id[user.get_user_id()] = user
        self._by_username[user.get_username()] = user

    def count(self) -> int:
        return len(self._by_id)

    def __repr__(self) -> str:
        return f"<UserRepository [Singleton] users={self.count()}>"
