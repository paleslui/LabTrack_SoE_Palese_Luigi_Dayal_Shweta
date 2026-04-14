"""
patterns/search_strategy.py
============================
DESIGN PATTERN: Strategy  (Behavioral)
----------------------------------------
PROBLEM
-------
LabTrack must support multiple search and filter modes: by sample type,
by lifecycle status, by storage location, and by the registering user.
Implementing all of these as a single monolithic method in SampleService
would mix unrelated concerns, making the method hard to read, test, or
extend. Adding a new filter criterion would require modifying
SampleService itself, violating the Open/Closed Principle.

SOLUTION
--------
Each filter mode is encapsulated as a concrete Strategy class that
implements a common SearchStrategy interface. SampleSearchContext holds
a reference to the active strategy and delegates all filtering to it.
The active strategy can be swapped at runtime without changing any
client code — a new filter criterion only requires a new class.

LINKS TO REQUIREMENTS
---------------------
FR-11 (users shall search samples by ID, type, status, location, date
range, and registering user) and FR-16 (support combining multiple
filter criteria simultaneously) are both served by this pattern.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from models.sample import Sample, SampleStatus


# ---------------------------------------------------------------------------
# Abstract Strategy
# ---------------------------------------------------------------------------

class SearchStrategy(ABC):
    """
    Common interface for all sample search/filter algorithms.

    Concrete strategies implement search() and return the subset of
    *samples* that match the given *query*.
    """

    @abstractmethod
    def search(self, samples: list[Sample], query: str) -> list[Sample]:
        """
        Filter *samples* according to this strategy's criterion.

        Parameters
        ----------
        samples : list[Sample] — the full collection to filter
        query   : str          — the search term (interpreted by each strategy)

        Returns
        -------
        list[Sample] — the matching subset (may be empty, never None)
        """


# ---------------------------------------------------------------------------
# Concrete Strategies
# ---------------------------------------------------------------------------

class SearchByType(SearchStrategy):
    """
    Filter samples whose sample_type contains the query string.

    Example: query="blood" matches "whole blood", "blood serum", etc.
    Search is case-insensitive.
    """

    def search(self, samples: list[Sample], query: str) -> list[Sample]:
        q = query.strip().lower()
        return [s for s in samples if q in s.get_sample_type().lower()]


class SearchByStatus(SearchStrategy):
    """
    Filter samples whose current lifecycle status matches the query.

    Query must be one of the SampleStatus values (case-insensitive).
    Example: query="stored" returns all stored samples.
    """

    def search(self, samples: list[Sample], query: str) -> list[Sample]:
        q = query.strip().lower()
        return [
            s for s in samples
            if s.get_status().value.lower() == q
        ]


class SearchByLocation(SearchStrategy):
    """
    Filter samples whose storage location contains the query string.

    Example: query="freezer" matches "Freezer-A3", "Freezer-B1", etc.
    """

    def search(self, samples: list[Sample], query: str) -> list[Sample]:
        q = query.strip().lower()
        return [s for s in samples if q in s.get_storage_location().lower()]


class SearchByUser(SearchStrategy):
    """
    Filter samples registered by a specific user.

    Query must be a numeric string representing the user_id.
    Example: query="3" returns all samples registered by user 3.
    """

    def search(self, samples: list[Sample], query: str) -> list[Sample]:
        try:
            uid = int(query.strip())
        except ValueError:
            return []
        return [s for s in samples if s.get_created_by_id() == uid]


class SearchByDateRange(SearchStrategy):
    """
    Filter samples collected within an inclusive date range.

    Query format: "YYYY-MM-DD,YYYY-MM-DD"  (start,end).
    Example: query="2025-01-01,2025-03-31"
    """

    def search(self, samples: list[Sample], query: str) -> list[Sample]:
        try:
            parts = query.split(",")
            start = datetime.strptime(parts[0].strip(), "%Y-%m-%d")
            end   = datetime.strptime(parts[1].strip(), "%Y-%m-%d")
        except (ValueError, IndexError):
            return []
        return [
            s for s in samples
            if start <= s.get_collection_date() <= end
        ]


class CompositeSearch(SearchStrategy):
    """
    Combines multiple strategies with AND logic (FR-16).

    All constituent strategies must match for a sample to be included.

    Example
    -------
    strategy = CompositeSearch([SearchByType(), SearchByStatus()])
    results = strategy.search(samples, "blood")  # type matches "blood"
    # Note: for CompositeSearch, each sub-strategy receives the same query.
    # For independent queries per field, use SampleSearchContext.multi_search().
    """

    def __init__(self, strategies: list[SearchStrategy]):
        if not strategies:
            raise ValueError("CompositeSearch requires at least one strategy.")
        self._strategies = strategies

    def search(self, samples: list[Sample], query: str) -> list[Sample]:
        result = samples
        for strategy in self._strategies:
            result = strategy.search(result, query)
        return result


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

class SampleSearchContext:
    """
    Context that holds and delegates to a SearchStrategy.

    The context decouples client code (SampleService, Flask routes)
    from the concrete algorithm. The strategy can be swapped at runtime
    without restarting the application or modifying the caller.

    Usage
    -----
    ctx = SampleSearchContext(SearchByType())
    results = ctx.execute_search(all_samples, "tissue")

    ctx.set_strategy(SearchByStatus())
    results = ctx.execute_search(all_samples, "stored")
    """

    def __init__(self, strategy: SearchStrategy):
        self._strategy: SearchStrategy = strategy

    def set_strategy(self, strategy: SearchStrategy) -> None:
        """Replace the active search strategy."""
        self._strategy = strategy

    def get_strategy(self) -> SearchStrategy:
        """Return the currently active strategy."""
        return self._strategy

    def execute_search(self, samples: list[Sample], query: str) -> list[Sample]:
        """Delegate filtering to the active strategy."""
        return self._strategy.search(samples, query)

    def multi_search(
        self,
        samples: list[Sample],
        filters: dict[str, str],
    ) -> list[Sample]:
        """
        Apply multiple independent field→query filters sequentially (AND logic).

        Parameters
        ----------
        samples : list[Sample]     — full collection
        filters : dict[str, str]   — mapping of field name to query string
                                     Supported fields: 'type', 'status',
                                     'location', 'user', 'date_range'

        Returns
        -------
        list[Sample] — samples matching ALL filters

        Example
        -------
        results = ctx.multi_search(
            samples,
            {"type": "blood", "status": "stored"}
        )
        """
        _strategy_map: dict[str, SearchStrategy] = {
            "type":       SearchByType(),
            "status":     SearchByStatus(),
            "location":   SearchByLocation(),
            "user":       SearchByUser(),
            "date_range": SearchByDateRange(),
        }

        result = samples
        for field, query in filters.items():
            strategy = _strategy_map.get(field)
            if strategy is None:
                raise ValueError(
                    f"Unknown filter field {field!r}. "
                    f"Supported: {list(_strategy_map.keys())}"
                )
            result = strategy.search(result, query)
        return result
