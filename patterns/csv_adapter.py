"""
patterns/csv_adapter.py
========================
DESIGN PATTERN: Adapter  (Structural)
---------------------------------------
PROBLEM
-------
Laboratory users need to bulk-import sample records from CSV files
exported by existing spreadsheet tools (Excel, Google Sheets).
A raw CSV file has an incompatible interface: it delivers rows as
string dictionaries with inconsistent column names and date formats.
SampleService.register_sample() expects named Python arguments with
validated types (datetime objects, stripped strings, etc.).

Directly parsing CSV inside SampleService would couple the service
to external format details. If the import format changes, or if a
second format (Excel, JSON) needs to be supported later, the
service itself would need to be modified.

SOLUTION
--------
CsvImportAdapter wraps the raw CSV reader and exposes the interface
that SampleService already understands. It converts column names,
parses dates, strips whitespace, and separates valid rows from
invalid ones. SampleService never sees the raw CSV — it only sees
clean Python dicts ready to be passed directly to register_sample().

This matches the course's Adapter definition: "Convert an
incompatible interface into one that clients expect."

LINKS TO REQUIREMENTS
---------------------
FR-12 (Administrators and Researchers shall import samples via CSV)
and FR-13 (the system shall validate imported rows and report failures
without interrupting valid rows) are directly implemented by this class.
"""

import csv
from io import StringIO
from datetime import datetime
from typing import Iterator


# The interface that SampleService.register_sample() expects:
#   { 'sample_type': str, 'source_organism': str,
#     'collection_date': datetime, 'storage_location': str,
#     'notes': str }
SampleCreateDict = dict


class CsvImportAdapter:
    """
    Adapts a raw CSV string into an iterator of SampleCreateDict objects.

    The adapter translates the external CSV format (string rows with
    user-defined column names) into the internal interface expected by
    SampleService without modifying either side.

    Supported CSV columns
    ----------------------
    Required: sample_type, source_organism, collection_date (YYYY-MM-DD),
              storage_location
    Optional: notes

    Usage
    -----
    adapter = CsvImportAdapter(csv_string)
    valid_rows, errors = adapter.parse()

    for row in valid_rows:
        service.register_sample(user_id=uid, **row)

    if errors:
        print("Skipped rows:", errors)
    """

    REQUIRED_COLUMNS: list[str] = [
        "sample_type",
        "source_organism",
        "collection_date",
        "storage_location",
    ]
    DATE_FORMAT: str = "%Y-%m-%d"

    def __init__(self, csv_content: str):
        """
        Parameters
        ----------
        csv_content : str — the full text content of the uploaded CSV file.
        """
        self._csv_content: str = csv_content
        self._valid_rows:  list[SampleCreateDict] = []
        self._errors:      list[str] = []
        self._parsed:      bool = False

    # ── Public interface (what SampleService calls) ──────────────────────
    def parse(self) -> tuple[list[SampleCreateDict], list[str]]:
        """
        Parse the CSV and return (valid_rows, error_messages).

        Valid rows are converted to SampleCreateDict — the exact format
        expected by SampleService.register_sample(**row).

        Invalid rows are collected in error_messages with their line
        number and reason, so the caller can report them without
        aborting the entire import (FR-13).

        Returns
        -------
        valid_rows : list[SampleCreateDict]
        errors     : list[str]
        """
        if self._parsed:
            return self._valid_rows, self._errors

        self._valid_rows.clear()
        self._errors.clear()

        try:
            reader = csv.DictReader(StringIO(self._csv_content))
        except Exception as exc:
            return [], [f"Failed to read CSV: {exc}"]

        # Validate that all required columns are present
        fieldnames = [f.strip() for f in (reader.fieldnames or [])]
        missing = [c for c in self.REQUIRED_COLUMNS if c not in fieldnames]
        if missing:
            return [], [f"Missing required column(s): {', '.join(missing)}"]

        for line_num, raw_row in enumerate(reader, start=2):
            try:
                adapted = self._adapt_row(raw_row)
                self._valid_rows.append(adapted)
            except (ValueError, KeyError) as exc:
                self._errors.append(f"Row {line_num}: {exc}")

        self._parsed = True
        return self._valid_rows, self._errors

    def iter_valid(self) -> Iterator[SampleCreateDict]:
        """
        Convenience iterator over valid rows (parses on first call).

        Usage
        -----
        for row in adapter.iter_valid():
            service.register_sample(user_id=uid, **row)
        """
        valid, _ = self.parse()
        yield from valid

    @property
    def error_count(self) -> int:
        """Number of rows that failed validation."""
        self.parse()
        return len(self._errors)

    @property
    def valid_count(self) -> int:
        """Number of successfully parsed rows."""
        self.parse()
        return len(self._valid_rows)

    # ── Internal translation (the adaptation logic) ───────────────────────
    def _adapt_row(self, raw: dict) -> SampleCreateDict:
        """
        Translate a raw CSV row (all strings) into a typed SampleCreateDict.

        Raises
        ------
        ValueError — if a required field is empty or cannot be converted
        """
        sample_type = raw.get("sample_type", "").strip()
        if not sample_type:
            raise ValueError("'sample_type' must not be empty.")

        source = raw.get("source_organism", "").strip()
        if not source:
            raise ValueError("'source_organism' must not be empty.")

        date_str = raw.get("collection_date", "").strip()
        try:
            collection_date = datetime.strptime(date_str, self.DATE_FORMAT)
        except ValueError:
            raise ValueError(
                f"'collection_date' must be YYYY-MM-DD, got {date_str!r}."
            )

        location = raw.get("storage_location", "").strip()
        if not location:
            raise ValueError("'storage_location' must not be empty.")

        notes = raw.get("notes", "").strip()

        # Return the dict that maps 1-to-1 onto SampleService.register_sample()
        return {
            "sample_type":      sample_type,
            "source_organism":  source,
            "collection_date":  collection_date,
            "storage_location": location,
            "notes":            notes,
        }

    def __repr__(self) -> str:
        state = "parsed" if self._parsed else "unparsed"
        return (
            f"<CsvImportAdapter [{state}] "
            f"valid={self.valid_count} errors={self.error_count}>"
        )
