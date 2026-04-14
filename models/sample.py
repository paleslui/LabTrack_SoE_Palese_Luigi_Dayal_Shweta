"""
models/sample.py
----------------
Defines the Sample class — the central entity of LabTrack.

Relationships:
  - Sample is composed of one AuditLog list (composition: logs cannot
    exist independently of the sample they belong to)
  - Sample has an association with User (created_by, updated_by)

Design note (Stage 5):
  The Strategy pattern will be applied to the search/filter logic
  that operates on collections of Sample objects.
"""

from datetime import datetime
from enum import Enum
from typing import Optional


class SampleStatus(Enum):
    """
    Enumeration of the valid lifecycle states for a sample.
    Transitions must follow the defined order (enforced by Sample).
    """
    COLLECTED  = "Collected"
    PROCESSING = "Processing"
    STORED     = "Stored"
    CONSUMED   = "Consumed"
    DISCARDED  = "Discarded"


# Valid forward transitions — a sample may only move to one of these next states
ALLOWED_TRANSITIONS: dict[SampleStatus, list[SampleStatus]] = {
    SampleStatus.COLLECTED:  [SampleStatus.PROCESSING],
    SampleStatus.PROCESSING: [SampleStatus.STORED],
    SampleStatus.STORED:     [SampleStatus.CONSUMED, SampleStatus.DISCARDED],
    SampleStatus.CONSUMED:   [],   # terminal state
    SampleStatus.DISCARDED:  [],   # terminal state
}


