"""FastAPI entrypoint and routing for AgentLabyrinth M1 Slice B."""

import asyncio
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from apps.api.schemas import (
    CreateEpisodeRequest,
    CreateExperimentRequest,
    EpisodeResponse,
    ErrorResponse,
    ExperimentDashboardResponse,
    ExperimentJobState,
    ExperimentResponse,
    MetaResponse,
)
from apps.api.service import EpisodeService, ExperimentJobStopped
from packages.application.experiment import ReferenceCostBudgetExceeded, experiment_checkpoint_path
from packages.domain.models import TraceEvent

app = FastAPI(
    title="AgentLabyrinth API",
    description="Minimal local single-user API for ToolLab Episode execution and trace inspection.",
    version="1.0.0",
)

# Enable CORS for local Vite development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_default_service = EpisodeService(live_model_catalog=True)
_stream_runs: set[asyncio.Task[None]] = set()
_experiment_jobs: dict[UUID, asyncio.Task[None]] = {}
_experiment_slots = asyncio.Semaphore(2)


async def _run_experiment_job(
    req: CreateExperimentRequest | None,
    service: EpisodeService,
    experiment_id: UUID,
) -> None:
    """Run one durable job; each Experiment retains serial paired execution."""
    try:
        async with _experiment_slots:
            current = service.get_experiment_job(experiment_id)
            service.update_experiment_job(
                experiment_id,
                status="running",
                requested_action=current.requested_action if current else None,
            )
            if req is None:
                await service.resume_experiment_job(experiment_id)
            else:
                await service.execute_experiment(req, job_id=experiment_id)
            service.update_experiment_job(experiment_id, status="completed")
    except ExperimentJobStopped as exc:
        service.update_experiment_job(
            experiment_id, status="paused" if exc.action == "pause" else "cancelled"
        )
    except ReferenceCostBudgetExceeded:
        service.update_experiment_job(
            experiment_id, status="failed", error_code="REFERENCE_COST_BUDGET_EXCEEDED"
        )
    except Exception:
        service.update_experiment_job(
            experiment_id, status="failed", error_code="EXPERIMENT_FAILED"
        )


def _schedule_experiment_job(
    req: CreateExperimentRequest | None, service: EpisodeService, experiment_id: UUID
) -> None:
    task = asyncio.create_task(_run_experiment_job(req, service, experiment_id))
    _experiment_jobs[experiment_id] = task
    task.add_done_callback(lambda _: _experiment_jobs.pop(experiment_id, None))


