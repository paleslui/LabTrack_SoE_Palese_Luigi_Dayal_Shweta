"""
reseed_demo.py — wipe samples / projects / attachments / audit log and reseed.

Users and the activity log are preserved. Run from project root:

    python3 reseed_demo.py

Use this whenever you want fresh demo data to exercise the UI features.
"""

from database.db import (init_db, migrate_db, db_session,
                         seed_demo_projects, seed_demo_samples)
from database.models import (SampleModel, AuditEntryModel, AttachmentModel,
                             ProjectModel)


def reseed():
    init_db()
    migrate_db()

    with db_session() as s:
        attach = s.query(AttachmentModel).delete()
        audit  = s.query(AuditEntryModel).delete()
        # samples must clear FK refs to projects/parents before delete; SQLite
        # doesn't enforce these without PRAGMA foreign_keys, but order matters
        # for any future migration to Postgres.
        s.query(SampleModel).filter(SampleModel.parent_sample_id.isnot(None)).update(
            {"parent_sample_id": None}
        )
        samples = s.query(SampleModel).delete()
        projects = s.query(ProjectModel).delete()
        print(f"Wiped: {samples} samples, {audit} audit entries, "
              f"{attach} attachments, {projects} projects")

    seed_demo_projects()
    seed_demo_samples()
    print("✓ Reseed complete. Restart the app to see the new data.")


if __name__ == "__main__":
    reseed()
