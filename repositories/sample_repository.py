"""
repositories/sample_repository.py
----------------------------------
Data access layer for Sample objects.

Relationship:
  - SampleRepository has an association with Sample (aggregation).
    The repository manages a collection of samples but does not own them —
    samples exist independently in the database.

Design note (Stage 5):
  The Singleton pattern will be applied to SampleRepository to ensure
  only one database connection pool is maintained at runtime.
"""

from models.sample import Sample, SampleStatus
from datetime import datetime
from typing import Optional


class SampleRepository:
    """
    Provides CRUD operations and queries for Sample records.

    In Stage 3 this class uses an in-memory store (a plain dict) so the
    class structure can be defined and tested without a database.
    The implementation will be replaced with SQLAlchemy calls in Stage 7.

    Attributes
    ----------
    _store : dict[str, Sample] — in-memory dictionary keyed by sample_id
    _counter : int             — monotonic counter used to generate IDs
    """

    def __init__(self):
        self._store: dict[str, Sample] = {}
        self._counter: int = 0

    # ── ID generation ──────────────────────────────────────────────────────
    def _generate_id(self) -> str:
        """Generate the next sample ID in format LT-YYYY-NNNN."""
        self._counter += 1
        year = datetime.utcnow().year
        return f"LT-{year}-{self._counter:04d}"

    # ── Create ─────────────────────────────────────────────────────────────
    def add(self, sample: Sample) -> None:
        """
        Persist a new sample record.

        Parameters
        ----------
        sample : Sample — the sample to store

        Raises
        ------
        ValueError — if a sample with the same ID already exists
        """
        sid = sample.get_sample_id()
        if sid in self._store:
            raise ValueError(f"Sample with ID {sid!r} already exists.")
        self._store[sid] = sample

    def create(
        self,
        sample_type: str,
        source_organism: str,
        collection_date: datetime,
        storage_location: str,
        created_by_id: int,
        notes: str = "",
    ) -> Sample:
        """
        Factory-style convenience method: generate an ID, build a Sample,
        persist it, and return it.
        """
        new_id = self._generate_id()
        sample = Sample(
            sample_id=new_id,
            sample_type=sample_type,
            source_organism=source_organism,
            collection_date=collection_date,
            storage_location=storage_location,
            created_by_id=created_by_id,
            notes=notes,
        )
        self.add(sample)
        return sample

    # ── Read ───────────────────────────────────────────────────────────────
    def get_by_id(self, sample_id: str) -> Optional[Sample]:
        """Return the Sample with the given ID, or None if not found."""
        return self._store.get(sample_id)

    def get_all(self) -> list[Sample]:
        """Return all stored samples as a list."""
        return list(self._store.values())

    def find_by_status(self, status: SampleStatus) -> list[Sample]:
        """Return all samples currently in the given lifecycle state."""
        return [s for s in self._store.values() if s.get_status() == status]

    def find_by_type(self, sample_type: str) -> list[Sample]:
        """Return all samples matching the given type (case-insensitive)."""
        t = sample_type.lower()
        return [s for s in self._store.values() if s.get_sample_type().lower() == t]

    def find_by_user(self, user_id: int) -> list[Sample]:
        """Return all samples registered by the given user."""
        return [s for s in self._store.values() if s.get_created_by_id() == user_id]

    # ── Update ─────────────────────────────────────────────────────────────
    def update(self, sample: Sample) -> None:
        """
        Persist changes to an existing sample.

        Parameters
        ----------
        sample : Sample — the modified sample object

        Raises
        ------
        KeyError — if the sample does not exist in the store
        """
        sid = sample.get_sample_id()
        if sid not in self._store:
            raise KeyError(f"Sample {sid!r} not found. Cannot update.")
        self._store[sid] = sample

    # ── Delete ─────────────────────────────────────────────────────────────
    def delete(self, sample_id: str) -> None:
        """
        Remove a sample from the store.
        Note: in production this will be a soft-delete (setting a deleted_at flag).
        """
        if sample_id not in self._store:
            raise KeyError(f"Sample {sample_id!r} not found. Cannot delete.")
        del self._store[sample_id]

    def count(self) -> int:
        """Return the total number of samples in the store."""
        return len(self._store)

    def __repr__(self) -> str:
        return f"<SampleRepository samples={self.count()}>"