def get_episode_service() -> EpisodeService:
    """Dependency provider for EpisodeService."""
    return _default_service


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle schema validation errors without leaking internal path details."""
    req_id = uuid4()
    err = ErrorResponse(
        schema_version="1.0",
        request_id=req_id,
        error_code="VALIDATION_ERROR",
        message="Invalid request payload or prohibited parameter values.",
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=err.model_dump(mode="json"),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle explicit HTTP exceptions with sanitized ErrorResponse structure."""
    req_id = uuid4()
    err = ErrorResponse(
        schema_version="1.0",
        request_id=req_id,
        error_code="REQUEST_FAILED",
        message=str(exc.detail),
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=err.model_dump(mode="json"),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all exception handler preventing system paths or raw upstream leakage."""
    req_id = uuid4()
    err = ErrorResponse(
        schema_version="1.0",
        request_id=req_id,
        error_code="INTERNAL_SERVER_ERROR",
        message="An internal server error occurred while processing the request.",
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=err.model_dump(mode="json"),
    )


@app.get(
    "/api/v1/meta",
    response_model=MetaResponse,
    summary="Get available models, tasks, and system defaults",
)
async def get_meta(
    service: Annotated[EpisodeService, Depends(get_episode_service)],
) -> MetaResponse:
    """Return available models, tasks, and system default choices."""
    return await asyncio.to_thread(service.get_meta)


@app.post(
    "/api/v1/episodes",
    response_model=EpisodeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute a ToolLab episode and persist its artifact",
)
async def create_episode(
    req: CreateEpisodeRequest,
    service: Annotated[EpisodeService, Depends(get_episode_service)],
) -> EpisodeResponse:
    """Run an episode using the requested model or scenario, saving the resulting trace."""
    try:
        artifact = await service.execute_episode(req)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Episode execution encountered an unexpected runtime failure.",
        ) from exc

    return EpisodeResponse(
        schema_version="1.0",
        request_id=req.request_id,
        artifact=artifact,
    )


@app.post("/api/v1/episodes/stream", summary="Run one episode with live Trace events")
async def stream_episode(
    req: CreateEpisodeRequest,
    service: Annotated[EpisodeService, Depends(get_episode_service)],
) -> StreamingResponse:
    """Stream recorded events while independently completing and saving the episode."""
    events: asyncio.Queue[tuple[str, str]] = asyncio.Queue()

    def publish(event: TraceEvent) -> None:
        events.put_nowait(("trace", event.model_dump_json()))

    async def run() -> None:
        try:
            artifact = await service.execute_episode(req, on_event=publish)
            response = EpisodeResponse(request_id=req.request_id, artifact=artifact)
            events.put_nowait(("complete", response.model_dump_json()))
        except ValueError as exc:
            events.put_nowait(
                (
                    "error",
                    ErrorResponse(
                        request_id=req.request_id, error_code="VALIDATION_ERROR", message=str(exc)
                    ).model_dump_json(),
                )
            )
        except Exception:
            events.put_nowait(
                (
                    "error",
                    ErrorResponse(
                        request_id=req.request_id,
                        error_code="INTERNAL_ERROR",
                        message="Episode execution failed.",
                    ).model_dump_json(),
                )
            )
        finally:
            events.put_nowait(("done", ""))

    task = asyncio.create_task(run())
    _stream_runs.add(task)
    task.add_done_callback(_stream_runs.discard)

    async def stream() -> AsyncIterator[str]:
        while True:
            kind, payload = await events.get()
            if kind == "done":
                break
            yield f"event: {kind}\ndata: {payload}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get(
    "/api/v1/episodes/resumable",
    response_model=list[UUID],
    summary="List unfinished ToolLab episodes from an earlier API instance",
)
async def list_resumable_episodes(
    service: Annotated[EpisodeService, Depends(get_episode_service)],
) -> list[UUID]:
    """Return IDs that can safely be resumed after an API restart."""
    return service.resumable_episode_ids()


@app.post(
    "/api/v1/episodes/{episode_id}/resume",
    response_model=EpisodeResponse,
    summary="Resume an unfinished ToolLab episode from an earlier API instance",
)
async def resume_episode(
    episode_id: UUID,
    service: Annotated[EpisodeService, Depends(get_episode_service)],
) -> EpisodeResponse:
    """Continue an existing Episode ID using its saved provenance and Trace."""
    try:
        artifact = await service.resume_episode(episode_id)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Episode resume encountered an unexpected failure.",
        ) from exc
    return EpisodeResponse(request_id=uuid4(), artifact=artifact)


@app.get(
    "/api/v1/episodes/{episode_id}",
    response_model=EpisodeResponse,
    summary="Retrieve a previously executed episode by UUID without invoking models",
)
async def get_episode(
    episode_id: UUID,
    service: Annotated[EpisodeService, Depends(get_episode_service)],
) -> EpisodeResponse:
    """Read a saved artifact by its strictly validated UUID."""
    artifact = service.get_episode(episode_id)
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Episode '{episode_id}' not found.",
        )

    return EpisodeResponse(
        schema_version="1.0",
        request_id=uuid4(),
        artifact=artifact,
    )


@app.post(
    "/api/v1/episodes/{episode_id}/rerun",
    response_model=EpisodeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def rerun_failed_episode(
    episode_id: UUID,
    service: Annotated[EpisodeService, Depends(get_episode_service)],
) -> EpisodeResponse:
    """Explicitly rerun one failed Episode with a new ID and saved lineage."""
    try:
        artifact = await service.rerun_failed_episode(episode_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return EpisodeResponse(request_id=uuid4(), artifact=artifact)


@app.post(
    "/api/v1/experiments",
    response_model=ExperimentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute a paired comparison experiment (Baseline vs Recovery)",
)
async def create_experiment(
    req: CreateExperimentRequest,
    service: Annotated[EpisodeService, Depends(get_episode_service)],
) -> ExperimentResponse:
    """Run paired episodes serially and return the aggregated ExperimentArtifact."""
    try:
        artifact = await service.execute_experiment(req)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Experiment execution encountered an unexpected runtime failure.",
        ) from exc

    return ExperimentResponse(
        schema_version="1.0",
        request_id=req.request_id,
        experiment=artifact,
    )


@app.post(
    "/api/v1/experiments/jobs",
    response_model=ExperimentJobState,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_experiment_job(
    req: CreateExperimentRequest,
    service: Annotated[EpisodeService, Depends(get_episode_service)],
) -> ExperimentJobState:
    """Queue a bounded background Experiment with a stable, client-known ID."""
    try:
        state = service.reserve_experiment_job(req.request_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _schedule_experiment_job(req, service, req.request_id)
    return state


@app.get("/api/v1/experiments/jobs/resumable", response_model=list[UUID])
async def list_resumable_experiment_jobs(
    service: Annotated[EpisodeService, Depends(get_episode_service)],
) -> list[UUID]:
    """Discover stopped jobs after a refresh or API process restart."""
    return [
        experiment_id
        for experiment_id in service.resumable_experiment_job_ids()
        if experiment_id not in _experiment_jobs
    ]


@app.get("/api/v1/experiments/jobs/{experiment_id}", response_model=ExperimentJobState)
async def get_experiment_job(
    experiment_id: UUID,
    service: Annotated[EpisodeService, Depends(get_episode_service)],
) -> ExperimentJobState:
    """Report persisted state; an orphaned running job is an interruption."""
    state = service.get_experiment_job(experiment_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Experiment job not found")
    if state.status in {"queued", "running"} and experiment_id not in _experiment_jobs:
        return state.model_copy(update={"status": "interrupted"})
    return state


@app.post("/api/v1/experiments/jobs/{experiment_id}/{action}", response_model=ExperimentJobState)
async def control_experiment_job(
    experiment_id: UUID,
    action: str,
    service: Annotated[EpisodeService, Depends(get_episode_service)],
) -> ExperimentJobState:
    """Pause, cancel, or resume a job without changing completed Episode artifacts."""
    if action == "resume":
        state = service.get_experiment_job(experiment_id)
        if state is None or state.status not in {"paused", "interrupted", "running"}:
            raise HTTPException(status_code=409, detail="Job is not resumable")
        if experiment_id in _experiment_jobs:
            raise HTTPException(status_code=409, detail="Job is already active")
        if not experiment_checkpoint_path(service.artifacts_dir, experiment_id).is_file():
            raise HTTPException(status_code=409, detail="Experiment plan is unavailable")
        queued = service.update_experiment_job(experiment_id, status="queued")
        _schedule_experiment_job(None, service, experiment_id)
        return queued
    try:
        return service.request_experiment_action(experiment_id, action)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get(
    "/api/v1/experiments",
    response_model=ExperimentDashboardResponse,
    summary="Summarize completed experiments from saved artifacts",
)
async def list_experiments(
    service: Annotated[EpisodeService, Depends(get_episode_service)],
) -> ExperimentDashboardResponse:
    """Read the local experiment index without running a model."""
    return await asyncio.to_thread(service.experiment_dashboard)


@app.get(
    "/api/v1/experiments/resumable",
    response_model=list[UUID],
    summary="List unfinished paired experiments from an earlier API instance",
)
async def list_resumable_experiments(
    service: Annotated[EpisodeService, Depends(get_episode_service)],
) -> list[UUID]:
    """Return persisted experiment plans that can continue with their original IDs."""
    return service.resumable_experiment_ids()


@app.post(
    "/api/v1/experiments/{experiment_id}/resume",
    response_model=ExperimentResponse,
    summary="Resume an unfinished paired experiment",
)
async def resume_experiment(
    experiment_id: UUID,
    service: Annotated[EpisodeService, Depends(get_episode_service)],
) -> ExperimentResponse:
    """Continue remaining matrix cells and reuse completed Episode artifacts."""
    try:
        artifact = await service.resume_experiment(experiment_id)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Experiment resume encountered an unexpected failure.",
        ) from exc
    return ExperimentResponse(request_id=uuid4(), experiment=artifact)


@app.get(
    "/api/v1/experiments/{experiment_id}",
    response_model=ExperimentResponse,
    summary="Retrieve a previously executed experiment artifact by UUID",
)
async def get_experiment(
    experiment_id: UUID,
    service: Annotated[EpisodeService, Depends(get_episode_service)],
) -> ExperimentResponse:
    """Read a saved ExperimentArtifact by its strictly validated UUID."""
    artifact = service.get_experiment(experiment_id)
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment '{experiment_id}' not found.",
        )

    return ExperimentResponse(
        schema_version="1.0",
        request_id=uuid4(),
        experiment=artifact,
    )
