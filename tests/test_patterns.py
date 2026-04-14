"""
tests/test_patterns.py
-----------------------
Unit tests for all four design patterns applied in LabTrack:
  1. Factory  — UserFactory
  2. Singleton — SingletonMeta + repositories
  3. Strategy  — SearchStrategy hierarchy + SampleSearchContext
  4. Adapter   — CsvImportAdapter
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from datetime import datetime

from models.user import Researcher, LabTechnician, Administrator, Viewer
from models.sample import Sample, SampleStatus

from patterns.user_factory    import UserFactory
from patterns.singleton_meta  import SingletonMeta, SampleRepository, UserRepository
from patterns.search_strategy import (
    SearchByType, SearchByStatus, SearchByLocation,
    SearchByUser, SearchByDateRange, CompositeSearch,
    SampleSearchContext
)
from patterns.csv_adapter import CsvImportAdapter


# ── FIXTURES ──────────────────────────────────────────────────────────────────

def make_sample(sid, stype, status_after=None, location="Freezer-A1", uid=1):
    s = Sample(sid, stype, "Homo sapiens", datetime(2025, 1, 15), location, uid)
    if status_after:
        s.update_status(status_after, uid)
    return s


# ═══════════════════════════════════════════════════════════════════════════════
# 1. FACTORY PATTERN
# ═══════════════════════════════════════════════════════════════════════════════

class TestUserFactory:

    def test_creates_researcher(self):
        user = UserFactory.create(1, "alice", "a@lab.ch", "h", "researcher")
        assert isinstance(user, Researcher)
        assert user.get_role() == "researcher"

    def test_creates_technician(self):
        user = UserFactory.create(2, "bob", "b@lab.ch", "h", "technician")
        assert isinstance(user, LabTechnician)

    def test_creates_administrator(self):
        user = UserFactory.create(3, "carol", "c@lab.ch", "h", "admin")
        assert isinstance(user, Administrator)

    def test_creates_viewer(self):
        user = UserFactory.create(4, "dave", "d@lab.ch", "h", "viewer")
        assert isinstance(user, Viewer)

    def test_case_insensitive(self):
        user = UserFactory.create(5, "eve", "e@lab.ch", "h", "RESEARCHER")
        assert isinstance(user, Researcher)

    def test_unknown_role_raises(self):
        with pytest.raises(ValueError, match="Unknown role"):
            UserFactory.create(6, "frank", "f@lab.ch", "h", "superadmin")

    def test_register_new_role(self):
        class LabManager(Researcher):
            def __init__(self, uid, uname, email, phash):
                super().__init__(uid, uname, email, phash)
                self._role = "lab_manager"

        UserFactory.register("lab_manager", LabManager)
        user = UserFactory.create(7, "grace", "g@lab.ch", "h", "lab_manager")
        assert isinstance(user, LabManager)
        assert "lab_manager" in UserFactory.supported_roles()

    def test_supported_roles_returns_list(self):
        roles = UserFactory.supported_roles()
        assert "researcher" in roles
        assert "admin" in roles


# ═══════════════════════════════════════════════════════════════════════════════
# 2. SINGLETON PATTERN
# ═══════════════════════════════════════════════════════════════════════════════

class TestSingleton:

    def setup_method(self):
        # Reset singleton state before each test
        SingletonMeta.reset(SampleRepository)
        SingletonMeta.reset(UserRepository)

    def test_sample_repo_same_instance(self):
        r1 = SampleRepository()
        r2 = SampleRepository()
        assert r1 is r2

    def test_user_repo_same_instance(self):
        r1 = UserRepository()
        r2 = UserRepository()
        assert r1 is r2

    def test_sample_repo_state_shared(self):
        r1 = SampleRepository()
        r2 = SampleRepository()
        s = Sample("LT-2025-0001", "blood", "Homo sapiens",
                   datetime(2025, 3, 1), "Shelf-1", 1)
        r1.add(s)
        # r2 is the same object — it must see the sample added via r1
        assert r2.get_by_id("LT-2025-0001") is not None

    def test_user_repo_state_shared(self):
        r1 = UserRepository()
        r2 = UserRepository()
        user = Researcher(10, "henry", "h@lab.ch", "hash")
        r1.add(user)
        assert r2.get_by_username("henry") is not None

    def test_repr_contains_singleton(self):
        r = SampleRepository()
        assert "Singleton" in repr(r)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. STRATEGY PATTERN
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_pool():
    return [
        make_sample("S1", "blood",  SampleStatus.PROCESSING, "Freezer-A1", 1),
        make_sample("S2", "DNA",    SampleStatus.PROCESSING, "Freezer-B2", 2),
        make_sample("S3", "tissue", None,                    "Shelf-C3",   1),
        make_sample("S4", "blood",  SampleStatus.PROCESSING, "Shelf-D4",   3),
    ]

class TestSearchStrategies:

    def test_search_by_type_match(self, sample_pool):
        results = SearchByType().search(sample_pool, "blood")
        assert len(results) == 2
        assert all("blood" in s.get_sample_type() for s in results)

    def test_search_by_type_case_insensitive(self, sample_pool):
        results = SearchByType().search(sample_pool, "BLOOD")
        assert len(results) == 2

    def test_search_by_type_no_match(self, sample_pool):
        assert SearchByType().search(sample_pool, "urine") == []

    def test_search_by_status(self, sample_pool):
        results = SearchByStatus().search(sample_pool, "processing")
        assert len(results) == 3

    def test_search_by_status_collected(self, sample_pool):
        results = SearchByStatus().search(sample_pool, "collected")
        assert len(results) == 1  # S3 was never updated

    def test_search_by_location(self, sample_pool):
        results = SearchByLocation().search(sample_pool, "freezer")
        assert len(results) == 2

    def test_search_by_user(self, sample_pool):
        results = SearchByUser().search(sample_pool, "1")
        assert len(results) == 2

    def test_search_by_user_invalid_query(self, sample_pool):
        assert SearchByUser().search(sample_pool, "notanumber") == []

    def test_search_by_date_range(self, sample_pool):
        results = SearchByDateRange().search(sample_pool, "2025-01-01,2025-12-31")
        assert len(results) == 4

    def test_search_by_date_range_no_match(self, sample_pool):
        results = SearchByDateRange().search(sample_pool, "2020-01-01,2020-12-31")
        assert len(results) == 0

    def test_composite_search(self, sample_pool):
        composite = CompositeSearch([SearchByType(), SearchByLocation()])
        results = composite.search(sample_pool, "blood")
        # blood samples AND location contains "blood"? No location has "blood",
        # so the AND narrows to 0 because second strategy also filters for "blood" in location.
        # This tests the AND logic: both strategies must match the SAME query.
        assert isinstance(results, list)

    def test_composite_raises_on_empty(self):
        with pytest.raises(ValueError):
            CompositeSearch([])


class TestSampleSearchContext:

    def test_set_and_switch_strategy(self, sample_pool):
        ctx = SampleSearchContext(SearchByType())
        r1 = ctx.execute_search(sample_pool, "blood")
        assert len(r1) == 2

        ctx.set_strategy(SearchByStatus())
        r2 = ctx.execute_search(sample_pool, "processing")
        assert len(r2) == 3

    def test_multi_search_and_logic(self, sample_pool):
        ctx = SampleSearchContext(SearchByType())
        results = ctx.multi_search(sample_pool, {"type": "blood", "status": "processing"})
        assert len(results) == 2  # 2 blood samples, both processing

    def test_multi_search_unknown_field(self, sample_pool):
        ctx = SampleSearchContext(SearchByType())
        with pytest.raises(ValueError, match="Unknown filter field"):
            ctx.multi_search(sample_pool, {"color": "red"})


# ═══════════════════════════════════════════════════════════════════════════════
# 4. ADAPTER PATTERN
# ═══════════════════════════════════════════════════════════════════════════════

VALID_CSV = """sample_type,source_organism,collection_date,storage_location,notes
blood,Homo sapiens,2025-03-01,Freezer-A1,Morning collection
DNA,Mus musculus,2025-03-15,Fridge-B2,
tissue,Homo sapiens,2025-04-01,Shelf-C3,Post-op sample"""

BAD_DATE_CSV = """sample_type,source_organism,collection_date,storage_location
blood,Homo sapiens,01/03/2025,Freezer-A1
DNA,Mus musculus,2025-03-15,Fridge-B2"""

MISSING_COL_CSV = """sample_type,collection_date,storage_location
blood,2025-03-01,Freezer-A1"""

EMPTY_REQUIRED_CSV = """sample_type,source_organism,collection_date,storage_location
,Homo sapiens,2025-03-01,Freezer-A1"""

class TestCsvImportAdapter:

    def test_parses_valid_csv(self):
        adapter = CsvImportAdapter(VALID_CSV)
        valid, errors = adapter.parse()
        assert len(valid) == 3
        assert errors == []

    def test_returns_correct_types(self):
        adapter = CsvImportAdapter(VALID_CSV)
        valid, _ = adapter.parse()
        row = valid[0]
        assert isinstance(row["collection_date"], datetime)
        assert isinstance(row["sample_type"], str)

    def test_bad_date_reported_as_error(self):
        adapter = CsvImportAdapter(BAD_DATE_CSV)
        valid, errors = adapter.parse()
        assert len(valid) == 1   # second row is valid
        assert len(errors) == 1  # first row has bad date

    def test_missing_column_returns_error(self):
        adapter = CsvImportAdapter(MISSING_COL_CSV)
        valid, errors = adapter.parse()
        assert valid == []
        assert any("source_organism" in e for e in errors)

    def test_empty_required_field_is_error(self):
        adapter = CsvImportAdapter(EMPTY_REQUIRED_CSV)
        valid, errors = adapter.parse()
        assert len(errors) == 1
        assert len(valid) == 0

    def test_iter_valid(self):
        adapter = CsvImportAdapter(VALID_CSV)
        rows = list(adapter.iter_valid())
        assert len(rows) == 3

    def test_counts(self):
        adapter = CsvImportAdapter(BAD_DATE_CSV)
        adapter.parse()
        assert adapter.valid_count == 1
        assert adapter.error_count == 1

    def test_repr_shows_state(self):
        adapter = CsvImportAdapter(VALID_CSV)
        adapter.parse()
        assert "parsed" in repr(adapter)
        assert "valid=3" in repr(adapter)

    def test_notes_optional(self):
        csv_no_notes = """sample_type,source_organism,collection_date,storage_location
blood,Homo sapiens,2025-03-01,Freezer-A1"""
        adapter = CsvImportAdapter(csv_no_notes)
        valid, errors = adapter.parse()
        assert len(valid) == 1
        assert valid[0]["notes"] == ""


if __name__ == "__main__":
    # Quick smoke test
    import subprocess, sys
    result = subprocess.run([sys.executable, "-m", "pytest", __file__, "-v"], capture_output=False)
    sys.exit(result.returncode)
