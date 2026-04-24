"""
repositories/project_repository.py — CRUD for project groupings.
"""

from typing import Optional
from database.db import db_session
from database.models import ProjectModel, SampleModel


class ProjectRepository:

    @staticmethod
    def _to_dict(orm: ProjectModel, sample_count: int = 0) -> dict:
        return {
            "project_id":   orm.project_id,
            "name":         orm.name,
            "description":  orm.description or "",
            "created_by":   orm.created_by,
            "created_at":   orm.created_at.isoformat() if orm.created_at else None,
            "sample_count": sample_count,
        }

    def get_all(self) -> list[dict]:
        with db_session() as session:
            rows = session.query(ProjectModel).order_by(ProjectModel.name).all()
            out = []
            for r in rows:
                count = session.query(SampleModel).filter_by(project_id=r.project_id).count()
                out.append(self._to_dict(r, count))
            return out

    def get_by_id(self, project_id: int) -> Optional[dict]:
        with db_session() as session:
            r = session.query(ProjectModel).filter_by(project_id=project_id).first()
            if not r:
                return None
            count = session.query(SampleModel).filter_by(project_id=r.project_id).count()
            return self._to_dict(r, count)

    def create(self, name: str, description: str, created_by_id: int) -> dict:
        name = (name or "").strip()
        if not name:
            raise ValueError("Project name is required.")
        with db_session() as session:
            if session.query(ProjectModel).filter_by(name=name).first():
                raise ValueError(f"A project named {name!r} already exists.")
            orm = ProjectModel(
                name=name,
                description=(description or "").strip() or None,
                created_by=created_by_id,
            )
            session.add(orm)
            session.flush()
            return self._to_dict(orm, 0)

    def delete(self, project_id: int) -> None:
        with db_session() as session:
            r = session.query(ProjectModel).filter_by(project_id=project_id).first()
            if not r:
                raise KeyError(f"Project {project_id} not found.")
            # Unlink samples (set their project_id to NULL) before delete
            session.query(SampleModel).filter_by(project_id=project_id).update(
                {"project_id": None}
            )
            session.delete(r)
