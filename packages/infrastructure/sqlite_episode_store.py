"""SQLAlchemy/Alembic adapter for authoritative single-Episode persistence."""

import hashlib
import json
from pathlib import Path
from time import time_ns
from typing import Any, Literal
from uuid import UUID

from alembic import command
from alembic.config import Config
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    event,
    inspect,
    select,
)
from sqlalchemy.engine import Connection

from packages.application.checkpoint import (
    EpisodeCheckpoint,
    build_checkpoint,
    validate_completed_episode,
)
from packages.application.experiment import ExperimentArtifact, ExperimentCheckpoint
from packages.application.review import EpisodeReviewArtifact
from packages.application.trace import JsonTraceRecorder, sanitize
from packages.domain.models import AgentSpec, EpisodeArtifact, RunConfig, TaskSpec
from packages.runtime.session import SessionState

_metadata = MetaData()
_episodes = Table(
    "episode_records",
    _metadata,
    Column("episode_id", String(36), primary_key=True),
    Column("kind", String(16), nullable=False),
    Column("payload", Text, nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("fake_scenario", String(64), nullable=True),
    Column("updated_at_ns", BigInteger(), nullable=False),
    CheckConstraint("kind IN ('checkpoint', 'finished')", name="episode_record_kind"),
)
_records = Table(
    "artifact_records",
    _metadata,
    Column("kind", String(24), primary_key=True),
    Column("record_id", String(36), primary_key=True),
    Column("parent_id", String(36), nullable=True),
    Column("payload", Text, nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("updated_at_ns", BigInteger(), nullable=False),
    CheckConstraint(
        "kind IN ('experiment_plan', 'experiment_result', 'experiment_job', 'review')",
        name="artifact_record_kind",
    ),
)


def _serialized(model: EpisodeCheckpoint | EpisodeArtifact) -> tuple[str, str]:
    payload = json.dumps(sanitize(model.model_dump(mode="json")), ensure_ascii=False)
    return payload, hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _checked_payload(payload: str, digest: str) -> None:
    if hashlib.sha256(payload.encode("utf-8")).hexdigest() != digest:
        raise ValueError("Stored Episode digest mismatch")


def _json_payload(model: Any) -> tuple[str, str]:
    payload = json.dumps(sanitize(model.model_dump(mode="json")), ensure_ascii=False)
    return payload, hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _checked_record(payload: str, digest: str) -> None:
    if hashlib.sha256(payload.encode("utf-8")).hexdigest() != digest:
        raise ValueError("Stored artifact digest mismatch")


class SQLiteEpisodeStore:
    """Store one immutable result or one extend-only safety point per Episode."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.engine = create_engine(f"sqlite:///{path.as_posix()}")

        @event.listens_for(self.engine, "connect")
        def configure_sqlite(dbapi_connection: object, _: object) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=FULL")
            cursor.close()

        self._upgrade()

    def _upgrade(self) -> None:
        allowed = {"alembic_version", "episode_records", "artifact_records"}
        with self.engine.connect() as connection:
            tables = set(inspect(connection).get_table_names())
            if tables - allowed or ("episode_records" in tables) != ("alembic_version" in tables):
                raise ValueError("Unrecognized SQLite database")
            config = Config()
            migrations = Path(__file__).resolve().parent / "migrations"
            config.set_main_option("script_location", str(migrations))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            connection.commit()

    def _record(self, kind: str, record_id: UUID) -> Any | None:
        with self.engine.connect() as connection:
            return connection.execute(
                select(
                    _records.c.parent_id,
                    _records.c.payload,
                    _records.c.sha256,
                    _records.c.updated_at_ns,
                ).where(
                    _records.c.kind == kind,
                    _records.c.record_id == str(record_id),
                )
            ).one_or_none()

    def _insert_record(
        self,
        connection: Connection,
        *,
        kind: str,
        record_id: UUID,
        payload: str,
        digest: str,
        parent_id: UUID | None = None,
    ) -> None:
        row = connection.execute(
            select(_records.c.payload, _records.c.sha256, _records.c.parent_id).where(
                _records.c.kind == kind,
                _records.c.record_id == str(record_id),
            )
        ).one_or_none()
        if row is not None:
            _checked_record(row.payload, row.sha256)
            if row.payload != payload or row.parent_id != (str(parent_id) if parent_id else None):
                raise ValueError("Stored artifact cannot be overwritten")
            return
        connection.execute(
            _records.insert().values(
                kind=kind,
                record_id=str(record_id),
                parent_id=str(parent_id) if parent_id else None,
                payload=payload,
                sha256=digest,
                updated_at_ns=time_ns(),
            )
        )

    def save_experiment_plan(self, plan: ExperimentCheckpoint) -> None:
        plan.verify()
        payload, digest = _json_payload(plan)
        with self._write_connection() as connection:
            try:
                self._insert_record(
                    connection,
                    kind="experiment_plan",
                    record_id=plan.experiment_id,
                    payload=payload,
                    digest=digest,
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    def load_experiment_plan(self, experiment_id: UUID) -> ExperimentCheckpoint | None:
        row = self._record("experiment_plan", experiment_id)
        if row is None:
            return None
        _checked_record(row.payload, row.sha256)
        plan = ExperimentCheckpoint.model_validate_json(row.payload)
        if plan.experiment_id != experiment_id:
            raise ValueError("Stored Experiment plan identity mismatch")
        plan.verify()
        return plan

    def save_experiment_result(self, artifact: ExperimentArtifact) -> None:
        if artifact.experiment_id is None:
            raise ValueError("Experiment identity is required")
        payload, digest = _json_payload(artifact)
        with self._write_connection() as connection:
            try:
                self._insert_record(
                    connection,
                    kind="experiment_result",
                    record_id=artifact.experiment_id,
                    payload=payload,
                    digest=digest,
                )
                connection.execute(
                    _records.delete().where(
                        _records.c.kind == "experiment_plan",
                        _records.c.record_id == str(artifact.experiment_id),
                    )
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    def load_experiment_result(self, experiment_id: UUID) -> ExperimentArtifact | None:
        row = self._record("experiment_result", experiment_id)
        if row is None:
            return None
        _checked_record(row.payload, row.sha256)
        artifact = ExperimentArtifact.model_validate_json(row.payload)
        if artifact.experiment_id != experiment_id:
            raise ValueError("Stored Experiment identity mismatch")
        return artifact

    def experiment_ids(self) -> list[UUID]:
        return self._record_ids("experiment_result")

    def experiment_plan_ids(self, *, before_ns: int | None = None) -> list[UUID]:
        return self._record_ids("experiment_plan", before_ns=before_ns)

    def save_experiment_job(self, experiment_id: UUID, payload: str, *, create: bool) -> None:
        json.loads(payload)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        with self._write_connection() as connection:
            try:
                row = connection.execute(
                    select(_records.c.payload, _records.c.sha256).where(
                        _records.c.kind == "experiment_job",
                        _records.c.record_id == str(experiment_id),
                    )
                ).one_or_none()
                if row is None:
                    self._insert_record(
                        connection,
                        kind="experiment_job",
                        record_id=experiment_id,
                        payload=payload,
                        digest=digest,
                        parent_id=experiment_id,
                    )
                else:
                    _checked_record(row.payload, row.sha256)
                    if create:
                        raise ValueError("Experiment job already exists")
                    connection.execute(
                        _records.update()
                        .where(
                            _records.c.kind == "experiment_job",
                            _records.c.record_id == str(experiment_id),
                        )
                        .values(payload=payload, sha256=digest, updated_at_ns=time_ns())
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    def reserve_experiment(self, plan: ExperimentCheckpoint, job_payload: str) -> None:
        plan.verify()
        json.loads(job_payload)
        plan_payload, plan_digest = _json_payload(plan)
        job_digest = hashlib.sha256(job_payload.encode("utf-8")).hexdigest()
        with self._write_connection() as connection:
            try:
                self._insert_record(
                    connection,
                    kind="experiment_plan",
                    record_id=plan.experiment_id,
                    payload=plan_payload,
                    digest=plan_digest,
                )
                self._insert_record(
                    connection,
                    kind="experiment_job",
                    record_id=plan.experiment_id,
                    parent_id=plan.experiment_id,
                    payload=job_payload,
                    digest=job_digest,
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    def load_experiment_job(self, experiment_id: UUID) -> str | None:
        row = self._record("experiment_job", experiment_id)
        if row is None:
            return None
        _checked_record(row.payload, row.sha256)
        return str(row.payload)

    def experiment_job_ids(self) -> list[UUID]:
        return self._record_ids("experiment_job")

    def save_review(self, review: EpisodeReviewArtifact) -> None:
        payload, digest = _json_payload(review)
        with self._write_connection() as connection:
            try:
                self._insert_record(
                    connection,
                    kind="review",
                    record_id=review.review_id,
                    parent_id=review.episode_id,
                    payload=payload,
                    digest=digest,
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    def load_review(self, review_id: UUID) -> EpisodeReviewArtifact | None:
        row = self._record("review", review_id)
        if row is None:
            return None
        _checked_record(row.payload, row.sha256)
        review = EpisodeReviewArtifact.model_validate_json(row.payload)
        if review.review_id != review_id:
            raise ValueError("Stored Review identity mismatch")
        return review

    def review_ids(self, episode_id: UUID | None = None) -> list[UUID]:
        return self._record_ids("review", parent_id=episode_id)

    def _record_ids(
        self,
        kind: str,
        *,
        parent_id: UUID | None = None,
        before_ns: int | None = None,
    ) -> list[UUID]:
        statement = select(_records.c.record_id).where(_records.c.kind == kind)
        if parent_id is not None:
            statement = statement.where(_records.c.parent_id == str(parent_id))
        if before_ns is not None:
            statement = statement.where(_records.c.updated_at_ns < before_ns)
        with self.engine.connect() as connection:
            values = connection.execute(statement.order_by(_records.c.record_id)).scalars()
            return [UUID(value) for value in values]

    def _write_connection(self) -> Connection:
        connection = self.engine.connect()
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        return connection

    def status(self, episode_id: UUID) -> Literal["checkpoint", "finished"] | None:
        with self.engine.connect() as connection:
            value = connection.execute(
                select(_episodes.c.kind).where(_episodes.c.episode_id == str(episode_id))
            ).scalar_one_or_none()
        return value if value in ("checkpoint", "finished") else None

    def save(
        self,
        state: SessionState,
        agent: AgentSpec,
        task: TaskSpec,
        config: RunConfig,
        recorder: JsonTraceRecorder,
        fake_scenario: str | None = None,
    ) -> None:
        self.save_checkpoint(build_checkpoint(state, agent, task, config, recorder, fake_scenario))

    def save_checkpoint(self, checkpoint: EpisodeCheckpoint) -> None:
        checkpoint.validated_recorder()
        payload, digest = _serialized(checkpoint)
        checked = EpisodeCheckpoint.model_validate_json(payload)
        checked.validated_recorder()
        with self._write_connection() as connection:
            try:
                row = connection.execute(
                    select(
                        _episodes.c.kind,
                        _episodes.c.payload,
                        _episodes.c.sha256,
                    ).where(_episodes.c.episode_id == str(checkpoint.episode_id))
                ).one_or_none()
                if row is not None:
                    if row.kind != "checkpoint":
                        raise ValueError("Episode already completed")
                    _checked_payload(row.payload, row.sha256)
                    previous = EpisodeCheckpoint.model_validate_json(row.payload)
                    previous.validated_recorder()
                    if previous == checked:
                        connection.commit()
                        return
                    if (
                        previous.episode_id != checked.episode_id
                        or previous.agent != checked.agent
                        or previous.task != checked.task
                        or previous.run_config != checked.run_config
                        or previous.fake_scenario != checked.fake_scenario
                        or len(previous.events) >= len(checked.events)
                        or checked.events[: len(previous.events)] != previous.events
                    ):
                        raise ValueError("Checkpoint does not extend the saved safety point")
                    connection.execute(
                        _episodes.update()
                        .where(_episodes.c.episode_id == str(checkpoint.episode_id))
                        .values(payload=payload, sha256=digest, updated_at_ns=time_ns())
                    )
                else:
                    connection.execute(
                        _episodes.insert().values(
                            episode_id=str(checkpoint.episode_id),
                            kind="checkpoint",
                            payload=payload,
                            sha256=digest,
                            fake_scenario=checkpoint.fake_scenario,
                            updated_at_ns=time_ns(),
                        )
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    def load_checkpoint(self, episode_id: UUID) -> EpisodeCheckpoint:
        row = self._row(episode_id)
        if row is None or row.kind != "checkpoint":
            raise FileNotFoundError("Episode checkpoint does not exist")
        _checked_payload(row.payload, row.sha256)
        checkpoint = EpisodeCheckpoint.model_validate_json(row.payload)
        if checkpoint.episode_id != episode_id:
            raise ValueError("Stored Episode identity mismatch")
        checkpoint.validated_recorder()
        return checkpoint

    def save_completed(
        self, artifact: EpisodeArtifact, *, fake_scenario: str | None = None
    ) -> None:
        episode_id = artifact.episode.episode_id
        validate_completed_episode(artifact, episode_id)
        payload, digest = _serialized(artifact)
        checked = EpisodeArtifact.model_validate_json(payload)
        validate_completed_episode(checked, episode_id)
        with self._write_connection() as connection:
            try:
                row = connection.execute(
                    select(
                        _episodes.c.kind,
                        _episodes.c.payload,
                        _episodes.c.sha256,
                        _episodes.c.fake_scenario,
                    ).where(_episodes.c.episode_id == str(episode_id))
                ).one_or_none()
                if row is not None and row.kind == "finished":
                    _checked_payload(row.payload, row.sha256)
                    if EpisodeArtifact.model_validate_json(row.payload) != checked:
                        raise ValueError("Completed Episode cannot be overwritten")
                    connection.commit()
                    return
                if row is not None:
                    _checked_payload(row.payload, row.sha256)
                    checkpoint = EpisodeCheckpoint.model_validate_json(row.payload)
                    checkpoint.validated_recorder()
                    if (
                        checkpoint.episode_id != episode_id
                        or checkpoint.agent != checked.agent
                        or checkpoint.task != checked.task
                        or checkpoint.run_config != checked.run_config
                        or row.fake_scenario != fake_scenario
                        or checked.events[: len(checkpoint.events)] != checkpoint.events
                    ):
                        raise ValueError("Completed Episode does not match its safety point")
                    connection.execute(
                        _episodes.update()
                        .where(_episodes.c.episode_id == str(episode_id))
                        .values(
                            kind="finished",
                            payload=payload,
                            sha256=digest,
                            fake_scenario=row.fake_scenario,
                            updated_at_ns=time_ns(),
                        )
                    )
                else:
                    connection.execute(
                        _episodes.insert().values(
                            episode_id=str(episode_id),
                            kind="finished",
                            payload=payload,
                            sha256=digest,
                            fake_scenario=fake_scenario,
                            updated_at_ns=time_ns(),
                        )
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    def load_completed(self, episode_id: UUID) -> EpisodeArtifact | None:
        row = self._row(episode_id)
        if row is None or row.kind == "checkpoint":
            return None
        if row.kind != "finished":
            raise ValueError("Stored Episode kind invalid")
        _checked_payload(row.payload, row.sha256)
        artifact = EpisodeArtifact.model_validate_json(row.payload)
        validate_completed_episode(artifact, episode_id)
        return artifact

    def checkpoint_ids(self, *, before_ns: int) -> list[UUID]:
        with self.engine.connect() as connection:
            values = connection.execute(
                select(_episodes.c.episode_id)
                .where(_episodes.c.kind == "checkpoint")
                .where(_episodes.c.updated_at_ns < before_ns)
                .order_by(_episodes.c.episode_id)
            ).scalars()
            return [UUID(value) for value in values]

    def fake_scenario(self, episode_id: UUID) -> str | None:
        with self.engine.connect() as connection:
            return connection.execute(
                select(_episodes.c.fake_scenario).where(_episodes.c.episode_id == str(episode_id))
            ).scalar_one_or_none()

    def backup(self, target: Path) -> None:
        """Create a consistent online SQLite backup without copying WAL files."""
        import sqlite3

        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise FileExistsError(target)
        with sqlite3.connect(self.path) as source, sqlite3.connect(target) as destination:
            source.backup(destination)
        with sqlite3.connect(target) as restored:
            if restored.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                target.unlink(missing_ok=True)
                raise ValueError("SQLite backup integrity check failed")

    def _row(self, episode_id: UUID) -> Any | None:
        with self.engine.connect() as connection:
            return connection.execute(
                select(
                    _episodes.c.kind,
                    _episodes.c.payload,
                    _episodes.c.sha256,
                    _episodes.c.fake_scenario,
                ).where(_episodes.c.episode_id == str(episode_id))
            ).one_or_none()
