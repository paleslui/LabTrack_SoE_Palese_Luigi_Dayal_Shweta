"""
services/sample_service.py
---------------------------
Application-layer service that orchestrates sample-related use cases.

Sits between the Flask routes (presentation layer) and the repositories
(data layer), keeping business logic out of both.

Relationships:
  - SampleService has a dependency on SampleRepository and UserRepository
  - SampleService works with Sample and User objects
"""

from models.sample import Sample, SampleStatus
from models.user import User
from repositories.sample_repository import SampleRepository
from repositories.user_repository import UserRepository
from datetime import datetime


class SampleService:
    """
    Coordinates the core business workflows for sample management.

    Attributes
    ----------
    _sample_repo : SampleRepository — data access for samples
    _user_repo   : UserRepository   — data access for users (for permission checks)
    """

    def __init__(self, sample_repo: SampleRepository, user_repo: UserRepository):
        self._sample_repo: SampleRepository = sample_repo
        self._user_repo: UserRepository = user_repo

    def register_sample(
        self,
        requesting_user_id: int,
        sample_type: str,
        source_organism: str,
        collection_date: datetime,
        storage_location: str,
        notes: str = "",
    ) -> Sample:
        """
        Register a new sample on behalf of a user.

        Checks that the requesting user has the `can_register_sample` permission
        before delegating to the repository.

        Returns
        -------
        Sample — the newly created and persisted sample

        Raises
        ------
        PermissionError — if the user does not have register permission
        ValueError      — if required fields are missing or invalid
        """
        user = self._get_user_or_raise(requesting_user_id)

        if not user.can_register_sample():
            raise PermissionError(
                f"User {user.get_username()!r} (role: {user.get_role()!r}) "
                "does not have permission to register samples."
            )

        if not sample_type or not source_organism or not storage_location:
            raise ValueError("sample_type, source_organism, and storage_location are required.")

        return self._sample_repo.create(
            sample_type=sample_type,
            source_organism=source_organism,
            collection_date=collection_date,
            storage_location=storage_location,
            created_by_id=requesting_user_id,
            notes=notes,
        )

    def update_sample_status(
        self,
        requesting_user_id: int,
        sample_id: str,
        new_status: SampleStatus,
    ) -> Sample:
        """
        Transition a sample to a new lifecycle status.

        Checks both user permission and lifecycle validity.

        Returns
        -------
        Sample — the updated sample object

        Raises
        ------
        PermissionError — if the user may not update status
        KeyError        — if the sample does not exist
        ValueError      — if the lifecycle transition is invalid
        """
        user = self._get_user_or_raise(requesting_user_id)

        if not user.can_update_status():
            raise PermissionError(
                f"User {user.get_username()!r} (role: {user.get_role()!r}) "
                "does not have permission to update sample status."
            )

        sample = self._sample_repo.get_by_id(sample_id)
        if sample is None:
            raise KeyError(f"Sample {sample_id!r} not found.")

        sample.update_status(new_status, requesting_user_id)  # raises ValueError if invalid
        self._sample_repo.update(sample)
        return sample

    def get_sample(self, sample_id: str) -> Sample:
        """
        Retrieve a sample by ID.

        Raises
        ------
        KeyError — if not found
        """
        sample = self._sample_repo.get_by_id(sample_id)
        if sample is None:
            raise KeyError(f"Sample {sample_id!r} not found.")
        return sample

    def list_samples(
        self,
        status: SampleStatus | None = None,
        sample_type: str | None = None,
        user_id: int | None = None,
    ) -> list[Sample]:
        """
        Return a filtered list of samples.

        All filters are optional and additive (AND logic).
        """
        results = self._sample_repo.get_all()

        if status is not None:
            results = [s for s in results if s.get_status() == status]
        if sample_type is not None:
            results = [s for s in results if s.get_sample_type().lower() == sample_type.lower()]
        if user_id is not None:
            results = [s for s in results if s.get_created_by_id() == user_id]

        return results

    # ── Internal helpers ──────────────────────────────────────────────────
    def _get_user_or_raise(self, user_id: int) -> User:
        user = self._user_repo.get_by_id(user_id)
        if user is None:
            raise KeyError(f"User {user_id} not found.")
        return user
