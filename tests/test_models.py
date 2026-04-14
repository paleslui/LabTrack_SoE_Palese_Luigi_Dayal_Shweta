"""
tests/test_models.py
--------------------
Basic unit tests for the core model classes.
Covers: Sample lifecycle transitions, User permissions, AuditEntry creation.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from datetime import datetime
from models.sample import Sample, SampleStatus, AuditEntry
from models.user import Researcher, LabTechnician, Administrator, Viewer
from repositories.sample_repository import SampleRepository
from services.sample_service import SampleService
from repositories.user_repository import UserRepository


# ── Fixtures ───────────────────────────────────────────────────────────────

def make_sample(sample_id="LT-2025-0001"):
    return Sample(
        sample_id=sample_id,
        sample_type="blood",
        source_organism="Homo sapiens",
        collection_date=datetime(2025, 4, 1),
        storage_location="Freezer-A3",
        created_by_id=1,
    )


# ── Sample tests ───────────────────────────────────────────────────────────

def test_sample_initial_status():
    s = make_sample()
    assert s.get_status() == SampleStatus.COLLECTED

def test_sample_valid_transition():
    s = make_sample()
    s.update_status(SampleStatus.PROCESSING, changed_by_id=1)
    assert s.get_status() == SampleStatus.PROCESSING

def test_sample_invalid_transition_raises():
    s = make_sample()
    with pytest.raises(ValueError):
        s.update_status(SampleStatus.STORED, changed_by_id=1)  # skips PROCESSING

def test_sample_audit_log_appended():
    s = make_sample()
    s.update_status(SampleStatus.PROCESSING, changed_by_id=1)
    log = s.get_audit_log()
    assert len(log) == 1
    assert log[0].get_new_status() == SampleStatus.PROCESSING

def test_sample_terminal_state():
    s = make_sample()
    s.update_status(SampleStatus.PROCESSING, changed_by_id=1)
    s.update_status(SampleStatus.STORED, changed_by_id=1)
    s.update_status(SampleStatus.DISCARDED, changed_by_id=1)
    assert s.is_terminal()

def test_sample_to_dict_has_required_keys():
    s = make_sample()
    d = s.to_dict()
    for key in ("sample_id","sample_type","status","storage_location","created_by_id"):
        assert key in d


# ── User permission tests ──────────────────────────────────────────────────

def test_researcher_permissions():
    r = Researcher(1, "alice", "alice@lab.ch", "hash")
    assert r.can_register_sample() is True
    assert r.can_update_status() is True
    assert r.can_manage_users() is False

def test_technician_permissions():
    t = LabTechnician(2, "bob", "bob@lab.ch", "hash")
    assert t.can_register_sample() is False
    assert t.can_update_status() is True

def test_viewer_permissions():
    v = Viewer(3, "carol", "carol@lab.ch", "hash")
    assert v.can_register_sample() is False
    assert v.can_update_status() is False
    assert v.can_manage_users() is False

def test_admin_permissions():
    a = Administrator(4, "dave", "dave@lab.ch", "hash")
    assert a.can_register_sample() is True
    assert a.can_manage_users() is True


# ── SampleService integration tests ───────────────────────────────────────

def setup_service():
    sample_repo = SampleRepository()
    user_repo = UserRepository()
    researcher = Researcher(1, "alice", "alice@lab.ch", "hash")
    viewer = Viewer(2, "carol", "carol@lab.ch", "hash")
    user_repo.add(researcher)
    user_repo.add(viewer)
    service = SampleService(sample_repo, user_repo)
    return service

def test_service_register_sample_success():
    service = setup_service()
    sample = service.register_sample(
        requesting_user_id=1,
        sample_type="DNA",
        source_organism="Mus musculus",
        collection_date=datetime(2025, 4, 5),
        storage_location="Fridge-B1",
    )
    assert sample.get_sample_id().startswith("LT-")

def test_service_register_sample_permission_denied():
    service = setup_service()
    with pytest.raises(PermissionError):
        service.register_sample(
            requesting_user_id=2,  # Viewer — no permission
            sample_type="DNA",
            source_organism="Mus musculus",
            collection_date=datetime(2025, 4, 5),
            storage_location="Fridge-B1",
        )

def test_service_update_status_success():
    service = setup_service()
    sample = service.register_sample(
        requesting_user_id=1,
        sample_type="tissue",
        source_organism="Homo sapiens",
        collection_date=datetime(2025, 3, 10),
        storage_location="Freezer-C2",
    )
    updated = service.update_sample_status(1, sample.get_sample_id(), SampleStatus.PROCESSING)
    assert updated.get_status() == SampleStatus.PROCESSING


if __name__ == "__main__":
    # Run without pytest: quick smoke test
    test_sample_initial_status()
    test_sample_valid_transition()
    test_researcher_permissions()
    test_service_register_sample_success()
    print("All smoke tests passed.")