class Sample:
    """
    Represents a biological sample tracked through its full lifecycle.

    Attributes
    ----------
    _sample_id        : str      — unique ID in format LT-YYYY-NNNN
    _sample_type      : str      — type of biological material (e.g., "blood", "DNA")
    _source_organism  : str      — organism of origin (e.g., "Homo sapiens")
    _collection_date  : datetime — date the sample was physically collected
    _storage_location : str      — physical or logical storage location code
    _status           : SampleStatus — current lifecycle state
    _notes            : str      — optional free-text notes
    _created_by_id    : int      — user_id of the registering researcher
    _created_at       : datetime — database insertion timestamp
    _updated_at       : datetime — timestamp of last modification
    _audit_log        : list     — ordered list of AuditEntry objects (composition)
    """

    def __init__(
        self,
        sample_id: str,
        sample_type: str,
        source_organism: str,
        collection_date: datetime,
        storage_location: str,
        created_by_id: int,
        notes: str = "",
    ):
        self._sample_id: str = sample_id
        self._sample_type: str = sample_type
        self._source_organism: str = source_organism
        self._collection_date: datetime = collection_date
        self._storage_location: str = storage_location
        self._status: SampleStatus = SampleStatus.COLLECTED
        self._notes: str = notes
        self._created_by_id: int = created_by_id
        self._created_at: datetime = datetime.utcnow()
        self._updated_at: datetime = datetime.utcnow()
        self._audit_log: list["AuditEntry"] = []   # composition

    # ── Getters ────────────────────────────────────────────────────────────
    def get_sample_id(self) -> str:
        return self._sample_id

    def get_sample_type(self) -> str:
        return self._sample_type

    def get_source_organism(self) -> str:
        return self._source_organism

    def get_collection_date(self) -> datetime:
        return self._collection_date

    def get_storage_location(self) -> str:
        return self._storage_location

    def get_status(self) -> SampleStatus:
        return self._status

    def get_notes(self) -> str:
        return self._notes

    def get_created_by_id(self) -> int:
        return self._created_by_id

    def get_created_at(self) -> datetime:
        return self._created_at

    def get_updated_at(self) -> datetime:
        return self._updated_at

    def get_audit_log(self) -> list["AuditEntry"]:
        """Return a copy of the audit log to prevent external mutation."""
        return list(self._audit_log)

    # ── Setters ────────────────────────────────────────────────────────────
    def set_storage_location(self, location: str) -> None:
        """Update the physical or logical storage location."""
        self._storage_location = location
        self._updated_at = datetime.utcnow()

    def set_notes(self, notes: str) -> None:
        """Replace the free-text notes field."""
        self._notes = notes
        self._updated_at = datetime.utcnow()

    # ── Business logic ────────────────────────────────────────────────────
    def update_status(self, new_status: SampleStatus, changed_by_id: int) -> None:
        """
        Transition the sample to a new lifecycle status.

        Only allows transitions defined in ALLOWED_TRANSITIONS.
        Appends an AuditEntry to the internal audit log on success.

        Parameters
        ----------
        new_status    : SampleStatus — the target lifecycle state
        changed_by_id : int          — user_id of the user making the change

        Raises
        ------
        ValueError — if the transition is not permitted
        """
        allowed = ALLOWED_TRANSITIONS.get(self._status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Invalid transition: {self._status.value} → {new_status.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )

        entry = AuditEntry(
            sample_id=self._sample_id,
            old_status=self._status,
            new_status=new_status,
            changed_by_id=changed_by_id,
        )
        self._audit_log.append(entry)
        self._status = new_status
        self._updated_at = datetime.utcnow()

    def is_terminal(self) -> bool:
        """Return True if the sample has reached a terminal state."""
        return self._status in (SampleStatus.CONSUMED, SampleStatus.DISCARDED)

    def to_dict(self) -> dict:
        """Serialize the sample to a plain dictionary (for API responses)."""
        return {
            "sample_id":        self._sample_id,
            "sample_type":      self._sample_type,
            "source_organism":  self._source_organism,
            "collection_date":  self._collection_date.isoformat(),
            "storage_location": self._storage_location,
            "status":           self._status.value,
            "notes":            self._notes,
            "created_by_id":    self._created_by_id,
            "created_at":       self._created_at.isoformat(),
            "updated_at":       self._updated_at.isoformat(),
        }

    def __repr__(self) -> str:
        return (
            f"<Sample id={self._sample_id!r} type={self._sample_type!r} "
            f"status={self._status.value!r}>"
        )


# ══════════════════════════════════════════════════════════════════════════════
# AuditEntry — composed by Sample (cannot exist without a parent Sample)
# ══════════════════════════════════════════════════════════════════════════════

class AuditEntry:
    """
    Records a single lifecycle status change for a sample.

    Relationship: Composition with Sample.
    An AuditEntry is created inside Sample.update_status() and is never
    instantiated independently in the application layer.

    Attributes
    ----------
    _sample_id    : str          — FK reference to the parent sample
    _old_status   : SampleStatus — status before the transition
    _new_status   : SampleStatus — status after the transition
    _changed_by_id: int          — user_id of the actor
    _timestamp    : datetime     — UTC time of the transition
    """

    def __init__(
        self,
        sample_id: str,
        old_status: SampleStatus,
        new_status: SampleStatus,
        changed_by_id: int,
    ):
        self._sample_id: str = sample_id
        self._old_status: SampleStatus = old_status
        self._new_status: SampleStatus = new_status
        self._changed_by_id: int = changed_by_id
        self._timestamp: datetime = datetime.utcnow()

    def get_sample_id(self) -> str:
        return self._sample_id

    def get_old_status(self) -> SampleStatus:
        return self._old_status

    def get_new_status(self) -> SampleStatus:
        return self._new_status

    def get_changed_by_id(self) -> int:
        return self._changed_by_id

    def get_timestamp(self) -> datetime:
        return self._timestamp

    def to_dict(self) -> dict:
        return {
            "sample_id":     self._sample_id,
            "old_status":    self._old_status.value,
            "new_status":    self._new_status.value,
            "changed_by_id": self._changed_by_id,
            "timestamp":     self._timestamp.isoformat(),
        }

    def __repr__(self) -> str:
        return (
            f"<AuditEntry sample={self._sample_id!r} "
            f"{self._old_status.value} → {self._new_status.value} "
            f"by user {self._changed_by_id}>"
        )
